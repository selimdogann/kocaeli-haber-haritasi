"""Benzer haber birleştirme kuralları: sadece farklı sitelerin aynı haberi birleşir."""

import pytest

from scraper.scraper_manager import ScraperManager


def benzer(link, oran):
    return {"haber": {"haber_linki": link}, "benzerlik_orani": oran}


OZGUR = "https://www.ozgurkocaeli.com.tr/haber/2/devam-haberi"


def test_ayni_sitenin_devam_haberi_birlestirilmez():
    secilen = ScraperManager.birlestirilecek_benzer(
        {"haber_linki": OZGUR},
        [benzer("https://www.ozgurkocaeli.com.tr/haber/1/ilk-haber", 0.93)],
    )
    assert secilen is None


def test_farkli_sitedeki_ayni_haber_birlestirilir():
    secilen = ScraperManager.birlestirilecek_benzer(
        {"haber_linki": OZGUR},
        [
            benzer("https://ozgurkocaeli.com.tr/haber/1/x", 0.95),   # www'suz ama aynı site
            benzer("https://www.cagdaskocaeli.com.tr/haber/9/y", 0.91),
        ],
    )
    assert secilen["haber"]["haber_linki"].startswith("https://www.cagdaskocaeli")


@pytest.mark.parametrize("benzerler", [[], None])
def test_benzer_yoksa_none(benzerler):
    assert ScraperManager.birlestirilecek_benzer({"haber_linki": OZGUR}, benzerler) is None
