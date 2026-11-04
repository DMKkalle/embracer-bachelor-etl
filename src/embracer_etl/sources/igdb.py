from __future__ import annotations

import os
import time
from dataclasses import dataclass

import requests

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
IGDB_GAMES_URL = "https://api.igdb.com/v4/games"


@dataclass(frozen=True)
class IGDBCredentials:
    client_id: str
    client_secret: str

    @classmethod
    def from_environment(cls) -> "IGDBCredentials":
        client_id = os.getenv("TWITCH_CLIENT_ID")
        client_secret = os.getenv("TWITCH_CLIENT_SECRET")
        if not client_id or not client_secret:
            raise RuntimeError(
                "Set TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET to use IGDB."
            )
        return cls(client_id=client_id, client_secret=client_secret)


class IGDBClient:
    def __init__(
        self,
        credentials: IGDBCredentials | None = None,
        *,
        session: requests.Session | None = None,
        timeout: float = 20.0,
    ):
        self.credentials = credentials or IGDBCredentials.from_environment()
        self.session = session or requests.Session()
        self.timeout = timeout
        self._access_token: str | None = None
        self._expires_at = 0.0

    def _token(self) -> str:
        if self._access_token and self._expires_at > time.time() + 60:
            return self._access_token

        response = self.session.post(
            TOKEN_URL,
            params={
                "client_id": self.credentials.client_id,
                "client_secret": self.credentials.client_secret,
                "grant_type": "client_credentials",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()

        self._access_token = payload["access_token"]
        self._expires_at = time.time() + int(payload.get("expires_in", 3600))
        return self._access_token

    def search_games(self, title: str, *, limit: int = 10) -> list[dict]:
        query = (
            f'search "{title.replace(chr(34), "")}"; '
            "fields id,name,first_release_date,platforms.name,alternative_names.name;"
            f" limit {limit};"
        )
        response = self.session.post(
            IGDB_GAMES_URL,
            headers={
                "Client-ID": self.credentials.client_id,
                "Authorization": f"Bearer {self._token()}",
            },
            data=query,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()
