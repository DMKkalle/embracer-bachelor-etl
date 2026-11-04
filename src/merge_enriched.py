# src/merge_enriched.py
# Mergar enrichment från GiantBomb + IGDB + Wikidata + Wikipedia
# till en master-CSV per edition_id.

from __future__ import annotations

from pathlib import Path
import argparse
from typing import List, Any

import pandas as pd


def read_df(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"❌ Hittar inte filen: {p}")
    return pd.read_csv(p, dtype=str).fillna("")


def coalesce(*vals: List[str]) -> str:
    """
    Ta första icke-tomma strängen.
    """
    for v in vals:
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Mergar enrichment från GiantBomb + IGDB + Wikidata + Wikipedia "
            "till en master-CSV per edition_id."
        )
    )
    ap.add_argument("--gb", required=True, help="Path till giantbomb_enrichment.csv")
    ap.add_argument("--igdb", required=True, help="Path till igdb_enrichment.csv")
    ap.add_argument("--wikidata", required=True, help="Path till wikidata_enrichment.csv")
    ap.add_argument("--wikipedia", required=True, help="Path till wikipedia_enrichment.csv")
    ap.add_argument(
        "--out",
        required=True,
        help="Sökväg för masterfilen (t.ex. data/outputs/editions_enriched_master.csv)",
    )
    args = ap.parse_args()

    # --- Läs in källor --------------------------------------------------------
    gb = read_df(args.gb)
    ig = read_df(args.igdb)
    wd = read_df(args.wikidata)
    wiki = read_df(args.wikipedia)

    # -------------------------------------------------------------------------
    # Förbered GiantBomb
    # -------------------------------------------------------------------------
    if "edition_id" not in gb.columns:
        raise SystemExit("❌ GB-fil saknar kolumnen 'edition_id'")

    gb_cols_rename = {
        "title_primary": "title_primary_gb",
        "platform": "platform_gb",
        "igdb_id": "gb_game_id",
        "igdb_name": "gb_name",
        "genres": "gb_genres",
        "developers_for_platform": "gb_developers_for_platform",
        "publishers_for_platform": "gb_publishers_for_platform",
        "release_date_for_platform": "gb_release_date_for_platform",
        "region_for_platform": "gb_region_for_platform",
        "platforms_all": "gb_platforms_all",
        "release_dates_all": "gb_release_dates_all",
        "cover_url": "gb_cover_url",
        "confidence": "gb_confidence",
        "source": "gb_source",
    }
    gb = gb.rename(columns={k: v for k, v in gb_cols_rename.items() if k in gb.columns})

    # -------------------------------------------------------------------------
    # Förbered IGDB
    # -------------------------------------------------------------------------
    if "edition_id" not in ig.columns:
        raise SystemExit("❌ IGDB-fil saknar kolumnen 'edition_id'")

    ig_cols_rename = {
        "title_primary": "title_primary_igdb",
        "platform": "platform_igdb",
        "igdb_id": "igdb_game_id",
        "igdb_name": "igdb_name",
        "genres": "igdb_genres",
        "developers_for_platform": "igdb_developers_for_platform",
        "publishers_for_platform": "igdb_publishers_for_platform",
        "release_date_for_platform": "igdb_release_date_for_platform",
        "region_for_platform": "igdb_region_for_platform",
        "platforms_all": "igdb_platforms_all",
        "release_dates_all": "igdb_release_dates_all",
        "cover_url": "igdb_cover_url",
        "confidence": "igdb_confidence",
        "source": "igdb_source",
    }
    ig = ig.rename(columns={k: v for k, v in ig_cols_rename.items() if k in ig.columns})

    # -------------------------------------------------------------------------
    # Mergar GB + IGDB på edition_id
    # -------------------------------------------------------------------------
    base = gb.merge(ig, on="edition_id", how="outer", suffixes=("_gb_unused", "_igdb_unused"))

    # Canonical title/platform (föredra GB om finns, annars IGDB)
    base["title_primary"] = base.apply(
        lambda r: coalesce(r.get("title_primary_gb", ""), r.get("title_primary_igdb", "")),
        axis=1,
    )
    base["platform"] = base.apply(
        lambda r: coalesce(r.get("platform_gb", ""), r.get("platform_igdb", "")),
        axis=1,
    )

    # IDs + konfidenser
    base["gb_game_id"] = base.get("gb_game_id", "")
    base["igdb_game_id"] = base.get("igdb_game_id", "")
    base["gb_confidence"] = base.get("gb_confidence", "")
    base["igdb_confidence"] = base.get("igdb_confidence", "")

    # primary_source: GB om den finns, annars IGDB, annars tomt
    def pick_source(row) -> str:
        has_gb = bool(str(row.get("gb_game_id", "")).strip())
        has_ig = bool(str(row.get("igdb_game_id", "")).strip())
        if has_gb:
            return "giantbomb"
        if has_ig:
            return "igdb"
        return ""

    base["primary_source"] = base.apply(pick_source, axis=1)

    def pick_field(row: Any, gb_col: str, ig_col: str) -> str:
        """
        Välj fält från GB eller IGDB beroende på primary_source.
        """
        src = row.get("primary_source", "")
        if src == "giantbomb":
            return str(row.get(gb_col, "") or "").strip()
        if src == "igdb":
            return str(row.get(ig_col, "") or "").strip()
        # fallback om inget primärt
        return coalesce(str(row.get(gb_col, "") or ""), str(row.get(ig_col, "") or ""))

    base["name"] = base.apply(
        lambda r: pick_field(r, "gb_name", "igdb_name"),
        axis=1,
    )
    base["genres"] = base.apply(
        lambda r: pick_field(r, "gb_genres", "igdb_genres"),
        axis=1,
    )
    base["developers_for_platform"] = base.apply(
        lambda r: pick_field(r, "gb_developers_for_platform", "igdb_developers_for_platform"),
        axis=1,
    )
    base["publishers_for_platform"] = base.apply(
        lambda r: pick_field(r, "gb_publishers_for_platform", "igdb_publishers_for_platform"),
        axis=1,
    )
    base["release_date_for_platform"] = base.apply(
        lambda r: pick_field(r, "gb_release_date_for_platform", "igdb_release_date_for_platform"),
        axis=1,
    )
    base["region_for_platform"] = base.apply(
        lambda r: pick_field(r, "gb_region_for_platform", "igdb_region_for_platform"),
        axis=1,
    )
    base["platforms_all"] = base.apply(
        lambda r: pick_field(r, "gb_platforms_all", "igdb_platforms_all"),
        axis=1,
    )
    base["release_dates_all"] = base.apply(
        lambda r: pick_field(r, "gb_release_dates_all", "igdb_release_dates_all"),
        axis=1,
    )
    base["cover_url"] = base.apply(
        lambda r: pick_field(r, "gb_cover_url", "igdb_cover_url"),
        axis=1,
    )

    base_out_cols = [
        "edition_id",
        "title_primary",
        "platform",
        "gb_game_id",
        "igdb_game_id",
        "name",
        "genres",
        "developers_for_platform",
        "publishers_for_platform",
        "release_date_for_platform",
        "region_for_platform",
        "platforms_all",
        "release_dates_all",
        "cover_url",
        "primary_source",
        "gb_confidence",
        "igdb_confidence",
    ]
    base_out = base.loc[:, [c for c in base_out_cols if c in base.columns]].copy()

    # -------------------------------------------------------------------------
    # Mergar in Wikidata
    # -------------------------------------------------------------------------
    if "edition_id" not in wd.columns:
        raise SystemExit("❌ Wikidata-fil saknar kolumnen 'edition_id'")

    drop_from_wd = [c for c in ["title_primary", "platform", "source"] if c in wd.columns]
    wd_clean = wd.drop(columns=drop_from_wd)

    merged = base_out.merge(wd_clean, on="edition_id", how="left")

    # -------------------------------------------------------------------------
    # Mergar in Wikipedia
    # -------------------------------------------------------------------------
    if "edition_id" not in wiki.columns:
        raise SystemExit("❌ Wikipedia-fil saknar kolumnen 'edition_id'")

    drop_from_wiki = [c for c in ["source"] if c in wiki.columns]
    wiki_clean = wiki.drop(columns=drop_from_wiki)

    final = merged.merge(wiki_clean, on="edition_id", how="left")

    # -------------------------------------------------------------------------
    # Slutgiltig masterkedja för centrala fält
    # -------------------------------------------------------------------------
    # Developer:
    #  1) Wikidata (plattform-specifik), 2) Wikidata (sammanfattning),
    #  3) Wikipedia (infobox), 4) GB/IGDB developers_for_platform
    def pick_developer(row: Any) -> str:
        return coalesce(
            row.get("developer_p178_for_platform", ""),
            row.get("developer_p178", ""),
            row.get("developer_p178_all", ""),
            row.get("wiki_developer", ""),
            row.get("developers_for_platform", ""),
        )

    # Publisher:
    #  1) Wikidata (plattform-specifik), 2) Wikidata (sammanfattning),
    #  3) Wikipedia (infobox), 4) GB/IGDB publishers_for_platform
    def pick_publisher(row: Any) -> str:
        return coalesce(
            row.get("publisher_p123_for_platform", ""),
            row.get("publisher_p123", ""),
            row.get("publisher_p123_all", ""),
            row.get("wiki_publisher", ""),
            row.get("publishers_for_platform", ""),
        )

    # Övriga kreativa roller – just nu bara från Wikipedia
    def pick_role(row: Any, wiki_col: str) -> str:
        return coalesce(row.get(wiki_col, ""))

    final["developer"] = final.apply(pick_developer, axis=1)
    final["publisher"] = final.apply(pick_publisher, axis=1)

    # Credits-fält från Wikipedia-infobox
    final["director"] = final.apply(lambda r: pick_role(r, "wiki_director"), axis=1)
    final["producer"] = final.apply(lambda r: pick_role(r, "wiki_producer"), axis=1)
    final["designer"] = final.apply(lambda r: pick_role(r, "wiki_designer"), axis=1)
    final["programmer"] = final.apply(lambda r: pick_role(r, "wiki_programmer"), axis=1)
    final["artist"] = final.apply(lambda r: pick_role(r, "wiki_artist"), axis=1)
    final["composer"] = final.apply(lambda r: pick_role(r, "wiki_composer"), axis=1)

    # -------------------------------------------------------------------------
    # Skriv ut masterfil
    # -------------------------------------------------------------------------
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(out_path, index=False, encoding="utf-8")

    n_rows = len(final)
    n_wd = (final.get("wikidata_qid", "") != "").sum() if "wikidata_qid" in final.columns else 0
    n_wiki = (final.get("wiki_has_infobox", "") == "1").sum() if "wiki_has_infobox" in final.columns else 0

    print(f"✅ Skrev {n_rows} rader → {out_path}")
    print(f"🔗 Med Wikidata-länk (wikidata_qid != ''): {n_wd} st")
    print(f"📚 Med Wikipedia-infobox (wiki_has_infobox == '1'): {n_wiki} st")


if __name__ == "__main__":
    main()
