#!/usr/bin/env python3
"""
NextStructure Lead Scraper — Interactive Mode
Usage: python lead_scraper.py
"""

import sys
import os
import csv
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")

NOMINATIM_URL   = "https://nominatim.openstreetmap.org/search"
TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL     = "https://maps.googleapis.com/maps/api/place/details/json"

DETAIL_FIELDS = (
    "place_id,name,formatted_address,formatted_phone_number,"
    "rating,user_ratings_total,website,opening_hours,business_status"
)

SEARCH_RADIUS = 10000  # metres

BRANCHEN = [
    ("Restaurant",          ["Restaurant", "Restaurant in", "Speiselokal", "Gasthaus"]),
    ("Bar & Café",          ["Bar", "Café", "Coffee Shop", "Bistro"]),
    ("Friseur & Kosmetik",  ["Friseur", "Friseursalon", "Kosmetikstudio", "Nagelstudio"]),
    ("Handwerker",          ["Handwerker", "Elektriker", "Klempner", "Malerbetrieb", "Tischler"]),
    ("Autowerkstatt",       ["Autowerkstatt", "KFZ-Werkstatt", "Reifenservice", "KFZ-Meister"]),
]


# ── Menu ───────────────────────────────────────────────────────────────────────

def prompt(text: str, default: str = "") -> str:
    val = input(text).strip()
    return val if val else default

def ask_yn(text: str, default: bool = True) -> bool:
    hint = " (j/n) [j]: " if default else " (j/n) [n]: "
    val = input(text + hint).strip().lower()
    if not val:
        return default
    return val in ("j", "ja", "y", "yes")

def show_menu() -> tuple[str, list[str], str, bool, bool]:
    print()
    print("╔══════════════════════════════════════╗")
    print("║   NextStructure Lead Scraper  v2.0   ║")
    print("╚══════════════════════════════════════╝")
    print()

    # City
    city = ""
    while not city:
        city = prompt("Stadt: ")
        if not city:
            print("  ⚠  Bitte eine Stadt eingeben.")

    # Category
    print()
    print("Branche:")
    for i, (label, _) in enumerate(BRANCHEN, 1):
        print(f"  {i}. {label}")
    print(f"  {len(BRANCHEN)+1}. Andere (manuell eingeben)")
    print()

    branch_label = ""
    search_terms: list[str] = []
    while not branch_label:
        choice = prompt(f"Auswahl [1-{len(BRANCHEN)+1}]: ")
        if choice.isdigit():
            idx = int(choice)
            if 1 <= idx <= len(BRANCHEN):
                branch_label, search_terms = BRANCHEN[idx - 1]
            elif idx == len(BRANCHEN) + 1:
                custom = prompt("Branche eingeben: ")
                if custom:
                    branch_label = custom
                    search_terms = [custom]
        if not branch_label:
            print("  ⚠  Ungültige Auswahl.")

    print()
    filter_no_website = ask_yn("Filter: Nur ohne Website?", default=True)
    filter_phone      = ask_yn("Filter: Nur mit Telefonnummer?", default=True)

    print()
    return city, search_terms, branch_label, filter_no_website, filter_phone


# ── Geocoding ──────────────────────────────────────────────────────────────────

def get_city_coords(city: str) -> tuple[float, float] | None:
    r = requests.get(
        NOMINATIM_URL,
        params={"q": city, "format": "json", "limit": 1},
        headers={"User-Agent": "NextStructure-LeadScraper/2.0"},
        timeout=10,
    )
    r.raise_for_status()
    results = r.json()
    if not results:
        return None
    return float(results[0]["lat"]), float(results[0]["lon"])


# ── Places search ──────────────────────────────────────────────────────────────

