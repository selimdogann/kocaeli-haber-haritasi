"""
Kocaeli Haber Haritası - Temel Scraper Sınıfı

Tüm haber sitesi scraper'larının miras aldığı soyut temel sınıf.
Her haber sitesi için ortak işlevsellik sağlar.
Cloudflare korumalı siteler için Playwright (headless) desteği içerir.
"""

import requests
from bs4 import BeautifulSoup
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from config.settings import Config

logger = logging.getLogger(__name__)

# Playwright browser ve context singleton
_playwright_instance = None
_playwright_browser = None
_playwright_basarisiz = False


def _playwright_browser_olustur():
    """Playwright Chromium browser başlatır (headless singleton)."""
    global _playwright_instance, _playwright_browser, _playwright_basarisiz

    if _playwright_basarisiz:
        return None

    if _playwright_browser is not None:
        try:
            # Browser hala açık mı kontrol et
            _playwright_browser.contexts
            return _playwright_browser
        except Exception:
            _playwright_browser = None

    try:
        from playwright.sync_api import sync_playwright

        _playwright_instance = sync_playwright().start()
        _playwright_browser = _playwright_instance.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        logger.info("Playwright Chromium başlatıldı (headless).")
        return _playwright_browser
    except Exception as e:
        logger.error(f"Playwright başlatma hatası: {e}")
        _playwright_basarisiz = True
        return None


def selenium_driver_kapat():
    """Playwright browser'ı kapatır (eski isim uyumluluğu için)."""
    global _playwright_instance, _playwright_browser, _playwright_basarisiz
    if _playwright_browser is not None:
        try:
            _playwright_browser.close()
        except Exception:
            pass
        _playwright_browser = None
    if _playwright_instance is not None:
        try:
            _playwright_instance.stop()
        except Exception:
            pass
        _playwright_instance = None
    _playwright_basarisiz = False


