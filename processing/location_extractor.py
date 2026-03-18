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

    NER_ETIKETLERI = {"LOC", "ORG", "MISC"}
    NER_KONUM_IPUCLARI = [
        "mahallesi", "mah.", "caddesi", "cad.", "sokağı", "sok.",
        "bulvarı", "blv.", "park", "meydanı", "avm", "hastanesi",
        "devlet hastanesi", "limanı", "köprüsü", "organize sanayi",
        "kayak merkezi", "stadyumu", "terminali",
    ]

    def __init__(self):
        """Konum çıkarıcıyı başlatır."""
        self.derli_kaliplar = [
            re.compile(kalip, re.UNICODE | re.IGNORECASE)
            for kalip in self.KONUM_KALIPLARI
        ]
        self.ner_pipeline = None
        self.ner_yukleme_denendi = False

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

        # 6. Regex sonuç vermezse NER fallback ile konumu tahmin et
        if not any([mahalle, cadde_sokak, bilinen_yer, tum_konumlar]):
            ner_sonuc = self._ner_ile_konum_tespit_et(birlesik_metin)
            if ner_sonuc:
                ilce = ilce or ner_sonuc.get("ilce")
                mahalle = mahalle or ner_sonuc.get("mahalle")
                cadde_sokak = cadde_sokak or ner_sonuc.get("cadde_sokak")
                bilinen_yer = bilinen_yer or ner_sonuc.get("bilinen_yer")
                if ilce:
                    sonuc["ilce"] = ilce
                if mahalle:
                    sonuc["mahalle"] = mahalle
                if cadde_sokak:
                    sonuc["cadde_sokak"] = cadde_sokak
                for konum in ner_sonuc.get("tum_konumlar", []):
                    if konum not in sonuc["tum_konumlar"]:
                        sonuc["tum_konumlar"].append(konum)

        # 7. En spesifik konum metnini oluştur
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

    def _ner_pipeline_getir(self):
        """NER pipeline'ını ilk ihtiyaçta yükler."""
        if self.ner_pipeline:
            return self.ner_pipeline
        if self.ner_yukleme_denendi or not Config.LOCATION_NER_ENABLED:
            return None

        self.ner_yukleme_denendi = True

        try:
            from transformers import pipeline

            self.ner_pipeline = pipeline(
                "token-classification",
                model=Config.LOCATION_NER_MODEL,
                aggregation_strategy="simple",
            )
            logger.info("Konum NER pipeline yüklendi.")
        except Exception as e:
            logger.warning(f"Konum NER pipeline yüklenemedi: {e}")
            self.ner_pipeline = None

        return self.ner_pipeline

    def _ner_ile_konum_tespit_et(self, metin: str) -> dict:
        """Regex sonuç vermediğinde NER ile konum adayı çıkarır."""
        ner_pipeline = self._ner_pipeline_getir()
        if not ner_pipeline or not metin:
            return None

        try:
            varliklar = ner_pipeline(metin)
        except Exception as e:
            logger.warning(f"NER ile konum tespiti başarısız: {e}")
            return None

        adaylar = []
        for varlik in varliklar:
            etiket = (varlik.get("entity_group") or varlik.get("entity") or "").upper()
            etiket = etiket.split("-")[-1]
            if etiket not in self.NER_ETIKETLERI:
                continue

            aday = self._ner_adayini_temizle(varlik.get("word", ""))
            if not aday:
                continue
            if not self._ner_konum_adayi_mi(aday):
                continue
            if aday not in adaylar:
                adaylar.append(aday)

        if not adaylar:
            return None

        en_iyi_aday = max(adaylar, key=self._ner_konum_puani)
        ilce = self._ilce_tespit_et(en_iyi_aday) or self._ilce_tespit_et(metin)
        mahalle = self._mahalle_tespit_et(en_iyi_aday)
        cadde_sokak = self._cadde_sokak_tespit_et(en_iyi_aday)
        bilinen_yer = self._bilinen_yer_tespit_et(en_iyi_aday)

        return {
            "ilce": ilce,
            "mahalle": mahalle,
            "cadde_sokak": cadde_sokak,
            "bilinen_yer": bilinen_yer or en_iyi_aday,
            "tum_konumlar": adaylar,
        }

    def _ner_adayini_temizle(self, metin: str) -> str:
        """NER çıktısındaki aday metni normalize eder."""
        temiz = (metin or "").replace("##", "").strip(" .,;:!?()[]{}\"'")
        temiz = re.sub(r"\s+", " ", temiz).strip()
        return temiz

    def _ner_konum_adayi_mi(self, aday: str) -> bool:
        """NER adayının konum olma ihtimalini kaba kurallarla filtreler."""
        aday_lower = aday.lower()
        if len(aday) < 3:
            return False

        if self._ilce_tespit_et(aday) or self._bilinen_yer_tespit_et(aday):
            return True

        if any(ipucu in aday_lower for ipucu in self.NER_KONUM_IPUCLARI):
            return True

        # En az iki kelimeli özel isim gruplarını yedek aday olarak kabul et.
        return len(aday.split()) >= 2

    def _ner_konum_puani(self, aday: str) -> int:
        """NER adaylarını konum özgüllüğüne göre sıralar."""
        puan = len(aday.split())
        aday_lower = aday.lower()

        if self._ilce_tespit_et(aday):
            puan += 3
        if self._bilinen_yer_tespit_et(aday):
            puan += 5
        if any(ipucu in aday_lower for ipucu in self.NER_KONUM_IPUCLARI):
            puan += 4

        return puan

    def _ilce_tespit_et(self, metin: str) -> str:
        """İlçe adını tespit eder."""
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
