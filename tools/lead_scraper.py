#!/usr/bin/env python3
"""
NextStructure Lead Scraper
Findet lokale Unternehmen ohne Website via Google Places API.
Usage: python lead_scraper.py "Kiel" "Restaurant"
"""

import sys
import os
import csv
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL     = "https://maps.googleapis.com/maps/api/place/details/json"

DETAIL_FIELDS = "name,formatted_address,formatted_phone_number,rating,user_ratings_total,website,opening_hours"


def text_search(query: str, page_token: str = None) -> dict:
    params = {"query": query, "key": API_KEY, "language": "de"}
    if page_token:
        params["pagetoken"] = page_token
    r = requests.get(TEXT_SEARCH_URL, params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def place_details(place_id: str) -> dict:
    params = {"place_id": place_id, "fields": DETAIL_FIELDS, "key": API_KEY, "language": "de"}
    r = requests.get(DETAILS_URL, params=params, timeout=10)
    r.raise_for_status()
    return r.json().get("result", {})


def format_hours(opening_hours: dict) -> str:
    if not opening_hours:
        return ""
    weekday_text = opening_hours.get("weekday_text", [])
    return " | ".join(weekday_text)


def scrape(city: str, category: str, max_results: int = 60) -> list[dict]:
    query = f"{category} in {city}"
    print(f"\nSuche: „{query}"")
    print("─" * 50)

    results = []
    page_token = None
    page = 0

    while len(results) < max_results:
        page += 1
        # Google requires a short delay before using a next_page_token
        if page_token:
            time.sleep(2)

        print(f"  Seite {page} laden …", end=" ", flush=True)
        data = text_search(query, page_token)
        status = data.get("status")

        if status not in ("OK", "ZERO_RESULTS"):
            print(f"\n  API Fehler: {status} — {data.get('error_message', '')}")
            break

        places = data.get("results", [])
        print(f"{len(places)} Treffer")

        for place in places:
            if len(results) >= max_results:
                break

            place_id = place.get("place_id")
            if not place_id:
                continue

            details = place_details(place_id)

            # Skip if business already has a website
            if details.get("website"):
                continue

            row = {
                "Name":            details.get("name", place.get("name", "")),
                "Adresse":         details.get("formatted_address", place.get("formatted_address", "")),
                "Telefon":         details.get("formatted_phone_number", ""),
                "Bewertung":       details.get("rating", ""),
                "Anzahl_Reviews":  details.get("user_ratings_total", ""),
                "Kategorie":       category,
                "Öffnungszeiten":  format_hours(details.get("opening_hours")),
            }
            results.append(row)
            print(f"    ✓  {row['Name']} ({row['Adresse'][:50]}…)")

        page_token = data.get("next_page_token")
        if not page_token:
            break

    return results


def save_csv(rows: list[dict], city: str, category: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_city = city.replace(" ", "_")
    safe_cat  = category.replace(" ", "_")
    filename  = f"leads_{safe_city}_{safe_cat}_{timestamp}.csv"

    fieldnames = ["Name", "Adresse", "Telefon", "Bewertung", "Anzahl_Reviews", "Kategorie", "Öffnungszeiten"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return filename


def main():
    if len(sys.argv) < 3:
        print("Usage: python lead_scraper.py \"<Stadt>\" \"<Kategorie>\"")
        print("  z.B.: python lead_scraper.py \"Kiel\" \"Restaurant\"")
        sys.exit(1)

    if not API_KEY:
        print("Fehler: GOOGLE_PLACES_API_KEY nicht gesetzt.")
        print("Kopiere .env.example → .env und trage deinen API Key ein.")
        sys.exit(1)

    city     = sys.argv[1].strip()
    category = sys.argv[2].strip()

    leads = scrape(city, category)

    if not leads:
        print("\nKeine Leads ohne Website gefunden.")
        sys.exit(0)

    filename = save_csv(leads, city, category)

    print("\n" + "═" * 50)
    print(f"  Leads gefunden:       {len(leads)}")
    print(f"  Stadt:                {city}")
    print(f"  Kategorie:            {category}")
    print(f"  Gespeichert in:       {filename}")
    print("═" * 50)


if __name__ == "__main__":
    main()
