"""
Kocaeli Haber Haritası - Haber Sınıflandırma Modülü


Haber içeriklerini analiz ederek anahtar kelime tabanlı
sınıflandırma yapar. Her haber yalnızca bir türle etiketlenir.


Haber Türleri:
1. Trafik Kazası
2. Yangın
3. Elektrik Kesintisi
4. Afet ve Acil Durum
5. Hırsızlık
6. Vefat
7. Sağlık
8. Eğitim
9. Spor
10. Yerel Yönetim
11. Toplumsal Gündem
12. Ekonomi
13. Kamu Duyurusu
14. Medya ve Magazin
15. Kültürel Etkinlikler


Öncelik Sırası (birden fazla kategoriye giriyorsa):
Yangın > Trafik Kazası > Elektrik Kesintisi > Afet ve Acil Durum >
Hırsızlık > Vefat > Sağlık > Eğitim > Spor > Yerel Yönetim >
Toplumsal Gündem > Ekonomi > Kamu Duyurusu > Medya ve Magazin >
Kültürel Etkinlikler
"""


import re
import logging


logger = logging.getLogger(__name__)




class NewsClassifier:
   """Anahtar kelime tabanlı haber sınıflandırıcı."""


   TRAFIK_MIN_ESLESME = 2
   MIN_GUVEN_ESIGI = 0.5
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
       "afet_acil_durum": {
           "oncelik": 4,
           "anahtar_kelimeler": [
               "deprem", "sarsıntı", "artçı", "afad", "kandilli",
               "meteoroloji", "uyarı", "kar yağışı", "sağanak", "yıldırım",
               "fırtına", "firtina", "sel", "heyelan", "don uyarısı",
               "çığ", "cig", "sis", "buzlanma",
           ],
           "guclu_anahtar_kelimeler": [
               "deprem", "afad", "meteoroloji", "fırtına", "sel",
           ],
       },
       "hirsizlik": {
           "oncelik": 5,
           "anahtar_kelimeler": [
               "hırsızlık", "hırsız", "çalındı", "çaldı", "çalınan",
               "soygun", "soyuldu", "gasp", "gaspçı", "dolandırıcılık",
               "dolandırıcı", "kapkaç", "kapkaççı", "suçlu", "suçlular",
               "yakalandı", "gözaltı", "tutuklama", "tutuklandı",
               "polis", "jandarma", "operasyon", "baskın",
               "şüpheli", "şüpheliler", "hapis",
               "emniyet", "asayiş", "suç", "silahlı",
               "cinayet", "mühürlendi", "kaçak üretim", "denetim",
           ],
           "guclu_anahtar_kelimeler": [
               "hırsızlık", "hırsız", "soygun", "gasp", "kapkaç", "cinayet",
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
       "kulturel_etkinlik": {
           "oncelik": 15,
           "anahtar_kelimeler": [
               "etkinlik", "konser", "sergi", "tiyatro", "festival",
               "gösteri", "sahne", "sanat", "kültür", "müzik",
               "dans", "bale", "sinema", "film", "söyleşi",
               "panel", "seminer", "workshop", "atölye", "fuar",
               "kermes", "şenlik", "kutlama", "anma", "açılış",
               "ödül", "yarışma",
               "müze", "kütüphane", "gala", "performans", "iftar",
               "buluşma", "program", "vakfı", "dernek",
               "resital", "orkestra", "koro", "halk oyunları",
           ],
           "guclu_anahtar_kelimeler": [
               "konser", "sergi", "tiyatro", "festival", "etkinlik",
               "gösteri", "şenlik",
           ],
       },
       "vefat": {
           "oncelik": 6,
           "anahtar_kelimeler": [
               "vefat etti",
               "hayatını kaybetti",
               "yaşamını yitirdi",
               "son yolculuğuna uğurlandı",
               "hayata gözlerini yumdu",
               "son yolculuğuna",
               "cenaze",
               "cenazeye",
               "cenazesi",
               "öldü",
               "ölü",
               "kalp krizi",
            ],
           "guclu_anahtar_kelimeler": [
               "vefat etti",
               "hayatını kaybetti",
               "yaşamını yitirdi",
               "son yolculuğuna uğurlandı",
               "kalp krizi",
            ],
       },
       "saglik": {
           "oncelik": 7,
           "anahtar_kelimeler": [
               "sağlık", "saglik", "hastane", "doktor", "hekim",
               "hasta", "tedavi", "muayene", "ameliyat", "operasyon",
               "virüs", "virus", "enfeksiyon", "salgın", "aşı",
               "poliklinik", "acil servis", "yoğun bakım", "ambulans",
               "sağlık çalışanı", "entübe", "tıp fakültesi", "tıp bayramı",
            ],
           "guclu_anahtar_kelimeler": [
               "hastane", "ameliyat", "yoğun bakım", "aşı", "virüs",
           ],
       },
       "egitim": {
           "oncelik": 8,
           "anahtar_kelimeler": [
               "okul", "öğrenci", "ogrenci", "öğretmen", "ogretmen",
               "eğitim", "egitim", "üniversite", "universite", "sınav",
               "sinav", "ders", "akademik", "mezuniyet", "karne",
               "burs", "yurt", "kampüs", "kampus", "müdür", "mudur",
               "koü", "eğitim öğretim", "ara tatil",
            ],
           "guclu_anahtar_kelimeler": [
               "okul", "öğrenci", "öğretmen", "üniversite", "sınav",
           ],
       },
       "spor": {
           "oncelik": 9,
           "anahtar_kelimeler": [
               "spor", "maç", "mac", "futbol", "basketbol", "voleybol",
               "gol", "puan", "lig", "takım", "takim", "kulüp", "kulup",
               "taraftar", "antrenör", "antrenman", "teknik direktör",
               "transfer", "şampiyona", "turnuva", "kocaelispor",
               "galatasaray", "stadyum", "hakem", "var hakemi",
               "penaltı", "kırmızı kart", "galibiyet", "mağlup",
               "u19", "u18", "u17", "u16", "rekabet",
               "kağıtspor", "kagitspor", "yeşil-siyahlı",
               "belediyespor", "play-off", "müsabaka", "temsilcisi",
           ],
           "guclu_anahtar_kelimeler": [
               "maç", "futbol", "basketbol", "voleybol", "transfer",
               "kocaelispor", "galibiyet", "kağıtspor",
               "belediyespor", "şampiyona", "play-off",
           ],
       },
       "yerel_yonetim": {
           "oncelik": 10,
           "anahtar_kelimeler": [
               "belediye", "büyükşehir", "buyuksehir", "başkan", "baskan",
               "meclis", "encümen", "encumen", "muhtar", "valilik",
               "kaymakamlık", "kaymakamlik", "altyapı", "altyapi",
               "yol çalışması", "asfalt", "ihale", "proje", "duyuru",
               "açılış", "hizmet binası", "park", "ulaşım", "ulasim",
               "vali", "kaymakam", "dsi", "genel müdürlüğü", "vatandaş buluşması",
            ],
           "guclu_anahtar_kelimeler": [
               "belediye", "büyükşehir", "meclis", "altyapı", "ihale",
           ],
       },
       "toplumsal_gundem": {
           "oncelik": 11,
           "anahtar_kelimeler": [
               "cumhurbaşkanı", "cumhurbaskani", "erdoğan", "erdogan",
               "iftar", "sofra", "buluştu", "buluşma", "mesaj",
               "teşkilat", "teskilat", "vakfı", "vakfi", "gaziler",
               "şehit yakınları", "engelli", "cami", "imam", "vatandaş",
               "vatandas", "dertlerini dinledi", "anlamlı etkinlik",
           ],
           "guclu_anahtar_kelimeler": [
               "cumhurbaşkanı", "iftar", "buluştu", "imam", "vatandaş",
           ],
       },
       "ekonomi": {
           "oncelik": 12,
           "anahtar_kelimeler": [
               "ekonomi", "zam", "fiyat", "indirim", "maaş",
               "maas", "emekli", "ikramiye", "ödeme", "odeme", "işçi alımı",
               "isci alimi", "iş ilanı", "istihdam", "fabrika", "sanayi",
               "üretim", "uretim", "ihracat", "yatırım", "yatirim", "işkur",
               "işçi alacak", "personel alımı", "personel alacak",
               "işe alım", "alım yapacak",
           ],
           "guclu_anahtar_kelimeler": [
               "emekli", "ikramiye", "işçi alımı", "istihdam", "işkur",
               "işçi alacak", "personel alımı",
           ],
       },
       "kamu_duyurusu": {
           "oncelik": 13,
           "anahtar_kelimeler": [
               "nöbetçi eczane", "nobetci eczane", "eczane", "nöbetçi noter",
               "nobetci noter", "noter", "duyuru", "liste", "adresleri",
               "yayın akışı", "yayin akisi",
           ],
           "guclu_anahtar_kelimeler": [
               "nöbetçi eczane", "nöbetçi noter", "yayın akışı",
           ],
       },
       "medya_magazin": {
           "oncelik": 14,
           "anahtar_kelimeler": [
               "dizi", "televizyon", "tv", "atv", "yayın", "canlı yayında",
               "kitap", "baskısı", "sanatçı", "oyuncu", "program",
               "izleyici", "magazin", "ünlü", "unlu",
           ],
           "guclu_anahtar_kelimeler": [
               "dizi", "yayın akışı", "canlı yayında", "kitap",
           ],
       },
       "diger": {
           "oncelik": 999,
           "anahtar_kelimeler": [],
           "guclu_anahtar_kelimeler": [],
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

       vefat_guclu_var = any(
           kalip.search(birlesik_metin)
           for kalip in self.derli_kaliplar["vefat"]["guclu"]
       )
       if vefat_guclu_var:
           # Vefat haberlerinde meslek/bağlam kelimeleri sinyali bozmasın.
           skorlar["saglik"] = 0
           skorlar["egitim"] = 0
           skorlar["ekonomi"] = 0
           skorlar["spor"] = 0


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
           secilen_tur = "diger"


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
           list: Her haberin sınıflandırma sonucuu
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
