"""
Kocaeli Haber Haritası - Geocoding (Koordinat Dönüştürme) Modülü

Haber metninden tespit edilen konum bilgisini enlem/boylam
koordinatlarına dönüştürür. Google Geocoding API kullanır.

Özellikler:
- API sonuçlarını veritabanında cache'ler (gereksiz tekrar çağrı önleme)
- Başarısız geocoding durumunda kayıt işlenmez
- Kocaeli sınırları içinde doğrulama yapılır
"""

import logging
import hashlib
import googlemaps
from config.settings import Config
from database.mongodb import MongoDB

logger = logging.getLogger(__name__)


class Geocoder:
    """Google Geocoding API ile koordinat dönüştürme sınıfı."""

    # Kocaeli ili sınır koordinatları (yaklaşık dikdörtgen)
    KOCAELI_SINIRLAR = {
        "min_enlem": 40.45,
        "max_enlem": 41.10,
        "min_boylam": 29.20,
        "max_boylam": 30.30,
    }

    # Kocaeli ilçe merkez koordinatları (Google API kullanılamadığında fallback)
    ILCE_KOORDINATLARI = {
        "İzmit": {"enlem": 40.7654, "boylam": 29.9408},
        "Gebze": {"enlem": 40.8027, "boylam": 29.4307},
        "Darıca": {"enlem": 40.7690, "boylam": 29.3753},
        "Gölcük": {"enlem": 40.7167, "boylam": 29.8333},
        "Kandıra": {"enlem": 41.0714, "boylam": 30.1522},
        "Karamürsel": {"enlem": 40.6917, "boylam": 29.6167},
        "Körfez": {"enlem": 40.7239, "boylam": 29.7644},
        "Derince": {"enlem": 40.7550, "boylam": 29.8150},
        "Başiskele": {"enlem": 40.7167, "boylam": 29.9833},
        "Çayırova": {"enlem": 40.8261, "boylam": 29.3731},
        "Dilovası": {"enlem": 40.7833, "boylam": 29.5333},
        "Kartepe": {"enlem": 40.6833, "boylam": 30.0500},
        # Küçük yazım varyantları
        "izmit": {"enlem": 40.7654, "boylam": 29.9408},
        "gebze": {"enlem": 40.8027, "boylam": 29.4307},
        "darıca": {"enlem": 40.7690, "boylam": 29.3753},
        "gölcük": {"enlem": 40.7167, "boylam": 29.8333},
        "kandıra": {"enlem": 41.0714, "boylam": 30.1522},
        "karamürsel": {"enlem": 40.6917, "boylam": 29.6167},
        "körfez": {"enlem": 40.7239, "boylam": 29.7644},
        "derince": {"enlem": 40.7550, "boylam": 29.8150},
        "başiskele": {"enlem": 40.7167, "boylam": 29.9833},
        "çayırova": {"enlem": 40.8261, "boylam": 29.3731},
        "dilovası": {"enlem": 40.7833, "boylam": 29.5333},
        "kartepe": {"enlem": 40.6833, "boylam": 30.0500},
    }

    # Sabit koordinatlı önemli yerler alias listeleriyle birlikte tanımlanır.
    SABIT_KONUM_HARITASI = {
        "Kocaeli Stadyumu": {
            "aliaslar": [
                "Kocaeli Stadı",
                "Kocaeli Stadyumu",
                "İzmit Kocaeli Stadı",
                "Yıldız Entegre Kocaeli Stadyumu",
                "İzmit Stadyumu",
                "Kocaelispor",
            ],
            "enlem": 40.77104,
            "boylam": 30.02036,
            "formatli_adres": "Kocaeli Stadyumu, İzmit, Kocaeli",
        },
        "Brunga Tesisleri": {
            "aliaslar": [
                "Brunga Tesisleri",
                "Körfez Brunga Tesisleri",
            ],
            "enlem": 40.76172,
            "boylam": 29.78272,
            "formatli_adres": "Brunga Tesisleri, Körfez, Kocaeli",
        },
    }

    # Fallback işaretçileri küçük tutulur; doğruluk görsel dağılımdan daha önemlidir.
    YEREL_FALLBACK_MAX_OFFSET = 0.00035

    def __init__(self):
        """Geocoder'ı başlatır."""
        self.api_key = Config.GOOGLE_GEOCODING_API_KEY
        self.gmaps = None
        self.db = None

        if self.api_key:
            try:
                self.gmaps = googlemaps.Client(key=self.api_key)
                logger.info("Google Geocoding API bağlantısı kuruldu.")
            except Exception as e:
                logger.error(f"Google Maps API bağlantı hatası: {e}")

        try:
            self.db = MongoDB()
        except Exception as e:
            logger.warning(f"MongoDB bağlantısı kurulamadı (cache devre dışı): {e}")

    def koordinat_bul(self, konum_metni: str) -> dict:
        """
        Konum metnini koordinatlara dönüştürür.
        Önce cache'i kontrol eder, yoksa API'ye başvurur.

        Args:
            konum_metni: Geocoding yapılacak konum metni
                         Örn: "Yenişehir Mahallesi, İzmit, Kocaeli"

        Returns:
            dict: {
                "enlem": float,
                "boylam": float,
                "formatli_adres": str,
                "basarili": bool
            } veya başarısız ise {"basarili": False}
        """
        if not konum_metni:
            return {"basarili": False, "hata": "Konum metni boş"}

        # 1. Cache kontrolü
        cache_sonuc = self._cache_kontrol(konum_metni)
        if cache_sonuc:
            logger.info(f"Cache'den konum bulundu: {konum_metni}")
            return {
                "enlem": cache_sonuc["enlem"],
                "boylam": cache_sonuc["boylam"],
                "formatli_adres": konum_metni,
                "basarili": True,
                "kaynak": "cache",
            }

        # 2. Sabit bilinen yer koordinatları
        sabit_sonuc = self._bilinen_yer_koordinat_bul(konum_metni)
        if sabit_sonuc:
            self._cache_kaydet(konum_metni, sabit_sonuc["enlem"], sabit_sonuc["boylam"])
            return sabit_sonuc

        # 3. API ile geocoding
        if not self.gmaps:
            logger.warning("Google Maps API yapılandırılmamış, yerel fallback kullanılacak.")
            yerel_sonuc = self._yerel_koordinat_bul(konum_metni)
            if yerel_sonuc:
                self._cache_kaydet(konum_metni, yerel_sonuc["enlem"], yerel_sonuc["boylam"])
                return yerel_sonuc
            return {"basarili": False, "hata": "API yapılandırılmamış"}

        try:
            # Konum metnine "Kocaeli, Türkiye" ekleyerek daha iyi sonuç al
            sorgu = konum_metni
            if "kocaeli" not in konum_metni.lower():
                sorgu = f"{konum_metni}, Kocaeli, Türkiye"

            sonuc = self.gmaps.geocode(
                sorgu,
                language="tr",
                region="tr",
            )

            if not sonuc:
                logger.warning(f"Geocoding sonuç bulunamadı: {konum_metni}")
                return {"basarili": False, "hata": "Sonuç bulunamadı"}

            # İlk sonucu al
            ilk_sonuc = sonuc[0]
            enlem = ilk_sonuc["geometry"]["location"]["lat"]
            boylam = ilk_sonuc["geometry"]["location"]["lng"]
            formatli_adres = ilk_sonuc["formatted_address"]

            # Gerçek API koordinatlarını aynen kullan, sadece doğrula.
            if not self._kocaeli_sinirlarinda_mi(enlem, boylam):
                logger.warning(
                    f"Konum Kocaeli sınırları dışında: {konum_metni} "
                    f"({enlem}, {boylam})"
                )
                return {
                    "basarili": False,
                    "hata": "Konum Kocaeli sınırları dışında",
                }

            # 4. Cache'e kaydet
            self._cache_kaydet(konum_metni, enlem, boylam)

            logger.info(
                f"Geocoding başarılı: {konum_metni} -> ({enlem}, {boylam})"
            )

            return {
                "enlem": enlem,
                "boylam": boylam,
                "formatli_adres": formatli_adres,
                "basarili": True,
                "kaynak": "api",
            }

        except googlemaps.exceptions.ApiError as e:
            logger.error(f"Geocoding API hatası: {e}")
            yerel_sonuc = self._yerel_koordinat_bul(konum_metni)
            if yerel_sonuc:
                self._cache_kaydet(konum_metni, yerel_sonuc["enlem"], yerel_sonuc["boylam"])
                return yerel_sonuc
            return {"basarili": False, "hata": f"API hatası: {e}"}
        except Exception as e:
            logger.error(f"Geocoding genel hata: {e}")
            yerel_sonuc = self._yerel_koordinat_bul(konum_metni)
            if yerel_sonuc:
                self._cache_kaydet(konum_metni, yerel_sonuc["enlem"], yerel_sonuc["boylam"])
                return yerel_sonuc
            return {"basarili": False, "hata": str(e)}

    def toplu_koordinat_bul(self, konum_listesi: list) -> list:
        """
        Birden fazla konum için koordinat bulur.

        Args:
            konum_listesi: Konum metinleri listesi

        Returns:
            list: Koordinat sonuçları listesi
        """
        sonuclar = []
        for konum in konum_listesi:
            sonuc = self.koordinat_bul(konum)
            sonuclar.append({
                "konum_metni": konum,
                **sonuc,
            })
        return sonuclar

    def _yerel_koordinat_bul(self, konum_metni: str) -> dict:
        """
        Yerel ilçe koordinatları sözlüğünden konum metni içindeki
        ilçeyi tespit ederek koordinat döndürür.
        Google Geocoding API kullanılamadığında fallback olarak çalışır.

        Args:
            konum_metni: Konum metni (örn: "İzmit, Kocaeli" veya "Kartepe'de okul")

        Returns:
            dict: Koordinat bilgisi veya None
        """
        metin_lower = konum_metni.lower()
        for ilce_adi, koordinat in self.ILCE_KOORDINATLARI.items():
            # Sadece büyük harfli (orijinal) ilçe adlarını kontrol et
            if ilce_adi[0].isupper() and ilce_adi.lower() in metin_lower:
                enlem = koordinat["enlem"]
                boylam = koordinat["boylam"]

                # Fallback dağılımı çok küçük tutulur; ilçe merkezi esas kabul edilir.
                if self.YEREL_FALLBACK_MAX_OFFSET > 0:
                    enlem_offset, boylam_offset = self._deterministik_offset_uret(
                        f"{ilce_adi}|{konum_metni}"
                    )
                    enlem += enlem_offset
                    boylam += boylam_offset

                logger.info(
                    f"Yerel koordinat bulundu: {konum_metni} -> {ilce_adi} ({enlem:.4f}, {boylam:.4f})"
                )
                return {
                    "enlem": enlem,
                    "boylam": boylam,
                    "formatli_adres": f"{ilce_adi}, Kocaeli",
                    "basarili": True,
                    "kaynak": "yerel",
                }
        return None

    def _bilinen_yer_koordinat_bul(self, konum_metni: str) -> dict:
        """Sabit koordinatı bilinen landmark'ları doğrudan çözer."""
        konum_lower = konum_metni.lower()
        for yer_adi, tanim in self.SABIT_KONUM_HARITASI.items():
            if any(alias.lower() in konum_lower for alias in tanim["aliaslar"]):
                logger.info(
                    f"Sabit koordinat bulundu: {konum_metni} -> {yer_adi} ({tanim['enlem']}, {tanim['boylam']})"
                )
                return {
                    "enlem": tanim["enlem"],
                    "boylam": tanim["boylam"],
                    "formatli_adres": tanim["formatli_adres"],
                    "basarili": True,
                    "kaynak": "sabit",
                }
        return None

    def _deterministik_offset_uret(self, anahtar: str) -> tuple[float, float]:
        """Aynı anahtar için sabit küçük offset üretir."""
        digest = hashlib.sha256(anahtar.encode("utf-8")).digest()
        lat_seed = int.from_bytes(digest[:8], "big")
        lng_seed = int.from_bytes(digest[8:16], "big")

        max_offset = self.YEREL_FALLBACK_MAX_OFFSET
        if max_offset <= 0:
            return 0.0, 0.0

        enlem_offset = ((lat_seed / float(2**64 - 1)) * 2 - 1) * max_offset
        boylam_offset = ((lng_seed / float(2**64 - 1)) * 2 - 1) * max_offset
        return enlem_offset, boylam_offset

    def _kocaeli_sinirlarinda_mi(self, enlem: float, boylam: float) -> bool:
        """
        Koordinatların Kocaeli sınırları içinde olup olmadığını kontrol eder.

        Args:
            enlem: Enlem koordinatı
            boylam: Boylam koordinatı

        Returns:
            bool: Sınırlar içindeyse True
        """
        return (
            self.KOCAELI_SINIRLAR["min_enlem"] <= enlem <= self.KOCAELI_SINIRLAR["max_enlem"]
            and self.KOCAELI_SINIRLAR["min_boylam"] <= boylam <= self.KOCAELI_SINIRLAR["max_boylam"]
        )

    def _cache_kontrol(self, konum_metni: str) -> dict:
        """Cache'den konum bilgisi kontrol eder."""
        if self.db:
            return self.db.konum_getir(konum_metni)
        return None

    def _cache_kaydet(self, konum_metni: str, enlem: float, boylam: float):
        """Geocoding sonucunu cache'e kaydeder."""
        if self.db:
            self.db.konum_kaydet(konum_metni, enlem, boylam)
