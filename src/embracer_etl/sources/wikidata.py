from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests

SEARCH_URL = "https://www.wikidata.org/w/api.php"
ENTITY_URL = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"

ALLOWED_INSTANCE_OF = {
    "Q7889",  # video game
    "Q153813",  # video game expansion
    "Q705716",  # video game remake
}

DENIED_INSTANCE_OF = {
    "Q11424",  # film
    "Q5398426",  # television series
    "Q482994",  # album
    "Q134556",  # novel
    "Q21191270",  # soundtrack album
    "Q15265344",  # video game series
    "Q17379835",  # media franchise
}


@dataclass(frozen=True)
class WikidataCandidate:
    qid: str
    label: str
    description: str


class WikidataClient:
    def __init__(
        self,
        *,
        user_agent: str | None = None,
        timeout: float = 15.0,
        session: requests.Session | None = None,
    ):
        self.user_agent = user_agent or os.getenv(
            "WIKIDATA_USER_AGENT",
            "embracer-bachelor-etl/0.1 (portfolio demo)",
        )
        self.timeout = timeout
        self.session = session or requests.Session()

    @property
    def headers(self) -> dict[str, str]:
        return {"User-Agent": self.user_agent}

    def search(
        self,
        title: str,
        *,
        language: str = "en",
        limit: int = 10,
    ) -> list[WikidataCandidate]:
        if not title.strip():
            return []

        response = self.session.get(
            SEARCH_URL,
            params={
                "action": "wbsearchentities",
                "search": title,
                "language": language,
                "format": "json",
                "type": "item",
                "limit": str(limit),
            },
            headers=self.headers,
            timeout=self.timeout,
        )
        response.raise_for_status()

        return [
            WikidataCandidate(
                qid=item["id"],
                label=item.get("label", ""),
                description=item.get("description", ""),
            )
            for item in response.json().get("search", [])
            if item.get("id")
        ]

    def entity(self, qid: str) -> dict[str, Any]:
        response = self.session.get(
            ENTITY_URL.format(qid=qid),
            headers=self.headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json().get("entities", {}).get(qid, {})


def claim_entity_ids(entity: dict[str, Any], property_id: str) -> list[str]:
    values: list[str] = []
    for statement in entity.get("claims", {}).get(property_id, []):
        data = statement.get("mainsnak", {}).get("datavalue")
        if not data or data.get("type") != "wikibase-entityid":
            continue
        qid = data.get("value", {}).get("id")
        if qid:
            values.append(qid)
    return values


def is_video_game_entity(entity: dict[str, Any]) -> bool:
    instance_ids = set(claim_entity_ids(entity, "P31"))
    if not instance_ids:
        return False
    if instance_ids & DENIED_INSTANCE_OF:
        return False
    return bool(instance_ids & ALLOWED_INSTANCE_OF)
