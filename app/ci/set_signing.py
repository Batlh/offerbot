#!/usr/bin/env python3
"""Trägt den festen Signierschlüssel (ci/offerbot.keystore) in die von Flutter erzeugte Gradle-Datei ein.

Ohne feste Signatur bekäme jede APK einen neuen Schlüssel und Updates über die alte App würden scheitern.
Der Schlüssel liegt bewusst offen im Repo (private App, kein Store) – siehe docs/ANDROID.md.
"""
import sys

path = sys.argv[1]
text = open(path, encoding="utf-8").read()
config = """    signingConfigs {
        create("fest") {
            storeFile = file("../../ci/offerbot.keystore")
            storePassword = "angebotsbot"
            keyAlias = "angebotsbot"
            keyPassword = "angebotsbot"
        }
    }

    buildTypes {"""
if 'create("fest")' not in text:
    assert "    buildTypes {" in text, "buildTypes nicht gefunden"
    assert 'signingConfigs.getByName("debug")' in text, "Signatur nicht gefunden"
    text = text.replace("    buildTypes {", config, 1)
    text = text.replace('signingConfigs.getByName("debug")', 'signingConfigs.getByName("fest")')
    open(path, "w", encoding="utf-8").write(text)
