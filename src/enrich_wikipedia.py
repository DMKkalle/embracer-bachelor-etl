# src/enrich_wikipedia.py
# - Fixa default input-filnamn (editions.csv)
# - Ta bort hårdkodad User-Agent och använd config.get_wikidata_user_agent()

from __future__ import annotations
import argparse
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import pandas as pd
import requests
import re
import sys

from config import get_wikidata_user_agent  # NYTT

WIKI_API = "https://en.wikipedia.org/w/api.php"
ED_PATH = Path("data/outputs/editions.csv")  # NYTT: samma källa som annan enrichment

ROLE_FIELDS = {
    "developer": "Developer(s)",
    "publisher": "Publisher(s)",
    "designer": "Designer(s)",
    "programmer": "Programmer(s)",
    "artist": "Artist(s)",
    "composer": "Composer(s)",
    "producer": "Producer(s)",
    "director": "Director(s)",
}

# Hämta UA från .env via config (delad med Wikidata)
UA = get_wikidata_user_agent()


# ---------- Helpers för Wikipedia ----------

def fetch_wikitext(title: str, follow_redirect: bool = True) -> Tuple[Optional[str], Optional[str]]:
    """
    Hämta wikitext (source) för en given titel. Följer redirects en gång.
    Returnerar (faktisk_titel, wikitext) eller (titel, None) om inget hittas.
    """
    if not title:
        return None, None

    params = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "titles": title,
        "format": "json",
        "formatversion": "2",
        "redirects": 1,
    }
    resp = requests.get(
        WIKI_API,
        params=params,
        timeout=30,
        headers={
            "User-Agent": UA,  # NYTT: inte hårdkodat längre
        },
    )
    resp.raise_for_status()
    time.sleep(0.25)  # vara snäll mot API:t

    js = resp.json()
    pages = js.get("query", {}).get("pages", [])
    if not pages:
        return None, None

    page = pages[0]
    actual_title = page.get("title")
    revs = page.get("revisions", [])
    if not revs:
        return actual_title, None

    content = revs[0].get("slots", {}).get("main", {}).get("content", "")
    if not content:
        return actual_title, None

    # Manuell redirect-fallback (#REDIRECT [[Foo]])
    m = re.match(r"#REDIRECT\s*\[\[([^\]]+)\]\]", content, flags=re.IGNORECASE)
    if m and follow_redirect:
        new_title = m.group(1)
        return fetch_wikitext(new_title, follow_redirect=False)

    return actual_title, content


def extract_template_block(text: str, start_idx: int) -> Optional[str]:
    """
    Generisk template-parser: börja på '{{' och räkna klamrar tills nivå 0 igen.
    Returnerar hela '{{ ... }}'-blocket som sträng.
    """
    i = start_idx
    brace_level = 0
    buf: List[str] = []

    while i < len(text):
        if text.startswith("{{", i):
            brace_level += 1
            buf.append("{{")
            i += 2
            continue
        if text.startswith("}}", i):
            brace_level -= 1
            buf.append("}}")
            i += 2
            if brace_level == 0:
                break
            continue
        buf.append(text[i])
        i += 1

    result = "".join(buf)
    if not result.lower().startswith("{{infobox"):
        return None
    return result


def extract_infobox(wikitext: str) -> Optional[str]:
    """
    Försök hitta en Infobox video game i wikitexten.
    """
    if not wikitext:
        return None

    candidates = [m.start() for m in re.finditer(r"\{\{[Ii]nfobox", wikitext)]
    if not candidates:
        return None

    for start_idx in candidates:
        snippet = wikitext[start_idx:start_idx+60].lower()
        if "infobox vg" in snippet or "infobox video game" in snippet:
            box = extract_template_block(wikitext, start_idx)
            if box:
                return box

    # fallback: ta första infobox oavsett
    return extract_template_block(wikitext, candidates[0])


def clean_value(val: str) -> str:
    # ta bort refs
    val = re.sub(r"<ref[^>]*>.*?</ref>", "", val, flags=re.DOTALL)
    val = re.sub(r"<ref[^/]*/>", "", val)
    # <br> -> komma
    val = re.sub(r"<br\s*/?>", ", ", val, flags=re.IGNORECASE)

    # [[Foo|Bar]] -> Bar, [[Foo]] -> Foo
    def repl_link(m):
        inner = m.group(1)
        parts = inner.split("|")
        return parts[-1]
    val = re.sub(r"\[\[([^\]]+)\]\]", repl_link, val)

    # [http://... Title] -> Title
    def repl_http(m):
        inner = m.group(1).strip()
        parts = inner.split(" ", 1)
        if len(parts) == 2:
            return parts[1]
        else:
            return parts[0]
    val = re.sub(r"\[([^\]]+)\]", repl_http, val)

    # ta bort andra templates {{...}} helt (t.ex. {{nowrap|...}})
    val = re.sub(r"\{\{[^\}]+\}\}", "", val)

    # whitespace cleanup
    val = re.sub(r"\s+", " ", val).strip()
    return val


