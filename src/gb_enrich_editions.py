# src/gb_enrich_editions.py
# YAML-driven GiantBomb-enrichment för alla plattformar i editions.csv
from __future__ import annotations

import argparse
import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import pandas as pd
import yaml

from gb_client import _gb_get, game_detail, game_releases, join_names

# ------------------------------------------------------------
# Paths / konstanter
# ------------------------------------------------------------

ED_PATH = Path("data/outputs/editions.csv")

OUT_DIR = Path("data/outputs/enrichment")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = OUT_DIR / "giantbomb_enrichment.csv"

# Alla QA-relaterade saker (inkl. loggar) hamnar här:
QA_DIR = Path("data/outputs/qa")
QA_DIR.mkdir(parents=True, exist_ok=True)

PLATFORM_MAP_PATH = Path("configs/platform_map.yaml")

# Versionstagg för hur vi score:ar / loggar GiantBomb
SCORING_VERSION = "gb_v1_2025-01-01"


# ---------------------------------------------------------------------------
# Ladda plattformsalias från platform_map.yaml
# ---------------------------------------------------------------------------

def load_platform_aliases() -> Dict[str, List[str]]:
    """
    Läser configs/platform_map.yaml och plockar ut alias_map + försöker även
    komplettera med nycklar ur exact_map där värdet matchar koden.

    Resultat: { "SNES": ["Super Nintendo Entertainment System", "Super NES", ...], ... }
    """
    if not PLATFORM_MAP_PATH.exists():
        return {}

    with PLATFORM_MAP_PATH.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    alias_map = cfg.get("alias_map", {}) or {}
    exact_map = cfg.get("exact_map", {}) or {}

    out: Dict[str, List[str]] = {}

    # 1) alias_map: redan i rätt format
    for code, aliases in alias_map.items():
        if isinstance(aliases, list):
            out.setdefault(code, [])
            out[code].extend(str(a) for a in aliases)
        elif isinstance(aliases, str):
            out.setdefault(code, [])
            out[code].append(aliases)

    # 2) plocka alla nycklar i exact_map som mappar till en given code
    for raw_name, code in exact_map.items():
        code = str(code)
        out.setdefault(code, [])
        out[code].append(str(raw_name))

    # städa & dedupe
    for code, names in out.items():
        seen = set()
        clean = []
        for n in names:
            n_norm = " ".join(str(n).split())
            if n_norm and n_norm.lower() not in seen:
                seen.add(n_norm.lower())
                clean.append(n_norm)
        out[code] = clean

    return out


# ---------------------------------------------------------------------------
# Titel-normalisering, tokens, siffror
# ---------------------------------------------------------------------------

STOPWORDS = {
    "the", "and", "of", "in",
    "edition", "remaster", "collection",
    "hd", "ultimate", "deluxe", "game",
}

ROMAN_MAP = {
    "i": 1,
    "ii": 2,
    "iii": 3,
    "iv": 4,
    "v": 5,
    "vi": 6,
    "vii": 7,
    "viii": 8,
    "ix": 9,
    "x": 10,
    "xi": 11,
    "xii": 12,
    "xiii": 13,
    "xiv": 14,
    "xv": 15,
    "xvi": 16,
    "xvii": 17,
    "xviii": 18,
    "xix": 19,
    "xx": 20,
}


def norm_spaces(s: str) -> str:
    """Trimma whitespace och slå ihop flera spaces till ett."""
    return re.sub(r"\s+", " ", (s or "").strip())


def normalize_title(s: str) -> str:
    """
    Normalisera titlar:
      - ersätt konstiga multiplikationstecken med 'x'
      - normalisera olika streck
      - ta bort parenteser
      - trimma whitespace
    """
    s = (s or "").replace("×", "x").replace("✕", "x").replace("✖", "x")
    s = s.replace("—", "-").replace("–", "-")
    s = re.sub(r"[(){}\[\]]", " ", s)
    return norm_spaces(s)


