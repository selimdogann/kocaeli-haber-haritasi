"""
Scraper testleri (internetsiz).

Gerçek siteye bağlanmak yerine sayfa_getir() metodu örnek HTML döndürecek şekilde
değiştirilir (monkeypatch). Böylece link toplama, başlık/içerik/tarih çıkarma ve
"son 3 gün" filtresi sitelerin o anki erişilebilirliğinden bağımsız test edilir.
Gerçek sitelere bağlanan testler: test_canli_kaynaklar.py (--canli).
"""

from datetime import datetime, timedelta

import pytest
from bs4 import BeautifulSoup

from scraper.bizim_yaka import BizimYakaScraper
from scraper.cagdas_kocaeli import CagdasKocaeliScraper
from scraper.ozgur_kocaeli import OzgurKocaeliScraper
from scraper.ses_kocaeli import SesKocaeliScraper
from scraper.yeni_kocaeli import YeniKocaeliScraper

TUM_SCRAPERLAR = [
    CagdasKocaeliScraper, OzgurKocaeliScraper, SesKocaeliScraper,
    YeniKocaeliScraper, BizimYakaScraper,
]

# Her sitenin haber detay URL'si için gerçek formatta birer örnek
ORNEK_HABER_LINKI = {
    CagdasKocaeliScraper: "https://www.cagdaskocaeli.com.tr/haber/29224468/ornek-haber",
    OzgurKocaeliScraper: "https://www.ozgurkocaeli.com.tr/haber/29227766/ornek-haber",
    SesKocaeliScraper: "https://www.seskocaeli.com/haber/12345/ornek-haber",
    YeniKocaeliScraper: "https://www.yenikocaeli.com/haber/29230957/ornek-haber",
    BizimYakaScraper: "https://www.bizimyaka.com/haber/12345/ornek-haber",
}


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def detay_html(tarih_iso: str, govde_sinifi: str) -> str:
    """Daktilo CMS benzeri bir haber detay sayfası."""
    return f"""
    <html><head>
      <meta property="article:published_time" content="{tarih_iso}">
    </head><body>
      <nav><a href="/">Anasayfa</a></nav>
      <h1>İzmit'te iki otomobil çarpıştı</h1>
      <div class="{govde_sinifi}">
        <p>Kaza, İzmit'in Yenidoğan Mahallesi'nde sabah saatlerinde meydana geldi.</p>
        <p>Çarpışmanın ardından olay yerine sağlık ve polis ekipleri sevk edildi.</p>
        <p>Kısa</p>
        <div class="share"><p>Bu haberi Facebook ve X üzerinden paylaşın lütfen.</p></div>
        <div class="comments"><p>Yorumunuz: Geçmiş olsun, yol çok tehlikeli bir yer.</p></div>
        <script>var reklam = "bu metin içerikte görünmemeli";</script>
      </div>
    </body></html>
    """


# ------------------------------------------------------------- link desenleri
@pytest.mark.parametrize("cls", TUM_SCRAPERLAR)
def test_haber_linki_deseni(cls):
    s = cls()
    assert s._haber_linki_mi(ORNEK_HABER_LINKI[cls])
    assert not s._haber_linki_mi(f"{s.base_url}/kocaeli-asayis-haberleri")
    assert not s._haber_linki_mi(f"{s.base_url}/yazarlar/ornek-yazar")
    assert not s._haber_linki_mi("")


@pytest.mark.parametrize("cls", TUM_SCRAPERLAR)
def test_haber_listesi_linkleri_toplar_ve_suzer(cls, monkeypatch):
    s = cls()
    ornek = ORNEK_HABER_LINKI[cls]
    goreli = ornek.replace(s.base_url, "")
    kategori_sayfasi = soup(f"""
        <a href="{ornek}">mutlak link</a>
        <a href="{goreli}">göreli link (aynı haber, tekrar etmemeli)</a>
        <a href="{s.base_url}/kategori/spor">kategori sayfası</a>
        <a href="https://baska-site.com/haber/99999/x">başka site</a>
        <a href="#">boş</a>
    """)
    monkeypatch.setattr(s, "sayfa_getir", lambda url: kategori_sayfasi)

    linkler = s.haber_listesi_getir()

    assert linkler == [ornek]


