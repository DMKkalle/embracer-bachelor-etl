from __future__ import annotations

import os

import requests

SEARCH_URL = "https://www.giantbomb.com/api/search/"


class GiantBombClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        user_agent: str = "embracer-bachelor-etl/0.1",
        session: requests.Session | None = None,
        timeout: float = 20.0,
    ):
        self.api_key = api_key or os.getenv("GIANTBOMB_API_KEY")
        if not self.api_key:
            raise RuntimeError("Set GIANTBOMB_API_KEY to use GiantBomb.")

        self.user_agent = user_agent
        self.session = session or requests.Session()
        self.timeout = timeout

    def search_games(self, title: str, *, limit: int = 10) -> list[dict]:
        response = self.session.get(
            SEARCH_URL,
            params={
                "api_key": self.api_key,
                "format": "json",
                "query": title,
                "resources": "game",
                "limit": limit,
                "field_list": "id,name,deck,developers,publishers",
            },
            headers={"User-Agent": self.user_agent},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json().get("results", [])
