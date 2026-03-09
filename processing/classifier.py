"""
Kocaeli Haber Haritası - Haber Sınıflandırma Modülü

Haber içeriklerini analiz ederek anahtar kelime tabanlı
sınıflandırma yapar. Her haber yalnızca bir türle etiketlenir.

Haber Türleri:
1. Trafik Kazası
2. Yangın
3. Elektrik Kesintisi
4. Hırsızlık
5. Kültürel Etkinlikler

Öncelik Sırası (birden fazla kategoriye giriyorsa):
Yangın > Trafik Kazası > Hırsızlık > Elektrik Kesintisi > Kültürel Etkinlikler
"""

import re
import logging

logger = logging.getLogger(__name__)


class NewsClassifier:
    """Anahtar kelime tabanlı haber sınıflandırıcı."""

    # Haber türleri ve anahtar kelimeleri
    # Her kategorinin bir ağırlık/öncelik değeri vardır (düşük = yüksek öncelik)
    SINIFLANDIRMA_KURALLARI = {
        "yangin": {
            "oncelik": 1,
            "anahtar_kelimeler": [
                "yangın", "yangin", "yandı", "yanıyor", "tutuştu",
                "alevler", "alev aldı", "alev", "itfaiye", "söndürme",
                "söndürüldü", "dumanlı", "duman", "küle döndü", "kül oldu",
                "yangın çıktı", "kundaklama", "kundak", "yanarak",
                "yangın ihbarı", "yangında", "yanmış",
            ],
            "guclu_anahtar_kelimeler": [
                "yangın", "itfaiye", "alev aldı", "söndürme",
            ],
        },
        "trafik_kazasi": {
            "oncelik": 2,
            "anahtar_kelimeler": [
                "kaza", "trafik kazası", "trafik", "çarpışma", "çarpıştı",
                "takla attı", "takla", "devrildi", "savruldu", "kazada",
                "kazası", "kaza yapan", "yaralı", "yaralandı", "ölümlü",
                "can verdi", "hayatını kaybetti", "feci kaza", "zincirleme",
                "otomobil", "araç", "motosiklet", "kamyon", "tır",
                "minibüs", "otobüs", "sürücü", "yaya", "çarpma",
                "kaza anı", "maddi hasar", "ambulans",
            ],
            "guclu_anahtar_kelimeler": [
                "trafik kazası", "kaza", "çarpışma", "takla attı",
                "feci kaza", "zincirleme",
            ],
        },
        "hirsizlik": {
            "oncelik": 3,
            "anahtar_kelimeler": [
                "hırsızlık", "hırsız", "çalındı", "çaldı", "çalınan",
                "soygun", "soyuldu", "gasp", "gaspçı", "dolandırıcılık",
                "dolandırıcı", "kapkaç", "kapkaççı", "suçlu", "suçlular",
                "yakalandı", "gözaltı", "tutuklama", "tutuklandı",
                "polis", "jandarma", "operasyon", "baskın",
                "şüpheli", "şüpheliler", "hapis", "ceza",
                "emniyet", "asayiş", "suç", "silahlı",
            ],
            "guclu_anahtar_kelimeler": [
                "hırsızlık", "hırsız", "soygun", "gasp", "kapkaç",
            ],
        },
        "elektrik_kesintisi": {
            "oncelik": 4,
            "anahtar_kelimeler": [
                "elektrik kesintisi", "elektrik kesinti", "elektrikler kesildi",
                "elektrik kesildi", "enerji kesintisi", "elektriksiz",
                "karanlıkta kaldı", "karanlık", "trafo", "trafo arızası",
                "enerji arızası", "elektrik arızası", "kesinti programı",
                "planlı kesinti", "elektrik verilecek", "elektrikler geldi",
                "sedaş", "başkent edaş", "enerji dağıtım",
                "voltaj", "akım", "jeneratör",
            ],
            "guclu_anahtar_kelimeler": [
                "elektrik kesintisi", "elektrikler kesildi",
                "enerji kesintisi", "planlı kesinti", "sedaş",
            ],
        },
        "kulturel_etkinlik": {
            "oncelik": 5,
            "anahtar_kelimeler": [
                "etkinlik", "konser", "sergi", "tiyatro", "festival",
                "gösteri", "sahne", "sanat", "kültür", "müzik",
                "dans", "bale", "sinema", "film", "söyleşi",
                "panel", "seminer", "workshop", "atölye", "fuar",
                "kermes", "şenlik", "kutlama", "anma", "açılış",
                "ödül", "yarışma", "turnuva", "spor", "maç",
                "müze", "kütüphane", "gala", "performans",
                "resital", "orkestra", "koro", "halk oyunları",
            ],
            "guclu_anahtar_kelimeler": [
                "konser", "sergi", "tiyatro", "festival", "etkinlik",
                "gösteri", "şenlik",
            ],
        },
    }

    def __init__(self):
        """Sınıflandırıcıyı başlatır ve regex kalıplarını derler."""
        self.derli_kaliplar = {}
        for tur, kurallar in self.SINIFLANDIRMA_KURALLARI.items():
            self.derli_kaliplar[tur] = {
                "anahtar": [
                    re.compile(r"\b" + re.escape(kelime) + r"\b", re.IGNORECASE | re.UNICODE)
                    for kelime in kurallar["anahtar_kelimeler"]
                ],
                "guclu": [
                    re.compile(r"\b" + re.escape(kelime) + r"\b", re.IGNORECASE | re.UNICODE)
                    for kelime in kurallar["guclu_anahtar_kelimeler"]
                ],
                "oncelik": kurallar["oncelik"],
            }

    def siniflandir(self, baslik: str, icerik: str) -> dict:
        """
        Haber başlık ve içeriğini analiz ederek türünü belirler.

        Skor hesaplama:
        - Normal anahtar kelime eşleşmesi: +1 puan
        - Güçlü anahtar kelime eşleşmesi: +3 puan
        - Başlıkta eşleşme: x2 çarpan

        Args:
            baslik: Haber başlığı
            icerik: Haber içeriği

        Returns:
            dict: {
                "haber_turu": str,    # Belirlenen haber türü
                "guven_skoru": float, # Güven skoru (0-1)
                "tum_skorlar": dict   # Tüm kategorilerin skorları
            }
        """
        if not baslik and not icerik:
            return {
                "haber_turu": None,
                "guven_skoru": 0.0,
                "tum_skorlar": {},
            }

        birlesik_metin = f"{baslik} {icerik}".lower()
        baslik_lower = (baslik or "").lower()

        skorlar = {}

        for tur, kaliplar in self.derli_kaliplar.items():
            skor = 0

            # Normal anahtar kelime eşleşmeleri
            for kalip in kaliplar["anahtar"]:
                icerik_eslesmeler = len(kalip.findall(birlesik_metin))
                baslik_eslesmeler = len(kalip.findall(baslik_lower))

                skor += icerik_eslesmeler
                skor += baslik_eslesmeler * 2  # Başlıkta bulunma bonus

            # Güçlü anahtar kelime eşleşmeleri
            for kalip in kaliplar["guclu"]:
                icerik_eslesmeler = len(kalip.findall(birlesik_metin))
                baslik_eslesmeler = len(kalip.findall(baslik_lower))

                skor += icerik_eslesmeler * 3
                skor += baslik_eslesmeler * 5  # Başlıkta güçlü kelime büyük bonus

            skorlar[tur] = skor

        # En yüksek skorlu türü bul
        if not skorlar or max(skorlar.values()) == 0:
            return {
                "haber_turu": None,
                "guven_skoru": 0.0,
                "tum_skorlar": skorlar,
            }

        # Eşit skorlarda öncelik sırasına göre seç
        max_skor = max(skorlar.values())
        en_yuksek_turler = [
            tur for tur, skor in skorlar.items() if skor == max_skor
        ]

        if len(en_yuksek_turler) > 1:
            # Öncelik sırasına göre seç (düşük öncelik = yüksek değer)
            secilen_tur = min(
                en_yuksek_turler,
                key=lambda t: self.derli_kaliplar[t]["oncelik"],
            )
        else:
            secilen_tur = en_yuksek_turler[0]

        # Güven skoru hesapla (0-1 arası normalize)
        toplam_skor = sum(skorlar.values())
        guven_skoru = skorlar[secilen_tur] / toplam_skor if toplam_skor > 0 else 0.0

        return {
            "haber_turu": secilen_tur,
            "guven_skoru": round(guven_skoru, 4),
            "tum_skorlar": skorlar,
        }

    def toplu_siniflandir(self, haberler: list) -> list:
        """
        Birden fazla haberi toplu olarak sınıflandırır.

        Args:
            haberler: [{baslik, icerik}, ...] formatında haber listesi

        Returns:
            list: Her haberin sınıflandırma sonucu
        """
        sonuclar = []
        for haber in haberler:
            sonuc = self.siniflandir(
                haber.get("baslik", ""),
                haber.get("icerik", ""),
            )
            sonuclar.append(sonuc)

        logger.info(f"{len(haberler)} haber sınıflandırıldı.")
        return sonuclar
