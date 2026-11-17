# Changelog

Alle Versionen des AngebotsBot (offerbot). Die neueste steht oben.
Jede Release auf GitHub enthält die fertige Windows-Version als ZIP (`AngebotsBot-windows.zip`).

## 1.10.0 – 2026-11-17
### Neu
- **Handy-App als Einkaufsliste**: Die Liste liegt jetzt auf dem Handy und funktioniert komplett ohne PC und WLAN.
  Ist ein PC verbunden, wird automatisch abgeglichen – Haken, neue und gelöschte Artikel gehen in beide Richtungen,
  die neuere Änderung gewinnt.
- Schnell eintragen unten in der Liste, mit Mengen: „2 Milch“, „500 g Hackfleisch“, „Milch 2x“
- Vorschläge aus früher eingetragenen Artikeln; die App merkt sich Kategorie und Laden pro Artikel
- Sortieren nach Kategorien (Weg durch den Supermarkt: Obst & Gemüse, Brot, Kühlregal, …) oder nach Läden
- Antippen = abhaken (rutscht nach unten „Im Wagen“), wischen = löschen mit „Rückgängig“, lange drücken = bearbeiten
- Mehrere Listen (z. B. Wocheneinkauf, Metro, Drogerie): anlegen, umbenennen, löschen, Artikel verschieben
- Liste per WhatsApp teilen oder als Text kopieren
- Einrichtung: „Ohne PC nutzen – nur Einkaufsliste“; verbinden geht später jederzeit über das Menü
- PC: Einkaufszettel mit mehreren Listen, eigene Artikel per Eingabefeld (auch mit Menge), gleicher Abgleich
### Geändert
- Telegram /zettel und „Aufs Handy schicken“ zeigen Mengen; Preise nur, wenn bekannt
- Handy-Schnittstelle Version 2 (`/api/zettel/sync`). Die neue App braucht den AngebotsBot ab 1.10 am PC.

## 1.9.0 – 2026-11-16
### Neu
- **Android-App (Begleit-App)**: `AngebotsBot.apk` in jeder Release. Treffer (mit Grundpreis und Preis-Check),
  Einkaufszettel zum Abhaken (geht auch offline mit dem letzten Stand), Watchlist bearbeiten, „Amazon prüfen“,
  Prospekte blättern und zoomen, Suche in allen Angeboten, „Jetzt prüfen“
- PC: Schnittstelle für die Handy-App (Einstellungen → Handy-App), nur mit Schlüssel, Einrichtung per QR-Code

## 1.8.0 – 2026-11-16
### Neu
- Discord: Benachrichtigungen per Webhook in einen eigenen Discord-Kanal (neue Treffer, Wochenbericht,
  Einkaufszettel) – zusätzlich zu ntfy/Telegram einschaltbar

## 1.7.1 – 2026-11-16
### Geändert
- Telegram: jeder richtet seinen eigenen Bot ein, der nur seinem Besitzer antwortet – Zugangscode und
  Abonnentenliste entfallen. Verbinden per Knopf „Mit Telegram verbinden“ und /start an den eigenen Bot.
### Planung
- Android: Begleit-App (A) ist geplant, eigenständige App (B) als mögliche Option vorgemerkt (docs/ANDROID.md)

## 1.7.0 – 2026-11-16
### Neu
- Eingebauter Telegram-Bot: antwortet auf /treffer, /zettel, /suche <Begriff>, /bericht, /pruefen, /stop
  (läuft, solange der AngebotsBot läuft – kein Server nötig)
- Mitmachen per `/start <Zugangscode>`; neue Treffer gehen an alle Angemeldeten, „Alle abmelden“ in den Einstellungen
- Handy-Benachrichtigung „beide“: ntfy und Telegram gleichzeitig

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
