# src/export_enriched_catalog.py
"""
Bygger den slutliga 'Embracer-vyn' (catalog_enriched_embracer.csv).

Steg:
1. Läs originalkatalogen (Embracers export med object_number + metadata).
2. Koppla på edition_id via items_to_editions.csv (object_number ↔ edition_id).
3. Koppla på editions_enriched_master.csv (berikad info per edition).
4. Beräkna info_confidence_score/flag om de saknas.
5. Se till att alla originalkolumner finns (även om de saknas i CSV:n → fylls tomma).
6. Se till att alla enrichment-kolumner finns (annars fylls tomma).
7. Skriv ut en snygg CSV med stabil kolumnordning.
"""

from __future__ import annotations

from pathlib import Path
import argparse
from typing import Any, Tuple, List

import pandas as pd

# ---------------------------------------------------------------------------
#  Vilka originalfält Embracer-exporten *ska* ha (min "kontrakt" mot arkivet)
# ---------------------------------------------------------------------------
ORIGINAL_COLS: List[str] = [
    "object_number",
    "title",
    "title.type",
    "object_name",
    "object_name.type",
    "object_category",
    "broadcast_standard",
    "title.language",
    "place_of_publication",
]

# ---------------------------------------------------------------------------
#  Vilka enrichment-fält vi vill exponera per edition i Embracer-vyn
# ---------------------------------------------------------------------------
ENRICH_COLS: List[str] = [
    "developer",
    "publisher",
    "genres",
    "platform",
    "release_date_for_platform",
    "region_for_platform",
    "languages",
    "country_of_origin",
    "director",
    "producer",
    "designer",
    "programmer",
    "artist",
    "composer",
    "info_confidence_score",
    "info_confidence_flag",
    # interna ID-fält (kan vara bra för felsökning, men behövs inte i slutvyn)
    "primary_source",
    "gb_game_id",
    "igdb_game_id",
    "wikidata_qid",
    "wiki_has_infobox",
]

# Standard-output-katalog
OUT_DIR = Path("data/outputs")


# ---------------------------------------------------------------------------
#  Hjälpare: robust CSV-läsning
# ---------------------------------------------------------------------------
def read_df(path: str | Path) -> pd.DataFrame:
    """
    Läs en CSV som strängar och fyll NaN med tomma strängar.
    Avbryter programmet om filen saknas.
    """
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"❌ Hittar inte filen: {p}")
    return pd.read_csv(p, dtype=str).fillna("")


# ---------------------------------------------------------------------------
#  Hjälpare: extrahera årtal från datumsträng
# ---------------------------------------------------------------------------
def extract_year(s: Any) -> str:
    """
    Om vi har en datumsträng 'YYYY-MM-DD' eller liknande,
    plocka ut de första 4 tecknen om de är siffror → 'YYYY'.
    Annars returnera tom sträng.
    """
    if not isinstance(s, str):
        return ""
    s = s.strip()
    if len(s) >= 4 and s[:4].isdigit():
        return s[:4]
    return ""


# ---------------------------------------------------------------------------
#  Hjälpare: confidence-score för enrichment
# ---------------------------------------------------------------------------
def compute_info_confidence(row: Any) -> Tuple[int, str]:
    """
    Beräkna ett ganska strikt confidence-score 1–10 + flag (low/medium/high).

    Idé:
    - Vi tittar på vilka källor som finns (GB, IGDB, Wikidata, Wikipedia)
      och om viktiga fält som developer/publisher är satta.
    - 10 reserveras för "supersäkra" fall där allt sitter:
        * både GB- och IGDB-ID
        * primary_source är satt
        * Wikidata-länk finns
        * Wikipedia har infobox
        * både developer och publisher är ifyllda
    - Allt annat hamnar på 1–9.
    """
    score = 1  # baseline, så inget blir 0

    primary = str(row.get("primary_source", "") or "").strip()
    gb_id   = str(row.get("gb_game_id", "") or "").strip()
    igdb_id = str(row.get("igdb_game_id", "") or "").strip()
    wd_qid  = str(row.get("wikidata_qid", "") or "").strip()
    wiki_has_infobox = str(row.get("wiki_has_infobox", "") or "").strip()

    # 1) primary_source satt (vi har valt "bästa" källa)?
    if primary:
        score += 2

    # 2) GB/IGDB-ID – kräver båda för mer poäng
    if gb_id and igdb_id:
        score += 3
    elif gb_id or igdb_id:
        score += 1

    # 3) Wikidata-länk?
    if wd_qid:
        score += 2

    # 4) Wikipedia-infobox?
    if wiki_has_infobox == "1":
        score += 2

    # Begränsa preliminärt till max 9 – 10 reserveras nedan
    score = max(1, min(9, score))

    # --- Supersäker 10:a ------------------------------------------------------
    dev = str(row.get("developer", "") or "").strip()
    pub = str(row.get("publisher", "") or "").strip()

    if (
        primary
        and gb_id and igdb_id
        and wd_qid
        and wiki_has_infobox == "1"
        and dev and pub
    ):
        score = 10

    # Flagga beroende på score
    if score >= 8:
        flag = "high"
    elif score >= 5:
        flag = "medium"
    else:
        flag = "low"

    return score, flag


