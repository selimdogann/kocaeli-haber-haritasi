"""
REST API testleri.

Ayrı bir test veritabanı (kocaeli_haber_test) kullanır; gerçek veriye dokunmaz.
MongoDB çalışmıyorsa testler atlanır.
"""

from datetime import datetime, timedelta

import pytest
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from config.settings import Config

pytestmark = pytest.mark.mongo


def _mongo_var_mi() -> bool:
    try:
        MongoClient(Config.MONGODB_URI, serverSelectionTimeoutMS=1500).admin.command("ping")
        return True
    except PyMongoError:
        return False


if not _mongo_var_mi():
    pytest.skip("MongoDB çalışmıyor", allow_module_level=True)

assert Config.MONGODB_DB_NAME == "kocaeli_haber_test", "Testler gerçek veritabanında çalışmamalı"

from app import create_app  # noqa: E402
from database.mongodb import MongoDB  # noqa: E402

SIMDI = datetime.now().replace(microsecond=0)


def haber(baslik, tur, ilce=None, gun_once=0, konum=True, **ek):
    h = {
        "baslik": baslik,
        "icerik": f"{baslik} içeriği.",
        "haber_turu": tur,
        "ilce": ilce,
        "mahalle": None,
        "kaynak_site": "Çağdaş Kocaeli",
        "haber_linki": f"https://www.cagdaskocaeli.com.tr/haber/{abs(hash(baslik))}/x",
        "yayin_tarihi": SIMDI - timedelta(days=gun_once),
        "diger_kaynaklar": [],
        "enlem": 40.76 if konum else None,
        "boylam": 29.94 if konum else None,
    }
    if konum:
        h["konum_geojson"] = {"type": "Point", "coordinates": [29.94, 40.76]}
    else:
        h["konum_geojson"] = None   # pipeline konumsuz haberi böyle kaydeder
    h.update(ek)
    return h


ORNEK_HABERLER = [
    haber("A trafik İzmit bugün", "trafik_kazasi", "İzmit"),
    haber("B yangın Gebze dün", "yangin", "Gebze", gun_once=1),
    haber("C asayiş konumsuz", "asayis", None, konum=False),
    haber("D trafik Kartepe eski", "trafik_kazasi", "Kartepe", gun_once=10),
    haber("E geçersiz tür", "spor", "İzmit"),
    haber("F kültürel çok kaynak", "kulturel_etkinlik", "İzmit",
          diger_kaynaklar=[{"site_adi": "Özgür Kocaeli", "link": "https://www.ozgurkocaeli.com.tr/haber/1/x"}]),
]


@pytest.fixture()
def client():
    db = MongoDB()
    db.news_collection.delete_many({})
    for h in ORNEK_HABERLER:
        db.haber_ekle(dict(h))
    app = create_app()
    app.config["TESTING"] = True
    yield app.test_client()
    db.news_collection.delete_many({})


def basliklar(yanit):
    assert yanit.status_code == 200, yanit.get_json()
    return sorted(h["baslik"][0] for h in yanit.get_json()["haberler"])


def tarih(gun_once):
    return (SIMDI - timedelta(days=gun_once)).strftime("%Y-%m-%d")


# ------------------------------------------------------------------- liste
def test_varsayilan_liste_son_3_gun_konumlu_gecerli_tur(client):
    # C konumsuz, D 10 gün önce, E geçersiz tür → listede olmamalı
    assert basliklar(client.get("/api/haberler")) == ["A", "B", "F"]


def test_tur_filtresi(client):
    assert basliklar(client.get("/api/haberler?haber_turu=yangin")) == ["B"]


def test_coklu_tur_filtresi(client):
    assert basliklar(client.get("/api/haberler?haber_turu=trafik_kazasi,yangin")) == ["A", "B"]


def test_ilce_filtresi(client):
    assert basliklar(client.get("/api/haberler?ilce=Gebze")) == ["B"]


def test_ilce_filtresi_regex_karakteri_hata_vermez(client):
    yanit = client.get("/api/haberler?ilce=(")
    assert yanit.status_code == 200
    assert yanit.get_json()["haberler"] == []


def test_ilce_filtresi_tam_eslesme(client):
    # "zmit" gibi bir parça İzmit'i getirmemeli
    assert basliklar(client.get("/api/haberler?ilce=zmit")) == []


