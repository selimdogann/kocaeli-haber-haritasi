"""Konum çıkarımı testleri (regex tabanlı; NER modeli testlerde kapalı)."""

import pytest

from processing.location_extractor import LocationExtractor


@pytest.fixture(scope="module")
def cikarici():
    return LocationExtractor()


@pytest.mark.parametrize("baslik, icerik, ilce, mahalle", [
    ("Gebze'de iki otomobil çarpıştı", "Kaza Gebze'nin Mustafapaşa Mahallesi'nde meydana geldi.", "Gebze", "Mustafapaşa"),
    ("İzmit'te ev yangını", "Yahya Kaptan Mahallesi Kuşkonmaz Sokak'taki binada yangın çıktı.", "İzmit", "Yahya Kaptan"),
    ("KARTEPE'DE KAZA", "Kartepe ilçesinde meydana gelen kazada 2 kişi yaralandı.", "Kartepe", None),
    ("Körfez'de kavga", "Olay Körfez ilçesinde yaşandı.", "Körfez", None),
])
def test_kocaeli_konumu(cikarici, baslik, icerik, ilce, mahalle):
    sonuc = cikarici.konum_cikar(baslik, icerik)
    assert sonuc["ilce"] == ilce
    assert sonuc["mahalle"] == mahalle
    assert sonuc["geocoding_sorgusu"].endswith("Kocaeli")


def test_sokak_geocoding_sorgusuna_girer(cikarici):
    sonuc = cikarici.konum_cikar("İzmit'te ev yangını", "Yahya Kaptan Mahallesi Kuşkonmaz Sokak'taki binada yangın çıktı.")
    assert sonuc["geocoding_sorgusu"].startswith("Kuşkonmaz")


def test_kocaeli_disi_haber_konumsuz(cikarici):
    # Başka ildeki olay Kocaeli haritasına pin olarak düşmemeli
    sonuc = cikarici.konum_cikar("Ankara'da gasp çetesi çökertildi", "Ankara'da 5 şüpheli yakalandı.")
    assert sonuc["ilce"] is None
    assert sonuc["geocoding_sorgusu"] is None


def test_bos_metin(cikarici):
    sonuc = cikarici.konum_cikar("", "")
    assert sonuc["konum_metni"] is None
