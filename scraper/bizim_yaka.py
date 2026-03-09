"""
Kocaeli Haber Haritası - Bizim Yaka Scraper

Kaynak: https://bizimyaka.com
"""

import logging
from scraper.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class BizimYakaScraper(BaseScraper):
    """Bizim Yaka haber sitesi scraper'ı."""

    def __init__(self):
        super().__init__(
            kaynak_adi="Bizim Yaka",
            base_url="https://bizimyaka.com",
        )
        self.kategori_urls = [
            f"{self.base_url}/kategori/gundem",
            f"{self.base_url}/kategori/asayis",
            f"{self.base_url}/kategori/yasam",
            f"{self.base_url}/kategori/kultur-sanat",
        ]

    def haber_listesi_getir(self) -> list:
        """Bizim Yaka'dan haber linklerini çeker."""
        linkler = []

        for kategori_url in self.kategori_urls:
            try:
                soup = self.sayfa_getir(kategori_url)
                if not soup:
                    continue

                seciciler = [
                    "article a[href]",
                    ".news-item a[href]",
                    ".post-title a[href]",
                    "h2 a[href]",
                    "h3 a[href]",
                    ".card a[href]",
                    ".item a[href]",
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
                                and "bizimyaka" in href
                                and "/kategori/" not in href
                                and "/etiket/" not in href
                            ):
                                linkler.append(href)

                    if linkler:
                        break

            except Exception as e:
                logger.error(f"Bizim Yaka kategori hatası: {kategori_url} - {e}")

        return linkler[:50]

    def haber_detay_getir(self, url: str) -> dict:
        """Bizim Yaka haber detayını çeker."""
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
                ".article-content", ".detail-content", ".content",
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
            logger.error(f"Bizim Yaka detay hatası: {url} - {e}")

        return haber if haber.get("baslik") else None
