# To-do – offene Punkte

Stand: 21.11.2026. Reihenfolge = Vorschlag für die Bearbeitung.

## 1. Hilfe im Programm

- [ ] Hilfe-Menü bzw. „?“-Knopf in jedem Tab mit kurzer Erklärung, was der Tab macht und welche Felder es gibt
- [ ] Tooltips an allen Einstellungen (vor allem Quellen, Platzhalter `{ort}`/`{plz}`/`{kaufda}`, Stichwort-Regeln, KI)
- [ ] „Erste Schritte“-Seite beim ersten Start (Region setzen, Watchlist anlegen, ersten Lauf starten, Handy koppeln)
- [ ] Hilfetexte aus dem README übernehmen, damit Programm und Doku gleich bleiben

## 2. kaufDA: Händler fehlen (z. B. Netto)

Beobachtung: Bei kaufDA werden nicht alle Märkte durchsucht – Netto fehlt, andere Märkte ebenfalls.

- [ ] Prüfen, welche Händler kaufDA für Region Trier liefert und welche im Ergebnis ankommen (Debug-Modus-Log vergleichen)
- [ ] Mögliche Ursachen prüfen:
  - Filter über die Einstellung `haendler` in `core/sources/kaufda.py` (Schreibweise, z. B. „Netto Marken-Discount“ vs. „Netto“)
  - kaufDA lädt Händler nachträglich per Skript nach → im einfachen Seitenabruf nicht enthalten
  - Begriff hat bei kaufDA keine eigene Seite → Händler wird gar nicht abgefragt
  - Händler-Prospekte stehen nur auf eigenen Händlerseiten (`/Geschaefte/<Händler>`), nicht auf den Begriffsseiten
- [ ] Händlerliste in `gui/tab_prospekte.py` (`RETAILERS`) mit den kaufDA-Händlernamen abgleichen
- [ ] Im Protokoll pro Lauf anzeigen: „kaufDA: X Händler gefunden, Y ohne Treffer“, damit Lücken sichtbar werden

## 3. Offizielle Schnittstellen (APIs) statt Seiten auslesen

Wo es eine API gibt, ist das ein großer Gewinn: stabiler, schneller, kein Bruch bei Seitenumbauten, keine Captchas.

- [ ] Recherche, welche Händler/Portale offizielle oder offen dokumentierte Schnittstellen haben (kaufDA/Bonial, Marktguru, Prospekt-Portale, Händler-Apps, Preisvergleicher)
- [ ] Nutzungsbedingungen je API prüfen (privater Gebrauch erlaubt? Schlüssel nötig? Kosten?)
- [ ] Für Amazon: Keepa (Preisverlauf/Preisalarm, API kostenpflichtig) als Quelle prüfen statt Amazon direkt abzufragen
- [ ] Für Blitzangebote: mydealz-RSS-Feed als Quelle mit Stichwort-/Preisfilter
- [ ] Quellen-Typ „API“ im Kern vorsehen, damit neue Schnittstellen ohne Oberflächen-Umbau dazukommen
- [ ] Seiten-Auslesen nur noch als Rückfall, wenn keine API existiert
