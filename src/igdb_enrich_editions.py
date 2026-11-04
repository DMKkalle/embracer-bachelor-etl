# src/igdb_enrich_editions.py
# Enrich editions.csv med IGDB-data (per edition_id + platform), icke-destruktivt.
# Bygger både:
#   - data/outputs/enrichment/igdb_enrichment.csv  (till merge_enriched.py)
#   - data/outputs/qa/igdb_enrichment_log_*.csv   (QA + spårbarhet)

from __future__ import annotations

import re
import csv
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime, timezone, date

import pandas as pd
import yaml

from igdb_client import IGDBClient

# --- Paths --------------------------------------------------------------------

ED_PATH = Path("data/outputs/editions.csv")

OUT_DIR = Path("data/outputs/enrichment")
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV = OUT_DIR / "igdb_enrichment.csv"

QA_DIR = Path("data/outputs/qa")
QA_DIR.mkdir(parents=True, exist_ok=True)

PLATFORM_MAP_PATH = Path("configs/platform_map.yaml")

SCORING_VERSION = "igdb_v1"


# --- Plattformalias från platform_map.yaml ------------------------------------

def load_platform_aliases() -> Dict[str, List[str]]:
    """
    Läser platform_map.yaml och bygger:
      { "SNES": ["Super Nintendo Entertainment System", "Super NES", ...], ... }
    så att IGDB-plattformar matchas med samma logik som resten av pipelinen.
    """
    if not PLATFORM_MAP_PATH.exists():
        return {}

    with PLATFORM_MAP_PATH.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    alias_map = cfg.get("alias_map", {}) or {}
    exact_map = cfg.get("exact_map", {}) or {}

    out: Dict[str, List[str]] = {}

    # alias_map: kod -> lista med alias
    for code, aliases in alias_map.items():
        if isinstance(aliases, list):
            out.setdefault(code, [])
            out[code].extend(str(a) for a in aliases)
        elif isinstance(aliases, str):
            out.setdefault(code, [])
            out[code].append(aliases)

    # exact_map: "Super Nintendo Entertainment System" -> SNES
    for raw_name, code in exact_map.items():
        code = str(code)
        out.setdefault(code, [])
        out[code].append(str(raw_name))

    # städa + dedupe
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


PLATFORM_ALIASES: Dict[str, List[str]] = load_platform_aliases()


# --- små hjälpare -------------------------------------------------------------

