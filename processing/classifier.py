"""
Kocaeli Haber Haritası - Haber Sınıflandırma Modülü


Haber içeriklerini analiz ederek anahtar kelime tabanlı
sınıflandırma yapar. Her haber yalnızca bir türle etiketlenir.


Haber Türleri (6 tür):
1. Trafik Kazası
2. Yangın
3. Elektrik Kesintisi
4. Asayiş (Cinayet, Yaralama, Saldırı)
5. Hırsızlık
6. Kültürel Etkinlikler


Öncelik Sırası (birden fazla kategoriye giriyorsa):
Trafik Kazası > Yangın > Asayiş > Elektrik Kesintisi > Hırsızlık > Kültürel Etkinlikler
"""


import re
import logging


logger = logging.getLogger(__name__)




class NewsClassifier:
   """Anahtar kelime tabanlı haber sınıflandırıcı."""


   TRAFIK_MIN_ESLESME = 2
   MIN_GUVEN_ESIGI = 0.3
   TRAFIK_KAZA_KELIMELERI = [
       "kaza",
       "trafik kazası",
       "çarpışma",
       "çarpıştı",
       "takla attı",
       "devrildi",
       "zincirleme",
       "yoldan çıktı",
       "altında kaldı",
       "altında kalan",
   ]
   TRAFIK_ARAC_KELIMELERI = [
       "otomobil",
       "motosiklet",
       "kamyon",
       "kamyonet",
       "tır",
       "traktör",
       "traktor",
       "patpat",
       "tarım aracı",
       "çöp kamyonu",
       "minibüs",
       "otobüs",
       "araç",
       "sürücü",
   ]


   # Haber türleri ve anahtar kelimeleri (PDF zorunlu 5 tür)
   # Her kategorinin bir ağırlık/öncelik değeri vardır (düşük = yüksek öncelik)
   SINIFLANDIRMA_KURALLARI = {
       "trafik_kazasi": {
           "oncelik": 1,
           "anahtar_kelimeler": [
               "trafik kazası",
               "feci kaza",
               "zincirleme",
               "çarpışma",
               "çarpıştı",
               "takla attı",
               "devrildi",
               "yoldan çıktı",
               "savruldu",
               "otomobil",
               "motosiklet",
               "kamyon",
               "kamyonet",
               "tır",
               "traktör",
               "traktor",
               "patpat",
               "tarım aracı",
               "çöp kamyonu",
               "minibüs",
               "otobüs",
               "sürücü",
               "araç",
               "yaya çarpması",
               "altında kaldı",
               "altında kalan",
            ],
           "guclu_anahtar_kelimeler": [
               "trafik kazası", "çarpışma", "takla attı",
               "feci kaza", "zincirleme", "yoldan çıktı", "altında kaldı",
               "altında kalan",
            ],
        },
       "yangin": {
           "oncelik": 2,
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
       "elektrik_kesintisi": {
           "oncelik": 3,
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
       "asayis": {
           "oncelik": 3.5,
           "anahtar_kelimeler": [
               "cinayet", "öldürme", "öldürdü", "öldürüldü", "öldürmüş",
               "bıçaklama", "bıçakladı", "bıçaklandı", "bıçaklı saldırı",
               "bıçak darbesi", "bıçakla yaraladı",
               "silahlı saldırı", "silahla vurdu", "silahla yaraladı",
               "ateş açtı", "ateş açıldı", "silahlı çatışma",
               "yaralama", "yaraladı", "yaralandı", "yaralı",
               "darp", "darp etti", "dövdü", "dövüldü", "dayak",
               "kavga", "kavgada", "kavgası",
               "saldırı", "saldırdı", "saldırıda",
               "infaz", "pusu", "pusu kurdu",
               "ceset", "cansız beden", "cansız bedeni",
               "hayatını kaybetti", "hayatını kaybeden",
               "can verdi", "olay yerinde öldü",
               "tutuklandı", "gözaltına alındı", "gözaltı",
               "cinayetle", "cinayette",
           ],
           "guclu_anahtar_kelimeler": [
               "cinayet", "öldürdü", "öldürüldü", "bıçakladı",
               "bıçaklandı", "silahlı saldırı", "ateş açtı",
               "bıçaklı saldırı", "pusu",
           ],
       },
       "hirsizlik": {
           "oncelik": 4,
           "anahtar_kelimeler": [
               "hırsızlık", "hırsız", "çalındı", "çaldı", "çalınan",
               "soygun", "soyuldu", "gasp", "gaspçı", "dolandırıcılık",
               "dolandırıcı", "kapkaç", "kapkaççı",
               "kaçak üretim", "uyuşturucu",
               "hırsızlık şüphelisi", "hırsızlık olayı",
               "eve girdi", "iş yerine girdi", "dükkana girdi",
           ],
           "guclu_anahtar_kelimeler": [
               "hırsızlık", "hırsız", "soygun", "gasp", "kapkaç",
               "dolandırıcılık", "uyuşturucu",
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
               "ödül", "yarışma",
               "müze", "kütüphane", "gala", "performans",
               "buluşma", "program",
               "resital", "orkestra", "koro", "halk oyunları",
           ],
           "guclu_anahtar_kelimeler": [
               "konser", "sergi", "tiyatro", "festival", "etkinlik",
               "gösteri", "şenlik",
           ],
       },
   }


   @staticmethod
   def _kalip_derle(kelime: str):
       """Anahtar kelimenin Turkce ek almis varyasyonlarini da eslestirir."""
       return re.compile(
           r"\b" + re.escape(kelime) + r"\w*",
           re.IGNORECASE | re.UNICODE,
       )


   def __init__(self):
       """Sınıflandırıcıyı başlatır ve regex kalıplarını derler."""
       self.derli_kaliplar = {}
       for tur, kurallar in self.SINIFLANDIRMA_KURALLARI.items():
           self.derli_kaliplar[tur] = {
               "anahtar": [
                   self._kalip_derle(kelime)
                   for kelime in kurallar["anahtar_kelimeler"]
               ],
               "guclu": [
                   self._kalip_derle(kelime)
                   for kelime in kurallar["guclu_anahtar_kelimeler"]
               ],
               "oncelik": kurallar["oncelik"],
           }


   def siniflandir(self, baslik: str, icerik: str) -> dict:
       """
       Haber başlık ve içeriğini analiz ederek türünü belirler.


       Skor hesaplama:
       - Normal anahtar kelime eşleşmesi: +1 puan
       - Güçlü anahtar kelime eşleşmesi: +6 puan
       - Başlıkta eşleşme: x5 çarpan


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
       trafik_eslesme_sayisi = 0


       for tur, kaliplar in self.derli_kaliplar.items():
           skor = 0


           # Normal anahtar kelime eşleşmeleri
           for kalip in kaliplar["anahtar"]:
               icerik_eslesmeler = len(kalip.findall(birlesik_metin))
               baslik_eslesmeler = len(kalip.findall(baslik_lower))


               skor += icerik_eslesmeler
               # Başlık eşleşmeleri daha yüksek ağırlık taşır.
               skor += baslik_eslesmeler * 5
               if tur == "trafik_kazasi":
                   trafik_eslesme_sayisi += icerik_eslesmeler + baslik_eslesmeler


           # Güçlü anahtar kelime eşleşmeleri
           for kalip in kaliplar["guclu"]:
               icerik_eslesmeler = len(kalip.findall(birlesik_metin))
               baslik_eslesmeler = len(kalip.findall(baslik_lower))


               # Güçlü anahtar kelimeler sınıflandırmayı daha net belirler.
               skor += icerik_eslesmeler * 6
               skor += baslik_eslesmeler * 10
               if tur == "trafik_kazasi":
                   trafik_eslesme_sayisi += icerik_eslesmeler + baslik_eslesmeler


           skorlar[tur] = skor


       if trafik_eslesme_sayisi < self.TRAFIK_MIN_ESLESME:
           skorlar["trafik_kazasi"] = 0

       kaza_var = any(
           kelime in birlesik_metin for kelime in self.TRAFIK_KAZA_KELIMELERI
       )
       arac_var = any(
           kelime in birlesik_metin for kelime in self.TRAFIK_ARAC_KELIMELERI
       )

       if not (kaza_var and arac_var):
           skorlar["trafik_kazasi"] = 0


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


       if guven_skoru < self.MIN_GUVEN_ESIGI:
           secilen_tur = None


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
