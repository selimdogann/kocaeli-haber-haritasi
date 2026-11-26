"""
Sınıflandırıcı testleri.

Buradaki cümleler gerçek haberlerden kopyalanmadı; her türün tipik kalıbını ve
geçmişte yanlış sınıflandırmaya yol açan tuzakları temsil etmek için yazıldı.
"""

import pytest

from processing.classifier import NewsClassifier, tr_kucuk_harf


@pytest.fixture(scope="module")
def siniflandirici():
    return NewsClassifier()


def tur(s, baslik, icerik=""):
    return s.siniflandir(baslik, icerik)["haber_turu"]


# ---------------------------------------------------------------- doğru türler
@pytest.mark.parametrize("baslik, icerik, beklenen", [
    # Trafik kazası
    ("Gebze'de iki otomobil çarpıştı: 3 yaralı",
     "D-100 karayolunda iki otomobilin çarpışması sonucu 3 kişi yaralandı.", "trafik_kazasi"),
    ("Kartepe'de kamyon devrildi",
     "Sürücüsünün direksiyon hakimiyetini kaybettiği kamyon yol kenarına devrildi.", "trafik_kazasi"),
    ("Motosiklet ile hafif ticari araç kafa kafaya çarpıştı",
     "Kazada motosiklet sürücüsü ağır yaralandı.", "trafik_kazasi"),
    ("TEM otoyolunda zincirleme kaza",
     "Yoğun sis nedeniyle 6 aracın karıştığı zincirleme kazada 4 kişi yaralandı.", "trafik_kazasi"),
    # Yangın
    ("İzmit'te ev yangını", "Yahya Kaptan Mahallesi'ndeki binada yangın çıktı, itfaiye söndürdü.", "yangin"),
    ("Fabrikada korkutan yangın", "Dilovası'ndaki bir fabrikanın deposu alev aldı.", "yangin"),
    ("İTFAİYE EKİPLERİ ZAMANLA YARIŞTI", "Gölcük'te çıkan yangında bir ev küle döndü.", "yangin"),
    # Elektrik kesintisi
    ("Kocaeli'de 6 ilçede elektrik kesintisi",
     "SEDAŞ'ın planlı kesinti programına göre yarın birçok mahalle elektriksiz kalacak.", "elektrik_kesintisi"),
    ("Derince'de elektrikler kesildi", "Trafo arızası nedeniyle mahalle saatlerce karanlıkta kaldı.", "elektrik_kesintisi"),
    # Asayiş
    ("Körfez'de bıçaklı kavga: 1 yaralı", "Tartıştığı kişiyi bıçakla yaralayan şüpheli gözaltına alındı.", "asayis"),
    ("Darıca'da silahlı saldırı", "Kahvehane önünde bekleyen kişiye ateş açıldı.", "asayis"),
    ("Ormanlık alanda ceset bulundu", "Jandarma olayla ilgili soruşturma başlattı.", "asayis"),
    ("Kadınları taciz eden şüpheli yakalandı", "Polis ekipleri şüpheliyi gözaltına aldı.", "asayis"),
    ("Yasa dışı bahis operasyonu: 12 gözaltı", "Emniyet ekipleri eş zamanlı operasyon düzenledi.", "asayis"),
    # Hırsızlık
    ("İş yerinden hırsızlık yapan şüpheli yakalandı", "Kasadan para çalan şüpheli tutuklandı.", "hirsizlik"),
    ("Kuyumcu soygunu kamerada", "Maskeli iki kişi ziynet eşyalarını alıp kaçtı.", "hirsizlik"),
    ("Telefonla kendini polis olarak tanıtan dolandırıcılar yakalandı",
     "Yaşlı kadını dolandıran şebeke çökertildi.", "hirsizlik"),
    ("Yaşlı kadının çantasını kapkaç yöntemiyle aldı", "", "hirsizlik"),
    # Kültürel etkinlik
    ("Sekapark'ta caz konseri", "Kocaeli Büyükşehir Belediyesi'nin düzenlediği konsere binlerce kişi katıldı.", "kulturel_etkinlik"),
    ("Fotoğraf sergisi kapılarını açtı", "Sergi bir ay boyunca ziyaret edilebilecek.", "kulturel_etkinlik"),
    ("Kartepe Kar Festivali başlıyor", "Festival üç gün sürecek.", "kulturel_etkinlik"),
    ("Çocuklar için masal etkinliği düzenlendi", "Kütüphanede yapılan etkinliğe 50 çocuk katıldı.", "kulturel_etkinlik"),
])
def test_dogru_tur(siniflandirici, baslik, icerik, beklenen):
    assert tur(siniflandirici, baslik, icerik) == beklenen