class BaseScraper(ABC):
    """Tüm scraper'ların temel sınıfı."""

    # Alt sınıflar True yaparak Selenium kullanımını etkinleştirir
    CLOUDFLARE_KORUMALI = False

    def __init__(self, kaynak_adi: str, base_url: str):
        """
        Temel scraper'ı başlatır.

        Args:
            kaynak_adi: Haber kaynağı adı
            base_url: Haber sitesinin ana URL'si
        """
        self.kaynak_adi = kaynak_adi
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        })
        self.timeout = Config.REQUEST_TIMEOUT
        self.gecikme = Config.REQUEST_DELAY

    def sayfa_getir(self, url: str) -> BeautifulSoup:
        """
        Verilen URL'den HTML içeriğini çeker ve BeautifulSoup nesnesi döndürür.
        Cloudflare korumalı siteler için otomatik olarak Playwright kullanır.

        Args:
            url: Çekilecek sayfa URL'si

        Returns:
            BeautifulSoup: Ayrıştırılmış HTML nesnesi veya None
        """
        if self.CLOUDFLARE_KORUMALI:
            return self._sayfa_getir_playwright(url)
        return self._sayfa_getir_requests(url)

    def _sayfa_getir_requests(self, url: str) -> BeautifulSoup:
        """Standart requests kütüphanesi ile sayfa çeker."""
        try:
            if self.gecikme > 0:
                time.sleep(self.gecikme)

            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()

            if response.encoding and response.encoding.lower() != "iso-8859-1":
                pass
            elif response.apparent_encoding:
                response.encoding = response.apparent_encoding
            else:
                response.encoding = "utf-8"

            return BeautifulSoup(response.text, "lxml")

        except requests.exceptions.Timeout:
            logger.error(f"Zaman aşımı: {url}")
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP hatası ({e.response.status_code}): {url}")
        except requests.exceptions.ConnectionError:
            logger.error(f"Bağlantı hatası: {url}")
        except Exception as e:
            logger.error(f"Sayfa çekme hatası: {url} - {e}")

        return None

    def _sayfa_getir_playwright(self, url: str) -> BeautifulSoup:
        """Playwright ile sayfa çeker (headless Cloudflare bypass)."""
        browser = _playwright_browser_olustur()
        if not browser:
            logger.warning(f"Playwright kullanılamıyor, requests ile deneniyor: {url}")
            return self._sayfa_getir_requests(url)

        try:
            if self.gecikme > 0:
                time.sleep(self.gecikme)

            page = browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            )
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            # Cloudflare challenge için kısa bekleme
            page.wait_for_timeout(2000)

            html = page.content()
            page.close()

            if html and len(html) > 1000:
                return BeautifulSoup(html, "lxml")

        except Exception as e:
            logger.error(f"Playwright sayfa çekme hatası: {url} - {e}")

        return None

    def son_n_gun_icinde_mi(self, tarih: datetime, gun: int = None) -> bool:
        """
        Verilen tarihin son N gün içinde olup olmadığını kontrol eder.

        Args:
            tarih: Kontrol edilecek tarih
            gun: Gün sayısı (varsayılan: Config.SCRAPING_DAYS)

        Returns:
            bool: Son N gün içindeyse True
        """
        if gun is None:
            gun = Config.SCRAPING_DAYS

        if tarih is None:
            return False

        sinir_tarih = (
            datetime.now() - timedelta(days=gun - 1)
        ).replace(hour=0, minute=0, second=0, microsecond=0)
        return tarih >= sinir_tarih

    def tarih_ayristir(self, tarih_metni: str) -> datetime:
        """
        Farklı tarih formatlarını ayrıştırır.

        Args:
            tarih_metni: Tarih metni

        Returns:
            datetime: Ayrıştırılmış tarih nesnesi veya None
        """
        if not tarih_metni:
            return None

        tarih_metni = tarih_metni.strip()

        # Timezone bilgisini temizle (+03:00, +0300, Z)
        import re as _re
        tarih_metni = _re.sub(r'[+-]\d{2}:\d{2}$', '', tarih_metni)
        tarih_metni = _re.sub(r'[+-]\d{4}$', '', tarih_metni)
        tarih_metni = _re.sub(r'Z$', '', tarih_metni)
        tarih_metni = tarih_metni.strip()

        # Önce standart ISO/sayısal formatları dene
        iso_formatlar = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%d.%m.%Y %H:%M",
            "%d.%m.%Y",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
        ]

        for fmt in iso_formatlar:
            try:
                return datetime.strptime(tarih_metni, fmt)
            except ValueError:
                continue

        # Türkçe ay isimleri dönüşümü (hem tam hem kısaltma)
        turkce_aylar = {
            "ocak": "01", "oca": "01",
            "şubat": "02", "şub": "02",
            "mart": "03", "mar": "03",
            "nisan": "04", "nis": "04",
            "mayıs": "05", "may": "05",
            "haziran": "06", "haz": "06",
            "temmuz": "07", "tem": "07",
            "ağustos": "08", "ağu": "08",
            "eylül": "09", "eyl": "09",
            "ekim": "10", "eki": "10",
            "kasım": "11", "kas": "11",
            "aralık": "12", "ara": "12",
        }

        # Metin tabanlı tarihlerde " - " ayırıcısını boşluğa çevir
        tarih_temiz = _re.sub(r'\s+-\s+', ' ', tarih_metni)

        for ay_adi, ay_no in sorted(turkce_aylar.items(), key=lambda x: -len(x[0])):
            if ay_adi in tarih_temiz.lower():
                tarih_temiz = _re.sub(
                    r'(?i)\b' + _re.escape(ay_adi) + r'\b',
                    ay_no,
                    tarih_temiz,
                )
                break

        # Sayısal hale gelmiş metin tabanlı formatlar
        metin_formatlar = [
            "%d %m %Y %H:%M",
            "%d %m %Y",
        ]

        for fmt in metin_formatlar:
            try:
                return datetime.strptime(tarih_temiz.strip(), fmt)
            except ValueError:
                continue

        # "X saat önce", "X gün önce" gibi göreceli tarihler
        try:
            return self._goreceli_tarih_ayristir(tarih_metni)
        except Exception:
            pass

        logger.warning(f"Tarih ayrıştırılamadı: {tarih_metni}")
        return None

    def _goreceli_tarih_ayristir(self, metin: str) -> datetime:
        """Göreceli tarih ifadelerini ayrıştırır."""
        import re

        metin = metin.lower().strip()
        simdi = datetime.now()

        # "X dakika önce"
        dakika = re.search(r"(\d+)\s*dakika", metin)
        if dakika:
            return simdi - timedelta(minutes=int(dakika.group(1)))

        # "X saat önce"
        saat = re.search(r"(\d+)\s*saat", metin)
        if saat:
            return simdi - timedelta(hours=int(saat.group(1)))

        # "X gün önce"
        gun = re.search(r"(\d+)\s*gün", metin)
        if gun:
            return simdi - timedelta(days=int(gun.group(1)))

        # "bugün"
        if "bugün" in metin:
            return simdi

        # "dün"
        if "dün" in metin:
            return simdi - timedelta(days=1)

        return None

    @abstractmethod
    def haber_listesi_getir(self) -> list:
        """
        Haber sitesinden haber URL listesini çeker.
        Her alt sınıf kendi implementasyonunu sağlamalıdır.

        Returns:
            list: Haber URL'lerinin listesi
        """
        pass

    @abstractmethod
    def haber_detay_getir(self, url: str) -> dict:
        """
        Tek bir haberin detay bilgilerini çeker.
        Her alt sınıf kendi implementasyonunu sağlamalıdır.

        Args:
            url: Haber detay sayfası URL'si

        Returns:
            dict: {
                "baslik": str,
                "icerik": str,
                "yayin_tarihi": datetime,
                "haber_linki": str,
                "kaynak_site": str,
            }
        """
        pass

    def tum_haberleri_cek(self) -> list:
        """
        Kaynaktaki tüm güncel haberleri çeker.

        Returns:
            list: Haber sözlükleri listesi
        """
        logger.info(f"📰 {self.kaynak_adi} - Haberler çekiliyor...")
        haberler = []

        try:
            haber_linkleri = self.haber_listesi_getir()

            # Performans için kaynak başına üst sınır uygula
            max_link = getattr(Config, "SCRAPER_MAX_LINKS_PER_SOURCE", 50)
            if isinstance(max_link, int) and max_link > 0:
                haber_linkleri = haber_linkleri[:max_link]

            logger.info(
                f"{self.kaynak_adi} - {len(haber_linkleri)} haber linki bulundu."
            )

            def _tek_haber_cek(link: str) -> dict:
                try:
                    haber = self.haber_detay_getir(link)
                    if haber and haber.get("baslik"):
                        # Tarihi olmayan haberler atlanır (son 3 gün zorunluluğu)
                        if not haber.get("yayin_tarihi"):
                            return None

                        # Son N gün dışındaki haberler atlanır
                        if not self.son_n_gun_icinde_mi(haber["yayin_tarihi"]):
                            return None

                        haber["kaynak_site"] = self.kaynak_adi
                        haber["haber_linki"] = link
                        haber["diger_kaynaklar"] = []
                        return haber

                except Exception as e:
                    logger.error(
                        f"{self.kaynak_adi} - Haber detay hatası: {link} - {e}"
                    )
                    return None

                return None

            max_workers = max(1, int(getattr(Config, "SCRAPER_MAX_WORKERS", 8)))

            # Cloudflare korumalı siteler Playwright kullandığı için seri çalışmalı
            if self.CLOUDFLARE_KORUMALI or max_workers == 1 or len(haber_linkleri) < 6:
                for link in haber_linkleri:
                    sonuc = _tek_haber_cek(link)
                    if sonuc:
                        haberler.append(sonuc)
            else:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    gelecektekiler = [executor.submit(_tek_haber_cek, link) for link in haber_linkleri]
                    for gelecek in as_completed(gelecektekiler):
                        sonuc = gelecek.result()
                        if sonuc:
                            haberler.append(sonuc)

        except Exception as e:
            logger.error(f"{self.kaynak_adi} - Genel hata: {e}")

        logger.info(f"✅ {self.kaynak_adi} - {len(haberler)} haber çekildi.")
        return haberler
