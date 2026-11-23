"""Aktualisierung der portablen Windows-Ausgabe aus dem offiziellen GitHub-Release."""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PureWindowsPath
from zipfile import ZipFile

import requests

from .. import __version__

REPO = "https://github.com/Batlh/offerbot"
LATEST = "https://api.github.com/repos/Batlh/offerbot/releases/latest"
ASSET = "AngebotsBot-windows.zip"
FILES = {"AngebotsBot.exe", "_internal", "README.md", "CHANGELOG.md"}


def update_asset(release, installed):
    tag = release.get("tag_name", "")
    if release.get("draft") or release.get("prerelease") or not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        return None
    if tuple(map(int, tag[1:].split("."))) <= tuple(map(int, installed.split("."))):
        return None
    for asset in release.get("assets", []):
        if asset.get("name") == ASSET and asset.get("state") == "uploaded":
            if (asset.get("browser_download_url") != f"{REPO}/releases/download/{tag}/{ASSET}"
                    or not re.fullmatch(r"sha256:[0-9a-f]{64}", asset.get("digest") or "")
                    or not isinstance(asset.get("size"), int) or asset["size"] <= 0):
                raise ValueError("Release-Datei oder SHA-256-Prüfsumme ungültig.")
            return tag, asset
    raise ValueError("Das Windows-Paket ist noch nicht veröffentlicht.")


def unpack(archive, stage):
    with ZipFile(archive) as package:
        for member in package.infolist():
            path = PureWindowsPath(member.filename)
            parts = path.parts
            if parts == ("AngebotsBot",) and member.filename.endswith(("/", chr(92))):
                continue
            if (len(parts) < 2 or parts[0] != "AngebotsBot" or parts[1] not in FILES
                    or any(p in (".", "..") or p.endswith((".", " ")) or ":" in p or PureWindowsPath(p).is_reserved()
                           for p in parts)
                    or (len(parts) > 2 and parts[1] != "_internal")):
                raise ValueError("Unerwarteter Pfad im Update-Paket.")
            target = stage.joinpath(*parts)
            if member.is_dir() or member.filename.endswith(chr(92)):
                target.mkdir(exist_ok=True, parents=True)
            else:
                target.parent.mkdir(exist_ok=True, parents=True)
                with package.open(member) as src, target.open("xb") as dest:
                    shutil.copyfileobj(src, dest)
    root = stage / "AngebotsBot"
    if not (root / "AngebotsBot.exe").is_file() or not (root / "_internal").is_dir():
        raise ValueError("Das Update-Paket ist unvollständig.")


def prepare(root, cancelled):
    response = requests.get(LATEST, timeout=(10, 30))
    response.raise_for_status()
    newer = update_asset(response.json(), __version__)
    if not newer or cancelled():
        return None
    tag, asset = newer
    stage = Path(tempfile.mkdtemp(prefix=".offerbot-update-", dir=root))
    try:
        archive = stage / "download.zip"
        digest = hashlib.sha256()
        with requests.get(asset["browser_download_url"], stream=True, timeout=(10, 45)) as stream:
            stream.raise_for_status()
            with archive.open("xb") as dest:
                for block in stream.iter_content(1024 * 1024):
                    if cancelled():
                        raise InterruptedError("Update unterbrochen.")
                    dest.write(block)
                    digest.update(block)
        if archive.stat().st_size != asset["size"] or "sha256:" + digest.hexdigest() != asset["digest"]:
            raise ValueError("Prüfsumme oder Dateigröße des Updates stimmt nicht.")
        with (root / "AngebotsBot.exe").open("rb") as current:
            original = hashlib.file_digest(current, "sha256").hexdigest()
        (stage / "installiert.sha256").write_text(original, encoding="ascii")
        unpack(archive, stage)
        archive.unlink()
        shutil.copyfile(Path(__file__).with_name("install_update.ps1"), stage / "install_update.ps1")
        return tag, stage
    except Exception:
        shutil.rmtree(stage)
        raise


def install(stage, restart=False):
    root = Path(sys.executable).resolve().parent
    if stage.resolve().parent != root or not stage.name.startswith(".offerbot-update-"):
        raise ValueError("Unerwarteter Update-Ordner.")
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    args = [str(powershell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
            "-File", str(stage / "install_update.ps1"), "-AppPid", str(os.getpid())]
    if restart:
        args.append("-Restart")
    subprocess.Popen(args, cwd=root, creationflags=subprocess.CREATE_NO_WINDOW)