def norm(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("×", "x").replace("✕", "x").replace("✖", "x")
    return s.lower()


def title_score(query: str, candidate_name: str) -> int:
    """2 = exakt (case-insensitive), 1 = substring, 0 = annan."""
    q = norm(query)
    c = norm(candidate_name)
    if q and c and q == c:
        return 2
    if q and (q in c or c in q):
        return 1
    return 0


def platform_match(platform_code: str, igdb_platforms: List[Dict[str, Any]]) -> bool:
    """
    Kollar om några av IGDB:s platform-namn matchar våra alias för editions.platform.
    Om vi saknar alias för en kod → returnera True (vi kan inte säga emot).
    """
    aliases = [a.lower() for a in PLATFORM_ALIASES.get(platform_code, [])]
    if not aliases:
        return True

    names = [norm(p.get("name", "")) for p in (igdb_platforms or [])]
    return any(any(a in n or n in a for n in names) for a in aliases)


def pick_best_hit(title: str, platform_code: str, hits: List[Dict[str, Any]]) -> Tuple[Dict[str, Any] | None, str]:
    """
    Välj bästa IGDB-träff: prioritera plattforms-match, sedan titelträff, sedan rating.
    Returnerar (hit, confidence_str) där confidence_str är t.ex. '1/2' (plat/titel).
    """
    scored: List[Tuple[int, int, float, int]] = []  # (plat_match, title_score, rating, index)
    for idx, h in enumerate(hits or []):
        ts = title_score(title, h.get("name", ""))
        pm = 1 if platform_match(platform_code, h.get("platforms", [])) else 0
        rating = float(h.get("aggregated_rating") or 0.0)
        scored.append((pm, ts, rating, idx))

    if not scored:
        return None, "0/0"

    pm, ts, rt, ix = max(scored)
    return hits[ix], f"{pm}/{ts}"


def join_names(items, key: str = "name") -> str:
    """Lista av dict → '; '-lista på valfri nyckel (default: 'name')."""
    return "; ".join(i.get(key) for i in (items or []) if i and i.get(key))


def dev_pub_for_platform(details: Dict[str, Any], platform_code: str) -> Tuple[str, str]:
    """
    IGDB har dev/pub via involved_companies, inte per plattform.
    Enkelt beslut:
      - Om spelet har vår plattform i 'platforms' → ta alla dev/pub.
      - Annars lämna tomt.
    """
    has_platform = platform_match(platform_code, details.get("platforms", []))
    devs: List[str] = []
    pubs: List[str] = []

    for ic in details.get("involved_companies", []) or []:
        name = (ic.get("company") or {}).get("name", "")
        if not name:
            continue
        if ic.get("developer"):
            devs.append(name)
        if ic.get("publisher"):
            pubs.append(name)

    devs_str = "; ".join(sorted(set(devs))) if has_platform else ""
    pubs_str = "; ".join(sorted(set(pubs))) if has_platform else ""
    return devs_str, pubs_str


def parse_human_date_key(human: str) -> tuple:
    """
    Gör IGDB:s 'human' till sorteringsnyckel (YYYY,MM,DD,is_tbd).
    Ger vettig sortering även för 'Aug 1993'.
    """
    if not human:
        return (9999, 12, 31, 1)

    m = re.search(r"\b(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?\b", human)
    if m:
        y = int(m.group(1))
        mm = int(m.group(2) or 1)
        dd = int(m.group(3) or 1)
        return (y, mm, dd, 0)

    m2 = re.search(r"\b([A-Za-z]{3,9})\s+(\d{4})\b", human)
    if m2:
        from calendar import month_abbr
        mon = m2.group(1)[:3].title()
        y = int(m2.group(2))
        try:
            mm = list(month_abbr).index(mon)
        except ValueError:
            mm = 1
        return (y, mm, 1, 0)

    return (9999, 12, 31, 1)


def cover_url_from_image_id(image_id: str | None) -> str:
    if not image_id:
        return ""
    return f"https://images.igdb.com/igdb/image/upload/t_cover_big/{image_id}.jpg"


# --- datum/region-hjälpare ---------------------------------------------------

def _ymd(s: str) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _ts_to_ymd_str(ts) -> str:
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _human_to_ymd_str(human: str) -> str:
    if not human:
        return ""
    m = re.search(r"\b(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?\b", human)
    if m:
        y = m.group(1)
        mo = m.group(2) or "01"
        d = m.group(3) or "01"
        return f"{y}-{mo}-{d}"

    m2 = re.search(r"\b([A-Za-z]{3,9})\s+(\d{4})\b", human)
    if m2:
        from calendar import month_abbr
        mon = m2.group(1)[:3].title()
        y = int(m2.group(2))
        try:
            mm = list(month_abbr).index(mon)
        except ValueError:
            mm = 1
        return f"{y}-{mm:02d}-01"
    return ""


def release_for_platform(details: Dict[str, Any], platform_code: str, regions_map: Dict[int, str]) -> Tuple[str, str]:
    """
    Välj bästa release-datum för vår plattform.
    - filtrerar på plattformsnamn som matchar våra alias
    - sorterar på datum
    - försöker fylla i region om den saknas
    """
    aliases = [a.lower() for a in PLATFORM_ALIASES.get(platform_code, [])]
    candidates = []

    for rd in details.get("release_dates", []) or []:
        plat = (rd.get("platform") or {}).get("name", "") or ""
        if not plat:
            continue
        if aliases and not any(a in plat.lower() or plat.lower() in a for a in aliases):
            continue

        date_ymd = _ts_to_ymd_str(rd.get("date")) or _human_to_ymd_str(rd.get("human") or "")
        region_name = regions_map.get(rd.get("region"), "") if rd.get("region") else ""
        candidates.append({"date_ymd": date_ymd, "region": region_name, "plat": plat})

    candidates.sort(key=lambda c: (c["date_ymd"] or "9999-12-31"))
    best = next((c for c in candidates if c["date_ymd"]), None)
    if not best:
        return "", ""

    if not best["region"]:
        target = _ymd(best["date_ymd"])
        if target:
            with_region = [c for c in candidates if c["region"] and c["date_ymd"]]
            if with_region:
                with_region.sort(key=lambda c: abs((_ymd(c["date_ymd"]) - target).days))
                best_region = with_region[0]["region"]
                return best["date_ymd"], best_region

    return best["date_ymd"], best["region"]


def flatten_all_release_rows(details: Dict[str, Any], regions_map: Dict[int, str], platform_code: str) -> str:
    """
    Bygger en deduplicerad, sorterad lista över alla releases:
      "1993-07-14 [Europe] <SNES> | 1994 [Japan] <SFC> | ..."
    Rader för aktuell plattform prioriteras först.
    """
    rows = []
    for rd in details.get("release_dates", []) or []:
        human = rd.get("human") or ""
        rid = rd.get("region")
        rname = regions_map.get(rid, "") if rid else ""
        plat = (rd.get("platform") or {}).get("name", "") or ""
        if not (human or rname or plat):
            continue

        parts = []
        if human:
            parts.append(human)
        if rname:
            parts.append(f"[{rname}]")
        if plat:
            parts.append(f"<{plat}>")

        item_str = " ".join(parts)
        rows.append((item_str, parse_human_date_key(human), norm(plat)))

    # dedupe
    seen = set()
    uniq = []
    for s, key, plat_lc in rows:
        if s not in seen:
            seen.add(s)
            uniq.append((s, key, plat_lc))

    uniq.sort(key=lambda x: (x[1], x[0]))

    aliases = [a.lower() for a in PLATFORM_ALIASES.get(platform_code, [])]

    def is_our_plat(plat_lc: str) -> bool:
        return any(a in plat_lc or plat_lc in a for a in aliases) if aliases else False

    ours = [u for u in uniq if is_our_plat(u[2])]
    others = [u for u in uniq if not is_our_plat(u[2])]
    ordered = ours + others

    return " | ".join(u[0] for u in ordered)


def generate_title_variants(title: str) -> List[str]:
    """
    Genererar några alternativa titlar att söka på om första sökningen ger svag träff.
    T.ex. utan skiljetecken, kortad före kolon, kompakt version.
    """
    if not title:
        return []
    base = title.strip()
    variants = set()
    variants.add(base)
    variants.add(base.replace("×", "x").replace("✕", "x").replace("✖", "x"))

    no_punct = re.sub(r"[(){}\[\]:;,.!?]", " ", base)
    variants.add(re.sub(r"\s+", " ", no_punct).strip())

    short1 = re.split(r"\s*[-–—:]\s*", base, maxsplit=1)[0]
    variants.add(short1.strip())

    compact = re.sub(r"[^0-9A-Za-z\u3040-\u30FF\u4E00-\u9FFF\s]", " ", base)
    variants.add(re.sub(r"\s+", " ", compact).strip())

    out = [v for v in variants if v and v != title]
    out.sort(key=len, reverse=True)
    return out[:8]


# --- CSV-utils ----------------------------------------------------------------

def write_rows(path: Path, header: List[str], rows: List[List[Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


# --- main ---------------------------------------------------------------------

def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="IGDB enrichment for editions.csv (non-invasive)")
    ap.add_argument("--input", default=str(ED_PATH), help="Path to editions.csv")
    ap.add_argument("--output", default=str(OUT_CSV), help="Output CSV path")
    ap.add_argument("--limit", type=int, default=50, help="Max antal editioner att köra (0 = alla)")
    ap.add_argument("--per_title_limit", type=int, default=5, help="Hur många IGDB-träffar att hämta per titel")
    ap.add_argument(
        "--platform_whitelist",
        nargs="*",
        default=[],
        help="Kör bara för dessa platform-koder (t.ex. SNES SFC)",
    )
    ap.add_argument(
        "--debug",
        action="store_true",
        help="Skriv extra debug-info från IGDBClient (queries, retries, etc.)",
    )
    args = ap.parse_args()

    df = pd.read_csv(args.input, dtype=str).fillna("")
    df = df.drop_duplicates(subset=["edition_id"]).reset_index(drop=True)

    if args.platform_whitelist:
        wl = set(args.platform_whitelist)
        df = df[df["platform"].isin(wl)]

    if args.limit > 0:
        df = df.head(args.limit)

    client = IGDBClient(debug=args.debug)
    regions_map = client.regions_map()

    # Enrichment-output (en rad per edition)
    header = [
        "edition_id",
        "title_primary",
        "platform",
        "igdb_id",
        "igdb_name",
        "genres",
        "developers_for_platform",
        "publishers_for_platform",
        "release_date_for_platform",
        "region_for_platform",
        "platforms_all",
        "release_dates_all",
        "cover_url",
        "confidence",
        "source",
    ]
    rows_out: List[List[Any]] = []

    # QA-logg (beslut per edition)
    run_ts = datetime.now(timezone.utc)
    run_id = f"igdb_{run_ts.strftime('%Y%m%dT%H%M%SZ')}"
    extracted_at = run_ts.isoformat()

    log_header = [
        "run_id",
        "edition_id",
        "title_primary",
        "platform",
        "igdb_id",
        "igdb_name",
        "status",           # picked | no_hits | error
        "reason",           # t.ex. picked_primary_search, no_hits_all_queries, exception_*
        "confidence",       # "plat/title" som 1/2
        "alias_used",       # yes/no (har vi alias för plattformen?)
        "platform_matched", # yes/no (enligt heuristiken)
        "region_present",   # yes/no (om vi fick region_for_platform)
        "query_used",       # söksträng som gav träffen
        "query_sequence",   # alla testade söksträngar
        "scoring_version",
        "extracted_at",
    ]
    log_rows: List[List[Any]] = []

    for i, r in df.iterrows():
        eid = r.get("edition_id", "")
        title = r.get("title_primary", "")
        plat = r.get("platform", "")

        print(f"[{i+1}/{len(df)}] {title} ({plat}) …")

        alias_used = "yes" if PLATFORM_ALIASES.get(plat) else "no"
        queries_tried: List[str] = []
        query_used = ""
        status = "no_hits"
        reason = "no_hits_all_queries"
        confidence = "0/0"
        igdb_id = ""
        igdb_name = ""
        platform_matched = "no"
        region_present = "no"

        try:
            # Sök med originaltitel
            queries_tried.append(title)
            hits = client.search_games_basic(title, limit=args.per_title_limit) or []
            pick = None
            if hits:
                pick, confidence = pick_best_hit(title, plat, hits)
                if pick:
                    query_used = title
                    reason = "picked_primary_search"

            # Om ingen eller väldigt låg confidence → testa varianter
            if (not pick) or confidence in {"0/0", "0/1"}:
                for v in generate_title_variants(title):
                    queries_tried.append(v)
                    hits2 = client.search_games_basic(v, limit=args.per_title_limit) or []
                    if not hits2:
                        continue
                    pick2, conf2 = pick_best_hit(title, plat, hits2)
                    if pick2 and conf2 != "0/0":
                        pick = pick2
                        confidence = conf2
                        query_used = v
                        reason = "picked_variant_search"
                        break

            # Inga träffar alls
            if not pick:
                rows_out.append([eid, title, plat, "", "", "", "", "", "", "", "", "", "", "0/0", "igdb"])
                log_rows.append(
                    [
                        run_id,
                        eid,
                        title,
                        plat,
                        "",
                        "",
                        "no_hits",
                        reason,
                        "0/0",
                        alias_used,
                        "no",
                        "no",
                        "",
                        "; ".join(queries_tried),
                        SCORING_VERSION,
                        extracted_at,
                    ]
                )
                continue

            # Hämta detaljer för vald IGDB-match
            details_list = client.game_details(pick["id"]) or []
            if not details_list:
                rows_out.append([eid, title, plat, "", "", "", "", "", "", "", "", "", "", confidence, "igdb"])
                log_rows.append(
                    [
                        run_id,
                        eid,
                        title,
                        plat,
                        "",
                        "",
                        "no_hits",
                        "details_empty_for_pick",
                        confidence,
                        alias_used,
                        "no",
                        "no",
                        query_used,
                        "; ".join(queries_tried),
                        SCORING_VERSION,
                        extracted_at,
                    ]
                )
                continue

            details = details_list[0]

            igdb_id = details.get("id", "")
            igdb_name = details.get("name", "")
            genres = join_names(details.get("genres", []))

            devs, pubs = dev_pub_for_platform(details, plat)

            plat_match_bool = platform_match(plat, details.get("platforms", []))
            date_ymd, region_name = ("", "")
            if plat_match_bool:
                date_ymd, region_name = release_for_platform(details, plat, regions_map)

            platforms_all = join_names(details.get("platforms", []))
            release_all = flatten_all_release_rows(details, regions_map, plat)

            image_id = (details.get("cover") or {}).get("image_id")
            cover_url = cover_url_from_image_id(image_id)

            rows_out.append(
                [
                    eid,
                    title,
                    plat,
                    igdb_id,
                    igdb_name,
                    genres,
                    devs,
                    pubs,
                    date_ymd,
                    region_name,
                    platforms_all,
                    release_all,
                    cover_url,
                    confidence,
                    "igdb",
                ]
            )

            status = "picked"
            platform_matched = "yes" if plat_match_bool else "no"
            region_present = "yes" if region_name else "no"

            log_rows.append(
                [
                    run_id,
                    eid,
                    title,
                    plat,
                    igdb_id,
                    igdb_name,
                    status,
                    reason,
                    confidence,
                    alias_used,
                    platform_matched,
                    region_present,
                    query_used,
                    "; ".join(queries_tried),
                    SCORING_VERSION,
                    extracted_at,
                ]
            )

        except Exception as e:
            err = str(e).replace("\n", " ")[:300]
            rows_out.append([eid, title, plat, "", "", "", "", "", "", "", "", "", "", "0/0", "igdb"])
            log_rows.append(
                [
                    run_id,
                    eid,
                    title,
                    plat,
                    "",
                    "",
                    "error",
                    f"exception_during_enrich: {err}",
                    "0/0",
                    alias_used,
                    "no",
                    "no",
                    "",
                    "; ".join(queries_tried),
                    SCORING_VERSION,
                    extracted_at,
                ]
            )
            print(f"   ! Fel under enrich för {title} ({plat}): {err}")

    # Skriv enrichment-fil (till merge_enriched)
    write_rows(Path(args.output), header, rows_out)
    print(f"✅ Skrev {len(rows_out)} rader → {args.output}")

    # Skriv QA-logg
    log_path = QA_DIR / f"igdb_enrichment_log_{run_id}.csv"
    write_rows(log_path, log_header, log_rows)
    print(f"📝 Skrev logg med {len(log_rows)} rader → {log_path}")


if __name__ == "__main__":
    main()
