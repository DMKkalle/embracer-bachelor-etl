# src/gb_credits.py
# Hämta GiantBomb-credits för alla editioner som har gb_game_id (inte låst till CAT- längre).
# - Läser länktabell (default: data/outputs/edition_links.csv)
# - Hämtar /game/{id}?field_list=name,deck,developers,publishers,people,site_detail_url,image
# - CACHAR varje svar på disk så vi inte slår i limit i onödan
# - Respekterar rate limit med bas-sleep + backoff på HTTP 420
#
# Env (via config.py eller direkt environment):
#   GIANTBOMB_API_KEY (krav)
#   GB_USER_AGENT     (valfritt, fallback: Exjobb-Embracer-GB/0.1)
#
# Output:
#   data/external/giantbomb/gb_credits_games.csv   (spelrad per edition)
#   data/external/giantbomb/gb_people.csv          (personrad per person)

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from pathlib import Path
from typing import Dict, Any, List
from urllib.error import HTTPError, URLError
import urllib.parse
import urllib.request

from config import get_giantbomb_api_key, get_giantbomb_user_agent

# ---------------------------------------------------------------------------
# Paths & konstanta
# ---------------------------------------------------------------------------

CACHE_DIR = Path("data/external/giantbomb/cache")
OUT_GAMES = Path("data/external/giantbomb/gb_credits_games.csv")
OUT_PEOPLE = Path("data/external/giantbomb/gb_people.csv")

FIELDS_GAME = "name,deck,developers,publishers,people,site_detail_url,image"


# ---------------------------------------------------------------------------
# Hjälpare för CSV
# ---------------------------------------------------------------------------

