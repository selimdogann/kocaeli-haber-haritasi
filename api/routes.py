"""
Kocaeli Haber Haritası - Flask API Rotaları

REST API endpoint'leri:
- GET  /api/haberler         → Tüm haberleri getir (filtreli)
- GET  /api/haberler/<id>    → Tek haber detayı
- POST /api/scrape           → Scraping işlemini başlat
- GET  /api/istatistikler    → Genel istatistikler
- GET  /api/haber-turleri    → Haber türleri listesi
- GET  /api/ilceler          → İlçe listesi
"""

from flask import Blueprint, jsonify, request
import logging
from database.mongodb import MongoDB
from scraper.scraper_manager import ScraperManager, scrape_progress
from config.settings import Config

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__, url_prefix="/api")


def get_db():
    """MongoDB bağlantısını döndürür."""
    try:
        return MongoDB()
    except Exception as e:
        logger.error(f"Veritabanı bağlantı hatası: {e}")
        return None


def _haber_formatla(haber: dict) -> dict:
    """
    MongoDB'den gelen haber verisini frontend'in beklediği formata dönüştürür.

    MongoDB alanları → Frontend beklentileri:
      enlem/boylam → koordinatlar.lat/lng
      ilce/mahalle → konum_bilgisi.ilce/mahalle
      yayin_tarihi → tarih
      kaynak_site → kaynak_adi
    """
    # Koordinat yapısı
    haber["koordinatlar"] = None
    if haber.get("enlem") and haber.get("boylam"):
        haber["koordinatlar"] = {
            "lat": haber["enlem"],
            "lng": haber["boylam"],
        }

    # Konum bilgisi yapısı
    haber["konum_bilgisi"] = {
        "ilce": haber.get("ilce"),
        "mahalle": haber.get("mahalle"),
    }

    # Tarih alanı (frontend 'tarih' bekliyor)
    if haber.get("yayin_tarihi"):
        try:
            haber["tarih"] = haber["yayin_tarihi"].isoformat()
            haber["yayin_tarihi"] = haber["yayin_tarihi"].isoformat()
        except AttributeError:
            haber["tarih"] = str(haber["yayin_tarihi"])

    # Kaynak adı (frontend 'kaynak_adi' bekliyor)
    if haber.get("kaynak_site") and not haber.get("kaynak_adi"):
        haber["kaynak_adi"] = haber["kaynak_site"]

    # Çoklu kaynak bilgisi (diger_kaynaklar → kaynaklar dizisi)
    kaynaklar = []
    # Ana kaynak
    kaynaklar.append({
        "kaynak_adi": haber.get("kaynak_site", ""),
        "link": haber.get("haber_linki", ""),
    })
    # Diğer kaynaklar (benzerlik analizi ile eklenenler)
    if haber.get("diger_kaynaklar"):
        for kaynak in haber["diger_kaynaklar"]:
            kaynaklar.append({
                "kaynak_adi": kaynak.get("site_adi", ""),
                "link": kaynak.get("link", ""),
            })
    haber["kaynaklar"] = kaynaklar

    # datetime nesnelerini string'e çevir
    if haber.get("olusturma_tarihi"):
        try:
            haber["olusturma_tarihi"] = haber["olusturma_tarihi"].isoformat()
        except AttributeError:
            pass
    if haber.get("guncelleme_tarihi"):
        try:
            haber["guncelleme_tarihi"] = haber["guncelleme_tarihi"].isoformat()
        except AttributeError:
            pass

    return haber