# -------------------------------------------------------------- detay çıkarma
@pytest.mark.parametrize("cls, govde_sinifi", [
    (CagdasKocaeliScraper, "haber-metni"),
    (OzgurKocaeliScraper, "haber-metni"),
    (SesKocaeliScraper, "detail-content"),
    (YeniKocaeliScraper, "post-text"),
    (BizimYakaScraper, "detail-content"),
])
def test_haber_detay_baslik_icerik_tarih(cls, govde_sinifi, monkeypatch):
    s = cls()
    tarih = datetime.now().replace(microsecond=0) - timedelta(hours=2)
    monkeypatch.setattr(s, "sayfa_getir", lambda url: soup(detay_html(tarih.isoformat() + "+03:00", govde_sinifi)))

    haber = s.haber_detay_getir(ORNEK_HABER_LINKI[cls])

    assert haber["baslik"] == "İzmit'te iki otomobil çarpıştı"
    assert "Yenidoğan Mahallesi" in haber["icerik"]
    assert "polis ekipleri" in haber["icerik"]
    assert "reklam" not in haber["icerik"]          # script içeriği alınmaz
    assert haber["yayin_tarihi"] == tarih


@pytest.mark.parametrize("cls, govde_sinifi", [
    (CagdasKocaeliScraper, "haber-metni"),
    (OzgurKocaeliScraper, "haber-metni"),
    (SesKocaeliScraper, "detail-content"),
    (YeniKocaeliScraper, "post-text"),
    (BizimYakaScraper, "detail-content"),
])
def test_yorum_ve_paylasim_icerige_karismaz(cls, govde_sinifi, monkeypatch):
    s = cls()
    monkeypatch.setattr(s, "sayfa_getir", lambda url: soup(detay_html("2026-11-26T10:00:00", govde_sinifi)))
    icerik = s.haber_detay_getir(ORNEK_HABER_LINKI[cls])["icerik"]
    assert "Facebook" not in icerik
    assert "Geçmiş olsun" not in icerik


@pytest.mark.parametrize("cls", TUM_SCRAPERLAR)
def test_basliksiz_sayfa_none(cls, monkeypatch):
    s = cls()
    monkeypatch.setattr(s, "sayfa_getir", lambda url: soup("<html><body><p>Sayfa bulunamadı</p></body></html>"))
    assert s.haber_detay_getir(ORNEK_HABER_LINKI[cls]) is None


@pytest.mark.parametrize("cls", TUM_SCRAPERLAR)
def test_sayfa_gelmezse_none(cls, monkeypatch):
    s = cls()
    monkeypatch.setattr(s, "sayfa_getir", lambda url: None)
    assert s.haber_detay_getir(ORNEK_HABER_LINKI[cls]) is None


# -------------------------------------------------------- tarih ayrıştırma
@pytest.mark.parametrize("metin, beklenen", [
    ("2026-11-26T14:05:00+03:00", datetime(2026, 11, 26, 14, 5)),
    ("2026-11-26T14:05:00Z", datetime(2026, 11, 26, 14, 5)),
    ("2026-11-26 14:05", datetime(2026, 11, 26, 14, 5)),
    ("26.11.2026 14:05", datetime(2026, 11, 26, 14, 5)),
    ("26.11.2026", datetime(2026, 11, 26)),
    ("26 Kasım 2026 14:05", datetime(2026, 11, 26, 14, 5)),
    ("26 Kasım 2026", datetime(2026, 11, 26)),
    ("3 Ara 2026", datetime(2026, 12, 3)),
])
def test_tarih_ayristir(metin, beklenen):
    assert CagdasKocaeliScraper().tarih_ayristir(metin) == beklenen


def test_goreli_tarih():
    s = CagdasKocaeliScraper()
    simdi = datetime.now()
    assert abs((s.tarih_ayristir("2 saat önce") - (simdi - timedelta(hours=2))).total_seconds()) < 5
    assert abs((s.tarih_ayristir("dün") - (simdi - timedelta(days=1))).total_seconds()) < 5


@pytest.mark.parametrize("metin", ["", None, "tarih yok"])
def test_gecersiz_tarih_none(metin):
    assert CagdasKocaeliScraper().tarih_ayristir(metin) is None


# ------------------------------------------------------------ son 3 gün kuralı
def test_son_n_gun():
    s = CagdasKocaeliScraper()
    bugun = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    assert s.son_n_gun_icinde_mi(datetime.now(), gun=3)
    assert s.son_n_gun_icinde_mi(bugun - timedelta(days=2), gun=3)        # 3. günün başı
    assert not s.son_n_gun_icinde_mi(bugun - timedelta(days=2, seconds=1), gun=3)
    assert not s.son_n_gun_icinde_mi(None, gun=3)


