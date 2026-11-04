from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import yaml

_NON_ASCII = re.compile(r"[^\x00-\x7F]")
_WHITESPACE = re.compile(r"\s+")

LANGUAGE_CODES = {
    "english": "en",
    "japanese": "ja",
    "french": "fr",
    "german": "de",
    "spanish": "es",
    "italian": "it",
    "dutch": "nl",
    "swedish": "sv",
    "norwegian": "no",
    "finnish": "fi",
    "danish": "da",
}

COUNTRY_TO_REGION = {
    "japan": "NTSC-J",
    "usa": "NTSC-U",
    "united states": "NTSC-U",
    "u.s.a.": "NTSC-U",
    "sweden": "PAL",
    "netherlands": "PAL",
    "france": "PAL",
    "germany": "PAL",
    "italy": "PAL",
    "spain": "PAL",
    "europe": "PAL",
    "united kingdom": "PAL",
    "uk": "PAL",
    "norway": "PAL",
    "finland": "PAL",
    "denmark": "PAL",
}


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def normalize_punctuation(value: Any) -> str:
    text = as_text(value)
    replacements = {
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "–": "-",
        "—": "-",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return _WHITESPACE.sub(" ", text).strip()


def is_ascii(value: Any) -> bool:
    text = as_text(value)
    return bool(text) and not _NON_ASCII.search(text)


def split_alternative_titles(value: Any) -> list[str]:
    text = as_text(value)
    if not text:
        return []

    parts = text.split("|")
    if len(parts) == 1:
        parts = re.split(r"[;,/]", text)

    return [normalized for part in parts if (normalized := normalize_punctuation(part))]


def choose_canonical_title(primary: Any, alternatives: list[str]) -> tuple[str, str]:
    primary_text = normalize_punctuation(primary)

    if is_ascii(primary_text):
        return primary_text, "primary_ascii"

    for alternative in alternatives:
        if is_ascii(alternative):
            return alternative, "alternative_ascii"

    fallback = primary_text or (alternatives[0] if alternatives else "")
    return fallback, "primary_fallback"


def normalize_language(value: Any) -> str:
    text = as_text(value)
    if not text:
        return "unknown"

    tokens = [token.strip() for token in text.split(";") if token.strip()]
    if not tokens:
        return "unknown"

    key = re.sub(r"[^a-z]", "", tokens[0].lower())
    return LANGUAGE_CODES.get(key, key or "unknown")


def infer_region(
    broadcast_standard: Any,
    place_of_publication: Any,
    title: Any = None,
) -> str:
    broadcast = as_text(broadcast_standard).upper()
    place = as_text(place_of_publication).lower()

    if broadcast in {"PAL", "NTSC-J", "NTSC-U"}:
        return broadcast

    if place in COUNTRY_TO_REGION:
        return COUNTRY_TO_REGION[place]

    for country, region in COUNTRY_TO_REGION.items():
        if country in place:
            return region

    title_text = as_text(title).lower()
    if any(
        term in title_text
        for term in ("controller", "mouse", "stick", "adapter", "multitap")
    ):
        return "ACCESSORY"

    return "UNKNOWN"


def load_platform_rules(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def normalize_platform(value: Any, rules: dict[str, Any]) -> str:
    raw = as_text(value)
    if not raw:
        return "UNKNOWN"

    exact_map = rules.get("exact_map", {})
    if raw in exact_map:
        return str(exact_map[raw])

    raw_lower = raw.lower()
    for canonical, aliases in rules.get("alias_map", {}).items():
        if raw_lower == str(canonical).lower():
            return str(canonical)
        if any(raw_lower == str(alias).lower() for alias in aliases or []):
            return str(canonical)

    for entry in rules.get("regex_map", []):
        pattern = entry.get("pattern")
        code = entry.get("code")
        if pattern and code and re.search(pattern, raw):
            return str(code)

    return "UNKNOWN"