@api_bp.route("/haberler", methods=["GET"])
def haberleri_getir():
    """
    Haberleri getirir. Filtreleme parametreleri:
    - haber_turu: Haber türü filtresi
    - ilce: İlçe filtresi
    - baslangic_tarihi: Başlangıç tarihi (YYYY-MM-DD)
    - bitis_tarihi: Bitiş tarihi (YYYY-MM-DD)
    - sadece_konumlu: Sadece konumu olan haberleri getir (varsayılan: true)
    """
    try:
        db = get_db()
        if not db:
            return jsonify({"hata": "Veritabanı bağlantı hatası"}), 500

        # Filtre parametrelerini al
        haber_turu = request.args.get("haber_turu")
        ilce = request.args.get("ilce")
        baslangic_tarihi = request.args.get("baslangic_tarihi")
        bitis_tarihi = request.args.get("bitis_tarihi")
        sadece_konumlu = request.args.get("sadece_konumlu", "true").lower() == "true"

        if sadece_konumlu:
            haberler = db.haberleri_filtrele(
                haber_turu=haber_turu,
                ilce=ilce,
                baslangic_tarihi=baslangic_tarihi,
                bitis_tarihi=bitis_tarihi,
            )
        else:
            filtre = {}
            if haber_turu:
                filtre["haber_turu"] = haber_turu
            if ilce:
                filtre["konum_metni"] = {"$regex": ilce, "$options": "i"}
            haberler = db.tum_haberleri_getir(filtre)

        # Haberleri frontend formatına dönüştür
        haberler = [_haber_formatla(h) for h in haberler]

        return jsonify({
            "basarili": True,
            "toplam": len(haberler),
            "haberler": haberler,
        })

    except Exception as e:
        logger.error(f"Haber getirme hatası: {e}")
        return jsonify({"hata": str(e)}), 500


@api_bp.route("/haberler/<haber_id>", methods=["GET"])
def haber_detay(haber_id):
    """Tek bir haberin detayını döndürür."""
    try:
        from bson import ObjectId

        db = get_db()
        if not db:
            return jsonify({"hata": "Veritabanı bağlantı hatası"}), 500

        haber = db.news_collection.find_one({"_id": ObjectId(haber_id)})
        if not haber:
            return jsonify({"hata": "Haber bulunamadı"}), 404

        haber["_id"] = str(haber["_id"])
        haber = _haber_formatla(haber)

        return jsonify({"basarili": True, "haber": haber})

    except Exception as e:
        logger.error(f"Haber detay hatası: {e}")
        return jsonify({"hata": str(e)}), 500


@api_bp.route("/scrape", methods=["POST"])
def scraping_baslat():
    """
    Web scraping işlemini başlatır.
    Tüm kaynaklardan haber çeker, işler ve kaydeder.
    """
    try:
        logger.info("🚀 Scraping işlemi başlatıldı...")
        manager = ScraperManager()
        rapor = manager.tum_kaynaklardan_cek()

        return jsonify({
            "basarili": True,
            "mesaj": "Scraping işlemi tamamlandı",
            "rapor": rapor,
        })

    except Exception as e:
        logger.error(f"Scraping hatası: {e}")
        return jsonify({"hata": str(e)}), 500


@api_bp.route("/scrape/progress", methods=["GET"])
def scrape_ilerleme():
    """Scraping işleminin ilerleme durumunu döndürür."""
    return jsonify(scrape_progress)


@api_bp.route("/istatistikler", methods=["GET"])
def istatistikleri_getir():
    """Genel istatistikleri döndürür."""
    try:
        db = get_db()
        if not db:
            return jsonify({"hata": "Veritabanı bağlantı hatası"}), 500

        istatistikler = db.istatistikleri_getir()

        return jsonify({
            "basarili": True,
            "istatistikler": istatistikler,
        })

    except Exception as e:
        logger.error(f"İstatistik hatası: {e}")
        return jsonify({"hata": str(e)}), 500


@api_bp.route("/haber-turleri", methods=["GET"])
def haber_turleri():
    """Haber türleri listesini döndürür."""
    return jsonify({
        "basarili": True,
        "haber_turleri": Config.NEWS_TYPES,
    })


@api_bp.route("/ilceler", methods=["GET"])
def ilceler():
    """Kocaeli ilçeleri listesini döndürür."""
    return jsonify({
        "basarili": True,
        "ilceler": Config.KOCAELI_DISTRICTS,
    })


@api_bp.route("/temizle", methods=["POST"])
def veritabani_temizle():
    """Veritabanını temizler (geliştirme amaçlı)."""
    try:
        db = get_db()
        if not db:
            return jsonify({"hata": "Veritabanı bağlantı hatası"}), 500

        db.veritabanini_temizle()

        return jsonify({
            "basarili": True,
            "mesaj": "Veritabanı temizlendi",
        })

    except Exception as e:
        logger.error(f"Temizleme hatası: {e}")
        return jsonify({"hata": str(e)}), 500
