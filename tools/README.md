# NextStructure Lead Scraper

Findet lokale Unternehmen **ohne Website** via Google Places API und exportiert sie als CSV — direkt importierbar in den NextStructure Hub Lead-Manager.

## Setup

```bash
# 1. Abhängigkeiten installieren
pip install requests python-dotenv --break-system-packages

# 2. API Key konfigurieren
cp .env.example .env
# .env öffnen und GOOGLE_PLACES_API_KEY eintragen
```

### Google Places API Key besorgen
1. [Google Cloud Console](https://console.cloud.google.com/) öffnen
2. Neues Projekt erstellen (oder bestehendes nutzen)
3. **Places API** aktivieren
4. Unter „Anmeldedaten" einen API Key erstellen
5. Key in `.env` eintragen

## Verwendung

```bash
python lead_scraper.py "<Stadt>" "<Kategorie>"
```

**Beispiele:**
```bash
python lead_scraper.py "Kiel" "Restaurant"
python lead_scraper.py "Hamburg" "Friseursalon"
python lead_scraper.py "Quickborn" "Zahnarzt"
python lead_scraper.py "Norderstedt" "Fitnessstudio"
```

## Output

Das Skript erstellt eine CSV-Datei im aktuellen Verzeichnis:
```
leads_Kiel_Restaurant_20240601_143022.csv
```

**Spalten:**

| Spalte | Beschreibung |
|---|---|
| Name | Firmenname |
| Adresse | Vollständige Adresse |
| Telefon | Telefonnummer (falls vorhanden) |
| Bewertung | Google-Bewertung (1–5) |
| Anzahl_Reviews | Anzahl der Bewertungen |
| Kategorie | Eingegebene Kategorie |
| Öffnungszeiten | Wochenplan (pipe-getrennt) |

Nur Unternehmen **ohne Website** werden gespeichert — das sind deine Akquise-Targets.

## In NextStructure Hub importieren

1. CSV-Datei generieren
2. Im Hub → **Lead-Manager** → **CSV importieren**
3. Leads bewerten und in die Kundenpipeline übernehmen

## Limits

- Bis zu **60 Ergebnisse** pro Suche (3 Seiten à 20, Google-Maximum)
- Google Places Details API: ~0,017 USD pro Abruf — bei 60 Leads ca. 1 USD
- Rate Limiting: 2 Sekunden Pause zwischen Seiten (Google-Anforderung)
