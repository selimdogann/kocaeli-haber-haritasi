"""
Kocaeli Haber Haritası - MongoDB Veritabanı Yönetimi

Bu modül MongoDB bağlantısını yönetir ve haber verilerinin
CRUD (Oluşturma, Okuma, Güncelleme, Silme) işlemlerini sağlar.
"""

from pymongo import MongoClient, DESCENDING
from pymongo.errors import DuplicateKeyError, ConnectionFailure
from datetime import datetime, timedelta
from config.settings import Config
import logging

# Loglama yapılandırması
logger = logging.getLogger(__name__)


class MongoDB:
    """MongoDB veritabanı yönetim sınıfı."""

    _instance = None

    def __new__(cls):
        """Singleton pattern - Tek bir MongoDB bağlantısı sağlar."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """MongoDB bağlantısını başlatır."""
        if self._initialized:
            return

        try:
            self.client = MongoClient(
                Config.MONGODB_URI,
                serverSelectionTimeoutMS=5000,
            )
            # Bağlantıyı test et
            self.client.admin.command("ping")
            self.db = self.client[Config.MONGODB_DB_NAME]
            self._setup_collections()
            self._create_indexes()
            self._initialized = True
            logger.info("MongoDB bağlantısı başarıyla kuruldu.")
        except ConnectionFailure as e:
            logger.error(f"MongoDB bağlantı hatası: {e}")
            raise

    def _setup_collections(self):
        """Veritabanı koleksiyonlarını ayarlar."""
        self.news_collection = self.db["haberler"]
        self.locations_collection = self.db["konumlar"]

    def _create_indexes(self):
        """Performans için gerekli indexleri oluşturur."""
        # Haber koleksiyonu indexleri
        self.news_collection.create_index("haber_linki", unique=True)
        self.news_collection.create_index("haber_turu")
        self.news_collection.create_index("yayin_tarihi")
        self.news_collection.create_index("kaynak_site")
        self.news_collection.create_index([("konum_geojson", "2dsphere")])
        self.news_collection.create_index(
            [("yayin_tarihi", DESCENDING), ("haber_turu", 1)]
        )

        # Konum koleksiyonu indexleri - aynı konum için tekrar API çağrısı önlenir
        self.locations_collection.create_index("konum_metni", unique=True)
        self.locations_collection.create_index([("konum_geojson", "2dsphere")])

        logger.info("Veritabanı indexleri oluşturuldu.")

    # ==========================================
    # HABER CRUD İŞLEMLERİ
    # ==========================================

    def haber_ekle(self, haber_verisi: dict) -> bool:
        """
        Yeni bir haber kaydı ekler.
        Aynı haber linki varsa ekleme yapmaz (duplicate kontrolü).

        Args:
            haber_verisi: Haber bilgilerini içeren sözlük

        Returns:
            bool: Ekleme başarılı ise True, değilse False
        """
        try:
            self._geojson_alanlarini_hazirla(haber_verisi)
            haber_verisi["olusturma_tarihi"] = datetime.now()
            haber_verisi["guncelleme_tarihi"] = datetime.now()
            self.news_collection.insert_one(haber_verisi)
            logger.info(f"Haber eklendi: {haber_verisi.get('baslik', 'Başlıksız')}")
            return True
        except DuplicateKeyError:
            logger.warning(
                f"Tekrar eden haber atlandı: {haber_verisi.get('haber_linki', '')}"
            )
            return False
        except Exception as e:
            logger.error(f"Haber ekleme hatası: {e}")
            return False

    def haber_guncelle(self, haber_linki: str, guncelleme: dict) -> bool:
        """
        Mevcut bir haberi günceller.

        Args:
            haber_linki: Güncellencek haberin linki
            guncelleme: Güncellenecek alanları içeren sözlük

        Returns:
            bool: Güncelleme başarılı ise True
        """
        try:
            self._geojson_alanlarini_hazirla(guncelleme)
            guncelleme["guncelleme_tarihi"] = datetime.now()
            sonuc = self.news_collection.update_one(
                {"haber_linki": haber_linki},
                {"$set": guncelleme},
            )
            return sonuc.modified_count > 0
        except Exception as e:
            logger.error(f"Haber güncelleme hatası: {e}")
            return False

    def haber_kaynak_ekle(self, haber_linki: str, yeni_kaynak: dict) -> bool:
        """
        Aynı haberin farklı kaynağını ekler.
        Birden fazla kaynakta yer alan haberler için kullanılır.

        Args:
            haber_linki: Ana haberin linki
            yeni_kaynak: Yeni kaynak bilgisi {site_adi, link}

        Returns:
            bool: Ekleme başarılı ise True
        """
        try:
            sonuc = self.news_collection.update_one(
                {"haber_linki": haber_linki},
                {
                    "$addToSet": {"diger_kaynaklar": yeni_kaynak},
                    "$set": {"guncelleme_tarihi": datetime.now()},
                },
            )
            return sonuc.modified_count > 0
        except Exception as e:
            logger.error(f"Kaynak ekleme hatası: {e}")
            return False

    def tum_haberleri_getir(self, filtreler: dict = None) -> list:
        """
        Tüm haberleri getirir, opsiyonel filtreleme ile.

        Args:
            filtreler: MongoDB sorgu filtresi

        Returns:
            list: Haber listesi
        """
        try:
            sorgu = filtreler or {}
            haberler = list(
                self.news_collection.find(sorgu).sort("yayin_tarihi", DESCENDING)
            )
            # ObjectId'yi string'e çevir
            for haber in haberler:
                haber["_id"] = str(haber["_id"])
            return haberler
        except Exception as e:
            logger.error(f"Haber getirme hatası: {e}")
            return []

    def haberleri_filtrele(
        self,
        haber_turu: str = None,
        ilce: str = None,
        baslangic_tarihi: str = None,
        bitis_tarihi: str = None,
    ) -> list:
        """
        Haberleri türe, ilçeye ve tarih aralığına göre filtreler.

        Args:
            haber_turu: Haber türü filtresi
            ilce: İlçe filtresi
            baslangic_tarihi: Başlangıç tarihi (YYYY-MM-DD)
            bitis_tarihi: Bitiş tarihi (YYYY-MM-DD)

        Returns:
            list: Filtrelenmiş haber listesi
        """
        filtre = {}

        if haber_turu:
            # Virgülle ayrılmış birden fazla tür desteği
            turler = [t.strip() for t in haber_turu.split(",") if t.strip()]
            if len(turler) == 1:
                filtre["haber_turu"] = turler[0]
            elif len(turler) > 1:
                filtre["haber_turu"] = {"$in": turler}

        if ilce:
            filtre["ilce"] = {"$regex": ilce, "$options": "i"}

        if baslangic_tarihi or bitis_tarihi:
            tarih_filtre = {}
            if baslangic_tarihi:
                tarih_filtre["$gte"] = datetime.strptime(
                    baslangic_tarihi, "%Y-%m-%d"
                )
            if bitis_tarihi:
                tarih_filtre["$lte"] = datetime.strptime(
                    bitis_tarihi, "%Y-%m-%d"
                ) + timedelta(days=1)
            filtre["yayin_tarihi"] = tarih_filtre

        # Sadece konumu olan haberleri getir (haritada göstermek için)
        filtre["konum_geojson"] = {"$exists": True}

        return self.tum_haberleri_getir(filtre)

    def haber_linki_var_mi(self, haber_linki: str) -> bool:
        """
        Verilen haber linkinin veritabanında olup olmadığını kontrol eder.

        Args:
            haber_linki: Kontrol edilecek haber linki

        Returns:
            bool: Link varsa True
        """
        return self.news_collection.count_documents(
            {"haber_linki": haber_linki}
        ) > 0

    def tum_haber_metinlerini_getir(self) -> list:
        """
        Tüm haberlerin başlık ve içeriklerini getirir.
        Benzerlik analizi için kullanılır.

        Returns:
            list: [{_id, baslik, icerik, haber_linki}, ...]
        """
        try:
            return list(
                self.news_collection.find(
                    {},
                    {"baslik": 1, "icerik": 1, "haber_linki": 1},
                )
            )
        except Exception as e:
            logger.error(f"Haber metinleri getirme hatası: {e}")
            return []

    # ==========================================
    # KONUM CACHE İŞLEMLERİ
    # ==========================================

    def konum_kaydet(self, konum_metni: str, enlem: float, boylam: float) -> bool:
        """
        Geocoding sonucunu cache'ler. Aynı konum için tekrar API çağrısı önlenir.

        Args:
            konum_metni: Konum metni
            enlem: Enlem koordinatı
            boylam: Boylam koordinatı

        Returns:
            bool: Kayıt başarılı ise True
        """
        try:
            konum_geojson = self._geojson_nokta_olustur(enlem, boylam)
            self.locations_collection.update_one(
                {"konum_metni": konum_metni},
                {
                    "$set": {
                        "konum_metni": konum_metni,
                        "enlem": enlem,
                        "boylam": boylam,
                        "konum_geojson": konum_geojson,
                        "guncelleme_tarihi": datetime.now(),
                    }
                },
                upsert=True,
            )
            return True
        except Exception as e:
            logger.error(f"Konum kaydetme hatası: {e}")
            return False

    def konum_getir(self, konum_metni: str) -> dict:
        """
        Cache'lenmiş konum bilgisini getirir.

        Args:
            konum_metni: Aranacak konum metni

        Returns:
            dict: {enlem, boylam} veya None
        """
        try:
            sonuc = self.locations_collection.find_one(
                {"konum_metni": konum_metni}
            )
            if sonuc:
                return {"enlem": sonuc["enlem"], "boylam": sonuc["boylam"]}
            return None
        except Exception as e:
            logger.error(f"Konum getirme hatası: {e}")
            return None

    # ==========================================
    # İSTATİSTİK İŞLEMLERİ
    # ==========================================

    def istatistikleri_getir(self) -> dict:
        """
        Genel istatistikleri döndürür.

        Returns:
            dict: İstatistik bilgileri
        """
        try:
            toplam_haber = self.news_collection.count_documents({})
            konumlu_haber = self.news_collection.count_documents(
                {"konum_geojson": {"$exists": True}}
            )

            # Haber türlerine göre dağılım
            tur_dagilimi = {}
            for tur in Config.NEWS_TYPES:
                tur_dagilimi[tur] = self.news_collection.count_documents(
                    {"haber_turu": tur}
                )

            # Kaynak sitelere göre dağılım
            kaynak_dagilimi = {}
            for kaynak_id, kaynak_bilgi in Config.NEWS_SOURCES.items():
                kaynak_dagilimi[kaynak_bilgi["name"]] = (
                    self.news_collection.count_documents(
                        {"kaynak_site": kaynak_bilgi["name"]}
                    )
                )

            return {
                "toplam_haber": toplam_haber,
                "konumlu_haber": konumlu_haber,
                "tur_dagilimi": tur_dagilimi,
                "kaynak_dagilimi": kaynak_dagilimi,
            }
        except Exception as e:
            logger.error(f"İstatistik getirme hatası: {e}")
            return {}

    def veritabanini_temizle(self):
        """Tüm verileri siler (geliştirme amaçlı)."""
        self.news_collection.delete_many({})
        self.locations_collection.delete_many({})
        logger.warning("Veritabanı tamamen temizlendi!")

    def baglantiyi_kapat(self):
        """MongoDB bağlantısını kapatır."""
        if self.client:
            self.client.close()
            logger.info("MongoDB bağlantısı kapatıldı.")

    def _geojson_alanlarini_hazirla(self, veri: dict):
        """Haber belgelerinde GeoJSON alanını enlem/boylam ile senkronize eder."""
        if not isinstance(veri, dict):
            return

        enlem = veri.get("enlem")
        boylam = veri.get("boylam")
        if enlem is None or boylam is None:
            return

        veri["konum_geojson"] = self._geojson_nokta_olustur(enlem, boylam)

    @staticmethod
    def _geojson_nokta_olustur(enlem: float, boylam: float) -> dict:
        """MongoDB 2dsphere uyumlu GeoJSON Point nesnesi döndürür."""
        return {
            "type": "Point",
            "coordinates": [boylam, enlem],
        }
