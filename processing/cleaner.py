"""
Kocaeli Haber Haritası - Veri Temizleme Modülü

Scraping sonrası elde edilen ham metin verilerini temizler ve
analiz edilebilir hale getirir.

İşlemler:
- HTML tag temizliği
- Fazla boşluk temizleme
- Gereksiz özel karakter temizleme
- Metin normalizasyonu
- Reklam ve alakasız bölüm çıkarma
"""

import re
import unicodedata
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


class TextCleaner:
    """Metin temizleme ve normalizasyon sınıfı."""

    # Reklam ve alakasız içerik kalıpları
    REKLAM_KALIPLARI = [
        r"reklam\s*alanı",
        r"sponsorlu\s*içerik",
        r"google\s*ads",
        r"adsbygoogle",
        r"advertisement",
        r"banner",
        r"popup",
        r"abone\s*ol",
        r"bülten(?:imiz)?e?\s*kayıt",
        r"newsletter",
        r"e-?posta\s*adresinizi?\s*girin",
        r"sosyal\s*medya\s*hesapları",
        r"bizi\s*takip\s*edin",
        r"paylaş",
        r"tweet(?:le)?",
        r"whatsapp",
        r"copyright\s*©",
        r"tüm\s*hakları\s*saklıdır",
        r"cookie",
        r"çerez\s*politikası",
        r"gizlilik\s*politikası",
        r"kvkk",
        r"kişisel\s*verilerin?\s*korunması",
    ]

    # Kaldırılacak HTML etiketleri
    KALDIRILACAK_ETIKETLER = [
        "script", "style", "nav", "footer", "header",
        "aside", "iframe", "noscript", "form",
    ]

    def __init__(self):
        """Temizleyiciyi başlatır."""
        self.reklam_regex = re.compile(
            "|".join(self.REKLAM_KALIPLARI),
            re.IGNORECASE | re.UNICODE,
        )

    def html_temizle(self, html_icerik: str) -> str:
        """
        HTML etiketlerini temizler ve saf metin çıkarır.

        Args:
            html_icerik: Ham HTML içerik

        Returns:
            str: Temizlenmiş metin
        """
        if not html_icerik:
            return ""

        try:
            soup = BeautifulSoup(html_icerik, "lxml")

            # Gereksiz HTML etiketlerini kaldır
            for etiket in self.KALDIRILACAK_ETIKETLER:
                for element in soup.find_all(etiket):
                    element.decompose()

            # Metin içeriğini al
            metin = soup.get_text(separator=" ", strip=True)
            return metin
        except Exception as e:
            logger.error(f"HTML temizleme hatası: {e}")
            return html_icerik

    def bosluk_temizle(self, metin: str) -> str:
        """
        Fazla boşlukları temizler.

        Args:
            metin: Temizlenecek metin

        Returns:
            str: Boşlukları temizlenmiş metin
        """
        if not metin:
            return ""

        # Birden fazla boşluğu tek boşluğa çevir
        metin = re.sub(r"\s+", " ", metin)
        # Satır başı ve sonundaki boşlukları temizle
        metin = metin.strip()
        # Noktalama işaretlerinden önceki boşlukları kaldır
        metin = re.sub(r"\s+([.,;:!?])", r"\1", metin)

        return metin

    def ozel_karakter_temizle(self, metin: str) -> str:
        """
        Gereksiz özel karakterleri temizler.
        Türkçe karakterler korunur.

        Args:
            metin: Temizlenecek metin

        Returns:
            str: Özel karakterleri temizlenmiş metin
        """
        if not metin:
            return ""

        # Türkçe karakterler ve temel noktalama işaretleri korunsun
        # İzin verilen: harf, rakam, boşluk, temel noktalama
        metin = re.sub(
            r"[^\w\s.,;:!?()'\"\-/&%°₺€$@#\n]",
            "",
            metin,
            flags=re.UNICODE,
        )

        return metin

    def metin_normalize_et(self, metin: str) -> str:
        """
        Metin normalizasyonu yapar.
        - Unicode normalizasyonu (NFC)
        - Küçük/büyük harf düzenlemesi

        Args:
            metin: Normalize edilecek metin

        Returns:
            str: Normalize edilmiş metin
        """
        if not metin:
            return ""

        # Unicode NFC normalizasyonu (Türkçe karakter uyumu)
        metin = unicodedata.normalize("NFC", metin)

        # Çift tırnak ve tek tırnak normalizasyonu
        metin = metin.replace("\u201c", '"').replace("\u201d", '"')
        metin = metin.replace("\u2018", "'").replace("\u2019", "'")

        # Tire normalizasyonu
        metin = metin.replace("\u2013", "-").replace("\u2014", "-")

        # Üç nokta normalizasyonu
        metin = metin.replace("\u2026", "...")

        return metin

    def reklam_temizle(self, metin: str) -> str:
        """
        Reklam ve alakasız bölümleri temizler.

        Args:
            metin: Temizlenecek metin

        Returns:
            str: Reklamsız metin
        """
        if not metin:
            return ""

        satirlar = metin.split("\n")
        temiz_satirlar = []

        for satir in satirlar:
            # Reklam kalıplarını kontrol et
            if not self.reklam_regex.search(satir):
                temiz_satirlar.append(satir)

        return "\n".join(temiz_satirlar)

    def tam_temizlik(self, html_icerik: str) -> str:
        """
        Tüm temizleme adımlarını sırasıyla uygular.

        Args:
            html_icerik: Ham HTML içerik

        Returns:
            str: Tamamen temizlenmiş ve normalize edilmiş metin
        """
        # 1. HTML etiketlerini temizle
        metin = self.html_temizle(html_icerik)

        # 2. Metin normalizasyonu
        metin = self.metin_normalize_et(metin)

        # 3. Reklam temizliği
        metin = self.reklam_temizle(metin)

        # 4. Özel karakter temizliği
        metin = self.ozel_karakter_temizle(metin)

        # 5. Boşluk temizliği
        metin = self.bosluk_temizle(metin)

        return metin

    def baslik_temizle(self, baslik: str) -> str:
        """
        Haber başlığını temizler.

        Args:
            baslik: Ham başlık metni

        Returns:
            str: Temizlenmiş başlık
        """
        if not baslik:
            return ""

        # HTML temizliği
        baslik = self.html_temizle(baslik)
        # Normalizasyon
        baslik = self.metin_normalize_et(baslik)
        # Boşluk temizliği
        baslik = self.bosluk_temizle(baslik)
        # Başlık başındaki ve sonundaki gereksiz karakterleri temizle
        baslik = baslik.strip("-–—:| ")

        return baslik
