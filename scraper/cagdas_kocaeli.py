"""
Kocaeli Haber Haritası - Çağdaş Kocaeli Scraper

Kaynak: https://www.cagdaskocaeli.com.tr
"""

import logging
from scraper.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class CagdasKocaeliScraper(BaseScraper):
    """Çağdaş Kocaeli haber sitesi scraper'ı."""

    def __init__(self):
        super().__init__(
            kaynak_adi="Çağdaş Kocaeli",
            base_url="https://www.cagdaskocaeli.com.tr",
        )
        # Haber kategori sayfaları
        self.kategori_urls = [
            f"{self.base_url}/kategori/gundem",
            f"{self.base_url}/kategori/asayis",
            f"{self.base_url}/kategori/yasam",
            f"{self.base_url}/kategori/kultur-sanat",
        ]

    def haber_listesi_getir(self) -> list:
        """Çağdaş Kocaeli'den haber linklerini çeker."""
        linkler = []

        for kategori_url in self.kategori_urls:
            try:
                soup = self.sayfa_getir(kategori_url)
                if not soup:
                    continue

                # Haber kartlarındaki linkleri bul
                # Farklı CSS seçiciler denenecek
                seciciler = [
                    "article a[href]",
                    ".news-card a[href]",
                    ".post-title a[href]",
                    ".category-news a[href]",
                    "h2 a[href]",
                    "h3 a[href]",
                    ".card a[href]",
                    ".listing a[href]",
                ]

                for secici in seciciler:
                    elemeler = soup.select(secici)
                    for eleman in elemeler:
                        href = eleman.get("href", "")
                        if href and href != "#":
                            # Tam URL oluştur
                            if href.startswith("/"):
                                href = f"{self.base_url}{href}"
                            elif not href.startswith("http"):
                                href = f"{self.base_url}/{href}"

                            if (
                                href not in linkler
                                and self.base_url in href
                                and "/kategori/" not in href
                                and "/etiket/" not in href
                                and "/yazar/" not in href
                            ):
                                linkler.append(href)

                    if linkler:
                        break

            except Exception as e:
                logger.error(f"Çağdaş Kocaeli kategori hatası: {kategori_url} - {e}")

        return linkler[:50]  # En fazla 50 haber

    def haber_detay_getir(self, url: str) -> dict:
        """Çağdaş Kocaeli haber detayını çeker."""
        soup = self.sayfa_getir(url)
        if not soup:
            return None

        haber = {}

        try:
            # Başlık
            baslik_seciciler = [
                "h1.post-title", "h1.entry-title", "h1.news-title",
                "h1.title", "article h1", "h1",
            ]
            for secici in baslik_seciciler:
                baslik = soup.select_one(secici)
                if baslik:
                    haber["baslik"] = baslik.get_text(strip=True)
                    break

            # İçerik
            icerik_seciciler = [
                ".post-content", ".entry-content", ".news-content",
                ".content", "article .text", ".article-body",
                ".news-detail-content", ".detail-content",
            ]
            for secici in icerik_seciciler:
                icerik = soup.select_one(secici)
                if icerik:
                    # Script ve style etiketlerini kaldır
                    for tag in icerik.find_all(["script", "style", "iframe"]):
                        tag.decompose()
                    haber["icerik"] = icerik.get_text(separator=" ", strip=True)
                    break

            # Tarih
            tarih_seciciler = [
                "time[datetime]", ".post-date", ".entry-date",
                ".news-date", ".date", "span.date", ".published",
            ]
            for secici in tarih_seciciler:
                tarih = soup.select_one(secici)
                if tarih:
                    tarih_metni = tarih.get("datetime") or tarih.get_text(strip=True)
                    haber["yayin_tarihi"] = self.tarih_ayristir(tarih_metni)
                    break

            if not haber.get("yayin_tarihi"):
                # Meta tag'lardan tarih çekmeyi dene
                meta_tarih = soup.find("meta", property="article:published_time")
                if meta_tarih:
                    haber["yayin_tarihi"] = self.tarih_ayristir(
                        meta_tarih.get("content", "")
                    )

        except Exception as e:
            logger.error(f"Çağdaş Kocaeli detay hatası: {url} - {e}")

        return haber if haber.get("baslik") else None
