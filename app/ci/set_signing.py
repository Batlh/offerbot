#!/usr/bin/env python3
"""Trägt den Release-Signierschlüssel in die von Flutter erzeugte Gradle-Datei ein.

Der Schlüssel liegt NICHT im Repo. Die CI schreibt ihn aus dem Secret SIGNING_STORE_B64 nach
$RUNNER_TEMP und übergibt Pfad und Passwort per Umgebung (OB_KEYSTORE, OB_KEYSTORE_PW, OB_KEY_ALIAS).
Ohne diese Variablen (lokaler Build) wird der Debug-Schlüssel von Android genommen – solche APKs lassen
sich nicht über die echte App installieren.
"""
import sys

path = sys.argv[1]
text = open(path, encoding="utf-8").read()
config = """    signingConfigs {
        create("fest") {
            storeFile = file(System.getenv("OB_KEYSTORE") ?: "kein-schluessel.jks")
            storePassword = System.getenv("OB_KEYSTORE_PW") ?: ""
            keyAlias = System.getenv("OB_KEY_ALIAS") ?: "offerbot"
            keyPassword = System.getenv("OB_KEYSTORE_PW") ?: ""
        }
    }

    buildTypes {"""
if 'create("fest")' not in text:
    assert "    buildTypes {" in text, "buildTypes nicht gefunden"
    assert 'signingConfigs.getByName("debug")' in text, "Signatur nicht gefunden"
    text = text.replace("    buildTypes {", config, 1)
    text = text.replace('signingConfigs.getByName("debug")',
                        'signingConfigs.getByName(if (System.getenv("OB_KEYSTORE") != null) "fest" else "debug")')
    open(path, "w", encoding="utf-8").write(text)
