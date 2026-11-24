# To-do – offene Punkte

Stand: 22.11.2026. Ergebnisse und Zugangsbedingungen: [Quellenprüfung und Trierer Stichprobe](QUELLEN-API.md).

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

## 4. Lizenzen (vorgemerkt für 25.11.2026)

Hinweis aus einer Lizenzprüfung: Das Repo steht unter MIT, die Windows-EXE enthält aber **PyMuPDF/MuPDF**. Die gibt es nur
unter **AGPL** oder mit kommerzieller Lizenz. Weil PyInstaller PyMuPDF in die EXE packt und die EXE über die Releases
verteilt wird, fällt die EXE als Ganzes unter die AGPL. Das README sagt aber nur „MIT“. Der Quellcode ist ohnehin
öffentlich, es ist also kein Drama, aber falsch dokumentiert.

- [ ] Entscheiden (Vorschlag: **a**):
  - **a) PyMuPDF ersetzen**, z. B. durch `pypdfium2` (Apache-2.0/BSD-3), dann bleibt alles MIT.
    Betroffen sind mehr Dateien als zunächst gedacht: `core/prospekte/pdftext.py` (Text, Seiten als Bild für OCR),
    `core/prospekte/fetchers.py` (PDF aus Bildern bauen → z. B. mit Pillow), `core/api.py` (Seitenbilder für die
    Handy-App), `core/sources/rewe.py`, dazu `tests/test_core.py`, `requirements.txt` und `--collect-data pymupdf`
    im Workflow. Die Seitensuche im PDF-Viewer läuft über Qt (QtPdf), sie ist nicht betroffen.
    Texterkennung bleibt **RapidOCR** (PaddleOCR-Modelle über ONNX Runtime, Apache-2.0/MIT). Das volle PaddleOCR
    mit PaddlePaddle wäre viel größer und brächte für Prospekte kaum mehr. pdfplumber ist nicht nötig: pypdfium2
    liefert Text samt Zeichen-Koordinaten selbst. Optional: Koordinaten nutzen, um Preise genauer dem Produkt
    daneben zuzuordnen (heute: Preis aus dem Text in der Nähe geraten).
  - b) AGPL akzeptieren: im README vermerken, dass die EXE unter AGPL steht, AGPL-Text und Link zum Quellcode
    in die EXE packen.
- [ ] **Lizenzhinweise in der EXE**: Fenster „Über / Lizenzen“ und eine Datei `THIRD_PARTY_LICENSES.txt` im ZIP.
  Inhalt: PySide6/Qt (LGPL-3.0, Bibliotheken bleiben austauschbar – Hinweis + Link zum Quellcode), Playwright
  (Apache-2.0), RapidOCR + PaddleOCR-Modelle (Apache-2.0), ONNX Runtime (MIT), OpenCV (Apache-2.0), requests, BeautifulSoup, lxml, keyring, qrcode usw.
  Am besten beim Build automatisch erzeugen, z. B. mit `pip-licenses`.
- [ ] **Lizenzhinweise in der Android-App**: Menüpunkt „Lizenzen“ mit Flutters eingebautem `showLicensePage`
  (listet die Pakete automatisch), dazu App-Version und Link zum Repo.
- [ ] README-Abschnitt „Lizenz“ anpassen: eigener Code MIT, mitgelieferte Bibliotheken mit eigenen Lizenzen.