def title_tokens(s: str) -> List[str]:
    """Tokenisera titel till små bokstäver, filtrera bort stopwords."""
    s = normalize_title(s).lower()
    toks = re.split(r"[^a-z0-9]+", s)
    return [t for t in toks if t and t not in STOPWORDS]


def extract_numbers(s: str) -> List[int]:
    """
    Hämta ut siffror i titeln både som:
      - vanliga heltal (2, 3, 2020)
      - romerska tal (II, III, IV, …)
    """
    s = normalize_title(s).lower()
    nums = [int(n) for n in re.findall(r"\b\d+\b", s)]
    romans = [
        ROMAN_MAP[g]
        for g in re.findall(
            r"\b(i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii|xiii|xiv|xv|xvi|xvii|xviii|xix|xx)\b",
            s,
        )
    ]
    return sorted(set(nums + romans))


def token_overlap(a: str, b: str) -> int:
    """Antal gemensamma tokens mellan två titlar."""
    A = set(title_tokens(a))
    B = set(title_tokens(b))
    return len(A & B)


def numbers_compatible(q: str, n: str) -> bool:
    """
    Siffror/romerska i titlarna ska antingen saknas båda – eller vara samma uppsättning.
    (Golden Axe II ↔ Golden Axe 2 är OK, men 2 ↔ 3 är inte OK.)
    """
    qa = extract_numbers(q)
    nb = extract_numbers(n)
    if not qa and not nb:
        return True
    return set(qa) == set(nb)


def score_title(query: str, name: str) -> int:
    """
    Enkel titelscore:
      - 4 = exakt match efter normalisering
      - annars = token_overlap (0..N)
    """
    qn = normalize_title(query).lower()
    nn = normalize_title(name).lower()
    if qn and nn and qn == nn:
        return 4  # exakt match
    return token_overlap(query, name)  # 0..N


# ---------------------------------------------------------------------------
# GiantBomb-klient (search) + plattforms-matchning
# ---------------------------------------------------------------------------

def search_games(query: str, limit: int = 12) -> List[dict]:
    """
    Söker spel på GiantBomb via /search/ endpoint.
    Returnerar listan med 'results' (id, name, platforms, original_release_date).
    """
    if not query or not query.strip():
        return []
    params = {
        "query": query,
        "resources": "game",
        "limit": int(limit),
        "field_list": "id,name,platforms,original_release_date",
    }
    data = _gb_get("/search/", params)
    return data.get("results") or []


def platform_name_matches(
    plat_norm: str,
    candidate_name: str,
    aliases: Dict[str, List[str]],
) -> bool:
    """
    Jämför GiantBombs plattformsnamn mot vår alias-lista från platform_map.yaml.
    Matchar på casefold + 'equals or contains'.
    """
    cand = norm_spaces(candidate_name).casefold()
    if not cand:
        return False

    alias_list = aliases.get(plat_norm, [])
    alias_cf = [norm_spaces(a).casefold() for a in alias_list]

    for a in alias_cf:
        if not a:
            continue
        if cand == a or cand in a or a in cand:
            return True
    return False


def platform_match_score(
    plat_norm: str,
    candidate_platforms: List[dict],
    aliases: Dict[str, List[str]],
) -> int:
    """
    Returnerar 1 om minst en GiantBomb-plattform matchar med våra alias; annars 0.
    Om vi saknar alias för koden → 0 (hanteras i pick_best_hit med fallback).
    """
    if not candidate_platforms:
        return 0
    for p in candidate_platforms:
        name = (p or {}).get("name", "") or ""
        if platform_name_matches(plat_norm, name, aliases):
            return 1
    return 0


def parse_year(dt: str) -> Optional[int]:
    """(Finns kvar om vi vill använda år senare, just nu ej använd.)"""
    if not dt:
        return None
    try:
        return int(dt[:4])
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Kandidatval
# ---------------------------------------------------------------------------

