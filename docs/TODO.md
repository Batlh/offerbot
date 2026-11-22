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
