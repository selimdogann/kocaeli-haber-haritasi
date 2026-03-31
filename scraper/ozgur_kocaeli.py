"""
Kocaeli Haber Haritası - Özgür Kocaeli Scraper

Kaynak: https://www.ozgurkocaeli.com.tr
Platform: Daktilo Haber Yazılımı v1.9
"""

import re
import logging
from scraper.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class OzgurKocaeliScraper(BaseScraper):
    """Özgür Kocaeli haber sitesi scraper'ı (Daktilo CMS)."""

    CLOUDFLARE_KORUMALI = True

    IGNORE_PHRASES = [
        "Yorumunuz",
        "Topluluk Kuralları",
        "Oturum aç",
        "Okunma",
        "Yazdır",
    ]

    def __init__(self):
        super().__init__(
            kaynak_adi="Özgür Kocaeli",
            base_url="https://www.ozgurkocaeli.com.tr",
        )
        # Daktilo CMS kategori sayfaları (gerçek URL yapısı)
        self.kategori_urls = [
            f"{self.base_url}/kocaeli-haberleri",          # Gündem
            f"{self.base_url}/kocaeli-asayis-haberleri",    # Asayiş
            f"{self.base_url}/kocaeli-yasam-haberleri",     # Yaşam
            f"{self.base_url}/kocaeli-ekonomi-haberleri",   # Ekonomi
        ]

    def _haber_linki_mi(self, href: str) -> bool:
        """Verilen linkin bir haber detay sayfası olup olmadığını kontrol eder."""
        if not href:
            return False
        # Daktilo CMS haber URL formatı: /haber/{id}/{slug}
        return bool(re.search(r'/haber/\d+/', href))

    def _icerigi_temizle(self, metin: str) -> str:
        """UI ve yorum kırıntılarını içerikten temizler."""
        temiz_metin = metin or ""
        for ifade in self.IGNORE_PHRASES:
            temiz_metin = temiz_metin.replace(ifade, " ")

        temiz_metin = re.sub(r"\s+", " ", temiz_metin).strip()
        return temiz_metin

    def _paragraf_metinlerini_topla(self, kapsayici) -> str:
        """Haber gövdesindeki paragraf metinlerini birleştirir."""
        if not kapsayici:
            return ""

        for secici in [
            "script",
            "style",
            "iframe",
            "aside",
            "footer",
            "form",
            "button",
            ".comments",
            ".comment",
            ".yorum",
            ".social",
            ".share",
            ".related",
            ".post-tags",
            ".news-tags",
        ]:
            for tag in kapsayici.select(secici):
                tag.decompose()

        paragraflar = []
        for p in kapsayici.find_all("p"):
            metin = self._icerigi_temizle(p.get_text(" ", strip=True))
            if len(metin) < 30:
                continue
            if any(ifade.lower() in metin.lower() for ifade in self.IGNORE_PHRASES):
                continue
            paragraflar.append(metin)

        return " ".join(paragraflar)

    def haber_listesi_getir(self) -> list:
        """Özgür Kocaeli'den haber linklerini çeker."""
        linkler = []

        for kategori_url in self.kategori_urls:
            try:
                soup = self.sayfa_getir(kategori_url)
                if not soup:
                    continue

                # Daktilo CMS'de tüm linkleri tara
                tum_linkler = soup.find_all("a", href=True)
                for eleman in tum_linkler:
                    href = eleman.get("href", "")
                    if not href or href == "#":
                        continue

                    # Tam URL oluştur
                    if href.startswith("/"):
                        href = f"{self.base_url}{href}"
                    elif not href.startswith("http"):
                        href = f"{self.base_url}/{href}"

                    # Sadece haber detay sayfalarını al
                    if (
                        self._haber_linki_mi(href)
                        and href not in linkler
                        and self.base_url in href
                    ):
                        linkler.append(href)

            except Exception as e:
                logger.error(f"Özgür Kocaeli kategori hatası: {kategori_url} - {e}")

        logger.info(f"Özgür Kocaeli - {len(linkler)} benzersiz haber linki bulundu.")
        return linkler[:50]

    def haber_detay_getir(self, url: str) -> dict:
        """Özgür Kocaeli haber detayını çeker (Daktilo CMS formatı)."""
        soup = self.sayfa_getir(url)
        if not soup:
            return None

        haber = {}

        try:
            # Başlık - Daktilo CMS <h1> kullanır
            baslik = soup.find("h1")
            if baslik:
                haber["baslik"] = baslik.get_text(strip=True)

            # İçerik - Daktilo CMS yapısı
            icerik_seciciler = [
                ".haber-metni",
                ".news-detail",
                ".detail-content", ".news-content", ".content-text",
                ".post-content", ".entry-content", ".article-body",
                "article .content", ".news-detail-content",
            ]
            for secici in icerik_seciciler:
                icerik = soup.select_one(secici)
                if icerik:
                    metin = self._paragraf_metinlerini_topla(icerik)
                    if len(metin) > 50:
                        haber["icerik"] = metin
                        break

            # İçerik bulunamazsa, paragrafları dene
            if not haber.get("icerik"):
                kapsayici = soup.find("article")
                if not kapsayici:
                    kapsayici = soup.find(
                        "div",
                        class_=re.compile(
                            r"(haber|news|detail|content|article)",
                            re.IGNORECASE,
                        ),
                    )

                metin = self._paragraf_metinlerini_topla(kapsayici)
                if len(metin) > 50:
                    haber["icerik"] = metin

            # Tarih - Önce meta tag, sonra sayfa içi
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
            logger.error(f"Özgür Kocaeli detay hatası: {url} - {e}")

        return haber if haber.get("baslik") else None
