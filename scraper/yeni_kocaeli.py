"""
Kocaeli Haber Haritası - Yeni Kocaeli Scraper

Kaynak: https://www.yenikocaeli.com
Platform: Özel CMS (PHP tabanlı)
URL yapısı: /haber/{kategori}/{slug}/{id}.html
"""

import re
import logging
from scraper.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class YeniKocaeliScraper(BaseScraper):
    """Yeni Kocaeli haber sitesi scraper'ı."""

    def __init__(self):
        super().__init__(
            kaynak_adi="Yeni Kocaeli",
            base_url="https://www.yenikocaeli.com",
        )
        # Gerçek kategori sayfaları (footer'dan alındı)
        self.kategori_urls = [
            f"{self.base_url}/haber/guncel.html",
            f"{self.base_url}/haber/polis-adliye.html",
            f"{self.base_url}/haber/siyaset.html",
            f"{self.base_url}/haber/yasam.html",
            f"{self.base_url}/haber/ekonomi.html",
            f"{self.base_url}/haber/saglik.html",
        ]

    def _haber_linki_mi(self, href: str) -> bool:
        """Verilen linkin bir haber detay sayfası olup olmadığını kontrol eder."""
        if not href:
            return False
        # Yeni Kocaeli URL formatı: /haber/{kategori}/{slug}/{id}.html
        return bool(re.search(r'/haber/[^/]+/[^/]+/\d+\.html', href))

    def haber_listesi_getir(self) -> list:
        """Yeni Kocaeli'den haber linklerini çeker."""
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
                        and "yenikocaeli" in href
                    ):
                        linkler.append(href)

            except Exception as e:
                logger.error(f"Yeni Kocaeli kategori hatası: {kategori_url} - {e}")

        logger.info(f"Yeni Kocaeli - {len(linkler)} benzersiz haber linki bulundu.")
        return linkler[:50]

    def haber_detay_getir(self, url: str) -> dict:
        """Yeni Kocaeli haber detayını çeker."""
        soup = self.sayfa_getir(url)
        if not soup:
            return None

        haber = {}

        try:
            # Başlık
            baslik = soup.find("h1")
            if baslik:
                haber["baslik"] = baslik.get_text(strip=True)

            # İçerik — birden fazla seçici dene
            icerik_seciciler = [
                ".news-detail-content", ".detail-content",
                ".news-content", ".content-text",
                ".post-content", ".entry-content", ".article-body",
                "article .content",
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

            # Paragraflardan fallback
            if not haber.get("icerik"):
                paragraflar = soup.find_all("p")
                metin_parcalari = []
                for p in paragraflar:
                    metin = p.get_text(strip=True)
                    if len(metin) > 30 and not metin.startswith(("©", "Cookie", "Veri", "Sitemiz")):
                        metin_parcalari.append(metin)
                if metin_parcalari:
                    haber["icerik"] = " ".join(metin_parcalari[:10])

            # Tarih — meta tag öncelikli
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
            logger.error(f"Yeni Kocaeli detay hatası: {url} - {e}")

        return haber if haber.get("baslik") else None
