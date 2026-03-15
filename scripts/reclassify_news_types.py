"""
Mevcut MongoDB haber kayitlarini guncel siniflandirici ile yeniden etiketler.

Kullanim:
    python scripts/reclassify_news_types.py
"""

from datetime import datetime
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.mongodb import MongoDB
from processing.classifier import NewsClassifier


def main():
    db = MongoDB()
    classifier = NewsClassifier()

    toplam = 0
    guncellenen = 0
    digerden_cikan = 0

    cursor = db.news_collection.find(
        {},
        {
            "baslik": 1,
            "icerik": 1,
            "haber_turu": 1,
            "siniflandirma_guven": 1,
        },
    )

    for haber in cursor:
        toplam += 1
        eski_tur = haber.get("haber_turu")

        sonuc = classifier.siniflandir(
            haber.get("baslik", ""),
            haber.get("icerik", ""),
        )
        yeni_tur = sonuc.get("haber_turu") or "diger"
        yeni_guven = sonuc.get("guven_skoru", 0.0)

        if eski_tur == yeni_tur and haber.get("siniflandirma_guven") == yeni_guven:
            continue

        db.news_collection.update_one(
            {"_id": haber["_id"]},
            {
                "$set": {
                    "haber_turu": yeni_tur,
                    "siniflandirma_guven": yeni_guven,
                    "guncelleme_tarihi": datetime.now(),
                }
            },
        )
        guncellenen += 1

        if eski_tur == "diger" and yeni_tur != "diger":
            digerden_cikan += 1

    print(f"Toplam haber: {toplam}")
    print(f"Guncellenen haber: {guncellenen}")
    print(f"Diger kategorisinden cikan: {digerden_cikan}")


if __name__ == "__main__":
    main()
