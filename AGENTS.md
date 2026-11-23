# Briefing für KI-Assistenten (GPT/Codex, Claude)

Stand: 23.11.2026, Version 1.10.7. Kurz und verbindlich – bitte vor jeder Arbeit lesen.

## Arbeitsweise (Vorgaben des Nutzers)

- **Sprache:** Antworten, Doku, Oberfläche, Commit-Texte auf **Deutsch**. Nicht zwischendurch ins Englische wechseln.
- **Kontingent:** Vor jedem größeren Schritt das eigene Kontingent prüfen. Wird es knapp: `docs/CHECKPOINT.md`
  anlegen mit allem Erledigten und Offenen (Dateien, nächste Schritte), committen und auf Hold gehen.
- **Commits:** Autor und Committer `Batlh <Batlh@users.noreply.github.com>`. **Keine** Sitzungs-/Chat-URLs oder
  Chat-IDs in Commits, Code oder Doku. Bestehende Commits nicht umschreiben.
- **Einwände** sind erwünscht, aber in Maßen. Bei Unklarheit lieber kurz fragen als groß umbauen.

## Release-Regeln

Jeder Push auf `main` (außer reine Doku: `docs/**`, `**.md`) baut über GitHub Actions
(`.github/workflows/windows-build.yml`) die Windows-EXE **und** die Android-APK und legt eine **neue Release** an.
Deshalb bei Code-Änderungen immer:

1. Version erhöhen in `angebotsbot/__init__.py` **und** `app/pubspec.yaml` (gleiche Nummer).
2. Abschnitt in `CHANGELOG.md` (Neu / Geändert / Behoben) – daraus entsteht der Release-Text.
3. Tests grün: `python -m pytest tests` (Python) – Flutter-Analyse und -Tests laufen in der CI.
4. Nach dem Push prüfen, ob der Build grün ist und die Release beide Dateien hat
   (`AngebotsBot-windows.zip`, `AngebotsBot.apk`).

## Grenzen (nicht verhandelbar)

- `robots.txt` und Sperren (403/429) respektieren. Keine Captcha-Umgehung, keine gefälschten Browser-Kennungen
  zum Austricksen von Schutzsystemen, keine API-Schlüssel aus fremden Apps/Seiten ziehen.
- Captchas löst **der Nutzer selbst** im sichtbaren Browserfenster (`core/assist.py`), der Bot nutzt danach
  dessen Cookies. Amazon nur auf Knopfdruck („Amazon prüfen“), nicht automatisch.
- Geheimnisse (API-Schlüssel, Telegram-Token, Discord-Webhook) nur im Windows-Tresor (`keyring`) bzw.
  verschlüsselt – nie in `config.json`, Logs, Tests oder Repo. Debug-Paket schwärzt sie (`core/logsetup.py`).
- Telegram: jeder Nutzer richtet seinen **eigenen** Bot ein (Besitzer-Kopplung), keine gemeinsame Konfiguration.

## Aufbau

```
angebotsbot/core/     Logik ohne Oberfläche (wiederverwendbar)
  engine.py           Lauf: Quellen abrufen → abgleichen (matcher.py) → Prospekte (prospekte/) → Ergebnis
  sources/            Quellentypen mit Registry (base.py: FieldSpec → Formular in der GUI); kaufda.py, rss.py …
  prospekte/          Prospekt-Abrufer (Schwarz/Lidl+Kaufland, Publitas, iPaper, FlipBuilder, Issuu, Screens),
                      pdftext.py (Text/OCR), analyze.py (Treffer, KI)
  db.py               SQLite: offers, matches, price_history, prospekte, shopping (mit Handy-Abgleich)
  net.py              Abruf mit Pausen je Seite, Browser-Modus (Playwright), Fehler/Prüfung erkennen
  browser_setup.py    Browser einrichten (Edge bevorzugt, sonst Chromium-Download), launch() repariert sich selbst
  api.py              HTTP-Schnittstelle für die Handy-App (Schlüssel per QR-Code), API_VERSION = 2
  notify.py, telegram_bot.py   ntfy / Telegram / Discord
  config.py           Einstellungen + Migrationen (settings["migrations"]) – neue Standards immer per Migration
angebotsbot/gui/      PySide6-Oberfläche, je Tab eine Datei; main_window.py verbindet alles
app/                  Flutter-Begleit-App (Android): lib/data/source.dart (DataSource/PcSource),
                      lib/data/zettel.dart (Einkaufsliste, Abgleich), lib/pages/*
tests/                pytest mit Fixtures echter Seitenstrukturen (tests/fixtures)
docs/ANDROID.md       Stand und Plan der App · docs/TODO.md  offene Punkte
```

Daten liegen im Ordner `data/` neben der EXE (nie committen).

## Technische Hinweise

- Python 3.12, PySide6. Lokal: `pip install -r requirements.txt`, Start `python main.py`.
- Flutter muss lokal nicht vorhanden sein – die CI (`app/ci/prepare.sh`) erzeugt den Android-Rahmen.
  Signatur: fester Schlüssel `app/ci/offerbot.keystore`, damit Updates über die installierte App gehen.
- Einkaufsliste: Einträge haben eine feste `sid` („o:<Angebot>“ / „f:<Zufall>“) und `updated` (UTC);
  beim Abgleich gewinnt die neuere Änderung, Löschen = Grabstein (`deleted`). PC und App gleich halten
  (`db.shopping_sync` ↔ `ZettelRepo.merge`), auch die Mengen-Erkennung (`units.split_quantity` ↔ `splitQuantity`).
- Android-Paketname: `io.github.batlh.offerbot`.
- Region-Platzhalter in Quellen: `{ort}`, `{plz}`, `{kaufda}` (Standard Trier/54290, Frankreich Thionville).

## Offene Punkte

Die bearbeiteten Punkte zu Hilfe, kaufDA und APIs stehen in `docs/TODO.md`. Weitere Aufgaben siehe
`docs/ANDROID.md` (Praxistests auf dem Handy und optionale eigenständige App). Ergänzend:

- mydealz-RSS ist **schon** als Quelle drin (`core/sources/rss.py`) – TODO-Punkt dazu nur noch auf Filter prüfen.
- Echte Tests auf dem Handy und an allen Quellen auf dem PC des Nutzers stehen noch aus.
