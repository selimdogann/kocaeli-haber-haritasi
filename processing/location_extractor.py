"""
Kocaeli Haber Haritası - Konum Bilgisi Çıkarım Modülü

Haber metninden olayın gerçekleştiği yer bilgisini çıkarır.
Kocaeli ili sınırları içindeki mahalle, sokak, cadde gibi
konum bilgilerini tespit eder.
"""

import logging
import re
from config.settings import Config

logger = logging.getLogger(__name__)


class LocationExtractor:
    """Haber metinlerinden konum bilgisi çıkaran sınıf."""

    ILCELER = [ilce.lower() for ilce in Config.KOCAELI_DISTRICTS]

    KONUM_KALIPLARI = [
        r"(?P<ilce>[A-ZÇĞİÖŞÜa-zçğıöşü]+)\s+ilçesi(?:nin|nde|ne)?\s+(?P<mahalle>[A-ZÇĞİÖŞÜa-zçğıöşü\s]+?)\s+(?:mahallesi|mah\.)",
        r"(?P<mahalle>[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)*)\s+(?:Mahallesi|mahallesi|Mah\.|mah\.)",
        r"(?P<cadde>[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜa-zçğıöşü]+)*)\s+(?:Caddesi|caddesi|Cad\.?|cad\.?|Bulvarı|bulvarı|Blv\.?|blv\.?)",
        r"(?P<sokak>[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜa-zçğıöşü]+)*)\s+(?:Sokağı?|sokağı?|Sok\.?|sok\.?)",
        r"(?:D-?\d+|O-?\d+|TEM|E-?\d+)\s*(?:karayolu|otoyolu?|yolu)",
        r"(?P<yol>(?:Kocaeli|İstanbul|Ankara|Bursa|Yalova|Sakarya)\s*[-–]\s*(?:Kocaeli|İstanbul|Ankara|Bursa|Yalova|Sakarya))\s+(?:karayolu|otoyolu?|yolu)",
        r"(?P<semt>[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)*)\s+(?:semtinde|bölgesinde|mevkiinde|mevkisinde|civarında|yakınında|karşısında|arkasında|önünde)",
        r"(?:Kocaeli|İzmit|Gebze|Darıca|Çayırova|Dilovası|Körfez|Derince|Gölcük|Karamürsel|Başiskele|Kartepe|Kandıra)'?\s*(?:de|da|te|ta)\b",
    ]

    BILINEN_YERLER = [
        "Gebze Organize Sanayi",
        "GOSB",
        "Dilovası Organize Sanayi",
        "Arslanbey Organize Sanayi",
        "Kocaeli Üniversitesi Hastanesi",
        "Derince Eğitim ve Araştırma",
        "Gebze Fatih Devlet Hastanesi",
        "Seka Devlet Hastanesi",
        "Cumhuriyet Meydanı",
        "Seka Park",
        "Ormanya",
        "Maşukiye",
        "Kartepe Kayak Merkezi",
        "Kocaeli Stadı",
        "Kocaeli Stadyumu",
        "İzmit Kocaeli Stadı",
        "Yıldız Entegre Kocaeli Stadyumu",
        "Brunga Tesisleri",
        "Körfez Brunga Tesisleri",
        "Symbol AVM",
        "Gebze Center",
        "41 Burda AVM",
        "İzmit Körfez Geçiş Köprüsü",
        "Osmangazi Köprüsü",
        "Derince Limanı",
        "Hereke",
    ]
    BILINEN_YER_ILCE_HARITASI = {
        "Kocaeli Stadı": "İzmit",
        "Kocaeli Stadyumu": "İzmit",
        "İzmit Kocaeli Stadı": "İzmit",
        "Yıldız Entegre Kocaeli Stadyumu": "İzmit",
        "Brunga Tesisleri": "Körfez",
        "Körfez Brunga Tesisleri": "Körfez",
    }

    # Extendable special location aliases feed both known-place and sports logic.
    OZEL_KONUM_IPUCLARI = {
        "Kocaeli Stadyumu": [
            "kocaelispor",
            "kocaeli stadyumu",
            "kocaeli stadı",
            "izmit stadyumu",
            "izmit kocaeli stadı",
            "yıldız entegre kocaeli stadyumu",
        ],
        "Brunga Tesisleri": [
            "brunga tesisleri",
            "körfez brunga tesisleri",
        ],
    }
    KOCELI_STADYUMU_MAC_IPUCLARI = [
        "konuk ediyor",
        "sahasında",
        "evinde",
        "iç sahada",
        "tribün",
        "tribünden",
        "seyirci",
        "stadyum",
        "taraftar",
        "taraftarlar",
        "karşılaşma",
        "maç",
        "rakip",
        "oynanacak",
    ]
    DEPLASMAN_IPUCLARI = [
        "deplasman",
        "deplasmanda",
        "dış sahada",
        "alanyaspor - kocaelispor",
        "kocaelispor - alanyaspor",
    ]

    NER_ETIKETLERI = {"LOC", "ORG", "MISC"}
    NER_KONUM_IPUCLARI = [
        "mahallesi",
        "mah.",
        "caddesi",
        "cad.",
        "sokağı",
        "sok.",
        "bulvarı",
        "blv.",
        "park",
        "meydanı",
        "avm",
        "hastanesi",
        "devlet hastanesi",
        "limanı",
        "köprüsü",
        "organize sanayi",
        "kayak merkezi",
        "stadyumu",
        "terminali",
        "tesisleri",
    ]

    KAYNAK_SKORLARI = {
        "bilinen_yer": 70,
        "spor_mekani": 75,
        "cadde_sokak": 48,
        "mahalle": 34,
        "regex": 28,
        "ner": 20,
        "ilce": 10,
    }

    def __init__(self):
        """Konum çıkarıcıyı başlatır."""
        self.derli_kaliplar = [
            # Baş harf mantığını korumak için regex adaylarında IGNORECASE kullanılmıyor.
            re.compile(kalip, re.UNICODE)
            for kalip in self.KONUM_KALIPLARI
        ]
        self.ilce_patternleri = {
            ilce: re.compile(
                r"\b" + re.escape(ilce) + r"\b",
                re.IGNORECASE | re.UNICODE,
            )
            for ilce in Config.KOCAELI_DISTRICTS
        }
        self.ner_pipeline = None
        self.ner_yukleme_denendi = False

    def konum_cikar(self, baslik: str, icerik: str) -> dict:
        """
        Haber başlık ve içeriğinden konum bilgisi çıkarır.

        Returns:
            dict: {
                "konum_metni": str,
                "ilce": str,
                "mahalle": str,
                "cadde_sokak": str,
                "tum_konumlar": list,
                "geocoding_sorgusu": str
            }
        """
        birlesik_metin = f"{baslik} {icerik}".strip()
        sonuc = {
            "konum_metni": None,
            "ilce": None,
            "mahalle": None,
            "cadde_sokak": None,
            "tum_konumlar": [],
            "geocoding_sorgusu": None,
        }

        adaylar = self._tum_adaylari_topla(birlesik_metin)
        en_iyi_aday = self._en_iyi_adayi_sec(adaylar)

        if not en_iyi_aday:
            return sonuc

        sonuc["ilce"] = en_iyi_aday.get("ilce")
        sonuc["mahalle"] = en_iyi_aday.get("mahalle")
        sonuc["cadde_sokak"] = en_iyi_aday.get("cadde_sokak")

        tum_konumlar = []
        for aday in adaylar:
            for konum in aday.get("tum_konumlar", []):
                if konum and konum not in tum_konumlar:
                    tum_konumlar.append(konum)
        sonuc["tum_konumlar"] = tum_konumlar

        konum_metni = self._aday_konum_metni_olustur(en_iyi_aday)
        if konum_metni:
            sonuc["konum_metni"] = konum_metni
            sonuc["geocoding_sorgusu"] = konum_metni

        return sonuc

    def _tum_adaylari_topla(self, metin: str) -> list:
        """Tüm kaynaklardan gelen konum sinyallerini aday havuzunda toplar."""
        aday_haritasi = {}

        ilce = self._ilce_tespit_et(metin)
        if ilce:
            self._aday_ekle(
                aday_haritasi,
                {
                    "kaynak": "ilce",
                    "ilce": ilce,
                    "tum_konumlar": [ilce],
                },
            )

        mahalle = self._mahalle_tespit_et(metin)
        if mahalle:
            self._aday_ekle(
                aday_haritasi,
                {
                    "kaynak": "mahalle",
                    "ilce": ilce,
                    "mahalle": mahalle,
                    "tum_konumlar": [f"{mahalle} Mahallesi"],
                },
            )

        cadde_sokak = self._cadde_sokak_tespit_et(metin)
        if cadde_sokak:
            self._aday_ekle(
                aday_haritasi,
                {
                    "kaynak": "cadde_sokak",
                    "ilce": ilce,
                    "mahalle": mahalle,
                    "cadde_sokak": cadde_sokak,
                    "tum_konumlar": [cadde_sokak],
                },
            )

        bilinen_yer = self._bilinen_yer_tespit_et(metin)
        if bilinen_yer:
            self._aday_ekle(
                aday_haritasi,
                {
                    "kaynak": "bilinen_yer",
                    "ilce": self.BILINEN_YER_ILCE_HARITASI.get(bilinen_yer, ilce),
                    "bilinen_yer": bilinen_yer,
                    "tum_konumlar": [bilinen_yer],
                },
            )

        spor_mekani = self._spor_mekani_tespit_et(metin)
        if spor_mekani:
            self._aday_ekle(
                aday_haritasi,
                {
                    "kaynak": "spor_mekani",
                    "ilce": self.BILINEN_YER_ILCE_HARITASI.get(spor_mekani, ilce),
                    "bilinen_yer": spor_mekani,
                    "tum_konumlar": [spor_mekani],
                },
            )

        for aday in self._regex_adaylarini_topla(metin, ilce, mahalle, cadde_sokak):
            self._aday_ekle(aday_haritasi, aday)

        for aday in self._ner_adaylarini_topla(metin):
            self._aday_ekle(aday_haritasi, aday)

        adaylar = list(aday_haritasi.values())
        self._aday_skorlarini_dengele(adaylar)
        return adaylar

    def _aday_ekle(self, aday_haritasi: dict, aday: dict):
        """Aynı konumu temsil eden adayları tek kayıtta birleştirir."""
        anahtar = self._aday_anahtari_olustur(aday)
        aday = {
            "kaynak": aday.get("kaynak"),
            "ilce": aday.get("ilce"),
            "mahalle": aday.get("mahalle"),
            "cadde_sokak": aday.get("cadde_sokak"),
            "bilinen_yer": aday.get("bilinen_yer"),
            "tum_konumlar": list(dict.fromkeys(aday.get("tum_konumlar", []))),
        }
        if aday["ilce"] and aday["mahalle"]:
            aday["mahalle"] = self._ilce_on_ekini_temizle(aday["mahalle"], aday["ilce"])
        if aday["mahalle"] and aday["cadde_sokak"]:
            aday["cadde_sokak"] = self._mahalle_on_ekini_temizle(
                aday["cadde_sokak"], aday["mahalle"]
            )
        aday["skor"] = self._aday_skorunu_hesapla(aday)

        mevcut = aday_haritasi.get(anahtar)
        if not mevcut:
            aday_haritasi[anahtar] = aday
            return

        mevcut["tum_konumlar"] = list(
            dict.fromkeys(mevcut["tum_konumlar"] + aday["tum_konumlar"])
        )
        if aday["skor"] > mevcut["skor"]:
            mevcut.update(
                {
                    "kaynak": aday["kaynak"],
                    "ilce": aday["ilce"] or mevcut.get("ilce"),
                    "mahalle": aday["mahalle"] or mevcut.get("mahalle"),
                    "cadde_sokak": aday["cadde_sokak"] or mevcut.get("cadde_sokak"),
                    "bilinen_yer": aday["bilinen_yer"] or mevcut.get("bilinen_yer"),
                    "skor": aday["skor"],
                }
            )

    def _aday_anahtari_olustur(self, aday: dict) -> str:
        return "|".join(
            [
                aday.get("bilinen_yer") or "",
                aday.get("cadde_sokak") or "",
                aday.get("mahalle") or "",
                aday.get("ilce") or "",
            ]
        )

    def _aday_skorunu_hesapla(self, aday: dict) -> int:
        """Daha spesifik ve daha güvenilir kaynakları yukarı taşır."""
        skor = self.KAYNAK_SKORLARI.get(aday.get("kaynak"), 0)

        if aday.get("bilinen_yer"):
            skor += 28
        if aday.get("cadde_sokak"):
            skor += 18
        if aday.get("mahalle"):
            skor += 12
        if aday.get("ilce"):
            skor += 4

        if aday.get("cadde_sokak") and aday.get("mahalle"):
            skor += 12
        if aday.get("bilinen_yer") and aday.get("ilce"):
            skor += 6

        return skor

    def _aday_skorlarini_dengele(self, adaylar: list):
        """İlçe-only adayları, daha spesifik adaylar varken zayıflat."""
        if not adaylar:
            return

        daha_spesifik_var = any(
            aday.get("bilinen_yer") or aday.get("mahalle") or aday.get("cadde_sokak")
            for aday in adaylar
        )
        sabit_mekan_var = any(aday.get("bilinen_yer") for aday in adaylar)

        for aday in adaylar:
            sadece_ilce = (
                aday.get("ilce")
                and not aday.get("mahalle")
                and not aday.get("cadde_sokak")
                and not aday.get("bilinen_yer")
            )
            if sadece_ilce and daha_spesifik_var:
                aday["skor"] -= 18
            if aday.get("kaynak") == "ner" and sabit_mekan_var and not aday.get("bilinen_yer"):
                aday["skor"] -= 8

    def _en_iyi_adayi_sec(self, adaylar: list) -> dict:
        """Adaylar içinden en yüksek skorlu ve en spesifik olanı seç."""
        if not adaylar:
            return None

        return max(
            adaylar,
            key=lambda aday: (
                aday.get("skor", 0),
                bool(aday.get("bilinen_yer")),
                bool(aday.get("cadde_sokak")),
                bool(aday.get("mahalle")),
                len(aday.get("tum_konumlar", [])),
            ),
        )

    def _aday_konum_metni_olustur(self, aday: dict) -> str:
        """Seçilen adayı mevcut geocoder ile uyumlu sorguya dönüştür."""
        if not aday:
            return None

        parcalar = []
        if aday.get("cadde_sokak"):
            parcalar.append(aday["cadde_sokak"])
        if aday.get("mahalle"):
            parcalar.append(f"{aday['mahalle']} Mahallesi")
        if aday.get("bilinen_yer"):
            parcalar.append(aday["bilinen_yer"])
        if aday.get("ilce"):
            parcalar.append(aday["ilce"])

        if not parcalar:
            return None

        if parcalar[-1] != "Kocaeli":
            parcalar.append("Kocaeli")
        return ", ".join(dict.fromkeys(parcalar))

    def _regex_adaylarini_topla(
        self,
        metin: str,
        varsayilan_ilce: str,
        varsayilan_mahalle: str,
        varsayilan_cadde: str,
    ) -> list:
        """Regex eşleşmelerini aday yapısına çevir."""
        adaylar = []
        for kalip in self.derli_kaliplar:
            for eslesme in kalip.finditer(metin):
                ham_konum = eslesme.group(0).strip()
                if not ham_konum:
                    continue

                grup_verisi = {
                    anahtar: (deger.strip() if deger else None)
                    for anahtar, deger in eslesme.groupdict().items()
                }
                cadde_sokak = (
                    grup_verisi.get("cadde")
                    or grup_verisi.get("sokak")
                    or grup_verisi.get("yol")
                    or self._cadde_sokak_tespit_et(ham_konum)
                )
                mahalle = grup_verisi.get("mahalle") or self._mahalle_tespit_et(ham_konum)
                adaylar.append(
                    {
                        "kaynak": "regex",
                        "ilce": grup_verisi.get("ilce") or self._ilce_tespit_et(ham_konum) or varsayilan_ilce,
                        "mahalle": mahalle,
                        "cadde_sokak": cadde_sokak,
                        "bilinen_yer": self._bilinen_yer_tespit_et(ham_konum),
                        "tum_konumlar": [ham_konum],
                    }
                )
        return adaylar

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

    def _ner_adaylarini_topla(self, metin: str) -> list:
        """NER çıktısını fallback yerine ek aday kaynağı olarak kullan."""
        ner_pipeline = self._ner_pipeline_getir()
        if not ner_pipeline or not metin:
            return []

        try:
            varliklar = ner_pipeline(metin)
        except Exception as e:
            logger.warning(f"NER ile konum tespiti başarısız: {e}")
            return []

        adaylar = []
        gorulenler = set()
        for varlik in varliklar:
            etiket = (varlik.get("entity_group") or varlik.get("entity") or "").upper()
            etiket = etiket.split("-")[-1]
            if etiket not in self.NER_ETIKETLERI:
                continue

            aday_metin = self._ner_adayini_temizle(varlik.get("word", ""))
            if not aday_metin or aday_metin in gorulenler:
                continue
            if not self._ner_konum_adayi_mi(aday_metin):
                continue

            gorulenler.add(aday_metin)
            adaylar.append(
                {
                    "kaynak": "ner",
                    "ilce": self._ilce_tespit_et(aday_metin),
                    "mahalle": self._mahalle_tespit_et(aday_metin),
                    "cadde_sokak": self._cadde_sokak_tespit_et(aday_metin),
                    "bilinen_yer": self._bilinen_yer_tespit_et(aday_metin),
                    "tum_konumlar": [aday_metin],
                }
            )

        return adaylar

    def _ner_ile_konum_tespit_et(self, metin: str) -> dict:
        """Mevcut uyumluluk için NER içindeki en iyi adayı döndür."""
        adaylar = self._ner_adaylarini_topla(metin)
        en_iyi_aday = self._en_iyi_adayi_sec(adaylar)
        if not en_iyi_aday:
            return None
        return {
            "ilce": en_iyi_aday.get("ilce"),
            "mahalle": en_iyi_aday.get("mahalle"),
            "cadde_sokak": en_iyi_aday.get("cadde_sokak"),
            "bilinen_yer": en_iyi_aday.get("bilinen_yer"),
            "tum_konumlar": en_iyi_aday.get("tum_konumlar", []),
        }

    def _ner_adayini_temizle(self, metin: str) -> str:
        """NER çıktısındaki aday metni normalize eder."""
        temiz = (metin or "").replace("##", "").strip(" .,;:!?()[]{}\"'")
        return re.sub(r"\s+", " ", temiz).strip()

    def _ner_konum_adayi_mi(self, aday: str) -> bool:
        """NER adayının konum olma ihtimalini kaba kurallarla filtreler."""
        aday_lower = aday.lower()
        if len(aday) < 3:
            return False

        if self._ilce_tespit_et(aday) or self._bilinen_yer_tespit_et(aday):
            return True

        if any(ipucu in aday_lower for ipucu in self.NER_KONUM_IPUCLARI):
            return True

        return len(aday.split()) >= 2

    def _ilce_on_ekini_temizle(self, metin: str, ilce: str) -> str:
        """Mahalle gibi adaylarda başa yapışan ilçe adını kaldır."""
        if not metin or not ilce:
            return metin

        on_ek = f"{ilce} "
        if metin.startswith(on_ek):
            return metin[len(on_ek):].strip()
        return metin

    def _mahalle_on_ekini_temizle(self, metin: str, mahalle: str) -> str:
        """Cadde adaylarında öne yapışan mahalle bilgisini temizle."""
        if not metin or not mahalle:
            return metin

        on_ek = f"{mahalle} Mahallesi "
        if metin.startswith(on_ek):
            return metin[len(on_ek):].strip()
        return metin

    def _ilce_tespit_et(self, metin: str) -> str:
        """İlçe adını tespit eder."""
        for ilce, pattern in self.ilce_patternleri.items():
            if pattern.search(metin):
                return ilce
        return None

    def _mahalle_tespit_et(self, metin: str) -> str:
        """Mahalle adını tespit eder."""
        mahalle_kaliplari = [
            r"\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ0-9][a-zçğıöşü0-9]+){0,3})\s+(?:Mahallesi|mahallesi|Mah\.|mah\.)\b",
        ]

        for kalip in mahalle_kaliplari:
            eslesme = re.search(kalip, metin, re.UNICODE)
            if eslesme:
                mahalle = eslesme.group(1).strip()
                if len(mahalle) > 2:
                    return mahalle
        return None

    def _cadde_sokak_tespit_et(self, metin: str) -> str:
        """Cadde veya sokak adını tespit eder."""
        kaliplar = [
            r"\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ0-9][a-zçğıöşü0-9]+){0,4})\s+(?:Caddesi|caddesi|Cad\.?|cad\.?)\b",
            r"\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ0-9][a-zçğıöşü0-9]+){0,4})\s+(?:Sokağı?|sokağı?|Sok\.?|sok\.?)\b",
            r"\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ0-9][a-zçğıöşü0-9]+){0,4})\s+(?:Bulvarı|bulvarı|Blv\.?|blv\.?)\b",
        ]

        for kalip in kaliplar:
            eslesme = re.search(kalip, metin, re.UNICODE)
            if eslesme:
                return eslesme.group(0).strip()
        return None

    def _bilinen_yer_tespit_et(self, metin: str) -> str:
        """Bilinen yerleri ve alias tabanlı özel mekanları tespit eder."""
        metin_lower = metin.lower()

        for yer_adi, anahtarlar in self.OZEL_KONUM_IPUCLARI.items():
            if any(anahtar in metin_lower for anahtar in anahtarlar):
                return yer_adi

        for yer in self.BILINEN_YERLER:
            if yer.lower() in metin_lower:
                return yer

        return None

    def _spor_mekani_tespit_et(self, metin: str) -> str:
        """Spor haberlerinde mekanı ilçe yerine daha güçlü bir aday olarak üret."""
        metin_lower = metin.lower()
        if "kocaelispor" not in metin_lower:
            return None

        if any(ipucu in metin_lower for ipucu in self.DEPLASMAN_IPUCLARI):
            return None

        # Kocaelispor haberleri, açık deplasman sinyali yoksa stadyumu ilçe adının önüne geçirir.
        if any(ipucu in metin_lower for ipucu in self.KOCELI_STADYUMU_MAC_IPUCLARI):
            return "Kocaeli Stadyumu"

        return "Kocaeli Stadyumu"

    def _tum_konumlari_bul(self, metin: str) -> list:
        """Geriye dönük uyumluluk için regex ile bulunan tüm konumları döndür."""
        return [aday["tum_konumlar"][0] for aday in self._regex_adaylarini_topla(metin, None, None, None)]