def parse_infobox_roles(infobox_text: str) -> Dict[str, List[str]]:
    """
    Plocka ut roller (developer, publisher, designer, osv.) från infoboxen.
    Returnerar dict: role_key -> list[str]
    """
    roles_out: Dict[str, List[str]] = {k: [] for k in ROLE_FIELDS.keys()}

    for raw_line in infobox_text.split("\n"):
        line = raw_line.strip()
        if not line.startswith("|"):
            continue

        # | programmer   = John Doe<br>Jane Doe
        m = re.match(r"^\|\s*([A-Za-z0-9_ ]+?)\s*=\s*(.+)$", line)
        if not m:
            continue

        raw_field = m.group(1).strip().lower()
        raw_val = m.group(2).strip()

        for role_key in ROLE_FIELDS.keys():
            if raw_field == role_key or raw_field == role_key + "s":
                cleaned = clean_value(raw_val)
                parts = [p.strip(" ,") for p in cleaned.split(",") if p.strip(" ,")]
                roles_out[role_key].extend(parts)

    # dedupe
    for k, arr in roles_out.items():
        seen = set()
        uniq = []
        for person in arr:
            low = person.lower()
            if low not in seen and person != "":
                seen.add(low)
                uniq.append(person)
        roles_out[k] = uniq

    return roles_out


def pick_search_title(row: pd.Series) -> str:
    """
    Välj vilken titel vi ska prova först mot Wikipedia.
    - Försök med 'name' (från GB/IGDB) om den finns
    - annars 'title_primary'
    """
    for col in ["name", "title_primary"]:
        if col in row and isinstance(row[col], str) and row[col].strip():
            return row[col].strip()
    return ""


# ---------- Huvudlogik: loopa över editioner ----------

def main():
    ap = argparse.ArgumentParser(description="Enrich editions med Wikipedia-infobox-roller")
    ap.add_argument(
        "--in",
        dest="editions_csv",
        default=str(ED_PATH),  # NYTT: editions.csv som standard
        help="Path till editions.csv eller merge:ad editions-fil att enrich:a",
    )
    ap.add_argument(
        "--out",
        dest="out_csv",
        default="data/outputs/enrichment/wikipedia_enrichment.csv",
        help="Output enrichment CSV (per edition, roller från Wikipedia)",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max antal rader att köra (0 = alla)",
    )
    args = ap.parse_args()

    in_path = Path(args.editions_csv)
    if not in_path.exists():
        print(f"❌ Hittar inte inputfilen: {in_path}")
        sys.exit(1)

    df = pd.read_csv(in_path, dtype=str).fillna("")

    if args.limit > 0:
        df = df.head(args.limit)

    rows_out: List[Dict[str, str]] = []

    total = len(df)
    for idx, (_, row) in enumerate(df.iterrows(), start=1):
        edition_id = row.get("edition_id", "")
        search_title = pick_search_title(row)

        print(f"[{idx}/{total}] {edition_id} – söker Wikipedia för: {search_title!r}")

        wiki_page_title = ""
        has_infobox = "0"
        roles = {k: [] for k in ROLE_FIELDS.keys()}

        if search_title:
            try:
                wiki_page_title, wikitext = fetch_wikitext(search_title)
                if wikitext:
                    infobox = extract_infobox(wikitext)
                    if infobox:
                        has_infobox = "1"
                        roles = parse_infobox_roles(infobox)
            except Exception as e:
                print(f"   ⚠️ Fel vid hämtning/parsing för {search_title!r}: {e}")

        # bygg rad
        out_row: Dict[str, str] = {
            "edition_id": edition_id,
            "wiki_search_title": search_title,
            "wiki_page_title": wiki_page_title or "",
            "wiki_has_infobox": has_infobox,
            "source": "wikipedia",
        }

        # lägg till kolumner för varje roll, med '; '-separerade namn
        for role_key in ROLE_FIELDS.keys():
            col_name = f"wiki_{role_key}"
            vals = roles.get(role_key, [])
            out_row[col_name] = "; ".join(vals) if vals else ""

        rows_out.append(out_row)

    out_df = pd.DataFrame(rows_out)
    out_path = Path(args.out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False, encoding="utf-8")

    print(f"\n✅ Skrev {len(out_df)} rader → {out_path}")
    hits = (out_df["wiki_has_infobox"] == "1").sum()
    print(f"🎯 Infobox hittad för {hits}/{len(out_df)} editioner ({hits/len(out_df):.1%})")


if __name__ == "__main__":
    main()
