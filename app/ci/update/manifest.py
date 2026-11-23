"""Installationsrechte und Rückmeldung der Systeminstallation ins Flutter-Manifest einsetzen."""
from pathlib import Path
from xml.etree import ElementTree as ET

ns = "http://schemas.android.com/apk/res/android"
ET.register_namespace("android", ns)
a = "{" + ns + "}"
path = Path("android/app/src/main/AndroidManifest.xml")
tree = ET.parse(path)
root = tree.getroot()
for permission in ("android.permission.REQUEST_INSTALL_PACKAGES", "android.permission.UPDATE_PACKAGES_WITHOUT_USER_ACTION"):
    if not any(node.get(a + "name") == permission for node in root.findall("uses-permission")):
        root.insert(0, ET.Element("uses-permission", {a + "name": permission}))
app = root.find("application")
receiver = "io.github.batlh.offerbot.UpdateResult"
if not any(node.get(a + "name") == receiver for node in app.findall("receiver")):
    ET.SubElement(app, "receiver", {a + "name": receiver, a + "exported": "false"})
tree.write(path, encoding="utf-8", xml_declaration=True)