# --------------------------------------------- 6 türe girmeyen haberler: None
@pytest.mark.parametrize("baslik, icerik", [
    # Eskiden "kültürel" sayılıyordu: açılış, program, buluşma, ödül, yarışmacı
    ("Bakan fabrikanın açılışını yaptı", "Açılış programında konuşan bakan yatırımların süreceğini söyledi."),
    ("Kocaelispor deplasman programını açıkladı", "Takım cuma günü kampa girecek."),
    ("Yarışma programında büyük ödül sahibini buldu", "Yarışmacı finalde ödülü kazandı."),
    ("Belediye başkanı esnafla buluştu", "Buluşmada kentsel dönüşüm konuşuldu."),
    ("Sendika başkanından açıklama",
     "Öğretmenler Günü etkinlikleri kapsamında yaptığı açıklamada kadro eksikliğine dikkat çekti."),
    # Eskiden "elektrik" sayılıyordu: SEDAŞ geçmesi kesinti demek değil
    ("SEDAŞ'tan borç yapılandırma fırsatı", "SEDAŞ, eski borçlar için indirim kampanyası başlattı."),
    # Eskiden "asayiş" sayılıyordu: vefat haberi suç değil
    ("Mahalle muhtarı hayatını kaybetti", "Uzun süredir tedavi gören muhtar hayatını kaybetti, cenazesi kılındı."),
    # Eskiden "trafik" sayılıyordu: "kazandı" ≠ "kaza", ihale ilanında "altında kalan"
    ("Kağıtspor deplasmanda kazandı", "Takım otobüsle döndü, sürücü ve kafile karşılandı."),
    ("İhale ilanı", "Teklifi sınır değerin altında kalan isteklilerin teklifleri değerlendirilecek. Araç parkı yenilenecek."),
    # Eskiden "hırsızlık" sayılıyordu: siyasi tartışmada geçen kelime
    ("Mecliste bütçe tartışması",
     "Milletvekilleri uzun süre tartıştı. " + "Görüşmeler sürdü. " * 40 + "Bir vekil 'kamu kaynağını hırsızlar yönetemez' dedi."),
    # Genel haberler
    ("Kocaeli'de 10 okul binası güçlendirilecek", "Okullarda deprem güçlendirme çalışması yapılacak."),
    ("Üniversite Avrupa sıralamasına girdi", "Mühendislik programları ilk 100'de yer aldı."),
    ("", ""),
])
def test_alakasiz_haber_none(siniflandirici, baslik, icerik):
    assert tur(siniflandirici, baslik, icerik) is None


# ------------------------------------------------------- kelime sınırı tuzakları
@pytest.mark.parametrize("baslik", [
    "Dağcılar zirveye tırmandı",          # "tır" ≠ tırmandı
    "Yeni sergilediği performansla dikkat çekti",  # "sergi" ≠ sergiledi
    "Operasyonel verimlilik arttı",       # "opera" ≠ operasyonel
])
def test_kelime_siniri_yanlis_eslesmez(siniflandirici, baslik):
    assert tur(siniflandirici, baslik) is None


def test_trafik_icin_arac_sart(siniflandirici):
    # Kaza var ama araç yok → trafik kazası değil (iş kazası)
    assert tur(siniflandirici, "İnşaatta iş kazası", "İşçi iskeleden düşerek yaralandı.") != "trafik_kazasi"


def test_oncelik_trafik_asayisten_once(siniflandirici):
    # Kazada ölen biri: hem trafik hem "hayatını kaybetti" → trafik kazası
    sonuc = tur(siniflandirici, "Otomobil devrildi: sürücü hayatını kaybetti",
                "Kontrolden çıkan otomobil şarampole devrildi.")
    assert sonuc == "trafik_kazasi"


def test_donus_formati(siniflandirici):
    sonuc = siniflandirici.siniflandir("Gebze'de yangın", "İtfaiye söndürdü.")
    assert set(sonuc) == {"haber_turu", "guven_skoru", "tum_skorlar"}
    assert 0 < sonuc["guven_skoru"] <= 1
    assert set(sonuc["tum_skorlar"]) == set(NewsClassifier.SINIFLANDIRMA_KURALLARI)


def test_toplu_siniflandir(siniflandirici):
    sonuclar = siniflandirici.toplu_siniflandir([
        {"baslik": "Konser", "icerik": "Konser yapıldı."},
        {"baslik": "Bütçe görüşüldü", "icerik": ""},
    ])
    assert [s["haber_turu"] for s in sonuclar] == ["kulturel_etkinlik", None]


# --------------------------------------------------------------- Türkçe harfler
@pytest.mark.parametrize("girdi, beklenen", [
    ("İTFAİYE", "itfaiye"),
    ("IŞIK", "ışık"),
    ("İzmit", "izmit"),
    ("", ""),
])
def test_tr_kucuk_harf(girdi, beklenen):
    assert tr_kucuk_harf(girdi) == beklenen


def test_buyuk_harfli_baslik_eslesir(siniflandirici):
    assert tur(siniflandirici, "İZMİT'TE KORKUTAN YANGIN") == "yangin"


# ------------------------------------------------------------ hariç ifadeler
@pytest.mark.parametrize("baslik, icerik", [
    ("Belediyenin ihalesi yeniden değerlendirilecek",
     "35 adet yangın söndürme tankeri alımı için yapılan ihaleye itiraz sonuçlandı."),
    ("Okulda deprem ve yangın tatbikatı yapıldı", "Öğrenciler tahliye edildi."),
    ("Kadın Platformu'ndan 25 Kasım yürüyüşü",
     "Platform kadın cinayetlerine ve şiddete karşı mücadele çağrısı yaptı."),
])
def test_haric_ifadeler_tur_atamaz(siniflandirici, baslik, icerik):
    assert tur(siniflandirici, baslik, icerik) is None


def test_cinayet_buro_tek_basina_asayis_degil(siniflandirici):
    sonuc = tur(siniflandirici, "Kayıp yaşlı adamdan 13 gündür haber yok",
                "Arama çalışmaları sürerken Cinayet Büro ekipleri incelemeye başladı.")
    assert sonuc is None


def test_haric_ifade_gercek_olayi_engellemez(siniflandirici):
    # Hem tatbikat hem gerçek yangın geçiyorsa yangın olarak kalmalı
    assert tur(siniflandirici, "Fabrikada yangın çıktı",
               "Geçen ay yangın tatbikatı yapılan fabrikada bu sabah yangın çıktı.") == "yangin"
    # Tekil "kadın cinayeti" bir olay haberidir
    assert tur(siniflandirici, "Gölcük'te kadın cinayeti", "Eşini öldüren şüpheli tutuklandı.") == "asayis"
