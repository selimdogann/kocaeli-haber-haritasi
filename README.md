# 🗺️ Kocaeli Haber Haritası

**Web Scraping Tabanlı Kentsel Haber İzleme ve Harita Üzerinde Görselleştirme Sistemi**

Kocaeli Üniversitesi - Bilgisayar Mühendisliği Bölümü  
Yazılım Laboratuvarı-II | Proje I

---

## 📋 Proje Açıklaması

Bu proje, Kocaeli yerel haber sitelerinden belirlenen haber türlerine ait haberlerin web ortamından otomatik olarak toplanmasını, işlenmesini ve Google Maps üzerinde görselleştirilmesini sağlayan bir sistemdir.

## 🏗️ Mimari

```
┌─────────────────────────────────────────────────────┐
│                  Kullanıcı Arayüzü                  │
│              (HTML/CSS/JS + Google Maps)             │
├─────────────────────────────────────────────────────┤
│                   Flask Backend API                  │
├──────────┬──────────┬───────────┬───────────────────┤
│ Scraping │ Temizleme│Sınıfland. │ Konum & Geocoding │
│  Modülü  │  Modülü  │  Modülü   │     Modülü        │
├──────────┴──────────┴───────────┴───────────────────┤
│                  MongoDB Veritabanı                  │
└─────────────────────────────────────────────────────┘
```

## 🔧 Teknolojiler

| Teknoloji | Kullanım Alanı |
|-----------|----------------|
| **Python 3.10+** | Backend, Scraping, NLP |
| **Flask** | Web Framework & REST API |
| **MongoDB** | NoSQL Veritabanı |
| **BeautifulSoup4** | Web Scraping |
| **Sentence-Transformers** | Metin Benzerliği (Embedding) |
| **Google Maps API** | Harita Görselleştirme |
| **Google Geocoding API** | Koordinat Dönüştürme |

## 📰 Haber Kaynakları

- [Çağdaş Kocaeli](https://www.cagdaskocaeli.com.tr/)
- [Özgür Kocaeli](https://www.ozgurkocaeli.com.tr/)
- [Ses Kocaeli](https://www.seskocaeli.com/)
- [Yeni Kocaeli](https://yenikocaeli.com)
- [Bizim Yaka](https://bizimyaka.com)

## 📂 Haber Türleri

| Simge | Haber Türü | Marker Rengi |
|-------|-----------|--------------|
| 🚗 | Trafik Kazası | Kırmızı |
| 🔥 | Yangın | Turuncu |
| ⚡ | Elektrik Kesintisi | Koyu Lacivert |
| 🔒 | Hırsızlık | Mor |
| 🕊️ | Vefat | Koyu Gri |
| 🩺 | Sağlık | Yeşil |
| 🎓 | Eğitim | Turkuaz |
| ⚽ | Spor | Yeşil |
| 🏛️ | Yerel Yönetim | Mor-Mavi |
| 🎭 | Kültürel Etkinlikler | Mavi |
| 📰 | Diğer | Gri |

## 🚀 Kurulum

### 1. Depoyu Klonlayın
```bash
git clone https://github.com/selimdogann/kocaeli-haber-haritasi.git
cd kocaeli-haber-haritasi
```

### 2. Sanal Ortam Oluşturun
```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows
```

### 3. Bağımlılıkları Yükleyin
```bash
pip install -r requirements.txt
```

### 4. Ortam Değişkenlerini Ayarlayın
```bash
cp .env.example .env
# .env dosyasını düzenleyerek API anahtarlarınızı girin
```

### 5. MongoDB'yi Başlatın
```bash
# MongoDB'nin çalıştığından emin olun
mongod --dbpath data/db
```

### 6. Uygulamayı Başlatın
```bash
python app.py
```

Uygulama varsayılan olarak `http://localhost:5000` adresinde çalışacaktır.

## 📁 Proje Yapısı

```
kocaeli-haber-harita/
├── app.py                    # Ana uygulama dosyası
├── config/
│   ├── __init__.py
│   └── settings.py           # Yapılandırma ayarları
├── scraper/
│   ├── __init__.py
│   ├── base_scraper.py       # Temel scraper sınıfı
│   ├── cagdas_kocaeli.py     # Çağdaş Kocaeli scraper
│   ├── ozgur_kocaeli.py      # Özgür Kocaeli scraper
│   ├── ses_kocaeli.py        # Ses Kocaeli scraper
│   ├── yeni_kocaeli.py       # Yeni Kocaeli scraper
│   └── bizim_yaka.py         # Bizim Yaka scraper
├── processing/
│   ├── __init__.py
│   ├── cleaner.py            # Veri temizleme
│   ├── classifier.py         # Haber sınıflandırma
│   ├── location_extractor.py # Konum çıkarımı
│   └── similarity.py         # Benzerlik analizi
├── database/
│   ├── __init__.py
│   └── mongodb.py            # MongoDB bağlantısı
├── geocoding/
│   ├── __init__.py
│   └── geocoder.py           # Geocoding işlemleri
├── static/
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── app.js
│   └── img/
├── templates/
│   └── index.html
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## 📄 Lisans

Bu proje eğitim amaçlı geliştirilmiştir.

## 👤 Geliştirici

- **Selim Doğan** - Kocaeli Üniversitesi, Bilgisayar Mühendisliği
