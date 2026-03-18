"""
Mevcut MongoDB haber ve konum cache kayitlarina GeoJSON alanini ekler.

Kullanim:
    python scripts/backfill_geojson.py
"""

from datetime import datetime
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.mongodb import MongoDB


def geojson_nokta(enlem, boylam):
    return {
        "type": "Point",
        "coordinates": [boylam, enlem],
    }


def main():
    db = MongoDB()

    haber_guncellenen = 0
    konum_guncellenen = 0

    haber_cursor = db.news_collection.find(
        {"enlem": {"$ne": None}, "boylam": {"$ne": None}},
        {"enlem": 1, "boylam": 1, "konum_geojson": 1},
    )
    for haber in haber_cursor:
        yeni_geojson = geojson_nokta(haber["enlem"], haber["boylam"])
        if haber.get("konum_geojson") == yeni_geojson:
            continue

        db.news_collection.update_one(
            {"_id": haber["_id"]},
            {
                "$set": {
                    "konum_geojson": yeni_geojson,
                    "guncelleme_tarihi": datetime.now(),
                }
            },
        )
        haber_guncellenen += 1

    konum_cursor = db.locations_collection.find(
        {"enlem": {"$ne": None}, "boylam": {"$ne": None}},
        {"enlem": 1, "boylam": 1, "konum_geojson": 1},
    )
    for konum in konum_cursor:
        yeni_geojson = geojson_nokta(konum["enlem"], konum["boylam"])
        if konum.get("konum_geojson") == yeni_geojson:
            continue

        db.locations_collection.update_one(
            {"_id": konum["_id"]},
            {
                "$set": {
                    "konum_geojson": yeni_geojson,
                    "guncelleme_tarihi": datetime.now(),
                }
            },
        )
        konum_guncellenen += 1

    print(f"Haber GeoJSON guncellenen: {haber_guncellenen}")
    print(f"Konum cache GeoJSON guncellenen: {konum_guncellenen}")


if __name__ == "__main__":
    main()
