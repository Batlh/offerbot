"""Versionsvergleich, Integrität und Austausch der portablen Ausgabe."""
import hashlib
import subprocess
import sys
from io import BytesIO
from zipfile import ZipFile

import pytest

from angebotsbot.core import updates


def release(archive=b""):
    return {"tag_name": "v1.11.0", "assets": [{
        "name": updates.ASSET, "state": "uploaded", "size": len(archive),
        "digest": "sha256:" + hashlib.sha256(archive).hexdigest(),
        "browser_download_url": f"{updates.REPO}/releases/download/v1.11.0/{updates.ASSET}",
    }]}


def test_nur_neuere_stabile_originalpakete():
    meta = release(b"zip")
    assert updates.update_asset(meta, "1.9.9")[0] == "v1.11.0"
    assert not updates.update_asset(meta, "1.11.0")
    assert not updates.update_asset(dict(meta, prerelease=True), "1.0.0")
    meta["assets"][0]["digest"] = ""
    with pytest.raises(ValueError):
        updates.update_asset(meta, "1.0.0")


@pytest.mark.parametrize("entry", ["../a.exe", "AngebotsBot/data/config.json", "AngebotsBot/_internal/../../a.exe",
                                    "AngebotsBot/_internal/config:stream", "AngebotsBot/_internal/CON"])
def test_paket_schuetzt_daten_und_pfade(tmp_path, entry):
    archive = tmp_path / "test.zip"
    with ZipFile(archive, "w") as z:
        z.writestr(entry, b"x")
    with pytest.raises(ValueError):
        updates.unpack(archive, tmp_path / "stage")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-Hilfsprogramm")
def test_windows_update_behaelt_benutzerdaten(tmp_path, monkeypatch):
    buffer = BytesIO()
    with ZipFile(buffer, "w") as z:
        z.writestr("AngebotsBot/AngebotsBot.exe", "neu")
        z.writestr("AngebotsBot/_internal/lib", "neu")
    archive = buffer.getvalue()
    meta = release(archive)

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def json(self):
            return meta
        def raise_for_status(self):
            pass
        def iter_content(self, size):
            yield archive

    monkeypatch.setattr(updates.requests, "get", lambda *args, **kwargs: Response())
    monkeypatch.setattr(updates, "__version__", "1.10.6")
    root = tmp_path / "Mein Angebots Bot"
    root.mkdir()
    (root / "AngebotsBot.exe").write_text("alt")
    (root / "_internal").mkdir()
    (root / "_internal/alt").touch()
    (root / "data").mkdir()
    (root / "data/config.json").write_text("behalten")
    (root / "eigene-datei.txt").write_text("behalten")
    tag, stage = updates.prepare(root, lambda: False)
    assert tag == "v1.11.0"
    # Ein bereits beendeter Prozess statt der laufenden Testsitzung.
    parent = subprocess.Popen([sys.executable, "-c", "pass"])
    parent.wait()
    subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                    str(stage / "install_update.ps1"), "-AppPid", str(parent.pid)], check=True, timeout=30)
    assert (root / "AngebotsBot.exe").read_text() == "neu"
    assert (root / "_internal/lib").read_text() == "neu"
    assert not (root / "_internal/alt").exists()
    assert (root / "data/config.json").read_text() == "behalten"
    assert (root / "eigene-datei.txt").read_text() == "behalten"
    assert not stage.exists()
