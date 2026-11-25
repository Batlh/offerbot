# To-do – offene Punkte

Stand: 25.11.2026. Ergebnisse und Zugangsbedingungen: [Quellenprüfung und Trierer Stichprobe](QUELLEN-API.md).

## 1. Hilfe im Programm

- [x] Hilfe-Menü bzw. „?“-Knopf in jedem Tab mit kurzer Erklärung, was der Tab macht und welche Felder es gibt
- [x] Tooltips an allen Einstellungen (vor allem Quellen, Platzhalter `{ort}`/`{plz}`/`{kaufda}`, Stichwort-Regeln, KI)
- [x] „Erste Schritte“-Seite beim ersten Start (Region setzen, Watchlist anlegen, ersten Lauf starten, Handy koppeln)
- [x] Hilfetexte aus dem README übernehmen, damit Programm und Doku gleich bleiben

## 2. kaufDA: Händler fehlen (z. B. Netto)

Beobachtung: Bei kaufDA werden nicht alle Märkte durchsucht – Netto fehlt, andere Märkte ebenfalls.

- [x] Prüfen, welche Händler kaufDA für Region Trier liefert und welche im Ergebnis ankommen (Debug-Modus-Log vergleichen)
- [x] Mögliche Ursachen prüfen:
  - Filter über die Einstellung `haendler` in `core/sources/kaufda.py` (Schreibweise, z. B. „Netto Marken-Discount“ vs. „Netto“)
  - kaufDA lädt Händler nachträglich per Skript nach → im einfachen Seitenabruf nicht enthalten
  - Begriff hat bei kaufDA keine eigene Seite → Händler wird gar nicht abgefragt
  - Händler-Prospekte stehen nur auf eigenen Händlerseiten (`/Geschaefte/<Händler>`), nicht auf den Begriffsseiten
- [x] Händlerliste in `gui/tab_prospekte.py` (`RETAILERS`) mit den kaufDA-Händlernamen abgleichen
- [x] Im Protokoll pro Lauf anzeigen: „kaufDA: X Händler gefunden, Y ohne Treffer“, damit Lücken sichtbar werden

## 3. Offizielle Schnittstellen (APIs) statt Seiten auslesen

Wo es eine API gibt, ist das ein großer Gewinn: stabiler, schneller, kein Bruch bei Seitenumbauten, keine Captchas.

- [x] Recherche, welche Händler/Portale offizielle oder offen dokumentierte Schnittstellen haben (kaufDA/Bonial, Marktguru, Prospekt-Portale, Händler-Apps, Preisvergleicher)
- [x] Nutzungsbedingungen je API prüfen (privater Gebrauch erlaubt? Schlüssel nötig? Kosten?)
- [x] Für Amazon: Keepa (Preisverlauf/Preisalarm, API kostenpflichtig) als Quelle prüfen statt Amazon direkt abzufragen
- [x] Für Blitzangebote: mydealz-RSS-Feed als Quelle mit Stichwort-/Preisfilter
- [x] API-Quelle im Kern über die bestehende Registry bereitstellen (WooCommerce Store API), damit neue Schnittstellen ohne Oberflächen-Umbau dazukommen
- [x] API-Vorrang für konfigurierte WooCommerce-Watchlist-Suchen: HTML-Rückfall nur bei fehlendem Endpunkt; bestehende individuelle Quellen können die Shop-Adresse ergänzen

## 4. Lizenzen (erledigt in 1.10.9)

- [x] Entschieden: **a) PyMuPDF ersetzt** durch pypdfium2 (PDFium, Apache-2.0/BSD-3) + Pillow, gebündelt in
  `core/prospekte/pdfwerk.py`. Betroffen waren `pdftext.py`, `fetchers.py`, `api.py`, `sources/rewe.py`, Tests,
  `requirements.txt`, `build_exe.bat` und der Workflow. Texterkennung bleibt RapidOCR.
- [x] **Lizenzhinweise in der EXE**: „Hilfe → Über / Lizenzen“ und `_internal\THIRD_PARTY_LICENSES.txt`, beim Build
  von `python -m angebotsbot.lizenzen` aus den installierten Paketen erzeugt (ohne pip-licenses). SPDX-Volltexte
  für Pakete ohne eigene Lizenzdatei liegen in `angebotsbot/lizenztexte/`. Die Datei liegt bewusst in `_internal`:
  der Updater bis 1.10.8 nimmt auf oberster Ebene des Update-Pakets nichts anderes an.
- [x] **Lizenzhinweise in der Android-App**: Menüpunkt „Über / Lizenzen“ (`showLicensePage`) mit Version und
  Repo-Link. Version steht in `app/lib/version.dart` (Test prüft Gleichstand mit pubspec und `__version__`).
- [x] README-Abschnitt „Lizenz“ angepasst.
- [ ] Optional: Zeichen-Koordinaten von PDFium nutzen, um Preise genauer dem Produkt daneben zuzuordnen.

## 5. Aus der Durchsicht vom 25.11.2026

- [ ] **Schlüsselwechsel 1.10.8:** Im CHANGELOG zu 1.10.8 steht der Hinweis (einmal deinstallieren, Liste vorher
  abgleichen). Fehlt noch in README (Abschnitt Handy-App) und `docs/ANDROID.md`; optional erkennt die App den Fall
  und zeigt genau diesen Hinweis statt „Signatur stimmt nicht“.
- [ ] **kaufDA-Sonderfall aus dem Code nehmen:** In `core/sources/kaufda.py` ist „Monster Energy → Energydrink“ fest
  verdrahtet. Stattdessen ein Feld „Ersatzbegriff für Prospekt-Portale“ im Watchlist-Eintrag (per Migration in
  `config.py` für den bestehenden Monster-Eintrag vorbelegen).
- [ ] **robots.txt-Fehler in `core/net.py` (`_public_delay`):** Antwortet der Server beim robots.txt mit einem anderen
  Fehler als 404 (z. B. 403/500), fliegt ein roher `HTTPError` statt einer verständlichen `FetchError`-Meldung, und
  der Abruf wird bei jeder Anfrage wiederholt. Ergebnis (auch „nicht erreichbar“) je Lauf zwischenspeichern und
  klar melden: „robots.txt von <Seite> nicht lesbar (HTTP …) – Quelle übersprungen“.
