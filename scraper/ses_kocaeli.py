"""
Kocaeli Haber Haritası - Ses Kocaeli Scraper

Kaynak: https://www.seskocaeli.com
"""

import logging
from scraper.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class SesKocaeliScraper(BaseScraper):
    """Ses Kocaeli haber sitesi scraper'ı."""

    def __init__(self):
        super().__init__(
            kaynak_adi="Ses Kocaeli",
            base_url="https://www.seskocaeli.com",
        )
        self.kategori_urls = [
            f"{self.base_url}/kategori/gundem",
            f"{self.base_url}/kategori/asayis",
            f"{self.base_url}/kategori/yasam",
            f"{self.base_url}/kategori/kultur-sanat",
            f"{self.base_url}/kategori/3-sayfa",
        ]

    def haber_listesi_getir(self) -> list:
        """Ses Kocaeli'den haber linklerini çeker."""
        linkler = []

        for kategori_url in self.kategori_urls:
            try:
                soup = self.sayfa_getir(kategori_url)
                if not soup:
                    continue

                seciciler = [
                    "article a[href]",
                    ".news-card a[href]",
                    ".post-title a[href]",
                    "h2 a[href]",
                    "h3 a[href]",
                    ".card a[href]",
                    ".news-item a[href]",
                    "a.post-link[href]",
                ]

                for secici in seciciler:
                    elemeler = soup.select(secici)
                    for eleman in elemeler:
                        href = eleman.get("href", "")
                        if href and href != "#":
                            if href.startswith("/"):
                                href = f"{self.base_url}{href}"
                            elif not href.startswith("http"):
                                href = f"{self.base_url}/{href}"

                            if (
                                href not in linkler
                                and self.base_url in href
                                and "/kategori/" not in href
                                and "/etiket/" not in href
                            ):
                                linkler.append(href)

                    if linkler:
                        break

            except Exception as e:
                logger.error(f"Ses Kocaeli kategori hatası: {kategori_url} - {e}")

        return linkler[:50]

    def haber_detay_getir(self, url: str) -> dict:
        """Ses Kocaeli haber detayını çeker."""
        soup = self.sayfa_getir(url)
        if not soup:
            return None

        haber = {}

        try:
            # Başlık
            baslik_seciciler = [
                "h1.post-title", "h1.entry-title",
                "h1.news-title", "h1.title", "h1",
            ]
            for secici in baslik_seciciler:
                baslik = soup.select_one(secici)
                if baslik:
                    haber["baslik"] = baslik.get_text(strip=True)
                    break

            # İçerik
            icerik_seciciler = [
                ".post-content", ".entry-content", ".news-content",
                ".article-body", ".detail-content", ".content",
            ]
            for secici in icerik_seciciler:
                icerik = soup.select_one(secici)
                if icerik:
                    for tag in icerik.find_all(["script", "style", "iframe"]):
                        tag.decompose()
                    haber["icerik"] = icerik.get_text(separator=" ", strip=True)
                    break

            # Tarih
            tarih_seciciler = [
                "time[datetime]", ".post-date", ".entry-date",
                ".news-date", ".date", "span.date",
            ]
            for secici in tarih_seciciler:
                tarih = soup.select_one(secici)
                if tarih:
                    tarih_metni = tarih.get("datetime") or tarih.get_text(strip=True)
                    haber["yayin_tarihi"] = self.tarih_ayristir(tarih_metni)
                    break

            if not haber.get("yayin_tarihi"):
                meta_tarih = soup.find("meta", property="article:published_time")
                if meta_tarih:
                    haber["yayin_tarihi"] = self.tarih_ayristir(
                        meta_tarih.get("content", "")
                    )

        except Exception as e:
            logger.error(f"Ses Kocaeli detay hatası: {url} - {e}")

        return haber if haber.get("baslik") else None
