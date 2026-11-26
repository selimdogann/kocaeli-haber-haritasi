"""
Kocaeli Haber Haritası - Haber Sınıflandırma Modülü

Haber başlığı ve içeriğini anahtar kelimelerle analiz eder; her habere en fazla
bir tür atar. Hiçbir türe uymayan haber None döner ve pipeline'da atlanır.

Haber Türleri (6 tür):
1. Trafik Kazası
2. Yangın
3. Elektrik Kesintisi
4. Asayiş (cinayet, yaralama, saldırı, taciz, gözaltı/operasyon)
5. Hırsızlık (hırsızlık, gasp, soygun, dolandırıcılık)
6. Kültürel Etkinlikler

Nasıl karar verilir:
1. "Kapı" kuralı: Bir tür ancak GÜÇLÜ kelimelerinden biri haberin başlığında
   veya ilk paragrafında (lead) geçiyorsa aday olur (kültürel: sadece başlık). Böylece haberin konusu
   olmayan, metnin derinlerinde geçen bir kelime ("etkinlikleri", "hırsızları")
   haberi yanlış türe sokamaz.
2. Skor: Aday türler için başlık + tüm metin üzerinden puan toplanır
   (zayıf kelime +1, güçlü kelime +6, başlıkta eşleşme ek puan).
3. Başlık önceliği: Güçlü kelimesi BAŞLIKTA geçen bir aday tür varsa seçim
   sadece bu türler arasında yapılır. Başlık haberin konusunu söyler; metinde
   yan bilgi olarak geçen kelime ("kavga ihbarına giden polis") onu ezemez.
4. En yüksek skorlu tür seçilir; eşitlikte öncelik sırası belirler:
   Trafik Kazası > Yangın > Elektrik Kesintisi > Asayiş > Hırsızlık > Kültürel
"""

import re
import logging

logger = logging.getLogger(__name__)


def tr_kucuk_harf(metin: str) -> str:
    """
    Türkçe kurallarına uygun küçük harfe çevirme.

    Python'un str.lower() fonksiyonu "İ" harfini "i̇" (i + birleşik nokta)
    yapar, "I" harfini de "i" yapar. İkisi de Türkçe için yanlıştır ve
    "İTFAİYE" gibi büyük harfli başlıkların eşleşmemesine yol açar.
    """
    if not metin:
        return ""
    return metin.replace("İ", "i").replace("I", "ı").lower()


# Kısa kelimeler (ve yanlış eşleşmeye açık olanlar) sadece bu Türkçe çekim
# ekleriyle eşleşir. Örn: "kaza" → kazası, kazada, kazaya ✓ ama kazandı ✗;
# "tır" → tırın ✓ ama tırmandı ✗; "sergi" → sergisi ✓ ama sergiledi ✗.
_KISA_EK = (
    r"(?:"
    r"s[ıiuü]nd[ae]|s[ıiuü]n[ıiuü]n|s[ıiuü]n[ae]|s[ıiuü]|"
    r"n[ıiuü]n|[ıiuü]n|"
    r"[dt][ae]n|[dt][ae]|"
    r"l[ae]r[ıiuü]?n?[ae]?|"
    r"y?l[ae]|[ıiuü]yl[ae]|"
    r"y[ae]|y[ıiuü]|[ıiuü]|[ae]"
    r")?"
)
_KISA_UZUNLUK = 5