# ---------------------------------------------------------------------------
#  Huvudflöde
# ---------------------------------------------------------------------------
def main() -> None:
    # -----------------------------
    # 1) CLI-argument
    # -----------------------------
    ap = argparse.ArgumentParser(
        description=(
            "Bygg Embracer-vy: originalkatalog → items_to_editions → editions_enriched_master."
        )
    )
    ap.add_argument(
        "--catalog",
        default="data/raw/alltsnesochsfam.csv",
        help="Path till original Embracer-katalog (CSV med object_number, title, osv.)",
    )
    ap.add_argument(
        "--links",
        default=str(OUT_DIR / "items_to_editions.csv"),
        help="Path till items_to_editions.csv (object_number ↔ edition_id)",
    )
    ap.add_argument(
        "--master",
        default=str(OUT_DIR / "editions_enriched_master.csv"),
        help="Path till editions_enriched_master.csv (per edition)",
    )
    ap.add_argument(
        "--out",
        default=str(OUT_DIR / "catalog_enriched_embracer.csv"),
        help="Path för Embracer-vyn (output CSV)",
    )
    args = ap.parse_args()

    # -----------------------------
    # 2) Läs in källfiler
    # -----------------------------
    catalog = read_df(args.catalog)   # Embracers råexport (object_number + metadata)
    links   = read_df(args.links)     # object_number ↔ edition_id
    master  = read_df(args.master)    # berikad info per edition_id

    # Grundkoll på viktiga kolumner
    if "object_number" not in catalog.columns:
        raise SystemExit("❌ Katalogfilen saknar kolumnen 'object_number'.")

    if "object_number" not in links.columns or "edition_id" not in links.columns:
        raise SystemExit(
            "❌ items_to_editions.csv måste innehålla 'object_number' och 'edition_id'."
        )

    if "edition_id" not in master.columns:
        raise SystemExit("❌ editions_enriched_master.csv saknar kolumnen 'edition_id'.")

    # ------------------------------------------------------
    # 3) Se till att alla ORIGINAL_COLS finns i katalogen
    #    Exempel: om en testfil saknar broadcast_standard
    #    så skapar vi kolumnen med tomma strängar.
    # ------------------------------------------------------
    for col in ORIGINAL_COLS:
        if col not in catalog.columns:
            catalog[col] = ""

    # ------------------------------------------------------
    # 4) Lägg på info_confidence_* direkt i master om de saknas
    # ------------------------------------------------------
    if (
        "info_confidence_score" not in master.columns
        or "info_confidence_flag" not in master.columns
    ):
        scores_flags = master.apply(compute_info_confidence, axis=1)
        master["info_confidence_score"] = scores_flags.apply(lambda t: t[0])
        master["info_confidence_flag"] = scores_flags.apply(lambda t: t[1])

    # ------------------------------------------------------
    # 5) Steg 1: katalog + edition_id via object_number
    #    (m:1-join – flera object_number kan peka på samma edition)
    # ------------------------------------------------------
    cat_with_ed = catalog.merge(
        links[["object_number", "edition_id"]],
        on="object_number",
        how="left",    # om något objekt saknar edition → edition_id blir tom
    )

    # ------------------------------------------------------
    # 6) Steg 2: välj relevanta kolumner ur master
    # ------------------------------------------------------
    master_cols_keep = ["edition_id"] + [
        c for c in ENRICH_COLS if c in master.columns
    ]
    master_sub = master.loc[:, master_cols_keep].copy()

    # ------------------------------------------------------
    # 7) Steg 3: joina in enrichment per edition_id
    # ------------------------------------------------------
    merged = cat_with_ed.merge(
        master_sub,
        on="edition_id",
        how="left",   # objekt utan enrichment får tomma fält
    )

    # ------------------------------------------------------
    # 8) Härled release_year från release_date_for_platform
    # ------------------------------------------------------
    if "release_date_for_platform" in merged.columns:
        merged["release_year"] = merged["release_date_for_platform"].apply(extract_year)
    else:
        merged["release_year"] = ""

    # ------------------------------------------------------
    # 9) Fallbacks för languages och country_of_origin
    # ------------------------------------------------------
    # Om vi saknar 'languages' men har t.ex. 'title.language' kan man
    # (om man vill) använda det som fallback, men här håller vi det enkelt:
    if "languages" not in merged.columns:
        merged["languages"] = ""

    if "country_of_origin" not in merged.columns:
        # En enkel fallback är att använda region_for_platform
        merged["country_of_origin"] = merged.get("region_for_platform", "")

    # ------------------------------------------------------
    # 10) Bygg exakt kolumnordning för Embracer-vyn
    #     (detta är vad du visar för Embracer)
    # ------------------------------------------------------
    desired_cols: List[str] = [
        # Originalkatalog-fält (Embracer)
        "object_number",
        "title",
        "title.type",
        "object_name",
        "object_name.type",
        "object_category",
        "broadcast_standard",
        "title.language",
        "place_of_publication",

        # Enrichment
        "developer",
        "publisher",
        "release_year",
        "platform",
        "genres",
        "country_of_origin",
        "languages",

        # Credits
        "director",
        "producer",
        "designer",
        "programmer",
        "artist",
        "composer",

        # Confidence
        "info_confidence_score",
        "info_confidence_flag",
    ]

    # Se till att alla desired_cols finns i merged (annars skapa tomma)
    for col in desired_cols:
        if col not in merged.columns:
            merged[col] = ""

    # ------------------------------------------------------
    # 11) Skriv ut slutfilen
    # ------------------------------------------------------
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    merged.loc[:, desired_cols].to_csv(out_path, index=False, encoding="utf-8")

    print(f"✅ Skrev Embracer-vy med {len(merged)} rader → {out_path}")
    print("   Kolumner:", ", ".join(desired_cols))


if __name__ == "__main__":
    main()