def collect_place_ids(query: str, lat: float, lng: float) -> set[str]:
    ids: set[str] = set()
    page_token = None
    page = 0

    while True:
        page += 1
        if page_token:
            time.sleep(2)

        params = {
            "query":    query,
            "location": f"{lat},{lng}",
            "radius":   SEARCH_RADIUS,
            "key":      API_KEY,
            "language": "de",
        }
        if page_token:
            params["pagetoken"] = page_token

        r = requests.get(TEXT_SEARCH_URL, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        status = data.get("status")

        if status == "ZERO_RESULTS":
            break
        if status != "OK":
            print(f"\n  ⚠  API Fehler {status}: {data.get('error_message', '')}")
            break

        for place in data.get("results", []):
            pid = place.get("place_id")
            if pid:
                ids.add(pid)

        page_token = data.get("next_page_token")
        if not page_token:
            break

    return ids


def get_details(place_id: str) -> dict:
    r = requests.get(
        DETAILS_URL,
        params={
            "place_id": place_id,
            "fields":   DETAIL_FIELDS,
            "key":      API_KEY,
            "language": "de",
        },
        timeout=10,
    )
    r.raise_for_status()
    return r.json().get("result", {})


# ── Scrape ─────────────────────────────────────────────────────────────────────

def scrape(
    city: str,
    search_terms: list[str],
    branch_label: str,
    lat: float,
    lng: float,
    filter_no_website: bool,
    filter_phone: bool,
) -> list[dict]:

    # Build query variants for every search term in the branch
    queries: list[str] = []
    for term in search_terms:
        queries += [
            f"{term} {city}",
            f"{term} in {city}",
            f"{term} {city} Altstadt",
            f"{term} {city} Zentrum",
        ]

    # Collect all place_ids (deduplicated)
    all_ids: set[str] = set()
    print(f"Suche läuft für {len(queries)} Queries …")
    for q in queries:
        print(f"  → \"{q}\" …", end=" ", flush=True)
        ids = collect_place_ids(q, lat, lng)
        new = ids - all_ids
        all_ids |= ids
        print(f"{len(ids)} Treffer, {len(new)} neu (gesamt {len(all_ids)})")

    total = len(all_ids)
    print(f"\n{total} eindeutige Orte gefunden. Details abrufen …\n")

    leads: list[dict] = []
    skipped_website  = 0
    skipped_phone    = 0
    skipped_closed   = 0

    for i, place_id in enumerate(all_ids, 1):
        d = get_details(place_id)

        bstatus = d.get("business_status", "OPERATIONAL")
        if bstatus != "OPERATIONAL":
            skipped_closed += 1
            _progress(i, total, len(leads), skipped_website, skipped_phone, skipped_closed)
            continue

        if filter_no_website and d.get("website"):
            skipped_website += 1
            _progress(i, total, len(leads), skipped_website, skipped_phone, skipped_closed)
            continue

        phone = d.get("formatted_phone_number", "")
        if filter_phone and not phone:
            skipped_phone += 1
            _progress(i, total, len(leads), skipped_website, skipped_phone, skipped_closed)
            continue

        leads.append({
            "Name":              d.get("name", ""),
            "Adresse":           d.get("formatted_address", ""),
            "Telefon":           phone,
            "Bewertung":         d.get("rating", ""),
            "Anzahl_Reviews":    d.get("user_ratings_total", ""),
            "Branche":           branch_label,
            "Status":            bstatus,
            "Website_vorhanden": "Ja" if d.get("website") else "Nein",
        })
        _progress(i, total, len(leads), skipped_website, skipped_phone, skipped_closed)

    print()  # end progress line
    return leads


def _progress(current: int, total: int, kept: int,
              skip_web: int, skip_phone: int, skip_closed: int) -> None:
    print(
        f"\r  [{current:>3}/{total}]  ✓ Leads: {kept}  "
        f"| ⊘ Website: {skip_web}  "
        f"| ⊘ Kein Tel: {skip_phone}  "
        f"| ⊘ Geschlossen: {skip_closed}   ",
        end="", flush=True,
    )


# ── CSV export ─────────────────────────────────────────────────────────────────

def save_csv(rows: list[dict], city: str, branch_label: str) -> str:
    date      = datetime.now().strftime("%Y-%m-%d")
    safe_city = city.replace(" ", "_")
    safe_br   = branch_label.replace(" ", "_").replace("&", "und").replace("/", "-")[:30]
    filename  = os.path.join(
        os.path.dirname(__file__),
        f"leads_{safe_city}_{safe_br}_{date}.csv",
    )
    fieldnames = [
        "Name", "Adresse", "Telefon", "Bewertung",
        "Anzahl_Reviews", "Branche", "Status", "Website_vorhanden",
    ]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return filename


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    if not API_KEY:
        print("Fehler: GOOGLE_PLACES_API_KEY nicht gesetzt.")
        print("Kopiere tools/.env.example → tools/.env und trage deinen API Key ein.")
        sys.exit(1)

    city, search_terms, branch_label, filter_no_website, filter_phone = show_menu()

    print(f"Koordinaten für \"{city}\" ermitteln …", end=" ", flush=True)
    coords = get_city_coords(city)
    if not coords:
        print(f"nicht gefunden.")
        sys.exit(1)
    lat, lng = coords
    print(f"{lat:.4f}, {lng:.4f}\n")

    leads = scrape(city, search_terms, branch_label, lat, lng, filter_no_website, filter_phone)

    print()
    if not leads:
        print("⚠  Keine Leads gefunden — Filterkriterien ggf. lockern.")
        sys.exit(0)

    filename = save_csv(leads, city, branch_label)
    basename = os.path.basename(filename)

    print(f"✅  {city} {branch_label} — {len(leads)} Leads gefunden")
    print(f"📁  Gespeichert: {basename}")


if __name__ == "__main__":
    main()
