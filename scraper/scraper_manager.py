"""
Kocaeli Haber Haritası - Scraper Yöneticisi

Tüm scraper'ları koordine eder, haberleri toplar,
temizler, sınıflandırır, konumlarını çıkarır ve veritabanına kaydeder.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import numpy as np
from scraper.base_scraper import selenium_driver_kapat
from scraper.cagdas_kocaeli import CagdasKocaeliScraper
from scraper.ozgur_kocaeli import OzgurKocaeliScraper
from scraper.ses_kocaeli import SesKocaeliScraper
from scraper.yeni_kocaeli import YeniKocaeliScraper
from scraper.bizim_yaka import BizimYakaScraper
from processing.cleaner import TextCleaner
from processing.classifier import NewsClassifier
from processing.location_extractor import LocationExtractor
from processing.similarity import SimilarityAnalyzer
from geocoding.geocoder import Geocoder
from database.mongodb import MongoDB
from config.settings import Config

logger = logging.getLogger(__name__)

# Global ilerleme durumu (thread-safe basit dict)
scrape_progress = {
    "aktif": False,
    "asama": "",
    "kaynak": "",
    "kaynak_no": 0,
    "toplam_kaynak": 5,
    "islenen_haber": 0,
    "toplam_haber": 0,
    "yuzde": 0,
}


class ScraperManager:
    """Tüm scraping sürecini yöneten ana sınıf."""

    def __init__(self):
        """Scraper yöneticisini başlatır."""
        # Scraper'lar
        self.scraperlar = [
            CagdasKocaeliScraper(),
            OzgurKocaeliScraper(),
            SesKocaeliScraper(),
            YeniKocaeliScraper(),
            BizimYakaScraper(),
        ]

        # İşlem modülleri
        self.temizleyici = TextCleaner()
        self.siniflandirici = NewsClassifier()
        self.konum_cikarici = LocationExtractor()
        self.geocoder = Geocoder()

        # Benzerlik analizörü (lazy loading - ihtiyaç olduğunda yükle)
        self._benzerlik_analizoru = None

        # Veritabanı
        try:
            self.db = MongoDB()
        except Exception as e:
            logger.error(f"MongoDB bağlantı hatası: {e}")
            self.db = None

        # Performans cache'leri (her scrape çağrısında yeniden hazırlanır)
        self._mevcut_haberler_cache = []
        self._mevcut_linkler_cache = set()
        self._mevcut_embeddingler_cache = np.array([])

        # Paralel işleme için paylaşılan cache'leri koruyacak kilit
        self._cache_lock = threading.Lock()

    @property
    def benzerlik_analizoru(self):
        """Benzerlik analizörünü lazy loading ile yükler."""
        if self._benzerlik_analizoru is None:
            self._benzerlik_analizoru = SimilarityAnalyzer()
        return self._benzerlik_analizoru

    def tum_kaynaklardan_cek(self) -> dict:
        """
        Tüm haber kaynaklarından haberleri çeker ve işler.

        Returns:
            dict: İşlem sonuç raporu
        """
        baslangic = datetime.now()
        rapor = {
            "baslangic_zamani": baslangic.isoformat(),
            "toplam_cekilen": 0,
            "toplam_kaydedilen": 0,
            "toplam_tekrar": 0,
            "toplam_benzer": 0,
            "toplam_konumsuz": 0,
            "kaynak_detay": {},
            "hatalar": [],
        }

        tum_haberler = []

        # İlerleme durumunu başlat
        scrape_progress["aktif"] = True
        scrape_progress["asama"] = "Hazırlanıyor..."
        scrape_progress["kaynak"] = ""
        scrape_progress["kaynak_no"] = 0
        scrape_progress["toplam_kaynak"] = len(self.scraperlar)
        scrape_progress["islenen_haber"] = 0
        scrape_progress["toplam_haber"] = 0
        scrape_progress["yuzde"] = 0

        # 0. DB bağlantısı kontrolü
        if not self.db:
            logger.error(
                "MongoDB bağlantısı yok! Haberler işlenecek ancak veritabanına kaydedilemeyecek."
            )

        # 0a. Eski haberleri temizle (son 3 günden eskiler silinir)
        if self.db:
            temizlik = self.db.eski_haberleri_temizle()
            if temizlik["silinen_haber"] > 0:
                logger.info(
                    f"🗑️ Eski veri temizliği: {temizlik['silinen_haber']} haber, "
                    f"{temizlik['silinen_embedding']} embedding silindi."
                )

        # 0b. Performans için mevcut haber/cache hazırlığı
        if self.db:
            self._mevcut_haberler_cache = self.db.tum_haber_metinlerini_getir()
            self._mevcut_linkler_cache = {
                h.get("haber_linki")
                for h in self._mevcut_haberler_cache
                if h.get("haber_linki")
            }

            if self._mevcut_haberler_cache:
                # Önce MongoDB'deki kayıtlı embedding'leri yükle
                _linkler, _matris = self.db.embeddingleri_getir()
                if len(_linkler) == len(self._mevcut_haberler_cache):
                    # Cache tam ve güncel → doğrudan kullan
                    self._mevcut_embeddingler_cache = _matris
                    logger.info(
                        f"Embedding cache MongoDB'den yüklendi ({len(_linkler)} kayıt)."
                    )
                else:
                    # Cache eksik veya güncel değil → yeniden hesapla ve kaydet
                    logger.info("Embedding cache yeniden hesaplanıyor...")
                    mevcut_metinler = [
                        f"{h.get('baslik', '')} {h.get('icerik', '')}"
                        for h in self._mevcut_haberler_cache
                    ]
                    self._mevcut_embeddingler_cache = (
                        self.benzerlik_analizoru.embeddingleri_olustur(mevcut_metinler)
                    )
                    # Yeni hesaplanan embedding'leri MongoDB'ye kaydet
                    for haber, emb in zip(
                        self._mevcut_haberler_cache,
                        self._mevcut_embeddingler_cache,
                    ):
                        if haber.get("haber_linki"):
                            self.db.embedding_kaydet(haber["haber_linki"], emb)

        # 1. Tüm kaynaklardan haberleri çek
        for idx, scraper in enumerate(self.scraperlar):
            try:
                scrape_progress["asama"] = "Haberler çekiliyor"
                scrape_progress["kaynak"] = scraper.kaynak_adi
                scrape_progress["kaynak_no"] = idx + 1
                scrape_progress["yuzde"] = int((idx / len(self.scraperlar)) * 50)
                logger.info(f"🔄 {scraper.kaynak_adi} haberleri çekiliyor...")
                haberler = scraper.tum_haberleri_cek()
                tum_haberler.extend(haberler)

                rapor["kaynak_detay"][scraper.kaynak_adi] = {
                    "cekilen": len(haberler),
                    "kaydedilen": 0,
                }
                rapor["toplam_cekilen"] += len(haberler)

            except Exception as e:
                hata_mesaji = f"{scraper.kaynak_adi} hatası: {e}"
                logger.error(hata_mesaji)
                rapor["hatalar"].append(hata_mesaji)

        logger.info(f"📊 Toplam {len(tum_haberler)} haber çekildi.")

        # 2. Her haberi işle ve kaydet (paralel pipeline)
        scrape_progress["asama"] = "Haberler işleniyor"
        scrape_progress["toplam_haber"] = len(tum_haberler)
        scrape_progress["yuzde"] = 50

        islenen_sayac = [0]  # thread-safe sayaç (liste trick)
        max_workers = max(1, Config.PROCESSING_MAX_WORKERS)

        def _isle(args):
            idx, haber = args
            try:
                return idx, haber, self._haber_isle_ve_kaydet(haber)
            except Exception as e:
                return idx, haber, "hata"

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            gelecektekiler = {
                executor.submit(_isle, (i, haber)): i
                for i, haber in enumerate(tum_haberler)
            }
            for gelecek in as_completed(gelecektekiler):
                try:
                    idx, haber, sonuc = gelecek.result()
                    islenen_sayac[0] += 1
                    scrape_progress["islenen_haber"] = islenen_sayac[0]
                    scrape_progress["yuzde"] = 50 + int(
                        (islenen_sayac[0] / max(len(tum_haberler), 1)) * 50
                    )

                    if sonuc == "kaydedildi" or sonuc == "konumsuz":
                        if sonuc == "kaydedildi":
                            rapor["toplam_kaydedilen"] += 1
                        else:
                            rapor["toplam_konumsuz"] += 1
                        kaynak = haber.get("kaynak_site", "")
                        if kaynak in rapor["kaynak_detay"]:
                            rapor["kaynak_detay"][kaynak]["kaydedilen"] += 1
                    elif sonuc == "tekrar":
                        rapor["toplam_tekrar"] += 1
                    elif sonuc == "benzer":
                        rapor["toplam_benzer"] += 1
                except Exception as e:
                    rapor["hatalar"].append(f"Haber işleme hatası: {e}")

        bitis = datetime.now()
        rapor["bitis_zamani"] = bitis.isoformat()
        rapor["sure_saniye"] = (bitis - baslangic).total_seconds()

        # Selenium driver'ı kapat (Cloudflare scraper'lar için açılmışsa)
        selenium_driver_kapat()

        # İlerleme durumunu sıfırla
        scrape_progress["aktif"] = False
        scrape_progress["asama"] = "Tamamlandı"
        scrape_progress["yuzde"] = 100

        logger.info(
            f"✅ Scraping tamamlandı: "
            f"{rapor['toplam_kaydedilen']} yeni haber kaydedildi, "
            f"{rapor['toplam_tekrar']} tekrar atlandı, "
            f"{rapor['toplam_benzer']} benzer birleştirildi "
            f"({rapor['sure_saniye']:.1f} saniye)"
        )

        return rapor

    def _haber_isle_ve_kaydet(self, haber: dict) -> str:
        """
        Tek bir haberi 7 adımlı işleme hattından (pipeline) geçirir:
        1. Link bazlı mükerrer kontrol
        2. Metin temizleme (HTML, boşluk, reklam, normalizasyon)
        3. Embedding bazlı benzerlik kontrolü (eşik: 0.90)
        4. Anahtar kelime tabanlı haber sınıflandırma
        5. Regex ile konum bilgisi çıkarımı (ilçe, mahalle, cadde)
        6. Google Geocoding API ile koordinat dönüştürme
        7. MongoDB'ye kaydetme

        Args:
            haber: Ham haber verisi (scraper'dan gelen dict)

        Returns:
            str: İşlem sonucu ('kaydedildi', 'tekrar', 'benzer', 'konumsuz', 'hata')
        """
        # ADIM 1: Link bazlı mükerrer kontrol (thread-safe)
        with self._cache_lock:
            if haber.get("haber_linki") in self._mevcut_linkler_cache:
                return "tekrar"

        # 2. Metin temizleme
        haber["baslik"] = self.temizleyici.baslik_temizle(
            haber.get("baslik", "")
        )
        haber["icerik"] = self.temizleyici.tam_temizlik(
            haber.get("icerik", "")
        )

        if not haber.get("baslik"):
            return "hata"

        if not haber.get("icerik"):
            logger.debug(f"İçeriksiz haber atlandı: {haber.get('haber_linki', '')}")
            return "hata"

        # ADIM 3: Embedding tabanlı benzerlik kontrolü
        # Farklı kaynaklardan gelen aynı haberin farklı linklere sahip
        # olabileceği durumlar için sentence-transformers modeli kullanılır.
        # Model: paraphrase-multilingual-MiniLM-L12-v2 (Türkçe destekli)
        # Kosinüs benzerliği hesaplanır: sim(a,b) = (a·b) / (||a|| * ||b||)
        # Eşik değeri: 0.90 (Config.SIMILARITY_THRESHOLD)
        yeni_metin = f"{haber['baslik']} {haber.get('icerik', '')}"

        # ADIM 3 için embedding önceden hesapla (lock dışında — CPU ağır iş)
        yeni_embedding = self.benzerlik_analizoru.embedding_olustur(yeni_metin)

        with self._cache_lock:
            cache_var = self.db and len(self._mevcut_haberler_cache) > 0
            haberler_snap = list(self._mevcut_haberler_cache) if cache_var else []
            embeddingler_snap = (
                self._mevcut_embeddingler_cache.copy()
                if cache_var and len(self._mevcut_embeddingler_cache) > 0
                else np.array([])
            )

        if cache_var and yeni_embedding is not None:
            benzerler = self.benzerlik_analizoru.benzerleri_bul(
                yeni_metin,
                haberler_snap,
                mevcut_embeddingler=embeddingler_snap,
                yeni_embedding=yeni_embedding,
            )

            if benzerler:
                en_benzer = benzerler[0]
                self.db.haber_kaynak_ekle(
                    en_benzer["haber"]["haber_linki"],
                    {
                        "site_adi": haber.get("kaynak_site", ""),
                        "link": haber.get("haber_linki", ""),
                        "benzerlik_orani": en_benzer["benzerlik_orani"],
                    },
                )
                with self._cache_lock:
                    self._mevcut_linkler_cache.add(haber.get("haber_linki"))
                return "benzer"

        # ADIM 4: Anahtar kelime tabanlı haber sınıflandırma
        # Her habere yalnızca bir tür atanır. Skor hesaplama:
        #   - Normal kelime eşleşmesi: +1 puan
        #   - Güçlü kelime eşleşmesi: +3 puan
        #   - Başlıkta eşleşme: x2 çarpan (güçlü ise x5)
        # Öncelik sırası: Yangın > Trafik > Hırsızlık > Elektrik > Vefat >
        # Sağlık > Eğitim > Spor > Yerel Yönetim > Kültürel
        siniflandirma = self.siniflandirici.siniflandir(
            haber.get("baslik", ""),
            haber.get("icerik", ""),
        )
        haber["haber_turu"] = siniflandirma["haber_turu"]
        haber["siniflandirma_guven"] = siniflandirma["guven_skoru"]

        # Sınıflandırılamayan haberler (5 zorunlu türden hiçbirine uymadı) atlanır
        if not haber["haber_turu"]:
            return "hata"

        # ADIM 5: Konum bilgisi çıkarımı (NLP / Regex)
        # 8 farklı regex kalıbı ile ilçe, mahalle, cadde/sokak, yol,
        # semt tespiti yapılır. Ayrıca GOSB, Seka Park gibi bilinen
        # landmark'lar da tanınır.
        # Sonuç: En spesifikten genele → cadde + mahalle + ilçe + Kocaeli
        konum_bilgisi = self.konum_cikarici.konum_cikar(
            haber.get("baslik", ""),
            haber.get("icerik", ""),
        )
        haber["konum_metni"] = konum_bilgisi.get("konum_metni")
        haber["ilce"] = konum_bilgisi.get("ilce")
        haber["mahalle"] = konum_bilgisi.get("mahalle")
        haber["tum_konumlar"] = konum_bilgisi.get("tum_konumlar", [])

        # ADIM 6: Geocoding (konum metni → enlem/boylam koordinatları)
        # Strateji: 1) Cache kontrol  2) Yerel ilçe fallback  3) Google API
        # Sonuç Kocaeli sınırları içinde doğrulanır (40.45°-41.10° / 29.20°-30.30°)
        if konum_bilgisi.get("geocoding_sorgusu"):
            geo_sonuc = self.geocoder.koordinat_bul(
                konum_bilgisi["geocoding_sorgusu"]
            )
            if geo_sonuc.get("basarili"):
                haber["enlem"] = geo_sonuc["enlem"]
                haber["boylam"] = geo_sonuc["boylam"]
                haber["konum_geojson"] = {
                    "type": "Point",
                    "coordinates": [geo_sonuc["boylam"], geo_sonuc["enlem"]],
                }
                haber["formatli_adres"] = geo_sonuc.get("formatli_adres", "")
            else:
                # Geocoding başarısız - sadece ilçe ile dene
                if konum_bilgisi.get("ilce"):
                    geo_sonuc = self.geocoder.koordinat_bul(
                        f"{konum_bilgisi['ilce']}, Kocaeli"
                    )
                    if geo_sonuc.get("basarili"):
                        haber["enlem"] = geo_sonuc["enlem"]
                        haber["boylam"] = geo_sonuc["boylam"]
                        haber["konum_geojson"] = {
                            "type": "Point",
                            "coordinates": [geo_sonuc["boylam"], geo_sonuc["enlem"]],
                        }
                        haber["formatli_adres"] = geo_sonuc.get("formatli_adres", "")

        # Konumu olmayanları da kaydet ama haritada gösterme
        if not haber.get("enlem"):
            haber["enlem"] = None
            haber["boylam"] = None
            haber["konum_geojson"] = None

        # 7. Veritabanına kaydet
        if self.db:
            basarili = self.db.haber_ekle(haber)
            if basarili:
                # Cache'leri thread-safe güncelle
                with self._cache_lock:
                    self._mevcut_linkler_cache.add(haber.get("haber_linki"))
                    self._mevcut_haberler_cache.append({
                        "baslik": haber.get("baslik", ""),
                        "icerik": haber.get("icerik", ""),
                        "haber_linki": haber.get("haber_linki", ""),
                    })
                    if yeni_embedding is not None:
                        if self._mevcut_embeddingler_cache is None or len(self._mevcut_embeddingler_cache) == 0:
                            self._mevcut_embeddingler_cache = np.array([yeni_embedding])
                        else:
                            self._mevcut_embeddingler_cache = np.vstack(
                                [self._mevcut_embeddingler_cache, yeni_embedding]
                            )

                # Embedding'i kalıcı olarak MongoDB'ye kaydet (lock dışında)
                if yeni_embedding is not None and haber.get("haber_linki"):
                    self.db.embedding_kaydet(haber["haber_linki"], yeni_embedding)

                if not haber.get("enlem"):
                    return "konumsuz"
                return "kaydedildi"

            # haber_ekle False döndürdü → DuplicateKeyError (link daha önce eklendi)
            return "tekrar"

        # Veritabanı bağlantısı yok
        if not haber.get("enlem"):
            return "konumsuz"
        return "hata"

    def tek_kaynak_cek(self, kaynak_index: int) -> dict:
        """
        Belirli bir kaynaktan haber çeker.

        Args:
            kaynak_index: Scraper listesindeki index (0-4)

        Returns:
            dict: İşlem raporu
        """
        if 0 <= kaynak_index < len(self.scraperlar):
            scraper = self.scraperlar[kaynak_index]
            haberler = scraper.tum_haberleri_cek()

            kaydedilen = 0
            for haber in haberler:
                sonuc = self._haber_isle_ve_kaydet(haber)
                if sonuc == "kaydedildi":
                    kaydedilen += 1

            return {
                "kaynak": scraper.kaynak_adi,
                "cekilen": len(haberler),
                "kaydedilen": kaydedilen,
            }

        return {"hata": "Geçersiz kaynak indeksi"}
