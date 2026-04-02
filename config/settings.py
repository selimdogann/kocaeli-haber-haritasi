"""
Kocaeli Haber Haritası - Uygulama Yapılandırma Ayarları
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Ana yapılandırma sınıfı."""

    # MongoDB Ayarları
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "kocaeli_haber_haritasi")

    # Google API Anahtarları
    GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
    GOOGLE_GEOCODING_API_KEY = os.getenv("GOOGLE_GEOCODING_API_KEY", "")

    # Flask Ayarları
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    FLASK_PORT = int(os.getenv("FLASK_PORT", 5001))

    # Admin API Anahtarı (/api/temizle koruması)
    ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")

    # Scraping Ayarları
    SCRAPING_DAYS = int(os.getenv("SCRAPING_DAYS", 3))
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 20))
    REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", 0.1))
    SCRAPER_MAX_WORKERS = int(os.getenv("SCRAPER_MAX_WORKERS", 12))
    SCRAPER_MAX_LINKS_PER_SOURCE = int(os.getenv("SCRAPER_MAX_LINKS_PER_SOURCE", 50))
    PROCESSING_MAX_WORKERS = int(os.getenv("PROCESSING_MAX_WORKERS", 5))

    # Konum çıkarımı ayarları
    LOCATION_NER_ENABLED = os.getenv("LOCATION_NER_ENABLED", "True").lower() == "true"
    LOCATION_NER_MODEL = os.getenv(
        "LOCATION_NER_MODEL",
        "Babelscape/wikineural-multilingual-ner",
    )

    # Kocaeli Merkez Koordinatları (Harita başlangıç noktası)
    KOCAELI_CENTER_LAT = 40.7654
    KOCAELI_CENTER_LNG = 29.9408

    # Haber Kaynakları
    NEWS_SOURCES = {
        "cagdas_kocaeli": {
            "name": "Çağdaş Kocaeli",
            "base_url": "https://www.cagdaskocaeli.com.tr",
        },
        "ozgur_kocaeli": {
            "name": "Özgür Kocaeli",
            "base_url": "https://www.ozgurkocaeli.com.tr",
        },
        "ses_kocaeli": {
            "name": "Ses Kocaeli",
            "base_url": "https://www.seskocaeli.com",
        },
        "yeni_kocaeli": {
            "name": "Yeni Kocaeli",
            "base_url": "https://yenikocaeli.com",
        },
        "bizim_yaka": {
            "name": "Bizim Yaka",
            "base_url": "https://bizimyaka.com",
        },
    }

    # Haber Türleri ve Renkleri
    NEWS_TYPES = {
        "trafik_kazasi": {
            "label": "Trafik Kazası",
            "color": "#DC2626",
            "icon": "🚗",
            "marker_color": "red",
        },
        "yangin": {
            "label": "Yangın",
            "color": "#EA580C",
            "icon": "🔥",
            "marker_color": "orange",
        },
        "elektrik_kesintisi": {
            "label": "Elektrik Kesintisi",
            "color": "#1e293b",
            "icon": "⚡",
            "marker_color": "yellow",
        },
        "asayis": {
            "label": "Asayiş",
            "color": "#B91C1C",
            "icon": "🚨",
            "marker_color": "darkred",
        },
        "hirsizlik": {
            "label": "Hırsızlık",
            "color": "#7C3AED",
            "icon": "🔒",
            "marker_color": "purple",
        },
        "kulturel_etkinlik": {
            "label": "Kültürel Etkinlikler",
            "color": "#2563EB",
            "icon": "🎭",
            "marker_color": "blue",
        },
    }

    # Benzerlik Eşik Değeri
    SIMILARITY_THRESHOLD = 0.82

    # Kocaeli İlçeleri
    KOCAELI_DISTRICTS = [
        "İzmit", "Gebze", "Darıca", "Çayırova", "Dilovası",
        "Körfez", "Derince", "Gölcük", "Karamürsel", "Başiskele",
        "Kartepe", "Kandıra",
    ]