def pick_best_hit(
    title: str,
    plat_norm: str,
    hits: List[dict],
    aliases: Dict[str, List[str]],
) -> Tuple[Optional[dict], Tuple[int, int]]:
    """
    Välj bästa GiantBomb-träff för en (title, platform_norm).

    Steg:
      1) Primärt: kräver plattforms-match (om alias finns) + rimlig titelscore.
      2) Fallback: om vi saknar alias för plattformen → bästa titelmatch oavsett plattform.

    Returnerar (best_hit_dict, (platform_match, title_score)).
    """
    scored: List[Tuple[Tuple[int, int], dict]] = []

    # Primär pass: kräver plattformsmatch (om alias finns) + rimlig titelmatch
    for h in hits or []:
        name = h.get("name", "") or ""
        tscore = score_title(title, name)
        pmatch = platform_match_score(plat_norm, h.get("platforms") or [], aliases)

        # Om vi HAR alias för plattformen men pmatch==0 → kasta bort
        if plat_norm in aliases and pmatch != 1:
            continue

        # Titel måste vara vettig
        if tscore < 3 and tscore != 4:
            continue
        if not numbers_compatible(title, name):
            continue

        scored.append(((pmatch, tscore), h))

    if scored:
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[0]
        return top[1], top[0]

    # Fallback: om vi inte har alias för plattformen → välj bästa titelmatch oavsett plattform
    if plat_norm not in aliases:
        fallback: List[Tuple[int, dict]] = []
        for h in hits or []:
            name = h.get("name", "") or ""
            tscore = score_title(title, name)
            if tscore < 3 and tscore != 4:
                continue
            if not numbers_compatible(title, name):
                continue
            fallback.append((tscore, h))
        if fallback:
            fallback.sort(key=lambda x: x[0], reverse=True)
            best = fallback[0]
            return best[1], (0, best[0])

    return None, (0, 0)


# ---------------------------------------------------------------------------
# Releases-formattering
# ---------------------------------------------------------------------------

def format_release_dates_all(rels: List[dict]) -> str:
    """
    Gör en kompakt sträng med alla releases:
      "YYYY-MM-DD <Platform | Region> | ..."
    """
    out: List[str] = []
    for r in rels or []:
        dt = r.get("release_date") or r.get("date_added") or ""
        plat = ((r.get("platform") or {}).get("name")) or ""
        reg = ((r.get("region") or {}).get("name")) or ""
        if dt and plat:
            if reg:
                out.append(f"{dt} <{plat} | {reg}>")
            else:
                out.append(f"{dt} <{plat}>")
    return " | ".join(out)


def first_platform_release(
    rels: List[dict],
    plat_norm: str,
    aliases: Dict[str, List[str]],
) -> Tuple[str, str]:
    """
    Välj första release (äldsta datum) där plattformsnamnet matchar vår plat_norm via alias.
    Returnerar (release_date_iso, region_name) eller ("","") om ingen hittas.
    """
    candidates: List[Tuple[str, str]] = []

    for r in rels or []:
        plat_name = ((r.get("platform") or {}).get("name")) or ""
        if not platform_name_matches(plat_norm, plat_name, aliases):
            continue

        dt_raw = r.get("release_date") or r.get("date_added") or ""
        if not dt_raw:
            continue

        try:
            d = datetime.fromisoformat(dt_raw.split(" ")[0]).date()
            dt_norm = d.isoformat()
        except Exception:
            dt_norm = dt_raw

        region_name = ((r.get("region") or {}).get("name")) or ""
        candidates.append((dt_norm, region_name))

    if not candidates:
        return "", ""

    candidates.sort(key=lambda x: (x[0] or "9999-99-99"))
    return candidates[0]


# ---------------------------------------------------------------------------
# Enrichment + logg för en rad
# ---------------------------------------------------------------------------

