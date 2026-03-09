"""
Kocaeli Haber Haritası - Scraper Yöneticisi

Tüm scraper'ları koordine eder, haberleri toplar,
temizler, sınıflandırır, konumlarını çıkarır ve veritabanına kaydeder.
"""

import logging
from datetime import datetime
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

        # 1. Tüm kaynaklardan haberleri çek
        for scraper in self.scraperlar:
            try:
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
        for haber in tum_haberler:
            try:
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
        Tek bir haberi işler: temizler, sınıflandırır, konumlar ve kaydeder.

        Args:
            haber: Ham haber verisi

        Returns:
            str: İşlem sonucu ('kaydedildi', 'tekrar', 'benzer', 'konumsuz', 'hata')
        """
        # 1. Duplicate kontrolü (link bazlı)
        if self.db and self.db.haber_linki_var_mi(haber.get("haber_linki", "")):
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

        # 3. Benzerlik kontrolü (embedding tabanlı)
        if self.db:
            mevcut_haberler = self.db.tum_haber_metinlerini_getir()
            if mevcut_haberler:
                yeni_metin = f"{haber['baslik']} {haber.get('icerik', '')}"
                benzerler = self.benzerlik_analizoru.benzerleri_bul(
                    yeni_metin, mevcut_haberler
                )

                if benzerler:
                    # Aynı haber bulundu - kaynak bilgisini ekle
                    en_benzer = benzerler[0]
                    self.db.haber_kaynak_ekle(
                        en_benzer["haber"]["haber_linki"],
                        {
                            "site_adi": haber.get("kaynak_site", ""),
                            "link": haber.get("haber_linki", ""),
                            "benzerlik_orani": en_benzer["benzerlik_orani"],
                        },
                    )
                    return "benzer"

        # 4. Haber sınıflandırma
        siniflandirma = self.siniflandirici.siniflandir(
            haber.get("baslik", ""),
            haber.get("icerik", ""),
        )
        haber["haber_turu"] = siniflandirma["haber_turu"]
        haber["siniflandirma_guven"] = siniflandirma["guven_skoru"]

        # Sınıflandırılamayan haberleri atla
        if not haber["haber_turu"]:
            return "hata"

        # 5. Konum çıkarımı
        konum_bilgisi = self.konum_cikarici.konum_cikar(
            haber.get("baslik", ""),
            haber.get("icerik", ""),
        )
        haber["konum_metni"] = konum_bilgisi.get("konum_metni")
        haber["ilce"] = konum_bilgisi.get("ilce")
        haber["mahalle"] = konum_bilgisi.get("mahalle")
        haber["tum_konumlar"] = konum_bilgisi.get("tum_konumlar", [])

        # 6. Geocoding
        if konum_bilgisi.get("geocoding_sorgusu"):
            geo_sonuc = self.geocoder.koordinat_bul(
                konum_bilgisi["geocoding_sorgusu"]
            )
            if geo_sonuc.get("basarili"):
                haber["enlem"] = geo_sonuc["enlem"]
                haber["boylam"] = geo_sonuc["boylam"]
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
                        haber["formatli_adres"] = geo_sonuc.get("formatli_adres", "")

        # Konumu olmayanları da kaydet ama haritada gösterme
        if not haber.get("enlem"):
            haber["enlem"] = None
            haber["boylam"] = None

        # 7. Veritabanına kaydet
        if self.db:
            basarili = self.db.haber_ekle(haber)
            if basarili:
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