def test_tarih_araligi_eski_haberi_getirir(client):
    url = f"/api/haberler?baslangic_tarihi={tarih(11)}&bitis_tarihi={tarih(9)}"
    assert basliklar(client.get(url)) == ["D"]


def test_konumsuzlar_dahil_liste(client):
    assert basliklar(client.get("/api/haberler?sadece_konumlu=false")) == ["A", "B", "C", "F"]


def test_konumsuzlar_dahil_liste_filtrelere_uyar(client):
    url = f"/api/haberler?sadece_konumlu=false&haber_turu=trafik_kazasi,asayis"
    assert basliklar(client.get(url)) == ["A", "C"]
    url = f"/api/haberler?sadece_konumlu=false&baslangic_tarihi={tarih(11)}&bitis_tarihi={tarih(9)}"
    assert basliklar(client.get(url)) == ["D"]


def test_limit_ust_siniri(client):
    assert client.get("/api/haberler?limit=99999").get_json()["limit"] == 500
    assert client.get("/api/haberler?limit=abc").get_json()["limit"] == 200


def test_haber_formati(client):
    haberler = {h["baslik"][0]: h for h in client.get("/api/haberler").get_json()["haberler"]}
    a, f = haberler["A"], haberler["F"]
    assert a["koordinatlar"] == {"lat": 40.76, "lng": 29.94}
    assert a["konum_bilgisi"]["ilce"] == "İzmit"
    assert a["tarih"].startswith(SIMDI.strftime("%Y-%m-%d"))
    assert a["kaynaklar"][0]["link"].startswith("https://www.cagdaskocaeli.com.tr/haber/")
    assert [k["kaynak_adi"] for k in f["kaynaklar"]] == ["Çağdaş Kocaeli", "Özgür Kocaeli"]


# ----------------------------------------------------------------- detay
def test_haber_detay(client):
    haber_id = client.get("/api/haberler?haber_turu=yangin").get_json()["haberler"][0]["_id"]
    yanit = client.get(f"/api/haberler/{haber_id}")
    assert yanit.status_code == 200
    assert yanit.get_json()["haber"]["baslik"].startswith("B")


@pytest.mark.parametrize("haber_id", ["gecersiz-id", "0123456789abcdef01234567"])
def test_haber_detay_bulunamadi(client, haber_id):
    assert client.get(f"/api/haberler/{haber_id}").status_code == 404


# ----------------------------------------------------------- istatistikler
def test_istatistikler(client):
    ist = client.get("/api/istatistikler").get_json()["istatistikler"]
    assert ist["toplam_haber"] == 4            # A, B, C, F
    assert ist["konumlu_haber"] == 3           # C konumsuz
    assert ist["tur_dagilimi"]["trafik_kazasi"] == 1
    assert ist["tur_dagilimi"]["yangin"] == 1
    assert ist["tur_dagilimi"]["kulturel_etkinlik"] == 1
    assert ist["tur_dagilimi"]["asayis"] == 0  # tek asayiş haberi konumsuz


def test_istatistik_ilce_filtresi(client):
    ist = client.get("/api/istatistikler?ilce=İzmit").get_json()["istatistikler"]
    assert ist["konumlu_haber"] == 2           # A, F


# -------------------------------------------------------------- diğerleri
def test_haber_turleri_ve_ilceler(client):
    assert set(client.get("/api/haber-turleri").get_json()["haber_turleri"]) == set(Config.NEWS_TYPES)
    assert "Gebze" in client.get("/api/ilceler").get_json()["ilceler"]


def test_ana_sayfa(client):
    yanit = client.get("/")
    assert yanit.status_code == 200
    html = yanit.get_data(as_text=True)
    for tur_id in Config.NEWS_TYPES:
        assert f'value="{tur_id}"' in html


def test_temizle_anahtarsiz_reddedilir(client):
    assert client.post("/api/temizle").status_code == 401
    assert client.post("/api/temizle", headers={"Authorization": "Bearer yanlis"}).status_code == 401
    assert len(client.get("/api/haberler").get_json()["haberler"]) == 3


def test_temizle_dogru_anahtarla(client):
    yanit = client.post("/api/temizle", headers={"Authorization": f"Bearer {Config.ADMIN_API_KEY}"})
    assert yanit.status_code == 200
    assert client.get("/api/haberler").get_json()["haberler"] == []
