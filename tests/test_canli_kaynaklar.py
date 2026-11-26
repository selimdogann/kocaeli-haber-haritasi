"""
Canlı kaynak testleri: gerçek haber sitelerine bağlanır.

Varsayılan olarak ÇALIŞMAZ (sitelere gereksiz yük bindirmemek için).
Çalıştırmak için:  pytest --canli tests/test_canli_kaynaklar.py -v

Her kaynak için kontrol edilenler:
- Kategori sayfalarından haber linki toplanabiliyor mu?
- İlk haberin başlığı, içeriği ve tarihi çıkarılabiliyor mu?
- Kaydedilecek link gerçekten o haberin sayfası mı (sayfa başlığı tutuyor mu)?
"""

import pytest

from scraper.bizim_yaka import BizimYakaScraper
from scraper.cagdas_kocaeli import CagdasKocaeliScraper
from scraper.ozgur_kocaeli import OzgurKocaeliScraper
from scraper.ses_kocaeli import SesKocaeliScraper
from scraper.yeni_kocaeli import YeniKocaeliScraper

pytestmark = pytest.mark.canli


@pytest.mark.parametrize("cls", [
    CagdasKocaeliScraper, OzgurKocaeliScraper, SesKocaeliScraper,
    YeniKocaeliScraper, BizimYakaScraper,
], ids=lambda c: c.__name__)
def test_kaynaktan_haber_geliyor(cls):
    s = cls()
    linkler = s.haber_listesi_getir()

    assert not s.engellendi, f"{s.kaynak_adi} bot korumasıyla erişimi reddetti (Cloudflare challenge)"
    assert linkler, f"{s.kaynak_adi}: hiç haber linki bulunamadı (site yapısı değişmiş olabilir)"

    haber = s.haber_detay_getir(linkler[0])
    assert haber, f"{s.kaynak_adi}: haber detayı çekilemedi: {linkler[0]}"
    assert len(haber["baslik"]) > 10
    assert len(haber.get("icerik") or "") > 100, f"içerik çok kısa: {linkler[0]}"
    assert haber.get("yayin_tarihi"), f"tarih bulunamadı: {linkler[0]}"

    # Link doğrulaması: aynı URL tekrar açıldığında aynı başlık gelmeli
    tekrar = s.sayfa_getir(linkler[0])
    assert tekrar is not None and tekrar.find("h1").get_text(strip=True) == haber["baslik"]