def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def ensure_parent(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    if not rows:
        return
    ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------------------
# Hjälpare för roller/personer
# ---------------------------------------------------------------------------

def roles_to_list(roles_field: Any) -> List[str]:
    """
    Normaliserar GiantBombs 'roles'-fält till en enkel lista av strängar.
    """
    out: List[str] = []
    if isinstance(roles_field, list):
        for r in roles_field:
            if isinstance(r, dict):
                nm = (r.get("name") or "").strip()
                if nm:
                    out.append(nm)
            elif isinstance(r, str):
                nm = r.strip()
                if nm:
                    out.append(nm)
    elif isinstance(roles_field, dict):
        nm = (roles_field.get("name") or "").strip()
        if nm:
            out.append(nm)
    elif isinstance(roles_field, str):
        nm = roles_field.strip()
        if nm:
            out.append(nm)
    return [r for r in out if r]


# ---------------------------------------------------------------------------
# Cache-hantering
# ---------------------------------------------------------------------------

def cached_path(gb_id: str) -> Path:
    return CACHE_DIR / f"game_{gb_id}.json"


def load_cache(gb_id: str) -> Dict[str, Any] | None:
    p = cached_path(gb_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def save_cache(gb_id: str, data: Dict[str, Any]) -> None:
    ensure_parent(cached_path(gb_id))
    cached_path(gb_id).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# HTTP-hjälpare (med backoff)
# ---------------------------------------------------------------------------

def http_get_json(url: str, user_agent: str, timeout: int = 30) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_get_json_retry(
    url: str,
    user_agent: str,
    base_sleep_s: float,
    max_retries: int = 5,
) -> Dict[str, Any]:
    """
    På 420 (rate limit): exponentiell backoff.
    På andra fel: försök om ett par gånger ändå.
    """
    attempt = 0
    while True:
        try:
            return http_get_json(url, user_agent)
        except HTTPError as e:
            code = getattr(e, "code", None)
            attempt += 1
            if code == 420:
                if attempt > max_retries:
                    raise RuntimeError("för många försök (420)") from e
                wait = max(30.0, base_sleep_s) * attempt  # 30s, 60s, 90s, ...
                print(f"  [RATE/LIMIT] 420, väntar {int(wait)}s (försök {attempt}/{max_retries}) …")
                time.sleep(wait)
                continue
            else:
                if attempt > max_retries:
                    raise
                wait = max(5.0, base_sleep_s / 2.0) * attempt
                print(f"  [WARN] HTTP {code}, väntar {int(wait)}s (försök {attempt}/{max_retries}) …")
                time.sleep(wait)
                continue
        except URLError as e:
            attempt += 1
            if attempt > max_retries:
                raise
            wait = max(5.0, base_sleep_s / 2.0) * attempt
            print(f"  [WARN] Nätverksfel: {e}, väntar {int(wait)}s (försök {attempt}/{max_retries}) …")
            time.sleep(wait)
            continue


def gb_game_with_people(api_key: str, user_agent: str, gb_id: str) -> Dict[str, Any]:
    """
    Hämtar ett game-objekt från GiantBomb inkl. people/roles.
    """
    params = {
        "api_key": api_key,
        "format": "json",
        "field_list": FIELDS_GAME,
    }
    url = f"https://www.giantbomb.com/api/game/{gb_id}/?{urllib.parse.urlencode(params)}"
    return http_get_json_retry(url, user_agent, base_sleep_s=1.0)


# ---------------------------------------------------------------------------
# Huvudprogram
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Hämta GiantBomb-credits (spel + personer) för länkade editioner."
    )
    ap.add_argument(
        "--links",
        type=Path,
        default=Path("data/outputs/edition_links.csv"),
        help="CSV med edition_id, gb_game_id …",
    )
    ap.add_argument(
        "--max",
        type=int,
        default=0,
        help="max antal att köra (0 = alla)",
    )
    ap.add_argument(
        "--offset",
        type=int,
        default=0,
        help="hoppa över N första",
    )
    # Viktigt: default 20 sekunder → ≈180 req/h (under 200/h) + headroom
    ap.add_argument(
        "--sleep-ms",
        type=int,
        default=20000,
        help="minst så här lång paus mellan requests (per game) – default 20000ms (~20s)",
    )
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="(Legacy-flag; output skrivs alltid om i denna version.)",
    )
    ap.add_argument(
        "--no-cache",
        action="store_true",
        help="ignorera cache och tvinga hämtning",
    )
    args = ap.parse_args()

    # Hämta API-nyckel och User-Agent via config/env
    api_key = (get_giantbomb_api_key() or os.environ.get("GIANTBOMB_API_KEY") or "").strip()
    if not api_key:
        raise SystemExit("Saknar GIANTBOMB_API_KEY i environment/.env.")

    user_agent = (
        get_giantbomb_user_agent()
        or os.environ.get("GB_USER_AGENT")
        or "Exjobb-Embracer-GB/0.1"
    ).strip()

    if not args.links.exists():
        raise SystemExit(f"Hittar inte länktabellen: {args.links}")

    links = read_csv(args.links)

    # NYTT: ta med ALLA editioner som har både edition_id och gb_game_id (inte låst till CAT-)
    todo_all = [
        r
        for r in links
        if (r.get("edition_id") or "").strip()
        and (r.get("gb_game_id") or "").strip()
    ]

    if args.offset > 0:
        todo_all = todo_all[args.offset:]
    if args.max > 0:
        todo_all = todo_all[: args.max]

    print(f"[INFO] Totalt att köra: {len(todo_all)} (sleep={args.sleep_ms}ms)")

    games_rows: List[Dict[str, str]] = []
    people_rows: List[Dict[str, str]] = []

    last_call = 0.0
    min_interval = max(0.0, args.sleep_ms / 1000.0)

    for i, row in enumerate(todo_all, 1):
        eid = (row.get("edition_id") or "").strip()
        gbid = (row.get("gb_game_id") or "").strip()

        print(f"[{i}/{len(todo_all)}] edition_id={eid} GB:{gbid} – hämtar game+people …")

        # Rate: håll minst min_interval mellan anrop
        now = time.time()
        delta = now - last_call
        if delta < min_interval:
            time.sleep(min_interval - delta)

        data: Dict[str, Any] | None = None
        if not args.no_cache:
            data = load_cache(gbid)

        if data is None:
            # hämta live
            try:
                data = gb_game_with_people(api_key, user_agent, gbid)
                save_cache(gbid, data)
            except Exception as e:
                print(f"  [WARN] misslyckades för GB:{gbid}: {e}")
                last_call = time.time()
                continue
            last_call = time.time()
        else:
            # “virtually” uppdatera last_call så vi inte spammar när vi går vidare
            last_call = time.time()

        res = data.get("results") or {}

        # Spelrad
        devs = sorted(
            {
                (d or {}).get("name", "").strip()
                for d in (res.get("developers") or [])
                if (d or {}).get("name")
            }
        )
        pubs = sorted(
            {
                (p or {}).get("name", "").strip()
                for p in (res.get("publishers") or [])
                if (p or {}).get("name")
            }
        )

        games_rows.append(
            {
                "edition_id": eid,
                "gb_game_id": gbid,
                "name": res.get("name", ""),
                "deck": (res.get("deck") or "")[:500],
                "developers": "; ".join([d for d in devs if d]),
                "publishers": "; ".join([p for p in pubs if p]),
                "site_detail_url": res.get("site_detail_url", ""),
                "image_super_url": ((res.get("image") or {}) or {}).get("super_url", ""),
                "source": "giantbomb",
            }
        )

        # Personrader (om finns)
        ppl = res.get("people") or []
        for p in ppl:
            pname = (p or {}).get("name", "").strip()
            roles = roles_to_list((p or {}).get("roles"))
            people_rows.append(
                {
                    "edition_id": eid,
                    "gb_game_id": gbid,
                    "person_name": pname,
                    "roles": "; ".join(sorted(set(roles))),
                    "source": "giantbomb",
                }
            )

    # Skriv ut
    if games_rows:
        write_csv(OUT_GAMES, games_rows)
        print(f"Klart. Skrev {len(games_rows)} spelrader → {OUT_GAMES}")
    else:
        print(f"Klart. Skrev 0 spelrader → {OUT_GAMES}")

    if people_rows:
        write_csv(OUT_PEOPLE, people_rows)
        print(f"Klart. Skrev {len(people_rows)} personrader → {OUT_PEOPLE}")
    else:
        print(f"Klart. Skrev 0 personrader → {OUT_PEOPLE}")


if __name__ == "__main__":
    main()
