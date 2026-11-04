# src/run_pipeline.py
from __future__ import annotations 
#tillåter att typ-annoteringar ej behöver utvärderas direkt (framtidssäker python-syntax)
import subprocess
#används för att köra andra program/kommandon (andra python skriipt som separata processer)
import sys
#hämta rätt python-exekverare och avbryta programmet om ett steg misslyckas
from pathlib import Path

import shutil 

ROOT = Path(__file__).resolve().parents[1]  # repo-root (pekar en nivå upp från src)
OUT_DIR = ROOT / "data" / "outputs"

def run_step(name: str, cmd: list[str]) -> None:
    """
    Kör ett kommando, skriv ut en tydlig rubrik och avbryt pipelinen om något steg failar.
    """
    #skriv en visuell avdelare så man ser vilket steg som körs
    print("\n" + "=" * 80)
    print(f"▶ {name}")              #visa namnet på steget
    print("   " + " ".join(cmd))     # visa exakt kommandot som körs (bra för debugging)
    print("=" * 80)

    #kör kommandot i en separat process
    result = subprocess.run(cmd, cwd=ROOT)      #cwd=ROOT gör så skript körs som om vi stod i projektrot 
                                                #oavsett var användaren kör run_pipeline.py ifrån
    if result.returncode != 0:
        print(f"\n❌ Steg '{name}' misslyckades (exit code {result.returncode}). Avbryter pipeline.")
        sys.exit(result.returncode)
        #om kommandot inte returnerar 0 (dvs det kraschar) avslutas hela pipelinen

    print(f"✅ Klart: {name}")

#---------------------------------------------------------------------------------

def find_catalog_csv() -> str:
    """
    Hittar den enda .csv-filen i data/raw/ och returnerar dess relativa sökväg.
    Avbryter pipelinen om det saknas eller finns flera CSV-filer.
    """
    raw_dir = ROOT / "data" / "raw"
    csv_files = list(raw_dir.glob("*.csv"))

    if not csv_files:
        print("❌ Ingen CSV-fil hittad i data/raw/. Lägg dit katalogexporten.")
        sys.exit(1)

    if len(csv_files) > 1:
        print("❌ Fler än en CSV i data/raw/, kan inte veta vilken som är katalogfilen:")
        for f in csv_files:
            print("   -", f.name)
        sys.exit(1)

    # gör sökvägen relativ till ROOT eftersom subprocess körs med cwd=ROOT
    return str(csv_files[0].relative_to(ROOT))


#----------------------------------------------------------------------------------------
def clean_outputs() -> None:
    """
    Rensa outputs från tidigare körningar så att pipelinen alltid
    jobbar på en ren uppsättning filer.
    Rör INTE data/raw eller configs.
    """
    debug_dir = OUT_DIR / "debug"
    enr_dir = OUT_DIR / "enrichment"

    # Töm debug/
    if debug_dir.exists():
        for f in debug_dir.glob("*"):
            try:
                f.unlink()
            except Exception as e:
                print(f"⚠️ Kunde inte ta bort {f}: {e}")

    # Töm enrichment/
    if enr_dir.exists():
        for f in enr_dir.glob("*.csv"):
            try:
                f.unlink()
            except Exception as e:
                print(f"⚠️ Kunde inte ta bort {f}: {e}")

    # Ta bort centrala CSV:er som byggs om varje gång
    for fname in [
        "releases.csv",
        "release_sources.csv",
        "items_to_editions.csv",
        "objects_expanded.csv",
        "editions.csv",
        "editions_enriched_master.csv",
        "catalog_enriched_embracer.csv",
        "_normalize_summary.csv",
    ]:
        f = OUT_DIR / fname
        if f.exists():
            try:
                f.unlink()
            except Exception as e:
                print(f"⚠️ Kunde inte ta bort {f}: {e}")



