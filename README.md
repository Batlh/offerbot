# offerbot – AngebotsBot

Prüft Deals (Black Friday / Blackweek, mydealz, Geizhals, Shops) und Wochenprospekte (ALDI, Lidl, eigene PDFs)
gegen deine Watchlist – mit Oberfläche, PDF-Viewer, Preisvergleich und Windows-Benachrichtigung.

## Fertige Version (ohne Python)

Unter **[Releases](https://github.com/Batlh/offerbot/releases)** liegt `AngebotsBot-windows.zip`: entpacken, `AngebotsBot.exe` starten – fertig.
Jede Änderung wird automatisch über GitHub Actions getestet, gebaut und als neue Release veröffentlicht –
mit den Neuerungen aus dem [CHANGELOG](CHANGELOG.md) und der Liste aller Änderungen seit der letzten Release.
Update: neue ZIP über die alte Version entpacken, den Ordner `data` behalten.
Windows-SmartScreen warnt beim ersten Start, weil die EXE nicht signiert ist: „Weitere Informationen“ → „Trotzdem ausführen“.

## Start aus dem Quellcode (einmalig)

1. **Python 3.12 oder 3.13** installieren: https://www.python.org/downloads/ – beim Setup **„Add python.exe to PATH“** anhaken.
2. Ordner entpacken, z. B. nach `C:\Users\<du>\Documents\AngebotsBot`.
3. **`setup.bat`** doppelklicken (installiert alles in einen eigenen Unterordner `.venv`, dauert ein paar Minuten).
4. **`start.bat`** startet das Programm.

Optional:
- `autostart_einrichten.bat` – startet AngebotsBot mit Windows, unsichtbar im Infobereich (neben der Uhr).
- `build_exe.bat` – baut eine eigenständige `AngebotsBot.exe` (danach braucht es kein Python mehr).
- `start_mit_konsole.bat` – wie start.bat, zeigt aber Fehlermeldungen an.

## So benutzt du ihn

1. **Watchlist**: Was du suchst. Name, Stichwörter, Höchstpreis, optional Mindest-Rabatt.
   Häkchen, ob gegen *Deals & Shops* und/oder *Prospekte* geprüft wird.
   Der Knopf **„Amazon prüfen“** sucht den Eintrag einmalig bei Amazon und zeigt Preise, Streichpreise,
   Grundpreise, Spar-Abo-Rabatte und Hinweise wie „Früher Black Friday“ direkt im Bot an (gesponserte Ergebnisse
   ausgeblendet).
   Das passiert nur auf Knopfdruck, nie automatisch. Zeigt Amazon ein Captcha, bricht der Bot ab.
   Der Knopf **„Im Browser ansehen“** öffnet die Suche nach dem Eintrag bei idealo, Geizhals, mydealz, Amazon
   oder kaufDA in deinem normalen Browser (Liste unter *Einstellungen* änderbar).
   Bei *Produkt-Links* kannst du konkrete Produktseiten eintragen – deren Preis wird bei jedem Lauf gelesen
   und als eigener Preisverlauf gespeichert (Rechtsklick auf einen Treffer → „Preisverlauf anzeigen“).
2. **Quellen**: Wo gesucht wird. Alles an/aus-schaltbar, eigenes Intervall je Quelle, **„Testen“** zeigt sofort,
   was erkannt wird, ohne etwas zu speichern. „Neue Quelle ▾“ legt weitere an.
3. **Treffer**: Alles, was zur Watchlist passt. Doppelklick öffnet den Deal bzw. die Prospektseite.
4. **Prospekte**: geladene/importierte PDFs, Viewer mit Markierung, Suche über alle Prospekte,
   Unter-Tab **Preisvergleich** (günstigster Händler je Watchlist-Eintrag, sortiert nach Grundpreis).
5. **Einkaufszettel**: Rechtsklick auf einen Treffer → „Auf den Einkaufszettel“. Nach Läden sortiert, abhaken,
   drucken oder aufs Handy schicken.

### Grundpreise und „Preis-Check“

Der Bot rechnet Angebote auf €/kg, €/l oder €/Stück um (aus dem angegebenen Grundpreis oder der Menge im Titel,
z. B. „4x12x85g“ oder „3 x 10 Liter“). Die Spalte **Preis-Check** zeigt, ob der Preis wirklich günstig ist:
verglichen mit dem tiefsten Preis der letzten 30 Tage, den der Bot für dasselbe Angebot kennt.
Rechtsklick → **Preisverlauf** zeigt dazu ein Diagramm.

### Handy und Wochenbericht

- *Einstellungen → Handy-Benachrichtigung*: **ntfy** (App „ntfy“ installieren, Thema abonnieren – ohne Konto)
  oder **Telegram** (eigener Bot). Neue Treffer, Wochenbericht und Einkaufszettel kommen dann aufs Handy.
- *Einstellungen → Wochenbericht*: z. B. jeden Montag ab 7 Uhr je Watchlist-Eintrag die drei günstigsten aktuellen
  Angebote und welcher Laden sich lohnt – als HTML, Markdown und CSV im Export-Ordner unter `Wochenberichte`.
  Oder jederzeit über den Knopf „Wochenbericht“ bei den Treffern.

### Stichwort-Regeln

| Eingabe | Bedeutung |
|---|---|
| `ssd 2tb` | beide Wörter müssen vorkommen |
| `sn850x\|"990 pro"` | eins von beiden (Wortgruppen in Anführungszeichen) |
| `-gebraucht` | darf nicht vorkommen |
| `butter` | Wörter ab 4 Buchstaben passen auch mitten im Wort (Markenbutter, Butterkeks) – mit `-keks` ausschließen |

Groß-/Kleinschreibung und Umlaute sind egal (`kuhlschrank` findet „Kühlschrank“).

## Mitgelieferte Quellen

| Quelle | Stand |
|---|---|
| mydealz Heiß / Neu / Gruppen / Gutscheine (RSS) | geprüft – Preis, Händler und Grad werden erkannt |
| Geizhals-Suche je Watchlist-Eintrag | Geizhals blockt automatische Abrufe teilweise (HTTP 403) – dann Quelle ausschalten |
| Produktseiten der Watchlist | erkennt den Preis bei den meisten Shops automatisch; Amazon blockt teils |
| Shop-Seite / Shop-Suche (CSS-Selektoren) | für beliebige Shops selbst einrichten |
| ALDI SÜD Prospekte (PDF) | über prospekt.aldi-sued.de (die Hauptseite blockt automatische Abrufe) |
| kaufDA – Angebote in deiner Region | Prospekt-Angebote aller Händler im eingestellten Ort, je Watchlist-Eintrag + Themen wie Black-Week |
| Lidl Prospekte (PDF + Produkte mit Preis) | geprüft; für Lidl Luxemburg Übersichtsseite von lidl.lu eintragen |
| Direkter PDF-Link | für Händler mit fester PDF-Adresse ({kw} = Kalenderwoche) |
| Kaufland | Prospekt-PDFs über filiale.kaufland.de |
| Lidl Luxemburg | Prospekt-PDFs über lidl.lu |
| ALDI Luxemburg | Wochen-Prospekt als PDF über folder.aldi.lu |
| Delhaize Luxemburg | Seiten und Text direkt aus dem Online-Prospekt |
| Bonial.fr – Frankreich | Carrefour, E.Leclerc, Auchan, Intermarché, Super U, Lidl/Aldi FR – für den Ort unter *Region → Ort Frankreich* (Standard Thionville), sonst landesweit. Französischer Suchtext je Watchlist-Eintrag im Feld „Suchtext FR“ |
| Cactus Luxemburg | Seitenbilder des neuesten Prospekts von Issuu, Text per Texterkennung |
| Auchan Luxemburg | Blätterkatalog (Flipsnack) wird im Browser-Modus Seite für Seite fotografiert und per Texterkennung gelesen – Quelle einschalten, sobald der Browser-Modus an ist |
| Metro | über kaufDA (Feld „Zusätzliche Händler bundesweit“ in der kaufDA-Quelle) |
| marktguru-Suche (Beta, Browser-Modus) | Lebensmittel-Angebote vieler Händler je Watchlist-Eintrag |
| idealo | Produktseiten-Links von idealo in der Watchlist eintragen (Feld „Produkt-Links“) – der Bot liest den Bestpreis und führt einen Preisverlauf. Eine idealo-Suche gibt es bewusst nicht: idealo verbietet automatischen Zugriff auf die Suche (robots.txt) |

**Prüfung (Captcha)?** Verlangt eine Seite „Bist du ein Mensch?“, fragt der Bot, ob er ein Browserfenster öffnen soll.
Du löst die Prüfung dort selbst, der Bot übernimmt danach die Freigabe (Cookies, mit Windows verschlüsselt gespeichert)
und holt die Daten. Läuft die Freigabe ab, fragt er erneut. Manuell: *Quellen → „Prüfung im Browser lösen“*.
Der Bot löst oder umgeht keine Prüfung selbst. Seiten, die automatische Abrufe grundsätzlich sperren (z. B. Geizhals
mit Fehler 403), bleiben gesperrt.

Bitte die Intervalle nicht zu klein machen (Standard 30 Minuten, Prospekte 12 Stunden) – das schont die Seiten
und verhindert Sperren.

## Browser-Modus

Manche Seiten (z. B. marktguru) zeigen ihre Angebote erst per JavaScript. Dafür gibt es den Browser-Modus:
in den *Einstellungen* den Haken setzen – der Rest passiert automatisch. Es wird dein installiertes
Microsoft Edge unsichtbar benutzt; nur falls das nicht klappt, wird einmalig Chromium (ca. 150 MB) in den
Datenordner geladen.

## Region

Unter *Einstellungen → Region* Ort und PLZ eintragen (Standard: Trier, 54290). kaufDA zeigt dann die Angebote
der Händler in deinem Ort. In eigenen Quellen-URLs kannst du `{ort}` und `{plz}` als Platzhalter verwenden.
kaufDA hat nur für bekannte Begriffe eigene Seiten – am besten einfache Suchtexte wie „Butter“, „Kaffeebohnen“,
„Fernseher“. Welche Begriffe keine Seite haben, steht im Protokoll.

## KI (umschaltbar)

Standard ist **aus**: Prospekte werden lokal per Texterkennung (OCR) durchsucht, Preise werden geraten
(bitte im Viewer prüfen). Unter *Einstellungen → Prospekte & KI* kannst du **Claude** oder **OpenAI** einschalten;
dann werden Prospektseiten als Bild an die KI geschickt und alle Angebote sauber erkannt
(Produkt, Preis, Streichpreis, Grundpreis, Hinweise wie „nur mit App“). Standardmäßig nur Seiten mit
Watchlist-Treffern, damit es günstig bleibt. API-Schlüssel werden im Windows-Anmeldeinformations-Tresor gespeichert.

## Fehlersuche

Im Tab **Protokoll**: „Log-Ordner öffnen“ und „Debug-Paket erstellen“ (ZIP mit Logs, Absturzberichten,
Quellenstatus und Konfiguration – ohne Passwörter, Schlüssel und ntfy-Thema). Für ausführliche Logs
*Einstellungen → Fehlersuche → Debug-Modus* einschalten: dann steht jede Anfrage mit Statuscode und Dauer im Log.
Abstürze landen zusätzlich als `absturz_….txt` im Log-Ordner.

## Daten

Alles liegt im Ordner `data` neben dem Programm: `config.json` (Watchlist, Quellen, Einstellungen),
`angebote.db` (Angebote, Treffer, Preisverlauf) und `prospekte\` (PDFs). Zum Sichern einfach den Ordner kopieren.
Export als CSV (Excel) und HTML über „Exportieren …“ oder automatisch nach jedem Lauf in einen Ordner deiner Wahl.

## Aufbau (für die spätere Handy-Version)

- `angebotsbot/core` – die komplette Logik ohne Oberfläche (Quellen, Abgleich, Prospekte, KI, Datenbank)
- `angebotsbot/gui` – die Windows-Oberfläche (PySide6)

Eine Android-Version braucht nur eine neue Oberfläche, die `core.engine.Engine` aufruft.
Tests: `python -m pytest tests`.

## Lizenz

MIT – siehe [LICENSE](LICENSE).