def test_tum_haberleri_cek_eski_ve_tarihsizleri_atar(monkeypatch):
    s = CagdasKocaeliScraper()
    yeni, eski, tarihsiz = (f"{s.base_url}/haber/{i}/x" for i in (1, 2, 3))
    monkeypatch.setattr(s, "haber_listesi_getir", lambda: [yeni, eski, tarihsiz])
    detaylar = {
        yeni: {"baslik": "Yeni", "icerik": "...", "yayin_tarihi": datetime.now()},
        eski: {"baslik": "Eski", "icerik": "...", "yayin_tarihi": datetime.now() - timedelta(days=10)},
        tarihsiz: {"baslik": "Tarihsiz", "icerik": "...", "yayin_tarihi": None},
    }
    monkeypatch.setattr(s, "haber_detay_getir", lambda url: dict(detaylar[url]))

    haberler = s.tum_haberleri_cek()

    assert [h["baslik"] for h in haberler] == ["Yeni"]
    assert haberler[0]["haber_linki"] == yeni
    assert haberler[0]["kaynak_site"] == "Çağdaş Kocaeli"


# ------------------------------------------------------- bot koruması (403)
class _SahteYanit:
    def __init__(self, durum, basliklar=None, metin=""):
        import requests
        self.status_code = durum
        self.headers = basliklar or {}
        self.text = metin
        self.encoding = "utf-8"
        self.apparent_encoding = "utf-8"
        self._requests = requests

    def raise_for_status(self):
        if self.status_code >= 400:
            raise self._requests.exceptions.HTTPError(response=self)


def test_cloudflare_engeli_algilanir_ve_kaynak_birakilir(monkeypatch):
    s = BizimYakaScraper()
    s.gecikme = 0
    istekler = []

    def sahte_get(url, timeout):
        istekler.append(url)
        return _SahteYanit(403, {"cf-mitigated": "challenge"}, "<title>Just a moment...</title>")

    monkeypatch.setattr(s.session, "get", sahte_get)

    assert s.haber_listesi_getir() == []
    assert s.engellendi is True
    assert len(istekler) == 1      # ilk engelden sonra diğer kategorilere istek atılmaz


def test_normal_403_engel_sayilmaz(monkeypatch):
    s = BizimYakaScraper()
    s.gecikme = 0
    monkeypatch.setattr(s.session, "get", lambda url, timeout: _SahteYanit(404))
    assert s.sayfa_getir(f"{s.base_url}/yok") is None
    assert s.engellendi is False


def test_yeni_kocaeli_itemprop_tarihi(monkeypatch):
    # Yeni Kocaeli tarihi <meta itemprop="datePublished"> içinde veriyor
    s = YeniKocaeliScraper()
    html = detay_html("x", "post-text").replace(
        '<meta property="article:published_time" content="x">',
        '<meta itemprop="datePublished" content="2026-11-26T17:54:00+03:00">',
    )
    monkeypatch.setattr(s, "sayfa_getir", lambda url: soup(html))
    assert s.haber_detay_getir(ORNEK_HABER_LINKI[YeniKocaeliScraper])["yayin_tarihi"] == datetime(2026, 11, 26, 17, 54)


def test_kayitli_linklerin_detayi_indirilmez(monkeypatch):
    s = CagdasKocaeliScraper()
    yeni, kayitli = f"{s.base_url}/haber/1/yeni", f"{s.base_url}/haber/2/kayitli"
    monkeypatch.setattr(s, "haber_listesi_getir", lambda: [yeni, kayitli])
    indirilen = []

    def detay(url):
        indirilen.append(url)
        return {"baslik": "x", "icerik": "...", "yayin_tarihi": datetime.now()}

    monkeypatch.setattr(s, "haber_detay_getir", detay)
    s.tum_haberleri_cek(atlanacak_linkler={kayitli})
    assert indirilen == [yeni]


def test_engelli_kaynak_hic_istek_atmaz(monkeypatch):
    s = OzgurKocaeliScraper()      # Playwright yolu olan kaynak
    s.engellendi = True
    monkeypatch.setattr(s, "_sayfa_getir_playwright", lambda url: pytest.fail("istek atılmamalı"))
    assert s.sayfa_getir(f"{s.base_url}/haber/1/x") is None
