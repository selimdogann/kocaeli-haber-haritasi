"""
Ortak test ayarları.

- Testler gerçek veritabanına DOKUNMAZ: ayrı bir test veritabanı kullanılır.
- NER modeli (yüzlerce MB) testlerde yüklenmez; regex tabanlı konum çıkarımı test edilir.
- İnternete çıkan testler varsayılan olarak kapalıdır: `pytest --canli` ile açılır.
"""

import os
import sys

# Config modülü import edilmeden ÖNCE ortam değişkenleri ayarlanmalı
# (load_dotenv var olan değişkenleri ezmez).
os.environ["MONGODB_DB_NAME"] = "kocaeli_haber_test"
os.environ["LOCATION_NER_ENABLED"] = "False"
os.environ["FLASK_DEBUG"] = "False"
os.environ["ADMIN_API_KEY"] = "test-admin-anahtari"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402


def pytest_addoption(parser):
    parser.addoption(
        "--canli",
        action="store_true",
        default=False,
        help="Gerçek haber sitelerine bağlanan testleri de çalıştır",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "canli: gerçek sitelere bağlanan test (--canli ile açılır)")
    config.addinivalue_line("markers", "mongo: çalışan bir MongoDB gerektirir")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--canli"):
        return
    atla = pytest.mark.skip(reason="canlı test: çalıştırmak için `pytest --canli`")
    for item in items:
        if "canli" in item.keywords:
            item.add_marker(atla)
