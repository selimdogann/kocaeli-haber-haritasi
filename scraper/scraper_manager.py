"""
Kocaeli Haber Haritası - Scraper Yöneticisi

Tüm scraper'ları koordine eder, haberleri toplar,
temizler, sınıflandırır, konumlarını çıkarır ve veritabanına kaydeder.
"""

import logging
from datetime import datetime
import numpy as np
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

logger = logging.getLogger(__name__)

# Global ilerleme durumu (thread-safe basit dict)
scrape_progress = {
    "aktif": False,
    "aşama": "",
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
        scrape_progress["aşama"] = "Hazırlanıyor..."
        scrape_progress["kaynak"] = ""
        scrape_progress["kaynak_no"] = 0
        scrape_progress["toplam_kaynak"] = len(self.scraperlar)
        scrape_progress["islenen_haber"] = 0
        scrape_progress["toplam_haber"] = 0
        scrape_progress["yuzde"] = 0

        # 0. Performans için mevcut haber/cache hazırlığı
        if self.db:
            self._mevcut_haberler_cache = self.db.tum_haber_metinlerini_getir()
            self._mevcut_linkler_cache = {
                h.get("haber_linki")
                for h in self._mevcut_haberler_cache
                if h.get("haber_linki")
            }

            if self._mevcut_haberler_cache:
                mevcut_metinler = [
                    f"{h.get('baslik', '')} {h.get('icerik', '')}"
                    for h in self._mevcut_haberler_cache
                ]
                self._mevcut_embeddingler_cache = (
                    self.benzerlik_analizoru.embeddingleri_olustur(mevcut_metinler)
                )

        # 1. Tüm kaynaklardan haberleri çek
        for idx, scraper in enumerate(self.scraperlar):
            try:
                scrape_progress["aşama"] = "Haberler çekiliyor"
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

        # 2. Her haberi işle ve kaydet
        scrape_progress["aşama"] = "Haberler işleniyor"
        scrape_progress["toplam_haber"] = len(tum_haberler)
        scrape_progress["yuzde"] = 50
        for i, haber in enumerate(tum_haberler):
            try:
                scrape_progress["islenen_haber"] = i + 1
                scrape_progress["yuzde"] = 50 + int((i / max(len(tum_haberler), 1)) * 50)
                sonuc = self._haber_isle_ve_kaydet(haber)

                if sonuc == "kaydedildi":
                    rapor["toplam_kaydedilen"] += 1
                    kaynak = haber.get("kaynak_site", "")
                    if kaynak in rapor["kaynak_detay"]:
                        rapor["kaynak_detay"][kaynak]["kaydedilen"] += 1
                elif sonuc == "tekrar":
                    rapor["toplam_tekrar"] += 1
                elif sonuc == "benzer":
                    rapor["toplam_benzer"] += 1
                elif sonuc == "konumsuz":
                    rapor["toplam_konumsuz"] += 1

            except Exception as e:
                rapor["hatalar"].append(f"Haber işleme hatası: {e}")

        bitis = datetime.now()
        rapor["bitis_zamani"] = bitis.isoformat()
        rapor["sure_saniye"] = (bitis - baslangic).total_seconds()

        # İlerleme durumunu sıfırla
        scrape_progress["aktif"] = False
        scrape_progress["aşama"] = "Tamamlandı"
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
        # ADIM 1: Link bazlı mükerrer kontrol
        # MongoDB'de haber_linki alanına unique index tanımlıdır.
        # Aynı link zaten veritabanında varsa işlem yapılmaz.
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

        # ADIM 3: Embedding tabanlı benzerlik kontrolü
        # Farklı kaynaklardan gelen aynı haberin farklı linklere sahip
        # olabileceği durumlar için sentence-transformers modeli kullanılır.
        # Model: paraphrase-multilingual-MiniLM-L12-v2 (Türkçe destekli)
        # Kosinüs benzerliği hesaplanır: sim(a,b) = (a·b) / (||a|| * ||b||)
        # Eşik değeri: 0.90 (Config.SIMILARITY_THRESHOLD)
        yeni_metin = f"{haber['baslik']} {haber.get('icerik', '')}"

        if self.db and self._mevcut_haberler_cache:
            # Yeni haberin embedding vektörünü oluştur (384 boyutlu)
            yeni_embedding = self.benzerlik_analizoru.embedding_olustur(yeni_metin)
            # Mevcut tüm haberlerle kosinüs benzerliğini karşılaştır
            benzerler = self.benzerlik_analizoru.benzerleri_bul(
                yeni_metin,
                self._mevcut_haberler_cache,
                mevcut_embeddingler=self._mevcut_embeddingler_cache,
                yeni_embedding=yeni_embedding,
            )

            if benzerler:
                # Benzerlik >= 0.90 → Aynı haber kabul edilir.
                # Ana haberin diger_kaynaklar dizisine yeni kaynak eklenir.
                # Bu sayede çoklu kaynak bilgisi korunur.
                en_benzer = benzerler[0]
                self.db.haber_kaynak_ekle(
                    en_benzer["haber"]["haber_linki"],
                    {
                        "site_adi": haber.get("kaynak_site", ""),
                        "link": haber.get("haber_linki", ""),
                        "benzerlik_orani": en_benzer["benzerlik_orani"],
                    },
                )
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

        # Sınıflandırılamayan haberler (hiçbir anahtar kelime eşleşmedi)
        # "diger" kategorisine atanır
        if not haber["haber_turu"]:
            haber["haber_turu"] = "diger"
            haber["siniflandirma_guven"] = 0.0

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
                # Cache'leri güncel tut
                self._mevcut_linkler_cache.add(haber.get("haber_linki"))
                self._mevcut_haberler_cache.append({
                    "baslik": haber.get("baslik", ""),
                    "icerik": haber.get("icerik", ""),
                    "haber_linki": haber.get("haber_linki", ""),
                })

                yeni_embedding = self.benzerlik_analizoru.embedding_olustur(yeni_metin)
                if yeni_embedding is not None:
                    if self._mevcut_embeddingler_cache is None or len(self._mevcut_embeddingler_cache) == 0:
                        self._mevcut_embeddingler_cache = np.array([yeni_embedding])
                    else:
                        self._mevcut_embeddingler_cache = np.vstack(
                            [self._mevcut_embeddingler_cache, yeni_embedding]
                        )

                return "kaydedildi"

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
