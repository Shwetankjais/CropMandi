"""Import the cleaned user-supplied crop market CSV into CropMandi's DB."""
from __future__ import annotations

import csv
import os
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from cropmandi.db.models import CropMarketObservation, MandiLocation
from cropmandi.db.session import create_all, make_engine
from cropmandi.config import get_settings
from ingest.crop_market_reports import DEFAULT_CSV, DEFAULT_REPORT, parse_archive, write_clean_csv, DEFAULT_ZIP

ROOT = Path(__file__).resolve().parents[1]


def import_csv(csv_path: Path = DEFAULT_CSV, database_url: str | None = None) -> dict:
    settings = get_settings()
    url = database_url or settings.database_url
    create_all(url)
    engine = make_engine(url)
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    with Session(engine) as session:
        session.execute(delete(CropMarketObservation))
        session.flush()
        objects = []
        markets: dict[tuple[str, str], dict] = {}
        for row in rows:
            objects.append(CropMarketObservation(
                crop_code=row["crop"],
                market_name=row["market_name"],
                district=row["district"] or "",
                state=row["state"] or "Karnataka",
                market_date=__import__("datetime").date.fromisoformat(row["market_date"]),
                variety=row["variety"] or "UNSPECIFIED",
                grade=row["grade"] or "UNSPECIFIED",
                arrivals=Decimal(row["arrivals"]),
                unit=row["unit"] or "Quintal",
                min_price=Decimal(row["min_price"]) if row["min_price"] else None,
                max_price=Decimal(row["max_price"]) if row["max_price"] else None,
                modal_price=Decimal(row["modal_price"]),
                source_file=row["source_file"],
                source_publisher=row["source_publisher"],
                data_status=row["data_status"],
            ))
            key = (row["market_name"].strip(), row["district"].strip())
            markets.setdefault(key, {"name": key[0], "district": key[1], "state": row["state"] or "Karnataka"})
        session.bulk_save_objects(objects)
        session.flush()

        new_markets = 0
        for item in markets.values():
            existing = session.scalar(select(MandiLocation).where(
                MandiLocation.name == item["name"],
                MandiLocation.district == item["district"],
                MandiLocation.state == item["state"],
            ))
            if existing is None:
                session.add(MandiLocation(
                    name=item["name"], district=item["district"], state=item["state"],
                    coordinate_status="UNVERIFIED", is_verified=False,
                    source="AGMARKNET date-wise user-supplied report",
                ))
                new_markets += 1
        # Product-spec Karnataka APMC candidates. These are directory seed
        # records only; no coordinates or fees are fabricated.
        candidate_markets = [
            ("SRINGERI", "Chikkamagaluru", "Candidate APMC name from product specification; verify identity and coordinates"),
        ]
        for name, district, source in candidate_markets:
            exists = session.scalar(select(MandiLocation).where(
                MandiLocation.name == name, MandiLocation.district == district, MandiLocation.state == "Karnataka"
            ))
            if exists is None:
                session.add(MandiLocation(name=name, district=district, state="Karnataka", source=source,
                                          coordinate_status="UNVERIFIED", is_verified=False))
                new_markets += 1
        session.commit()
        count = session.scalar(select(__import__("sqlalchemy").func.count()).select_from(CropMarketObservation))
        market_count = session.scalar(select(__import__("sqlalchemy").func.count()).select_from(MandiLocation))
    engine.dispose()
    return {"rows_imported": int(count or 0), "market_records": int(market_count or 0), "new_market_records": new_markets, "database": url}


def main() -> None:
    if not DEFAULT_CSV.exists():
        rows, audit = parse_archive(DEFAULT_ZIP)
        write_clean_csv(rows, DEFAULT_CSV)
        DEFAULT_REPORT.write_text(__import__("json").dumps(audit, indent=2), encoding="utf-8")
    print(import_csv())


if __name__ == "__main__":
    main()
