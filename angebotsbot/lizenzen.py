"""Lizenzhinweise für die mitgelieferten Bibliotheken (THIRD_PARTY_LICENSES.txt).

Beim Build: ``python -m angebotsbot.lizenzen dist/AngebotsBot/_internal/THIRD_PARTY_LICENSES.txt``.
Die Datei liegt bewusst in ``_internal``: Der Updater älterer Versionen nimmt im Update-Paket auf oberster
Ebene nur AngebotsBot.exe, _internal, README.md und CHANGELOG.md an.
Im Programm zeigt „Hilfe → Über / Lizenzen“ die mitgelieferte Datei, beim Start aus dem Quellcode wird der
Text aus den installierten Paketen erzeugt.
"""
from __future__ import annotations

import re
import sys
from importlib import metadata
from pathlib import Path

from . import APP_NAME, __version__

REPO = "https://github.com/Batlh/offerbot"
DATEI = "THIRD_PARTY_LICENSES.txt"

KOPF = f"""{APP_NAME} {__version__} – Lizenzhinweise
{'=' * 60}

Eigener Code: MIT-Lizenz, Copyright (c) Batlh. Quellcode: {REPO}

Die Windows-Version enthält Bibliotheken anderer Projekte. Sie stehen unter ihren eigenen Lizenzen,
die vollständigen Texte folgen unten.

Besondere Hinweise
------------------
- Qt / PySide6 (LGPL-3.0): Die Qt-Bibliotheken liegen als eigene Dateien im Ordner _internal und können
  durch eine andere, kompatible Version ersetzt werden. Quellcode von Qt: https://download.qt.io/ ,
  von PySide6: https://code.qt.io/cgit/pyside/pyside-setup.git/
- PDFium (über pypdfium2, Apache-2.0 / BSD-3-Clause) liest und erzeugt die Prospekt-PDFs.
- RapidOCR (Apache-2.0) mit den Texterkennungs-Modellen von PaddleOCR (Apache-2.0) über ONNX Runtime (MIT).
- Playwright (Apache-2.0) bringt einen eigenen Node.js-Laufzeitkern mit (MIT, https://nodejs.org/).
"""

_ANFORDERUNG = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_LIZENZDATEI = re.compile(r"(^|/)(LICEN[CS]E|COPYING|NOTICE|AUTHORS)[^/]*$|\.dist-info/licenses/.+", re.I)
VOLLTEXTE = Path(__file__).resolve().parent / "lizenztexte"  # SPDX-Texte für Pakete ohne eigene Lizenzdatei


def _name(anforderung: str) -> str | None:
    if ";" in anforderung and "extra ==" in anforderung.split(";", 1)[1]:
        return None  # optionale Zusätze nicht mitzählen
    if ";" in anforderung:
        try:
            from packaging.markers import Marker  # kommt mit pip/setuptools, nur hier gebraucht
            if not Marker(anforderung.split(";", 1)[1]).evaluate():
                return None
        except Exception:
            pass
    m = _ANFORDERUNG.match(anforderung)
    return m.group(1) if m else None


def pakete(requirements: Path | None = None) -> list[metadata.Distribution]:
    """Alle installierten Pakete aus requirements.txt samt ihrer Abhängigkeiten."""
    requirements = requirements or Path(__file__).resolve().parent.parent / "requirements.txt"
    offen = [n for n in (_name(z) for z in requirements.read_text(encoding="utf-8").splitlines()
                         if z.strip() and not z.lstrip().startswith("#")) if n]
    gefunden: dict[str, metadata.Distribution] = {}
    while offen:
        name = offen.pop()
        schluessel = re.sub(r"[-_.]+", "-", name).lower()
        if schluessel in gefunden:
            continue
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        gefunden[schluessel] = dist
        offen += [n for n in (_name(a) for a in dist.requires or []) if n]
    return sorted(gefunden.values(), key=lambda d: d.metadata["Name"].lower())


def _lizenz(dist: metadata.Distribution) -> str:
    md = dist.metadata
    if md.get("License-Expression"):
        return md["License-Expression"]
    klassen = [k.split("::")[-1].strip() for k in md.get_all("Classifier") or [] if k.startswith("License ::")]
    text = (md.get("License") or "").strip()
    if klassen:
        return ", ".join(klassen)
    return text.splitlines()[0][:120] if text else "siehe Lizenztext"


def erzeugen(requirements: Path | None = None) -> str:
    teile = [KOPF]
    eigene = Path(__file__).resolve().parent.parent / "LICENSE"
    if eigene.is_file():
        teile.append("Lizenz des eigenen Codes\n------------------------\n" + eigene.read_text(encoding="utf-8").strip())
    teile.append("\nÜbersicht\n---------")
    liste = pakete(requirements)
    for dist in liste:
        teile.append(f"- {dist.metadata['Name']} {dist.version}: {_lizenz(dist)}")
    for dist in liste:
        texte = []
        for datei in dist.files or []:
            if _LIZENZDATEI.search(str(datei).replace("\\", "/")):
                try:
                    texte.append(f"--- {datei.name} ---\n" + Path(datei.locate()).read_text(encoding="utf-8", errors="replace").strip())
                except OSError:
                    pass
        if not texte and (dist.metadata.get("License") or "").count("\n") > 2:
            texte.append(dist.metadata["License"].strip())
        kopf = f"{dist.metadata['Name']} {dist.version} – {_lizenz(dist)}"
        seite = dist.metadata.get("Home-page") or next(
            (u.split(",", 1)[1].strip() for u in dist.metadata.get_all("Project-URL") or [] if "," in u), "")
        ersatz = "(kein Lizenztext im Paket – Volltext der genannten Lizenz am Ende dieser Datei)"
        teile.append(f"\n\n{'=' * 60}\n{kopf}\n{seite}\n{'=' * 60}\n" + ("\n\n".join(texte) or ersatz))
    for datei in sorted(VOLLTEXTE.glob("*.txt")):
        teile.append(f"\n\n{'#' * 60}\nVolltext {datei.stem}\n{'#' * 60}\n" + datei.read_text(encoding="utf-8").strip())
    return "\n".join(teile) + "\n"


def text() -> str:
    """Mitgelieferte Datei (EXE) oder frisch erzeugt (Start aus dem Quellcode)."""
    basis = getattr(sys, "_MEIPASS", None)
    if basis and (Path(basis) / DATEI).is_file():
        return (Path(basis) / DATEI).read_text(encoding="utf-8")
    try:
        return erzeugen()
    except Exception as e:  # Hinweise sollen nie das Programm stören
        return KOPF + f"\n(Liste der Bibliotheken konnte nicht erzeugt werden: {e})\n"


if __name__ == "__main__":
    ziel = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(DATEI)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(erzeugen(), encoding="utf-8")
    print(f"{ziel} geschrieben ({len(pakete())} Pakete)")
