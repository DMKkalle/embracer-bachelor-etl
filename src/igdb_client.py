# src/igdb_client.py
# Klient mot IGDB API med enkel rate-limit-hantering, retries och debugläge.

from __future__ import annotations

import time
from typing import Any, Dict, List

import requests

from igdb_auth import get_access_token
from config import get_twitch_client_id

IGDB_BASE = "https://api.igdb.com/v4"


class IGDBClient:
    def __init__(
        self,
        sleep_between: float = 0.30,
        max_retries: int = 3,
        debug: bool = False,
        max_offset: int = 5000,
    ) -> None:
        """
        :param sleep_between: minsta paus mellan requests (sekunder)
        :param max_retries: max antal försök per request (vid 429/5xx)
        :param debug: om True -> skriv ut enkla debug-meddelanden
        :param max_offset: max tillåten offset i search-queries (skydd mot galna loopar)
        """
        self.client_id = get_twitch_client_id()
        self.sleep_between = sleep_between
        self.max_retries = max_retries
        self.debug = debug
        self.max_offset = max_offset

        self._token: str | None = None
        self._last_call_ts: float = 0.0

    # ------------------------------------------------------------------ #
    #  Token & headers
    # ------------------------------------------------------------------ #

    @property
    def token(self) -> str:
        if not self._token:
            self._token = get_access_token()
        return self._token

    def _headers(self) -> Dict[str, str]:
        return {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.token}",
        }

    # ------------------------------------------------------------------ #
    #  Central request-hantering
    # ------------------------------------------------------------------ #

    def _request_with_retry(self, endpoint: str, query: str) -> List[Dict[str, Any]]:
        """
        En enda central plats där vi:
          - respekterar sleep_between mellan anrop
          - hanterar 401 (token ogiltigt → hämta nytt)
          - hanterar 429 (rate limit → backoff + retry)
          - försöker om vid 5xx / nätverksfel upp till max_retries
        Returnerar JSON-listan från IGDB (eller tom lista).
        """
        url = f"{IGDB_BASE}/{endpoint}"

        # enkel debug-logg
        if self.debug:
            q_preview = " ".join(line.strip() for line in query.splitlines())
            if len(q_preview) > 120:
                q_preview = q_preview[:117] + "..."
            print(f"[IGDB] POST {endpoint} q={q_preview!r}")

        attempt = 0
        backoff = 1.0

        while True:
            attempt += 1

            # se till att vi inte gör anrop tätare än sleep_between
            now = time.time()
            delta = now - self._last_call_ts
            if delta < self.sleep_between:
                time.sleep(self.sleep_between - delta)

            try:
                resp = requests.post(
                    url,
                    data=query.encode("utf-8"),
                    headers=self._headers(),
                    timeout=30,
                )
                self._last_call_ts = time.time()

                # 401 → token ogiltigt, hämta nytt en gång
                if resp.status_code == 401 and attempt <= self.max_retries:
                    if self.debug:
                        print("[IGDB] 401 Unauthorized – refreschar token och försöker igen…")
                    self._token = None  # tvinga nytt token
                    continue

                # 429 → rate limit, backoff och försök igen
                if resp.status_code == 429 and attempt <= self.max_retries:
                    wait = max(1.0, backoff)
                    if self.debug:
                        print(f"[IGDB] 429 Too Many Requests – väntar {wait:.1f}s (försök {attempt})…")
                    time.sleep(wait)
                    backoff *= 2.0
                    continue

                # andra felkoder → försök om vid 5xx, annars ge upp
                if 500 <= resp.status_code < 600 and attempt <= self.max_retries:
                    wait = max(1.0, backoff)
                    if self.debug:
                        print(f"[IGDB] {resp.status_code} serverfel – väntar {wait:.1f}s (försök {attempt})…")
                    time.sleep(wait)
                    backoff *= 2.0
                    continue

                # kasta om fel kvarstår
                resp.raise_for_status()

                data = resp.json()
                if isinstance(data, list):
                    return data
                # många IGDB-endpoints returnerar listor; fallback till tom lista annars
                return data if isinstance(data, list) else data.get("results", [])

            except requests.RequestException as e:
                if attempt > self.max_retries:
                    raise RuntimeError(f"[IGDB] Misslyckades efter {self.max_retries} försök: {e}") from e
                wait = max(1.0, backoff)
                if self.debug:
                    print(f"[IGDB] Nätverksfel {e!r} – väntar {wait:.1f}s (försök {attempt})…")
                time.sleep(wait)
                backoff *= 2.0

    def post(self, endpoint: str, query: str) -> List[Dict[str, Any]]:
        return self._request_with_retry(endpoint, query)

    # ------------------------------------------------------------------ #
    #  Publika API-metoder
    # ------------------------------------------------------------------ #

    def search_games_basic(self, title: str, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Enkel sökning i games.
        - limit clampas till [1, 50] (IGDB-rekommendation)
        - offset får inte vara negativ och inte > max_offset
        """
        if not title or not title.strip():
            return []

        # skydda oss mot konstiga parametrar
        limit = max(1, min(int(limit), 50))
        if offset < 0:
            offset = 0
        if offset > self.max_offset:
            raise ValueError(f"offset {offset} > max_offset ({self.max_offset}) i IGDBClient.search_games_basic")

        safe_title = title.replace('"', r"\"")

        q = f"""
        fields
            id,
            name,
            first_release_date,
            platforms.name,
            genres.name,
            aggregated_rating,
            summary;
        search "{safe_title}";
        where version_parent = null;
        limit {limit};
        offset {offset};
        """
        return self.post("games", q)

    def game_companies(self, game_id: int) -> List[Dict[str, Any]]:
        q = f"""
        fields
            id,
            company.name,
            developer,
            publisher,
            porting,
            supporting;
        where game = {int(game_id)};
        """
        return self.post("involved_companies", q)

    def game_release_dates(self, game_id: int) -> List[Dict[str, Any]]:
        q = f"""
        fields
            id,
            date,
            human,
            region,
            platform,
            name,
            category,
            updated_at;
        where game = {int(game_id)};
        """
        return self.post("release_dates", q)

    def game_details(self, game_id: int) -> List[Dict[str, Any]]:
        q = f"""
        fields
            id,
            name,
            first_release_date,
            genres.name,
            themes.name,
            game_modes.name,
            player_perspectives.name,
            franchises.name,
            collection.name,
            alternative_names.name,
            websites.url,
            involved_companies.company.name,
            involved_companies.developer,
            involved_companies.publisher,
            involved_companies.porting,
            involved_companies.supporting,
            release_dates.date,
            release_dates.human,
            release_dates.region,
            release_dates.platform.name,
            platforms.name,
            aggregated_rating,
            cover.image_id;
        where id = {int(game_id)};
        """
        return self.post("games", q)

    def regions_map(self) -> Dict[int, str]:
        """Hämta en {region_id: region_name}-mappning från IGDB."""
        q = "fields id,name; limit 50;"
        rows = self.post("regions", q)
        return {row["id"]: row["name"] for row in rows if "id" in row and "name" in row}
