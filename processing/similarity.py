"""
Kocaeli Haber Haritası - Metin Benzerliği Analizi Modülü

Embedding tabanlı benzerlik ölçümü ile haberler arasında
metin benzerliği analizi yapar. Benzerlik oranı %90 ve üzeri
olan haberler aynı haber olarak kabul edilir.

Kullanılan model: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
(Türkçe destekli çok dilli model)
"""

import logging
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from config.settings import Config

logger = logging.getLogger(__name__)


class SimilarityAnalyzer:
    """Embedding tabanlı metin benzerliği analiz sınıfı."""

    def __init__(self):
        """
        Benzerlik analizörünü başlatır.
        Sentence-Transformers modelini yükler.
        """
        self.model = None
        self.esik_degeri = Config.SIMILARITY_THRESHOLD
        self._model_yukle()

    def _model_yukle(self):
        """Sentence-Transformers modelini yükler."""
        try:
            from sentence_transformers import SentenceTransformer

            # Türkçe destekli çok dilli model
            self.model = SentenceTransformer(
                "paraphrase-multilingual-MiniLM-L12-v2"
            )
            logger.info("Benzerlik analizi modeli yüklendi.")
        except ImportError:
            logger.warning(
                "sentence-transformers yüklü değil. "
                "pip install sentence-transformers komutuyla yükleyin."
            )
        except Exception as e:
            logger.error(f"Model yükleme hatası: {e}")

    def embedding_olustur(self, metin: str) -> np.ndarray:
        """
        Metin için embedding vektörü oluşturur.

        Args:
            metin: Embedding oluşturulacak metin

        Returns:
            numpy.ndarray: Embedding vektörü
        """
        if self.model is None:
            logger.error("Model yüklenmemiş!")
            return None

        try:
            embedding = self.model.encode(metin, show_progress_bar=False)
            return embedding
        except Exception as e:
            logger.error(f"Embedding oluşturma hatası: {e}")
            return None

    def embeddingleri_olustur(self, metinler: list) -> np.ndarray:
        """
        Metin listesi için toplu embedding üretir.

        Args:
            metinler: Embedding üretilecek metin listesi

        Returns:
            numpy.ndarray: Embedding matrisi veya boş dizi
        """
        if self.model is None or not metinler:
            return np.array([])

        try:
            return self.model.encode(metinler, show_progress_bar=False)
        except Exception as e:
            logger.error(f"Toplu embedding oluşturma hatası: {e}")
            return np.array([])

    def benzerlik_hesapla(self, metin1: str, metin2: str) -> float:
        """
        İki metin arasındaki kosinüs benzerliğini hesaplar.

        Args:
            metin1: İlk metin
            metin2: İkinci metin

        Returns:
            float: Benzerlik oranı (0.0 - 1.0)
        """
        if self.model is None:
            return 0.0

        try:
            embedding1 = self.embedding_olustur(metin1)
            embedding2 = self.embedding_olustur(metin2)

            if embedding1 is None or embedding2 is None:
                return 0.0

            benzerlik = cosine_similarity(
                embedding1.reshape(1, -1),
                embedding2.reshape(1, -1),
            )[0][0]

            return float(round(benzerlik, 4))
        except Exception as e:
            logger.error(f"Benzerlik hesaplama hatası: {e}")
            return 0.0

    def ayni_haber_mi(self, metin1: str, metin2: str) -> bool:
        """
        İki haberin aynı haber olup olmadığını kontrol eder.
        Benzerlik oranı %90 ve üzeri ise aynı haber kabul edilir.

        Args:
            metin1: İlk haberin metni (başlık + içerik)
            metin2: İkinci haberin metni (başlık + içerik)

        Returns:
            bool: Aynı haber ise True
        """
        benzerlik = self.benzerlik_hesapla(metin1, metin2)
        return benzerlik >= self.esik_degeri

    def benzerleri_bul(
        self,
        yeni_haber: str,
        mevcut_haberler: list,
        mevcut_embeddingler: np.ndarray = None,
        yeni_embedding: np.ndarray = None,
    ) -> list:
        """
        Yeni bir haberin mevcut haberler arasındaki benzerlerini bulur.

        Args:
            yeni_haber: Yeni haberin metni (başlık + içerik)
            mevcut_haberler: [{_id, baslik, icerik, haber_linki}, ...] listesi

        Returns:
            list: Benzer haberlerin listesi [{haber, benzerlik_orani}, ...]
        """
        if self.model is None or not mevcut_haberler:
            return []

        try:
            # Yeni haber embedding'i
            if yeni_embedding is None:
                yeni_embedding = self.embedding_olustur(yeni_haber)
            if yeni_embedding is None:
                return []

            # Mevcut haberlerin embedding'leri
            if mevcut_embeddingler is None:
                mevcut_metinler = [
                    f"{h.get('baslik', '')} {h.get('icerik', '')}"
                    for h in mevcut_haberler
                ]
                mevcut_embeddingler = self.embeddingleri_olustur(mevcut_metinler)

            if mevcut_embeddingler is None or len(mevcut_embeddingler) == 0:
                return []

            # Kosinüs benzerlikleri hesapla
            benzerlikler = cosine_similarity(
                yeni_embedding.reshape(1, -1),
                mevcut_embeddingler,
            )[0]

            # Eşik değerinin üstündekileri bul
            benzer_haberler = []
            for i, benzerlik in enumerate(benzerlikler):
                if benzerlik >= self.esik_degeri:
                    benzer_haberler.append({
                        "haber": mevcut_haberler[i],
                        "benzerlik_orani": float(round(benzerlik, 4)),
                    })

            # Benzerlik oranına göre sırala (yüksekten düşüğe)
            benzer_haberler.sort(
                key=lambda x: x["benzerlik_orani"], reverse=True
            )

            if benzer_haberler:
                logger.info(
                    f"{len(benzer_haberler)} benzer haber bulundu "
                    f"(eşik: {self.esik_degeri})"
                )

            return benzer_haberler

        except Exception as e:
            logger.error(f"Benzer haber bulma hatası: {e}")
            return []

    def toplu_benzerlik_matrisi(self, metinler: list) -> np.ndarray:
        """
        Metinler arasındaki benzerlik matrisini oluşturur.

        Args:
            metinler: Metin listesi

        Returns:
            numpy.ndarray: NxN benzerlik matrisi
        """
        if self.model is None or not metinler:
            return np.array([])

        try:
            embeddingler = self.model.encode(
                metinler, show_progress_bar=False
            )
            matris = cosine_similarity(embeddingler)
            return matris
        except Exception as e:
            logger.error(f"Benzerlik matrisi oluşturma hatası: {e}")
            return np.array([])
