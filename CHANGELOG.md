# Changelog

Alle Versionen des AngebotsBot (offerbot). Die neueste steht oben.
Jede Release auf GitHub enthält die fertige Windows-Version als ZIP (`AngebotsBot-windows.zip`).

## 1.6.2 – 2026-11-16
### Behoben
- Umlaute und Gedankenstriche im Release-Text werden richtig angezeigt

## 1.6.1 – 2026-11-16
### Neu
- Jeder Build erscheint automatisch als Release auf GitHub – mit Changelog und Liste der Änderungen

## 1.6.0 – 2026-11-16
### Neu
- Kaufland-Prospekte über filiale.kaufland.de
- Prüfungen (Captcha) selbst lösen wie in SimVault: sichtbares Browserfenster, du löst die Prüfung, der Bot
  übernimmt die Freigabe (unter Windows verschlüsselt gespeichert) und ruft die Quelle erneut ab
- Knopf „Prüfung im Browser lösen“ bei den Quellen, Freigaben in den Einstellungen löschbar

## 1.5.0 – 2026-11-16
### Neu
- Metro über kaufDA (bundesweite Händlerseiten, frei erweiterbar)
- Cactus Luxemburg: Issuu-Prospekt als Seitenbilder + Texterkennung
- Auchan Luxemburg: Blätterkatalog wird im Browser-Modus seitenweise fotografiert und per Texterkennung gelesen

## 1.4.0 – 2026-11-16
### Neu
- Grundpreis-Vergleich (€/kg, €/l, €/Stück), Preisvergleich danach sortiert
- Preis-Check: Vergleich mit dem 30-Tage-Tiefstpreis, Preisverlauf als Diagramm
- Luxemburg: Lidl, ALDI, Delhaize · Frankreich: Bonial.fr (Carrefour, E.Leclerc, Auchan, Intermarché, Super U …)
- Einkaufszettel nach Läden (abhaken, drucken, aufs Handy)
- Handy-Benachrichtigung über ntfy oder Telegram
- Wochenbericht als HTML, Markdown und CSV
- Amazon: Spar-Abo-Rabatt wird erkannt
- Debug-Log mit Logdatei, Absturzberichten und Debug-Paket

## 1.3.0 – 2026-11-16
### Neu
- „Amazon prüfen“: einmalige Amazon-Suche auf Knopfdruck mit Preisen, Streichpreisen, Grundpreisen und Hinweisen

## 1.2.1 – 2026-11-16
### Neu
- Knopf „Im Browser ansehen“ in der Watchlist (idealo, Geizhals, mydealz, Amazon, kaufDA – Liste änderbar)

## 1.2.0 – 2026-11-16
### Neu
- Browser-Modus richtet sich beim Anhaken selbst ein (nutzt Microsoft Edge, sonst Chromium-Download)
- idealo-Produktseiten als Produkt-Links
### Entfernt
- install_browser_mode.bat (nicht mehr nötig)

## 1.1.0 – 2026-11-16
### Neu
- Region (Ort/PLZ) in den Einstellungen
- kaufDA-Quelle: Prospekt-Angebote aller Händler im Ort, dazu Black-Week/Black-Friday-Seiten
### Behoben
- ALDI SÜD: Prospekt kommt direkt über prospekt.aldi-sued.de (Hauptseite blockte automatische Abrufe)
- Stichwörter ab 4 Buchstaben passen auch mitten im Wort („butter“ findet „Markenbutter“)

## 1.0.0 – 2026-11-16
### Neu
- Erste Version: Watchlist, mydealz-Feeds, Geizhals, Produktseiten, Shop-Quellen, ALDI-SÜD- und Lidl-Prospekte,
  PDF-Viewer, Texterkennung, umschaltbare KI-Auswertung, Windows-Oberfläche