def main() -> None:
    #börjar alltid med en ren output-mapp
    clean_outputs()
    # ===============================================================
    # 1) NORMALISERA råkatalogen
    # ===============================================================
    #    - Läser alla CSV i data/raw/
    #    - Städar/ standardiserar kolumner
    #    - Skriver debug-filer: data/outputs/debug/_debug_normalized_*.csv
    run_step(
        "normalize_one",
        [
            sys.executable,     #kör samma python som anropar skriptet
            "src/normalize_one.py", #skriptet som körs
        ],
    )

    # ===============================================================
    # 2) BYGG releases / editions / items_to_editions / objects_expanded
    # ===============================================================
    #    - Läser normalized-debug-filerna i data/outputs/debug/
    #    - grupperar rader till "editioner"
    #    - skapar edition_id för varje unik release
    #    - bygger länk-tabeller mellan objekt och editioner
    #    - Skriver:
    #         data/outputs/releases.csv
    #         data/outputs/release_sources.csv
    #         data/outputs/items_to_editions.csv
    #         data/outputs/objects_expanded.csv
    #         data/outputs/editions.csv
    run_step(
        "build_releases",
        [
            sys.executable,
            "src/build_releases.py",
        ],
    )

    # ===============================================================
    # 3) IGDB ENRICHMENT (per edition_id)
    # ===============================================================
    #    läser editions.csv
    #    söker matchningar i IGDB
    #    hämtar metadata som ...
    #    begränsningar:
    #    --limit 0 (ingen gräns på antal editioner att berika)
    #    --per_title_limit 5 (max 5 IGDB-matcher per titel/edition)
    #    skriver data/outputs/enrichment/igdb_enrichment.csv

    run_step(
        "igdb_enrich_editions",
        [
            sys.executable,
            "src/igdb_enrich_editions.py",
            "--input", "data/outputs/editions.csv",
            "--output", "data/outputs/enrichment/igdb_enrichment.csv",
            "--limit", "0",           #kör på alla editioner  
            "--per_title_limit", "5", #max 5 IGDB-matcher per titel
        ],
    )

    # ===============================================================
    # 4) GIANTBOMB ENRICHMENT (per edition_id)
    # ===============================================================
    #    Liknar IGDB-steget:
    #    - Matchar varje edition mot GiantBomb
    #    - hämtar metadata
    #    - skriver data/outputs/enrichment/giantbomb_enrichment.csv
    run_step(
        "gb_enrich_editions",
        [
            sys.executable,
            "src/gb_enrich_editions.py",
            "--in", "data/outputs/editions.csv",
            "--out", "data/outputs/enrichment/giantbomb_enrichment.csv",
            "--limit", "0",
        ],
    )

    # ===============================================================
    # 5) WIKIDATA ENRICHMENT 
    # ===============================================================
    # Stegen:
    # - söker spel på wikidata
    # - hämtar fakta som release-år, land, utvecklare, Q-ID osv.
    # - Skriver två filer:
    #      - skriver data/outputs/enrichment/wikidata_enrichment.csv (slutresultat per edition)
    #      - skriver data/outputs/enrichment/wikidata_candidates.csv (alla kandidater per edition, bra för QA)


    run_step(
        "enrich_wikidata",
        [
            sys.executable,
            "src/enrich_wikidata.py",
            "--in", "data/outputs/editions.csv",
            "--out", "data/outputs/enrichment/wikidata_enrichment.csv",
            "--candidates_out", "data/outputs/enrichment/wikidata_candidates.csv",
            "--limit", "0",
        ],
    )

    # ===============================================================
    # 6) ENRICHMENT: WIKIPEDIA (INFOBOX-DATA)
    # ===============================================================
    # Steget:
    # - läser editions.csv
    # - besöker Wikipedia-sidor
    # - hämtar infobox-information som t.ex. roller (dev/publisher)
    run_step(
        "enrich_wikipedia",
        [
            sys.executable,
            "src/enrich_wikipedia.py",
            "--in", "data/outputs/editions.csv",
            "--out", "data/outputs/enrichment/wikipedia_enrichment.csv",
            "--limit", "0",
        ],
    )

    # ===============================================================
    # 7) MERGE ALLA ENRICHMENT-FILER TILL EN MASTERFIL
    # ===============================================================
    # Steget:
    # - slår ihop IGDB + GiantBomb + Wikidata + Wikipedia per edition_id
    # - skapar data/outputs/editions_enriched_master.csv
    run_step(
        "merge_enriched",
        [
            sys.executable,
            "src/merge_enriched.py",
            "--gb", "data/outputs/enrichment/giantbomb_enrichment.csv",
            "--igdb", "data/outputs/enrichment/igdb_enrichment.csv",
            "--wikidata", "data/outputs/enrichment/wikidata_enrichment.csv",
            "--wikipedia", "data/outputs/enrichment/wikipedia_enrichment.csv",
            "--out", "data/outputs/editions_enriched_master.csv",
        ],
    )

    # ===============================================================
    # 8) SKAPA EMBRACER-VYN (DEN SLUTLIGA KATALOGLIKNANDE CSV)
    # ===============================================================
    # Steget:
    # - läser originalkatalogen från data/raw/
    # - läser länk-tabell items_to_editions.csv
    # - läser enriched-master
    # - kopplar ihop allt
    # - skriver slutfilen:
    #     catalog_enriched_embracer.csv
    run_step(
        "export_enriched_catalog",
        [
            sys.executable,
            "src/export_enriched_catalog.py",
            "--catalog", find_catalog_csv(), #gör så den alltid hittar filen i raw mappen
            "--links", "data/outputs/items_to_editions.csv",
            "--master", "data/outputs/editions_enriched_master.csv",
            "--out", "data/outputs/catalog_enriched_embracer.csv",
        ],
    )

    print("\n🎉 PIPELINE KLAR!")
    print("   - editions_enriched_master.csv klar")
    print("   - catalog_enriched_embracer.csv klar (Embracer-vyn med info_confidence_* )")


if __name__ == "__main__":
    main()
