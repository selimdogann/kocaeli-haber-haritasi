"""
Kocaeli Haber Haritası - Ana Uygulama Dosyası

Flask web uygulamasını başlatır ve tüm modülleri entegre eder.
"""

from flask import Flask, render_template
from flask_cors import CORS
from api.routes import api_bp
from config.settings import Config
import logging

# Loglama yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def create_app():
    """Flask uygulama fabrikası."""
    app = Flask(__name__)

    # CORS yapılandırması
    CORS(app)

    # API Blueprint'i kaydet
    app.register_blueprint(api_bp)

    # Ana sayfa rotası
    @app.route("/")
    def index():
        """Ana sayfa - Harita arayüzü."""
        return render_template(
            "index.html",
            google_maps_api_key=Config.GOOGLE_MAPS_API_KEY,
            kocaeli_center_lat=Config.KOCAELI_CENTER_LAT,
            kocaeli_center_lng=Config.KOCAELI_CENTER_LNG,
            news_types=Config.NEWS_TYPES,
            districts=Config.KOCAELI_DISTRICTS,
        )

    @app.errorhandler(404)
    def not_found(error):
        """404 hata sayfası."""
        return {"hata": "Sayfa bulunamadı"}, 404

    @app.errorhandler(500)
    def internal_error(error):
        """500 hata sayfası."""
        return {"hata": "Sunucu hatası"}, 500

    return app


if __name__ == "__main__":
    app = create_app()
    logger.info(
        f"🚀 Kocaeli Haber Haritası başlatılıyor... "
        f"(Port: {Config.FLASK_PORT})"
    )
    app.run(
        host="0.0.0.0",
        port=Config.FLASK_PORT,
        debug=Config.FLASK_DEBUG,
    )
