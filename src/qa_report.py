from pathlib import Path
import pandas as pd

OUT_DIR = Path("data/outputs")
DEBUG_DIR = OUT_DIR / "debug"
QA_DIR = OUT_DIR / "qa"
QA_DIR.mkdir(parents=True, exist_ok=True)


def read_csv_safe(p: Path, dtype=str):
    """
    Läs en CSV om den finns, annars returnera tom DataFrame och skriv ett meddelande.
    """
    if not p.exists():
        print(f"❌ Saknas: {p}")
        return pd.DataFrame()
    try:
        return pd.read_csv(p, dtype=dtype).fillna("")
    except Exception as e:
        print(f"❌ Kunde inte läsa {p}: {e}")
        return pd.DataFrame()


def main():
    # --- Läs in huvudfiler från pipelinen ---
    releases  = read_csv_safe(OUT_DIR / "releases.csv")
    editions  = read_csv_safe(OUT_DIR / "editions.csv")
    items     = read_csv_safe(OUT_DIR / "items_to_editions.csv")
    objects_x = read_csv_safe(OUT_DIR / "objects_expanded.csv")

    # Enriched Embracer-vy (slutkatalogen)
    catalog  = read_csv_safe(OUT_DIR / "catalog_enriched_embracer.csv")

    # --- Snabb sanity ---
    print("=== QA: INPUT ===")
    print(
        f"releases: {len(releases)} | "
        f"editions: {len(editions)} | "
        f"items_to_editions: {len(items)} | "
        f"objects_expanded: {len(objects_x)} | "
        f"catalog_enriched_embracer: {len(catalog)}"
    )

    # -------------------------------------------------------------------------
    # 1) UNK/xx översikter på releases-nivå
    # -------------------------------------------------------------------------
    if not releases.empty:
        unk_countries = releases[releases["country"] == "UNK"].copy()
        unk_langs     = releases[releases["language"] == "xx"].copy()
    else:
        unk_countries = pd.DataFrame()
        unk_langs = pd.DataFrame()

    unk_countries.to_csv(QA_DIR / "unk_countries.csv", index=False, encoding="utf-8")
    unk_langs.to_csv(QA_DIR / "xx_languages.csv", index=False, encoding="utf-8")

    # Top “hint-ord” från place_of_publication för UNK (om vi vill felsöka vidare)
    def top_tokens(series, n=20):
        from collections import Counter
        c = Counter()
        for s in series.fillna(""):
            for tok in str(s).lower().replace(",", " ").replace("|", " ").split():
                if 2 <= len(tok) <= 30:
                    c[tok] += 1
        return pd.DataFrame(c.most_common(n), columns=["token", "count"])

    # noop, håller API simpelt – kan aktiveras senare vid behov
    if "source_object" in releases.columns and "source_object" in objects_x.columns:
        # Tänkbar plats att göra mer avancerad analys mellan releases och objects_expanded.
        pass

    # -------------------------------------------------------------------------
    # 2) Unika nycklar & dubbletter
    # -------------------------------------------------------------------------
    # editions PK: edition_id
    if not editions.empty:
        dupe_editions = editions[editions.duplicated("edition_id", keep=False)].sort_values("edition_id")
    else:
        dupe_editions = pd.DataFrame()
    dupe_editions.to_csv(QA_DIR / "dupe_editions_by_id.csv", index=False, encoding="utf-8")

    # releases “unik”: (edition_id, country, language, release_date)
    if not releases.empty:
        key_cols = (
            ["edition_id", "country", "language", "release_date"]
            if "release_date" in releases.columns
            else ["edition_id", "country", "language"]
        )
        dupe_releases = releases[releases.duplicated(key_cols, keep=False)].sort_values(key_cols)
    else:
        dupe_releases = pd.DataFrame()
    dupe_releases.to_csv(QA_DIR / "dupe_releases_by_key.csv", index=False, encoding="utf-8")

    # items_to_editions “unik”: (object_number, edition_id)
    if not items.empty:
        dupe_items = items[items.duplicated(["object_number", "edition_id"], keep=False)].sort_values(
            ["object_number", "edition_id"]
        )
    else:
        dupe_items = pd.DataFrame()
    dupe_items.to_csv(QA_DIR / "dupe_items_links.csv", index=False, encoding="utf-8")

    # -------------------------------------------------------------------------
    # 3) Orphans (saknade relationer)
    # -------------------------------------------------------------------------
    # items → editions (edition_id som inte finns)
    if not items.empty and not editions.empty:
        missing_ed = items.merge(editions[["edition_id"]], on="edition_id", how="left", indicator=True)
        missing_ed = missing_ed[missing_ed["_merge"] == "left_only"].drop(columns="_merge")
    else:
        missing_ed = pd.DataFrame()
    missing_ed.to_csv(QA_DIR / "orphans_items_missing_edition.csv", index=False, encoding="utf-8")

    # releases → editions (edition_id som inte finns)
    if not releases.empty and not editions.empty:
        missing_rel_ed = releases.merge(editions[["edition_id"]], on="edition_id", how="left", indicator=True)
        missing_rel_ed = missing_rel_ed[missing_rel_ed["_merge"] == "left_only"].drop(columns="_merge")
    else:
        missing_rel_ed = pd.DataFrame()
    missing_rel_ed.to_csv(QA_DIR / "orphans_releases_missing_edition.csv", index=False, encoding="utf-8")

    # objects_expanded: barn utan parent?
    if not objects_x.empty and "is_virtual_child" in objects_x.columns and "parent_object" in objects_x.columns:
        orphans_children = objects_x[
            (objects_x["is_virtual_child"] == True)
            & (objects_x["parent_object"].astype(str).str.len() == 0)
        ]
    else:
        orphans_children = pd.DataFrame()
    orphans_children.to_csv(QA_DIR / "orphans_children_no_parent.csv", index=False, encoding="utf-8")

    # -------------------------------------------------------------------------
    # 4) Bundles-rapport
    # -------------------------------------------------------------------------
    if not objects_x.empty and "is_virtual_child" in objects_x.columns:
        bundles = (
            objects_x[objects_x["is_virtual_child"] == True]
            .groupby("parent_object")["object_id"]
            .count()
            .sort_values(ascending=False)
        )
        bundles = bundles.reset_index().rename(columns={"object_id": "child_count"})
    else:
        bundles = pd.DataFrame(columns=["parent_object", "child_count"])
    bundles.to_csv(QA_DIR / "bundles_summary.csv", index=False, encoding="utf-8")

    # -------------------------------------------------------------------------
    # 5) Konsolöversikt över QA-resultat i terminalen
    # -------------------------------------------------------------------------
    def count_or_empty(df): 
        return len(df) if not df.empty else 0

    print("\n=== QA: SUMMARY (core relations) ===")
    print(f"UNK countries              : {count_or_empty(unk_countries)}  -> data/outputs/qa/unk_countries.csv")
    print(f"xx languages               : {count_or_empty(unk_langs)}      -> data/outputs/qa/xx_languages.csv")
    print(f"Dupe editions              : {count_or_empty(dupe_editions)}  -> data/outputs/qa/dupe_editions_by_id.csv")
    print(f"Dupe releases              : {count_or_empty(dupe_releases)}  -> data/outputs/qa/dupe_releases_by_key.csv")
    print(f"Dupe items-map             : {count_or_empty(dupe_items)}     -> data/outputs/qa/dupe_items_links.csv")
    print(f"Items missing edition      : {count_or_empty(missing_ed)}     -> data/outputs/qa/orphans_items_missing_edition.csv")
    print(f"Releases missing edition   : {count_or_empty(missing_rel_ed)} -> data/outputs/qa/orphans_releases_missing_edition.csv")
    print(f"Children without parent    : {count_or_empty(orphans_children)} -> data/outputs/qa/orphans_children_no_parent.csv")
    if not bundles.empty:
        print("\nTop bundles by child_count:")
        print(bundles.head(10).to_string(index=False))

    # -------------------------------------------------------------------------
    # 6) Bonus: topp-frekventa UNK/xx per titel/plattform (felsökning)
    # -------------------------------------------------------------------------
    if not releases.empty and "title_primary" in releases.columns and "platform" in releases.columns:
        unk_titles = (
            releases[releases["country"] == "UNK"]
            .groupby(["title_primary", "platform"], as_index=False)
            .size()
            .sort_values("size", ascending=False)
            .head(20)
        )
        unk_titles.to_csv(QA_DIR / "top_unk_titles.csv", index=False, encoding="utf-8")

        xx_titles = (
            releases[releases["language"] == "xx"]
            .groupby(["title_primary", "platform"], as_index=False)
            .size()
            .sort_values("size", ascending=False)
            .head(20)
        )
        xx_titles.to_csv(QA_DIR / "top_xx_titles.csv", index=False, encoding="utf-8")

        print("\nTop UNK titles (saved to top_unk_titles.csv):")
        if not unk_titles.empty:
            print(unk_titles.head(10).to_string(index=False))

        print("\nTop xx titles (saved to top_xx_titles.csv):")
        if not xx_titles.empty:
            print(xx_titles.head(10).to_string(index=False))

    # -------------------------------------------------------------------------
    # 7) Enrichment-stats för catalog_enriched_embracer.csv
    # -------------------------------------------------------------------------
    print("\n=== ENRICHMENT STATS (catalog_enriched_embracer) ===")
    if catalog.empty:
        print("Ingen catalog_enriched_embracer.csv hittades eller filen är tom.")
    else:
        # Kolla att kolumnerna finns
        has_flag = "info_confidence_flag" in catalog.columns
        has_score = "info_confidence_score" in catalog.columns

        if has_flag:
            flag_counts = catalog["info_confidence_flag"].value_counts()
            flag_counts.to_csv(QA_DIR / "catalog_confidence_flags.csv", header=["count"], encoding="utf-8")
            print("\nFördelning info_confidence_flag:")
            print(flag_counts.to_string())

        if has_score:
            score_counts = catalog["info_confidence_score"].value_counts().sort_index()
            score_counts.to_csv(QA_DIR / "catalog_confidence_scores.csv", header=["count"], encoding="utf-8")
            print("\nFördelning info_confidence_score:")
            print(score_counts.to_string())

        # Spara high/medium/low separata filer för manuell QA
        if has_flag:
            high = catalog[catalog["info_confidence_flag"] == "high"]
            med  = catalog[catalog["info_confidence_flag"] == "medium"]
            low  = catalog[catalog["info_confidence_flag"] == "low"]

            high.to_csv(QA_DIR / "catalog_high_confidence.csv", index=False, encoding="utf-8")
            med.to_csv(QA_DIR / "catalog_medium_confidence.csv", index=False, encoding="utf-8")
            low.to_csv(QA_DIR / "catalog_low_confidence.csv", index=False, encoding="utf-8")

            print(f"\nHigh confidence rows  : {len(high)}  -> data/outputs/qa/catalog_high_confidence.csv")
            print(f"Medium confidence rows: {len(med)}   -> data/outputs/qa/catalog_medium_confidence.csv")
            print(f"Low confidence rows   : {len(low)}   -> data/outputs/qa/catalog_low_confidence.csv")

            # Visa några sämsta rader direkt i terminalen
            if has_score and not low.empty:
                print("\nExempel på LOW-confidence-rader (lägsta scores först):")
                worst = (
                    low.sort_values("info_confidence_score", ascending=True)
                    .head(10)
                    .loc[:, ["object_number", "title", "platform", "developer", "publisher", "info_confidence_score", "info_confidence_flag"]]
                )
                print(worst.to_string(index=False))

    print("\n✅ QA-rapport klar. Se data/outputs/qa/ för detaljerade CSV-filer.")


if __name__ == "__main__":
    main()