class NewsClassifier:
    """Anahtar kelime tabanlı haber sınıflandırıcı."""

    LEAD_KARAKTER = 400       # İlk paragraf sayılacak içerik uzunluğu
    MIN_GUVEN_ESIGI = 0.3     # Aday türler arasındaki pay

    # Trafik kazası için ek şart: hem bir kaza ifadesi hem bir araç geçmeli
    TRAFIK_ARAC_KELIMELERI = [
        "otomobil", "motosiklet", "kamyon", "kamyonet", "tır", "traktör",
        "traktor", "patpat", "tarım aracı", "minibüs", "otobüs", "araç",
        "sürücü", "tramvay", "bisiklet", "servis aracı", "hafif ticari",
        "pikap", "cip", "taksi", "arac",  # arac: aracı, araca (ç→c yumuşaması)
    ]

    SINIFLANDIRMA_KURALLARI = {
        "trafik_kazasi": {
            "oncelik": 1,
            "guclu_anahtar_kelimeler": [
                "trafik kazası", "kaza", "feci kaza", "zincirleme kaza",
                "çarpıştı", "çarpışma", "takla attı", "devrildi",
                "yoldan çıktı", "şarampole", "refüje çıktı", "yayaya çarptı",
                "kafa kafaya", "çarptı",
            ],
            # "Elektrik çarptı", "yıldırım çarptı" trafik kazası değildir
            "haric_ifadeler": [
                "elektrik çarp", "elektrik akımına kapıl", "yıldırım çarp", "akım çarp",
            ],
            "anahtar_kelimeler": [
                "savruldu", "yaralandı", "ağır yaralı",
                "hayatını kaybetti", "ambulans", "olay yerinde",
                "altında kaldı",
            ],
        },
        "yangin": {
            "oncelik": 2,
            "guclu_anahtar_kelimeler": [
                "yangın", "yangin", "alev aldı", "alevlere teslim",
                "küle döndü", "kül oldu", "kundakla", "tutuştu", "yanarak",
            ],
            # Bu ifadeler bir yangın OLAYI anlatmaz (ihale, ekipman, tatbikat)
            "haric_ifadeler": [
                "yangın söndürme tank", "yangın söndürme arac", "yangın söndürme cihaz",
                "yangın tüp", "yangın merdiven", "yangın tatbikat", "yangın güvenliği",
                "yangın alarm", "yangın dolab",
            ],
            "anahtar_kelimeler": [
                "itfaiye", "söndür", "duman", "alev", "yandı", "yanmış",
                "dumandan etkilen",
            ],
        },
        "elektrik_kesintisi": {
            "oncelik": 3,
            "guclu_anahtar_kelimeler": [
                "elektrik kesintisi", "elektrik kesinti", "elektrikler kesil",
                "elektrik kesil", "enerji kesintisi", "planlı kesinti",
                "elektriksiz kal", "elektrik verilemeyecek",
                "elektrik arızası", "elektrikler gitti",
            ],
            "anahtar_kelimeler": [
                "sedaş", "trafo", "kesinti", "enerji dağıtım", "arıza",
                "elektrik verilecek", "elektrikler geldi",
            ],
        },
        "asayis": {
            "oncelik": 4,
            "guclu_anahtar_kelimeler": [
                "cinayet", "öldürdü", "öldürüldü", "öldüren", "öldürme",
                "bıçakla", "bıçaklı", "bıçaklan", "silahlı saldırı",
                "silahla", "ateş açtı", "ateş açıldı", "kurşunlan",
                "darp", "darbedil", "dövdü", "dövül", "kavga",
                "yaraladı", "saldırıya uğra", "saldırgan",
                "ceset", "cesedi", "cesedin", "cansız beden",
                "taciz", "istismar", "tecavüz",
                "gözaltına alındı", "gözaltı", "tutuklandı", "tutuklanarak",
                "yasa dışı bahis", "uyuşturucu", "rehin", "kaçırıldı",
                "şantaj", "tacizci",
            ],
            # "Cinayet Büro" bir birim adı; "kadın cinayetleri" (çoğul) genelde
            # 25 Kasım açıklaması / istatistik haberinde geçer, tek bir olayı anlatmaz
            "haric_ifadeler": [
                "cinayet büro", "kadın cinayetleri",
            ],
            "anahtar_kelimeler": [
                "yaralandı", "yaralı", "hayatını kaybetti", "polis",
                "jandarma", "şüpheli", "adliye", "mahkeme", "savcılık",
                "emniyet", "operasyon", "suç",
            ],
        },
        "hirsizlik": {
            "oncelik": 5,
            "guclu_anahtar_kelimeler": [
                "hırsız", "hirsiz", "çalındı", "çalınan", "soygun", "soyuldu",
                "gasp", "gaspçı", "kapkaç", "dolandırıcı", "dolandırıl",
                "dolandırdı", "yankesici", "çaldılar",
            ],
            "anahtar_kelimeler": [
                "çaldı", "ziynet", "kasadan", "eve girdi", "iş yerine girdi",
                "dükkana girdi", "suçüstü", "şüpheli",
            ],
        },
        "kulturel_etkinlik": {
            "oncelik": 6,
            # "etkinlik" kelimesi haberlerde çok yan anlamda geçiyor
            # ("Öğretmenler Günü etkinlikleri kapsamında..."). Bu yüzden
            # kültürel tür için güçlü kelime BAŞLIKTA olmalı.
            "kapi": "baslik",
            "guclu_anahtar_kelimeler": [
                "konser", "sergi", "sergisi", "tiyatro", "festival", "şenlik",
                "etkinli",  # etkinlik, etkinliği, etkinliğinde (k→ğ yumuşaması)
                "söyleşi", "dinleti", "resital", "film gösterimi",
                "sahnelen", "opera", "bale", "halk oyunları", "imza günü",
                "kitap fuarı", "kermes", "fotoğraf sergisi", "müzikal",
            ],
            "anahtar_kelimeler": [
                "sanat", "kültürel", "müzik", "sahne", "sinema", "müze",
                "seminer", "panel", "atölye", "orkestra", "koro", "gala",
                "dans", "şiir", "edebiyat", "sanatçı", "seyirci", "izleyici",
            ],
        },
    }

    @staticmethod
    def _kalip_derle(kelime: str):
        """
        Anahtar kelimeyi Türkçe ek almış halleriyle eşleşen regex'e çevirir.

        Uzun kelimeler her eki alabilir (yangın → yangında, yangınla).
        Kısa kelimeler sadece _KISA_EK listesindeki çekim ekleriyle eşleşir.
        """
        govde = re.escape(tr_kucuk_harf(kelime))
        kisa = len(kelime) <= _KISA_UZUNLUK and " " not in kelime
        ek = _KISA_EK + r"(?!\w)" if kisa else r"\w*"
        return re.compile(r"(?<!\w)" + govde + ek, re.UNICODE)

    def __init__(self):
        """Sınıflandırıcıyı başlatır ve regex kalıplarını derler."""
        self.derli_kaliplar = {}
        for tur, kurallar in self.SINIFLANDIRMA_KURALLARI.items():
            self.derli_kaliplar[tur] = {
                "anahtar": [self._kalip_derle(k) for k in kurallar["anahtar_kelimeler"]],
                "guclu": [self._kalip_derle(k) for k in kurallar["guclu_anahtar_kelimeler"]],
                "oncelik": kurallar["oncelik"],
                "kapi": kurallar.get("kapi", "lead"),
                "haric": [self._kalip_derle(k) for k in kurallar.get("haric_ifadeler", [])],
            }
        self.arac_kaliplari = [self._kalip_derle(k) for k in self.TRAFIK_ARAC_KELIMELERI]

    @staticmethod
    def _say(kaliplar, metin: str) -> int:
        return sum(len(k.findall(metin)) for k in kaliplar)

    def eslesen_kelimeler(self, tur: str, baslik: str, icerik: str) -> list:
        """Hata ayıklama için: bir türde eşleşen kelimeleri döndürür."""
        metin = tr_kucuk_harf(f"{baslik} {icerik}")
        kaliplar = self.derli_kaliplar[tur]
        return sorted({m.group(0) for k in kaliplar["guclu"] + kaliplar["anahtar"] for m in k.finditer(metin)})

    def siniflandir(self, baslik: str, icerik: str) -> dict:
        """
        Haber başlık ve içeriğini analiz ederek türünü belirler.

        Returns:
            dict: {
                "haber_turu": str | None,  # Belirlenen tür (uymazsa None)
                "guven_skoru": float,      # Aday türler içindeki pay (0-1)
                "tum_skorlar": dict        # Tüm türlerin skorları
            }
        """
        if not baslik and not icerik:
            return {"haber_turu": None, "guven_skoru": 0.0, "tum_skorlar": {}}

        baslik_k = tr_kucuk_harf(baslik or "")
        icerik_k = tr_kucuk_harf(icerik or "")
        lead = f"{baslik_k} {icerik_k[: self.LEAD_KARAKTER]}"
        tum_metin = f"{baslik_k} {icerik_k}"

        skorlar = {}
        baslikta_guclu = set()   # güçlü kelimesi başlıkta geçen türler
        for tur, kaliplar in self.derli_kaliplar.items():
            # Hariç ifadeler bu tür için metinden çıkarılır
            # ("yangın söndürme tankeri" → yangın olayı sayılmaz)
            t_baslik, t_lead, t_tum = baslik_k, lead, tum_metin
            for haric in kaliplar["haric"]:
                t_baslik = haric.sub(" ", t_baslik)
                t_lead = haric.sub(" ", t_lead)
                t_tum = haric.sub(" ", t_tum)

            # Kapı: güçlü kelime başlıkta veya ilk paragrafta olmalı
            kapi_metni = t_baslik if kaliplar["kapi"] == "baslik" else t_lead
            if self._say(kaliplar["guclu"], kapi_metni) == 0:
                skorlar[tur] = 0
                continue

            if self._say(kaliplar["guclu"], t_baslik) > 0:
                baslikta_guclu.add(tur)

            skor = 0
            skor += self._say(kaliplar["anahtar"], t_tum)
            skor += self._say(kaliplar["anahtar"], t_baslik) * 4
            skor += self._say(kaliplar["guclu"], t_tum) * 6
            skor += self._say(kaliplar["guclu"], t_baslik) * 10
            skorlar[tur] = skor

        # Trafik kazası: metinde bir araç da geçmeli
        if skorlar.get("trafik_kazasi") and self._say(self.arac_kaliplari, tum_metin) == 0:
            skorlar["trafik_kazasi"] = 0

        max_skor = max(skorlar.values()) if skorlar else 0
        if max_skor == 0:
            return {"haber_turu": None, "guven_skoru": 0.0, "tum_skorlar": skorlar}

        # Başlık önceliği: başlıkta güçlü kelimesi olan aday varsa onlar yarışır
        yarisanlar = {t: s for t, s in skorlar.items() if s > 0 and t in baslikta_guclu} or skorlar
        max_skor = max(yarisanlar.values())
        en_yuksekler = [t for t, s in yarisanlar.items() if s == max_skor]
        secilen = min(en_yuksekler, key=lambda t: self.derli_kaliplar[t]["oncelik"])

        guven = skorlar[secilen] / sum(skorlar.values())
        if guven < self.MIN_GUVEN_ESIGI:
            secilen = None

        return {
            "haber_turu": secilen,
            "guven_skoru": round(guven, 4),
            "tum_skorlar": skorlar,
        }

    def toplu_siniflandir(self, haberler: list) -> list:
        """Birden fazla haberi toplu olarak sınıflandırır."""
        sonuclar = [
            self.siniflandir(h.get("baslik", ""), h.get("icerik", ""))
            for h in haberler
        ]
        logger.info(f"{len(haberler)} haber sınıflandırıldı.")
        return sonuclar
