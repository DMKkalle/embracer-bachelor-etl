from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_EDITION_NOISE = (
    "players choice",
    "greatest hits",
    "platinum",
    "selects",
    "limited edition",
    "collector",
    "complete in box",
    "cib",
    "boxed",
    "not for resale",
    "demo",
    "sample",
    "promo",
    "bundle",
    "pack",
    "cart only",
    "loose",
    "jpn",
    "usa",
    "eur",
    "pal",
    "ntsc",
    "ntsc-j",
    "ntsc-u",
)

_ROMAN_VALUES = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}

PLATFORM_ALIASES = {
    "snes": "super nintendo entertainment system",
    "super nintendo": "super nintendo entertainment system",
    "super nintendo entertainment system": "super nintendo entertainment system",
    "super famicom": "super nintendo entertainment system",
    "sfc": "super nintendo entertainment system",
}


@dataclass(frozen=True)
class MatchSignals:
    title: float
    platform: float
    year: float

    @property
    def weighted_score(self) -> float:
        return round(
            (self.title * 0.50) + (self.platform * 0.30) + (self.year * 0.20),
            4,
        )


def ascii_normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[\W_]+", " ", text).strip().lower()
    return re.sub(r"\s+", " ", text)


def roman_to_int(token: str) -> int | None:
    text = (token or "").lower()
    if not text or any(char not in _ROMAN_VALUES for char in text):
        return None

    total = 0
    previous = 0
    for char in reversed(text):
        value = _ROMAN_VALUES[char]
        if value < previous:
            total -= value
        else:
            total += value
            previous = value
    return total


def int_to_roman(number: int) -> str:
    if number <= 0:
        return ""

    values = (
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    )

    result = []
    remaining = number
    for value, symbol in values:
        while remaining >= value:
            result.append(symbol)
            remaining -= value
    return "".join(result)


def name_variants(title: str) -> set[str]:
    base = ascii_normalize(title)
    if not base:
        return set()

    tokens = base.split()
    variants = {base}

    roman_to_arabic = []
    for token in tokens:
        converted = roman_to_int(token)
        roman_to_arabic.append(str(converted) if converted is not None else token)
    variants.add(" ".join(roman_to_arabic))

    arabic_to_roman = []
    for token in tokens:
        if token.isdigit():
            arabic_to_roman.append(ascii_normalize(int_to_roman(int(token))))
        else:
            arabic_to_roman.append(token)
    variants.add(" ".join(arabic_to_roman))

    return {variant for variant in variants if variant}


def jaccard_similarity(left: str, right: str) -> float:
    left_tokens = set(ascii_normalize(left).split())
    right_tokens = set(ascii_normalize(right).split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def clean_title_for_match(title: str) -> str:
    text = str(title or "")
    text = re.sub(r"[\(\[\{].+?[\)\]\}]", " ", text)
    text = re.split(r"\s[-–—]\s", text, maxsplit=1)[0]
    text = text.replace("™", "").replace("®", "").replace("©", "").lower()

    for noise in _EDITION_NOISE:
        text = text.replace(noise, " ")

    return re.sub(r"\s+", " ", text).strip()


def normalize_platform_name(platform: str) -> str:
    normalized = ascii_normalize(platform)
    return PLATFORM_ALIASES.get(normalized, normalized)


def year_proximity_score(left: int | None, right: int | None) -> float:
    if left is None or right is None:
        return 0.0

    difference = abs(left - right)
    if difference == 0:
        return 1.0
    if difference >= 5:
        return 0.0
    return 1.0 - (difference / 5)


def score_candidate(
    edition_title: str,
    edition_platform: str,
    edition_year: int | None,
    candidate_title: str,
    candidate_platform: str,
    candidate_year: int | None,
) -> MatchSignals:
    edition_variants = name_variants(clean_title_for_match(edition_title))
    candidate_variants = name_variants(clean_title_for_match(candidate_title))

    title_score = max(
        (
            jaccard_similarity(left, right)
            for left in edition_variants
            for right in candidate_variants
        ),
        default=0.0,
    )

    platform_score = jaccard_similarity(
        normalize_platform_name(edition_platform),
        normalize_platform_name(candidate_platform),
    )

    return MatchSignals(
        title=round(title_score, 4),
        platform=round(platform_score, 4),
        year=round(year_proximity_score(edition_year, candidate_year), 4),
    )
