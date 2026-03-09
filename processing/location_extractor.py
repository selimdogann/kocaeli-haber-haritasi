"""
Kocaeli Haber Haritası - Konum Bilgisi Çıkarım Modülü

Haber metninden olayın gerçekleştiği yer bilgisini çıkarır.
Kocaeli ili sınırları içindeki mahalle, sokak, cadde gibi
konum bilgilerini tespit eder.
"""

import re
import logging
from config.settings import Config

logger = logging.getLogger(__name__)


class LocationExtractor:
    """Haber metinlerinden konum bilgisi çıkaran sınıf."""

    # Kocaeli ilçeleri
    ILCELER = [ilce.lower() for ilce in Config.KOCAELI_DISTRICTS]

    # Konum belirten anahtar kelime kalıpları
    KONUM_KALIPLARI = [
        # İlçe + Mahalle kalıpları
        r"(?P<ilce>[A-ZÇĞİÖŞÜa-zçğıöşü]+)\s+ilçesi(?:nin|nde|ne)?\s+(?P<mahalle>[A-ZÇĞİÖŞÜa-zçğıöşü\s]+?)\s+(?:mahallesi|mah\.?)",
        # Mahalle adı kalıbı
        r"(?P<mahalle>[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)*)\s+(?:Mahallesi|mahallesi|Mah\.?|mah\.?)",
        # Cadde/Sokak kalıbı
        r"(?P<cadde>[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜa-zçğıöşü]+)*)\s+(?:Caddesi|caddesi|Cad\.?|cad\.?|Bulvarı|bulvarı|Blv\.?|blv\.?)",
        r"(?P<sokak>[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜa-zçğıöşü]+)*)\s+(?:Sokağı?|sokağı?|Sok\.?|sok\.?)",
        # Yol/Otoyol kalıbı
        r"(?:D-?\d+|O-?\d+|TEM|E-?\d+)\s*(?:karayolu|otoyolu?|yolu)",
        r"(?P<yol>(?:Kocaeli|İstanbul|Ankara|Bursa|Yalova|Sakarya)\s*[-–]\s*(?:Kocaeli|İstanbul|Ankara|Bursa|Yalova|Sakarya))\s+(?:karayolu|otoyolu?|yolu)",
        # Semt/Bölge kalıpları
        r"(?P<semt>[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)*)\s+(?:semtinde|bölgesinde|mevkiinde|mevkisinde|civarında|yakınında|karşısında|arkasında|önünde)",
        # "X'de, X'da" kalıbı (yer belirten)
        r"(?:Kocaeli|İzmit|Gebze|Darıca|Çayırova|Dilovası|Körfez|Derince|Gölcük|Karamürsel|Başiskele|Kartepe|Kandıra)'?\s*(?:de|da|te|ta)\b",
    ]

    # Önemli yer isimleri ve landmark'lar
    BILINEN_YERLER = [
        # Sanayi bölgeleri
        "Gebze Organize Sanayi", "GOSB", "Dilovası Organize Sanayi",
        "Arslanbey Organize Sanayi",
        # Hastaneler
        "Kocaeli Üniversitesi Hastanesi", "Derince Eğitim ve Araştırma",
        "Gebze Fatih Devlet Hastanesi", "Seka Devlet Hastanesi",
        # Meydanlar ve parklar
        "Cumhuriyet Meydanı", "Seka Park", "Ormanya",
        "Maşukiye", "Kartepe Kayak Merkezi",
        # AVM'ler
        "Symbol AVM", "Gebze Center", "41 Burda AVM",
        # Limanlar
        "İzmit Körfez Geçiş Köprüsü", "Osmangazi Köprüsü",
        "Derince Limanı", "Hereke",
    ]

    def __init__(self):
        """Konum çıkarıcıyı başlatır."""
        self.derli_kaliplar = [
            re.compile(kalip, re.UNICODE | re.IGNORECASE)
            for kalip in self.KONUM_KALIPLARI
        ]

    def konum_cikar(self, baslik: str, icerik: str) -> dict:
        """
        Haber başlık ve içeriğinden konum bilgisi çıkarır.

        Args:
            baslik: Haber başlığı
            icerik: Haber içeriği

        Returns:
            dict: {
                "konum_metni": str,      # En spesifik konum metni
                "ilce": str,             # Tespit edilen ilçe
                "mahalle": str,          # Tespit edilen mahalle
                "cadde_sokak": str,      # Tespit edilen cadde/sokak
                "tum_konumlar": list,    # Tespit edilen tüm konum bilgileri
                "geocoding_sorgusu": str # Geocoding API'ye gönderilecek sorgu
            }
        """
        birlesik_metin = f"{baslik} {icerik}"
        sonuc = {
            "konum_metni": None,
            "ilce": None,
            "mahalle": None,
            "cadde_sokak": None,
            "tum_konumlar": [],
            "geocoding_sorgusu": None,
        }

        # 1. İlçe tespiti
        ilce = self._ilce_tespit_et(birlesik_metin)
        if ilce:
            sonuc["ilce"] = ilce

        # 2. Mahalle tespiti
        mahalle = self._mahalle_tespit_et(birlesik_metin)
        if mahalle:
            sonuc["mahalle"] = mahalle

        # 3. Cadde/Sokak tespiti
        cadde_sokak = self._cadde_sokak_tespit_et(birlesik_metin)
        if cadde_sokak:
            sonuc["cadde_sokak"] = cadde_sokak

        # 4. Bilinen yer tespiti
        bilinen_yer = self._bilinen_yer_tespit_et(birlesik_metin)

        # 5. Regex kalıpları ile tüm konumları topla
        tum_konumlar = self._tum_konumlari_bul(birlesik_metin)
        sonuc["tum_konumlar"] = tum_konumlar

        # 6. En spesifik konum metnini oluştur
        konum_parcalari = []

        if cadde_sokak:
            konum_parcalari.append(cadde_sokak)
        if mahalle:
            konum_parcalari.append(f"{mahalle} Mahallesi")
        if bilinen_yer:
            konum_parcalari.append(bilinen_yer)
        if ilce:
            konum_parcalari.append(ilce)

        if konum_parcalari:
            konum_parcalari.append("Kocaeli")
            sonuc["konum_metni"] = ", ".join(konum_parcalari)
            sonuc["geocoding_sorgusu"] = sonuc["konum_metni"]
        elif ilce:
            sonuc["konum_metni"] = f"{ilce}, Kocaeli"
            sonuc["geocoding_sorgusu"] = sonuc["konum_metni"]

        return sonuc

    def _ilce_tespit_et(self, metin: str) -> str:
        """İlçe adını tespit eder."""
        metin_lower = metin.lower()

        for ilce in Config.KOCAELI_DISTRICTS:
            # Tam kelime eşleşmesi
            pattern = re.compile(
                r"\b" + re.escape(ilce) + r"\b",
                re.IGNORECASE | re.UNICODE,
            )
            if pattern.search(metin):
                return ilce

        return None

    def _mahalle_tespit_et(self, metin: str) -> str:
        """Mahalle adını tespit eder."""
        # Mahalle kalıpları
        mahalle_kaliplari = [
            r"([A-ZÇĞİÖŞÜa-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜa-zçğıöşü]+)*)\s+(?:Mahallesi|mahallesi|Mah\.?|mah\.?)",
        ]

        for kalip in mahalle_kaliplari:
            eslesme = re.search(kalip, metin, re.UNICODE)
            if eslesme:
                mahalle = eslesme.group(1).strip()
                # Çok kısa veya anlamsız sonuçları filtrele
                if len(mahalle) > 2:
                    return mahalle

        return None

    def _cadde_sokak_tespit_et(self, metin: str) -> str:
        """Cadde veya sokak adını tespit eder."""
        kaliplar = [
            r"([A-ZÇĞİÖŞÜa-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜa-zçğıöşü]+)*)\s+(?:Caddesi|caddesi|Cad\.?|cad\.?)",
            r"([A-ZÇĞİÖŞÜa-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜa-zçğıöşü]+)*)\s+(?:Sokağı?|sokağı?|Sok\.?|sok\.?)",
            r"([A-ZÇĞİÖŞÜa-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜa-zçğıöşü]+)*)\s+(?:Bulvarı|bulvarı|Blv\.?|blv\.?)",
        ]

        for kalip in kaliplar:
            eslesme = re.search(kalip, metin, re.UNICODE)
            if eslesme:
                return eslesme.group(0).strip()

        return None

    def _bilinen_yer_tespit_et(self, metin: str) -> str:
        """Bilinen yerleri tespit eder."""
        metin_lower = metin.lower()

        for yer in self.BILINEN_YERLER:
            if yer.lower() in metin_lower:
                return yer

        return None

    def _tum_konumlari_bul(self, metin: str) -> list:
        """Metindeki tüm konum bilgilerini regex ile bulur."""
        konumlar = []

        for kalip in self.derli_kaliplar:
            eslesmeler = kalip.finditer(metin)
            for eslesme in eslesmeler:
                konum = eslesme.group(0).strip()
                if konum and konum not in konumlar:
                    konumlar.append(konum)

        return konumlar
