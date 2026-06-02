#!/usr/bin/env python3
"""
NextStructure Lead Scraper
Findet lokale Unternehmen ohne Website via Google Places API.
Usage: python lead_scraper.py "<Stadt>" "<Kategorie>"
  z.B.: python lead_scraper.py "Lübeck" "Restaurant"
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


# ── Geocoding via OpenStreetMap Nominatim (no extra API activation needed) ─────

def get_city_coords(city: str) -> tuple[float, float] | None:
    r = requests.get(
        NOMINATIM_URL,
        params={"q": city, "format": "json", "limit": 1},
        headers={"User-Agent": "NextStructure-LeadScraper/1.0"},
        timeout=10,
    )
    r.raise_for_status()
    results = r.json()
    if not results:
        return None
    return float(results[0]["lat"]), float(results[0]["lon"])


# ── Places search ──────────────────────────────────────────────────────────────

def text_search_page(query: str, lat: float, lng: float, page_token: str | None = None) -> dict:
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
    return r.json()


def collect_place_ids(query: str, lat: float, lng: float) -> set[str]:
    ids: set[str] = set()
    page_token = None
    page = 0

    while True:
        page += 1
        if page_token:
            time.sleep(2)  # Google requires delay before using next_page_token

        data = text_search_page(query, lat, lng, page_token)
        status = data.get("status")

        if status == "ZERO_RESULTS":
            break
        if status != "OK":
            print(f"\n    ⚠ API Status {status}: {data.get('error_message', '')}")
            break

        for place in data.get("results", []):
            pid = place.get("place_id")
            if pid:
                ids.add(pid)

        page_token = data.get("next_page_token")
        if not page_token:
            break

    return ids


# ── Place details ──────────────────────────────────────────────────────────────

def get_details(place_id: str) -> dict:
    r = requests.get(
        DETAILS_URL,
        params={"place_id": place_id, "fields": DETAIL_FIELDS, "key": API_KEY, "language": "de"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json().get("result", {})


def format_hours(opening_hours: dict) -> str:
    return " | ".join(opening_hours.get("weekday_text", []))


# ── Main scrape ────────────────────────────────────────────────────────────────

def scrape(city: str, category: str) -> list[dict]:
    print(f"\nStadt:     {city}")
    print(f"Kategorie: {category}")
    print(f"Radius:    {SEARCH_RADIUS // 1000} km")
    print("─" * 56)

    # Step 1: geocode
    print("Koordinaten ermitteln …", end=" ", flush=True)
    coords = get_city_coords(city)
    if not coords:
        print(f'Fehler — Stadt "{city}" nicht gefunden.')
        sys.exit(1)
    lat, lng = coords
    print(f"{lat:.4f}, {lng:.4f}")

    # Step 2: collect place_ids via multiple query variants
    queries = [
        f"{category} {city}",
        f"{category} in {city}",
        f"{category} {city} centrum",
        f"{category} {city} altstadt",
    ]

    all_ids: set[str] = set()
    for q in queries:
        print(f'  Suche: "{q}" …', end=" ", flush=True)
        ids = collect_place_ids(q, lat, lng)
        new = ids - all_ids
        all_ids |= ids
        print(f"{len(ids)} Treffer, {len(new)} neu (gesamt {len(all_ids)})")

    print(f"\nEindeutige Orte gesamt: {len(all_ids)}")
    print("Details abrufen …\n")

    # Step 3: fetch details + filter
    leads: list[dict] = []
    total     = len(all_ids)
    skipped   = 0
    no_website = 0

    for i, place_id in enumerate(all_ids, 1):
        d = get_details(place_id)

        # Skip closed businesses
        bstatus = d.get("business_status", "OPERATIONAL")
        if bstatus != "OPERATIONAL":
            skipped += 1
            _print_progress(i, total, no_website, skipped)
            continue

        has_website = bool(d.get("website"))
        if has_website:
            skipped += 1
            _print_progress(i, total, no_website, skipped)
            continue

        no_website += 1
        leads.append({
            "Name":             d.get("name", ""),
            "Adresse":          d.get("formatted_address", ""),
            "Telefon":          d.get("formatted_phone_number", ""),
            "Bewertung":        d.get("rating", ""),
            "Anzahl_Reviews":   d.get("user_ratings_total", ""),
            "Kategorie":        category,
            "Status":           bstatus,
            "Website_vorhanden": "Nein",
        })
        _print_progress(i, total, no_website, skipped)

    print()  # newline after progress line
    return leads


def _print_progress(current: int, total: int, kept: int, skipped: int) -> None:
    print(
        f"\r  [{current:>3}/{total}]  Gefunden: {current}  |  "
        f"Ohne Website: {kept}  |  Übersprungen: {skipped}   ",
        end="",
        flush=True,
    )


# ── CSV export ─────────────────────────────────────────────────────────────────

def save_csv(rows: list[dict], city: str, category: str) -> str:
    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_city  = city.replace(" ", "_")
    safe_cat   = category.replace(" ", "_")
    filename   = os.path.join(
        os.path.dirname(__file__),
        f"leads_{safe_city}_{safe_cat}_{timestamp}.csv",
    )
    fieldnames = [
        "Name", "Adresse", "Telefon", "Bewertung",
        "Anzahl_Reviews", "Kategorie", "Status", "Website_vorhanden",
    ]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return filename


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python lead_scraper.py \"<Stadt>\" \"<Kategorie>\"")
        print("  z.B.: python lead_scraper.py \"Lübeck\" \"Restaurant\"")
        sys.exit(1)

    if not API_KEY:
        print("Fehler: GOOGLE_PLACES_API_KEY nicht gesetzt.")
        print("Kopiere tools/.env.example → tools/.env und trage deinen API Key ein.")
        sys.exit(1)

    city     = sys.argv[1].strip()
    category = sys.argv[2].strip()

    leads = scrape(city, category)

    if not leads:
        print("\nKeine Leads ohne Website gefunden.")
        sys.exit(0)

    filename = save_csv(leads, city, category)

    print("\n" + "═" * 56)
    print(f"  Leads ohne Website:   {len(leads)}")
    print(f"  Stadt:                {city}")
    print(f"  Kategorie:            {category}")
    print(f"  Gespeichert in:       {filename}")
    print("═" * 56)


if __name__ == "__main__":
    main()