def enrich_row(
    edition_id: str,
    title: str,
    plat: str,
    aliases: Dict[str, List[str]],
    run_id: str,
    scoring_version: str,
) -> Tuple[dict, dict]:
    """
    Kör hela GiantBomb-enrichment för EN edition:
      - söker spel
      - väljer bästa träff
      - hämtar detaljer + releases
      - bygger enrichment-rad
      - bygger loggrad (för QA/debug)

    Returnerar (enrichment_dict, log_dict).
    """
    # 1) Sök på titel
    hits = search_games(title, limit=12)
    hits_count = len(hits)

    # 2) Välj bästa kandidat
    best, conf = pick_best_hit(title, plat, hits, aliases)
    platform_match_flag, title_score = conf  # t.ex. (1, 4) eller (0, 0)

    alias_used = "yes" if plat in aliases else "no"
    platform_matched = "yes" if platform_match_flag == 1 else "no"

    status = "picked"
    reason = "best_above_threshold"
    gb_id_for_log = ""
    gb_name_for_log = ""

    if not hits:
        status = "no_hits"
        reason = "search_returned_0"
    elif not best:
        status = "no_match"
        reason = "filtered_by_platform_or_score"

    extracted_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    def _empty_enrichment() -> dict:
        """Fallback: ingen träff eller fel → tom enrichment men med confidence-info."""
        return {
            "edition_id": edition_id,
            "title_primary": title,
            "platform": plat,
            "gb_game_id": "",
            "gb_name": "",
            "gb_genres": "",
            "gb_developers_for_platform": "",
            "gb_publishers_for_platform": "",
            "gb_release_date_for_platform": "",
            "gb_region_for_platform": "",
            "gb_platforms_all": "",
            "gb_release_dates_all": "",
            "gb_cover_url": "",
            "gb_confidence": f"{platform_match_flag}/{title_score}",
            "source": "giantbomb",
        }

    # Om vi inte hittade någon kandidat alls som passerar filtret
    if not best:
        log_row = {
            "run_id": run_id,
            "edition_id": edition_id,
            "title_primary": title,
            "platform": plat,
            "gb_game_id": "",
            "gb_name": "",
            "hits_count": hits_count,
            "status": status,
            "reason": reason,
            "query_used": title,
            "alias_used": alias_used,
            "platform_matched": platform_matched,
            "title_score": title_score,
            "extracted_at": extracted_at,
            "scoring_version": scoring_version,
        }
        return _empty_enrichment(), log_row

    # 3) Vi har en vald kandidat – hämta detaljer
    gid = best.get("id")
    details = game_detail(gid) or {}
    rels = game_releases(gid, limit=200) or []

    # Plattforms-specifik release
    date_for_plat, region_for_plat = first_platform_release(rels, plat, aliases)

    name = details.get("name", "") or ""
    genres = join_names(details.get("genres"))
    devs = join_names(details.get("developers"))
    pubs = join_names(details.get("publishers"))
    plats_all = join_names(details.get("platforms"))
    img = (details.get("image") or {}) or {}
    cover = img.get("super_url") or img.get("medium_url") or ""
    releases_all = format_release_dates_all(rels)

    gb_id_for_log = gid
    gb_name_for_log = name

    enr_row = {
        "edition_id": edition_id,
        "title_primary": title,
        "platform": plat,
        "gb_game_id": gid,
        "gb_name": name,
        "gb_genres": genres,
        "gb_developers_for_platform": devs,
        "gb_publishers_for_platform": pubs,
        "gb_release_date_for_platform": date_for_plat,
        "gb_region_for_platform": region_for_plat,
        "gb_platforms_all": plats_all,
        "gb_release_dates_all": releases_all,
        "gb_cover_url": cover,
        "gb_confidence": f"{platform_match_flag}/{title_score}",
        "source": "giantbomb",
    }

    log_row = {
        "run_id": run_id,
        "edition_id": edition_id,
        "title_primary": title,
        "platform": plat,
        "gb_game_id": gb_id_for_log,
        "gb_name": gb_name_for_log,
        "hits_count": hits_count,
        "status": status,
        "reason": reason,
        "query_used": title,
        "alias_used": alias_used,
        "platform_matched": platform_matched,
        "title_score": title_score,
        "extracted_at": extracted_at,
        "scoring_version": scoring_version,
    }

    return enr_row, log_row


