#!/usr/bin/env python3
from __future__ import annotations

"""
gb_client.py
------------
Liten klient runt GiantBombs API som används av t.ex. gb_enrich_editions.py.

Ansvar:
- Bygga rätt URL: https://www.giantbomb.com/api/...
- Lägga på api_key & format=json
- Sätta User-Agent (via config.py)
- Returnera JSON som dict
"""

import time
from typing import Any, Dict, List
from urllib.parse import urlencode

import requests

from config import get_giantbomb_api_key, get_giantbomb_user_agent

# Bas-URL till GiantBomb API (VIKTIGT med www + /api)
BASE = "https://www.giantbomb.com/api"


# ---------------------------------------------------------------------------
# Lågnivå: grundanrop
# ---------------------------------------------------------------------------

def _build_url(path: str, params: Dict[str, Any]) -> str:
    """
    Bygger full URL genom att:
      - se till att path börjar med '/'
      - lägga ihop BASE + path + querystring (?key=...&format=json&...)
    """
    if not path.startswith("/"):
        path = "/" + path

    qs = urlencode(params)
    return f"{BASE}{path}?{qs}"


def _gb_get(path: str, params: Dict[str, Any], sleep: float = 1.0) -> Dict[str, Any]:
    """
    Grundanrop mot GiantBomb API.
    - Hämtar API-nyckel från config
    - Lägger på api_key och format=json
    - Sätter User-Agent
    - Gör GET med liten sleep för att vara snäll
    - raise_for_status() vid HTTP-fel (404, 500, ...)
    - Returnerar JSON som dict

    Används av:
      - game_detail()
      - game_releases()
      - search i gb_enrich_editions via _gb_get
    """
    key = get_giantbomb_api_key()
    if not key:
        raise RuntimeError("Saknar GIANTBOMB_API_KEY (eller motsv) i .env/config.")

    ua = (
        get_giantbomb_user_agent()
        or "Exjobb-Embracer-GB/0.1 (contact: you@example.com)"
    )

    # Lägg på GiantBomb-standardparametrar
    q: Dict[str, Any] = {
        "api_key": key,
        "format": "json",
        **params,
    }

    url = _build_url(path, q)

    # Artigt mot GiantBomb: liten paus mellan requests
    if sleep and sleep > 0:
        time.sleep(sleep)

    try:
        r = requests.get(
            url,
            headers={
                "User-Agent": ua,
                "Accept": "application/json",
            },
            timeout=30,
        )
        # Ger t.ex. "404 Client Error..." om sidan inte finns
        r.raise_for_status()
    except requests.HTTPError as e:
        # Gör felet lite lättare att förstå när det printas uppströms
        raise RuntimeError(f"GiantBomb HTTP error {r.status_code} for URL: {url}") from e
    except requests.RequestException as e:
        # Nätverksfel, timeout etc.
        raise RuntimeError(f"GiantBomb request failed for URL: {url}: {e}") from e

    try:
        data = r.json()
    except Exception as e:
        raise RuntimeError(f"Kunde inte parsa JSON från GiantBomb ({url}): {e}") from e

    # GiantBomb har även egen 'error'-sträng i JSON
    if data.get("error") and data.get("error") != "OK":
        raise RuntimeError(f"GiantBomb error: {data.get('error')} for URL: {url}")

    return data


# ---------------------------------------------------------------------------
# Hjälpare: namn-join
# ---------------------------------------------------------------------------

def join_names(items: List[Dict[str, Any]] | None, key: str = "name") -> str:
    """
    Tar en lista av dictar (t.ex. developers/publishers/personer från GiantBomb)
    och plockar ut unika namn, joinade med '; '.
    """
    if not items:
        return ""

    seen: List[str] = []
    for it in items:
        nm = (it or {}).get(key) or ""
        nm = str(nm).strip()
        if nm and nm not in seen:
            seen.append(nm)

    return "; ".join(seen)


# ---------------------------------------------------------------------------
# Högre nivå: game_detail + game_releases
# ---------------------------------------------------------------------------

def game_detail(game_id: int) -> Dict[str, Any]:
    """
    Hämtar detaljer för ett spel:
      - id, name, platforms, original_release_date
      - genres, developers, publishers
      - image, images, site_detail_url
      - people (lista med personer + roller)

    Returnerar själva 'results'-objektet (dict) eller {}.
    """
    fields = ",".join(
        [
            "id",
            "name",
            "platforms",
            "original_release_date",
            "genres",
            "developers",
            "publishers",
            "image",
            "images",
            "site_detail_url",
            # Nyckeln här: 'people' innehåller personobjekt + deras roller
            "people",
        ]
    )
    data = _gb_get(f"/game/{int(game_id)}/", {"field_list": fields})
    return data.get("results") or {}


def game_releases(game_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Hämtar releases för ett visst spel (olika plattform/regioner).
    Returnerar listan 'results' eller [].
    """
    data = _gb_get(
        "/releases/",
        {
            "filter": f"game:{int(game_id)}",
            "limit": int(limit),
            # field_list kan klippas/utökas vid behov
            "field_list": "id,game,platform,region,release_date,date_added",
        },
    )
    return data.get("results") or []
