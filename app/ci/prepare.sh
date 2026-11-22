#!/usr/bin/env bash
# Erzeugt den Android-Ordner, setzt App-Namen, Rechte und die feste Signatur (Vorlage: casino-app).
set -euo pipefail
cd "$(dirname "$0")/.."
flutter create --project-name offerbot --org io.github.batlh --platforms=android .
rm -f test/widget_test.dart  # Beispieltest von flutter create, passt nicht zur App
flutter pub get
RES=android/app/src/main/res
mkdir -p "$RES/drawable" "$RES/mipmap-anydpi-v21" "$RES/mipmap-anydpi-v26" "$RES/values"
cp ci/icon/offer_tag.xml "$RES/drawable/offer_tag.xml"
cp ci/icon/offer_tag.xml "$RES/mipmap-anydpi-v21/ic_launcher.xml"
cp ci/icon/ic_launcher.xml "$RES/mipmap-anydpi-v26/ic_launcher.xml"
echo '<resources><color name="offer_background">#BF4120</color></resources>' > "$RES/values/offer_background.xml"
MAN=android/app/src/main/AndroidManifest.xml
# Name, Internet im Release (flutter create setzt es nur für Debug) und unverschlüsseltes HTTP im eigenen WLAN
sed -i "s/android:label=\"[^\"]*\"/android:label=\"AngebotsBot\" android:usesCleartextTraffic=\"true\"/" "$MAN"
grep -q 'android.permission.INTERNET' "$MAN" || \
  sed -i 's#<manifest xmlns:android="http://schemas.android.com/apk/res/android">#<manifest xmlns:android="http://schemas.android.com/apk/res/android">\n    <uses-permission android:name="android.permission.INTERNET"/>\n    <uses-permission android:name="android.permission.CAMERA"/>#' "$MAN"
python3 ci/set_signing.py android/app/build.gradle.kts
if [ -f android/build.gradle.kts ] && ! grep -q 'lintVital' android/build.gradle.kts; then
  cat >> android/build.gradle.kts <<'EOT'

subprojects {
    tasks.matching { it.name.startsWith("lintVital") }.configureEach { enabled = false }
}
EOT
fi
cat "$MAN"
