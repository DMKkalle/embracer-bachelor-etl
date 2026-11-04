# src/config.py
# Central hantering av API-nycklar och miljövariabler för projektet.

import os
from dotenv import load_dotenv

# Laddas en gång vid import
load_dotenv()

def _get_env(key: str, required: bool = True) -> str:
    """
    Hämtar en miljövariabel från .env-filen.
    Om den saknas och required=True -> kastar RuntimeError med tydligt fel.
    """
    value = os.getenv(key)
    if not value and required:
        raise RuntimeError(f"Saknar {key} i .env")
    return value or ""


# --- IGDB / Twitch -----------------------------------------------------------

def get_twitch_client_id() -> str:
    """Returnerar Twitch Client ID (krävs för IGDB API)."""
    return _get_env("TWITCH_CLIENT_ID")


def get_twitch_client_secret() -> str:
    """Returnerar Twitch Client Secret (krävs för IGDB API)."""
    return _get_env("TWITCH_CLIENT_SECRET")


# --- GiantBomb ---------------------------------------------------------------

def get_giantbomb_api_key() -> str:
    """Returnerar GiantBomb API-nyckel."""
    return _get_env("GIANTBOMB_API_KEY", required=True)


def get_giantbomb_user_agent() -> str:
    """Returnerar User-Agent som används vid GiantBomb API-anrop."""
    return _get_env("GB_USER_AGENT", required=True)


# --- Wikidata ------------------------------------------------------------------

def get_wikidata_user_agent() -> str:
    """Returnerar User-Agent för Wikidata/Wikipedia-förfrågningar."""
    return _get_env("WIKIDATA_USER_AGENT", required=True)
