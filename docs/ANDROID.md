# Android-Version – Plan und Checkpoint

Stand: 16.11.2026, Version 1.9.0 · Status: **A umgesetzt (erste Version)**, B als Option vorgemerkt

## Ausgangslage

- `angebotsbot/core` enthält die komplette Logik ohne Oberfläche (Quellen, Abgleich, Prospekte, Grundpreise,
  Berichte, Einkaufszettel). Die Windows-Oberfläche (`angebotsbot/gui`, PySide6) ist davon getrennt.
- Schwer auf Android: Texterkennung (rapidocr/onnxruntime), PDF (PyMuPDF), Browser-Modus (Playwright).
  Leicht: alles mit HTTP + HTML/JSON (mydealz, kaufDA, Bonial, Lidl, Amazon prüfen, Abgleich, Grundpreise).

## Optionen

| | A: Begleit-App (empfohlen) | B: Eigenständige App |
|---|---|---|
| Idee | Der PC-Bot bleibt das „Gehirn“, das Handy zeigt Treffer, Einkaufszettel, Watchlist, Prospektseiten | Alles läuft auf dem Handy |
| Technik | Flutter (wie casino-app) + kleine HTTP-Schnittstelle im PC-Bot (nur im WLAN, mit Schlüssel) | Flutter mit eigener Neuentwicklung der Quellen in Dart, oder Python über Chaquopy |
| Aufwand | klein–mittel | groß (Quellen, Abgleich, Prospekte doppelt pflegen) |
| Texterkennung/Prospekte | läuft weiter auf dem PC | nur ohne OCR oder mit Google ML Kit |
| Unterwegs | Treffer kommen per ntfy; Daten vom letzten Abgleich (Sync im WLAN, optional über Cloud) | voll unabhängig |

**Entscheidung: A wird gebaut.** Ein Code für die Logik, das Handy bekommt eine schnelle, saubere Oberfläche.
**B ist als Option vorgemerkt („eventuell geplant“)** – für alle, die den Bot ohne laufenden PC nutzen wollen.
Damit B später möglich bleibt, bekommt die Begleit-App eine Schicht „Datenquelle“: heute der PC-Bot, später
optional eigene Quellen direkt auf dem Handy (mydealz, kaufDA, Bonial, Lidl – alles ohne Texterkennung machbar).

## B – eventuell geplant (Option)
- Eigene Quellen in Dart: mydealz-RSS, kaufDA/Bonial (__NEXT_DATA__), Lidl-JSON, Abgleich, Grundpreise
- Keine Texterkennung von PDF-Prospekten (höchstens Google ML Kit), kein Browser-Modus
- Benachrichtigungen direkt auf dem Handy statt über ntfy/Telegram
- Umsetzung erst, wenn A steht und Bedarf da ist

## Plan für A

### PC-Seite (`angebotsbot/core/api.py`, neu)
- Kleiner HTTP-Server (Standardbibliothek, Thread), Port 8765, nur wenn in den Einstellungen eingeschaltet
- Zugang nur mit Schlüssel (zufällig erzeugt, als QR-Code in den Einstellungen anzeigen → Handy scannt)
- Endpunkte (JSON):
  - `GET  /api/status` – Version, letzter Lauf, ungelesene Treffer
  - `GET  /api/treffer?ungelesen=1` – Treffer inkl. Grundpreis, Preis-Check, Link/Prospektseite
  - `POST /api/treffer/<uid>/gelesen`
  - `GET  /api/einkaufszettel`, `POST /api/einkaufszettel` (hinzufügen), `POST /api/einkaufszettel/<id>/erledigt`
  - `GET  /api/watchlist`, `POST /api/watchlist` (anlegen/ändern)
  - `GET  /api/prospekt/<id>/seite/<n>.jpg` – Prospektseite als Bild (PyMuPDF rendert)
  - `POST /api/pruefen` – Lauf starten
  - `GET  /api/amazon?watch=<id>` – „Amazon prüfen“ vom Handy aus
- Windows-Firewall-Hinweis beim ersten Einschalten

### Handy-Seite (`android/`, Flutter)
- Tabs: Treffer · Einkaufszettel (abhaken, nach Läden) · Watchlist · Prospekt-Viewer (Seitenbilder, Zoom)
- Einrichten: QR-Code scannen (Adresse + Schlüssel)
- Offline: letzter Stand wird gespeichert, Einkaufszettel geht auch ohne PC
- Benachrichtigungen weiter über ntfy (schon fertig)
- Build: GitHub Actions baut die APK und hängt sie an dieselbe Release wie die Windows-ZIP

## Checkpoint

### Erledigt
- [x] Logik von der Oberfläche getrennt (`core` ohne PySide6)
- [x] Handy-Benachrichtigungen (ntfy/Telegram)
- [x] Plan und Schnittstellen-Entwurf (diese Datei)

### Offen (in dieser Reihenfolge)
1. [x] Entscheidung: A, B als Option vorgemerkt
2. [x] `core/api.py` + Einstellungen (Schalter, Port, Schlüssel, QR-Code) + Tests
3. [x] Flutter-Projekt `app/` (Android-Ordner wird im Build erzeugt): Einrichtung per QR, Treffer-Liste
4. [x] Einkaufszettel (offline-fähig) + Watchlist + „Amazon prüfen“ in der App
5. [x] Prospekt-Viewer in der App (Seitenbilder vom PC, Zoom)
6. [x] APK-Build in GitHub Actions (analyze, Tests, feste Signatur), an die Release gehängt
7. [ ] Test auf dem Handy im WLAN (Nutzer)
8. [ ] Später: Offline-Treffer, Benachrichtigungen in der App, App-Symbol

### Hinweise
- Signatur: fester Schlüssel `app/ci/offerbot.keystore` (liegt offen im Repo, private App ohne Store), damit
  Updates über die installierte App funktionieren.
- Datenquelle austauschbar: `app/lib/data/source.dart` (`DataSource`) – Grundlage für Option B.
