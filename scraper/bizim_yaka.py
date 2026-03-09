"""
Kocaeli Haber Haritası - Bizim Yaka Scraper

Kaynak: https://www.bizimyaka.com
Platform: Daktilo Haber Yazılımı v1.9
"""

import re
import logging
from scraper.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class BizimYakaScraper(BaseScraper):
    """Bizim Yaka haber sitesi scraper'ı (Daktilo CMS)."""

    def __init__(self):
        super().__init__(
            kaynak_adi="Bizim Yaka",
            base_url="https://www.bizimyaka.com",
        )
        # Daktilo CMS kategori sayfaları (gerçek URL yapısı)
        self.kategori_urls = [
            f"{self.base_url}/kocaeli-son-dakika-haberleri",  # Gündem
            f"{self.base_url}/kocaeli-asayis-haberleri",      # Asayiş
            f"{self.base_url}/yasam-haberleri",               # Yaşam
            f"{self.base_url}/kocaeli-ekonomi-haberleri",     # Ekonomi
            f"{self.base_url}/kocaeli-siyaset-haberleri",     # Siyaset
        ]

    def _haber_linki_mi(self, href: str) -> bool:
        """Verilen linkin bir haber detay sayfası olup olmadığını kontrol eder."""
        if not href:
            return False
        return bool(re.search(r'/haber/\d+/', href))

    def haber_listesi_getir(self) -> list:
        """Bizim Yaka'dan haber linklerini çeker."""
        linkler = []

        for kategori_url in self.kategori_urls:
            try:
                soup = self.sayfa_getir(kategori_url)
                if not soup:
                    continue

                tum_linkler = soup.find_all("a", href=True)
                for eleman in tum_linkler:
                    href = eleman.get("href", "")
                    if not href or href == "#":
                        continue

                    if href.startswith("/"):
                        href = f"{self.base_url}{href}"
                    elif not href.startswith("http"):
                        href = f"{self.base_url}/{href}"

                    if (
                        self._haber_linki_mi(href)
                        and href not in linkler
                        and "bizimyaka.com" in href
                    ):
                        linkler.append(href)

            except Exception as e:
                logger.error(f"Bizim Yaka kategori hatası: {kategori_url} - {e}")

        logger.info(f"Bizim Yaka - {len(linkler)} benzersiz haber linki bulundu.")
        return linkler[:50]

    def haber_detay_getir(self, url: str) -> dict:
        """Bizim Yaka haber detayını çeker (Daktilo CMS formatı)."""
        soup = self.sayfa_getir(url)
        if not soup:
            return None

        haber = {}

        try:
            baslik = soup.find("h1")
            if baslik:
                haber["baslik"] = baslik.get_text(strip=True)

            icerik_seciciler = [
                ".detail-content", ".news-content", ".content-text",
                ".post-content", ".entry-content", ".article-body",
                "article .content", ".news-detail-content",
            ]
            for secici in icerik_seciciler:
                icerik = soup.select_one(secici)
                if icerik:
                    for tag in icerik.find_all(["script", "style", "iframe", "aside"]):
                        tag.decompose()
                    metin = icerik.get_text(separator=" ", strip=True)
                    if len(metin) > 50:
                        haber["icerik"] = metin
                        break

            if not haber.get("icerik"):
                paragraflar = soup.find_all("p")
                metin_parcalari = []
                for p in paragraflar:
                    metin = p.get_text(strip=True)
                    if len(metin) > 30 and not metin.startswith(("©", "Cookie", "Veri")):
                        metin_parcalari.append(metin)
                if metin_parcalari:
                    haber["icerik"] = " ".join(metin_parcalari[:10])

            meta_tarih = soup.find("meta", property="article:published_time")
            if not meta_tarih:
                meta_tarih = soup.find("meta", attrs={"name": "datePublished"})
            if meta_tarih and meta_tarih.get("content"):
                haber["yayin_tarihi"] = self.tarih_ayristir(meta_tarih["content"])

            if not haber.get("yayin_tarihi"):
                time_tag = soup.find("time")
                if time_tag:
                    tarih_metni = time_tag.get("datetime") or time_tag.get_text(strip=True)
                    haber["yayin_tarihi"] = self.tarih_ayristir(tarih_metni)

        except Exception as e:
            logger.error(f"Bizim Yaka detay hatası: {url} - {e}")

        return haber if haber.get("baslik") else None