# ---------------------------------------------------------------------------
# main()
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Enrich editions via GiantBomb (titel + plattform via YAML-alias)"
    )
    ap.add_argument(
        "--in",
        dest="in_csv",
        default=str(ED_PATH),
        help="Path till editions.csv",
    )
    ap.add_argument(
        "--out",
        dest="out_csv",
        default=str(OUT_FILE),
        help="Output CSV (GiantBomb-enrichment per edition)",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max antal editioner att köra (0 = alla)",
    )
    ap.add_argument(
        "--platform_whitelist",
        nargs="*",
        default=[],
        help="Filtrera på plattformskoder (t.ex. SFC SNES PS1)",
    )
    args = ap.parse_args()

    aliases = load_platform_aliases()

    # Läs editions.csv
    df = pd.read_csv(args.in_csv, dtype=str).fillna("")
    df = df.drop_duplicates(subset=["edition_id"]).reset_index(drop=True)

    # Filtrera på plattformar om önskat
    if args.platform_whitelist:
        wl = set(args.platform_whitelist)
        df = df[df["platform"].isin(wl)]

    # Limit för snabbtest
    if args.limit and args.limit > 0:
        df = df.head(args.limit)

    # Unik run_id per körning (t.ex. gb_20250108T213045Z)
    run_id = datetime.utcnow().strftime("gb_%Y%m%dT%H%M%SZ")

    rows: List[dict] = []
    log_rows: List[dict] = []

    total = len(df)
    for i, r in df.iterrows():
        eid = r.get("edition_id", "")
        title = r.get("title_primary", "")
        plat = r.get("platform", "")
        print(f"[{i+1}/{total}] {title} ({plat}) …")
        try:
            enr_row, log_row = enrich_row(
                eid, title, plat, aliases, run_id, SCORING_VERSION
            )
            rows.append(enr_row)
            log_rows.append(log_row)
        except Exception as e:
            # Hårdfel: logga som error och skriv tom enrichment
            print(f"   ! Fel: {e}")
            rows.append(
                {
                    "edition_id": eid,
                    "title_primary": title,
                    "platform": plat,
                    "gb_game_id": "",
                    "gb_name": title,
                    "gb_genres": "",
                    "gb_developers_for_platform": "",
                    "gb_publishers_for_platform": "",
                    "gb_release_date_for_platform": "",
                    "gb_region_for_platform": "",
                    "gb_platforms_all": "",
                    "gb_release_dates_all": "",
                    "gb_cover_url": "",
                    "gb_confidence": "0/0",
                    "source": "giantbomb",
                }
            )
            log_rows.append(
                {
                    "run_id": run_id,
                    "edition_id": eid,
                    "title_primary": title,
                    "platform": plat,
                    "gb_game_id": "",
                    "gb_name": "",
                    "hits_count": 0,
                    "status": "error",
                    "reason": str(e),
                    "query_used": title,
                    "alias_used": "unknown",
                    "platform_matched": "no",
                    "title_score": 0,
                    "extracted_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    "scoring_version": SCORING_VERSION,
                }
            )

    # --- Skriv enrichment-CSV (som innan) ------------------------------------
    out_cols = [
        "edition_id",
        "title_primary",
        "platform",
        "gb_game_id",
        "gb_name",
        "gb_genres",
        "gb_developers_for_platform",
        "gb_publishers_for_platform",
        "gb_release_date_for_platform",
        "gb_region_for_platform",
        "gb_platforms_all",
        "gb_release_dates_all",
        "gb_cover_url",
        "gb_confidence",
        "source",
    ]
    with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_cols)
        w.writeheader()
        for row in rows:
            w.writerow(row)

    print(f"✅ Skrev {len(rows)} rader → {args.out_csv}")

    # --- Skriv logg-CSV till data/outputs/qa --------------------------------
    if log_rows:
        log_file = QA_DIR / f"giantbomb_enrichment_log_{run_id}.csv"
        log_cols = list(log_rows[0].keys())
        with open(log_file, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=log_cols)
            w.writeheader()
            for row in log_rows:
                w.writerow(row)
        print(f"📝 Skrev logg med {len(log_rows)} rader → {log_file}")
    else:
        print("⚠️ Inga loggrader att skriva (log_rows tom).")


if __name__ == "__main__":
    main()
