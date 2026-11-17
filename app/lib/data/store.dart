import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models.dart';

/// Lokaler Speicher: Verbindung zum PC und letzter Stand für unterwegs (ohne WLAN).
/// Der Einkaufszettel speichert sich selbst (data/zettel.dart).
class Store {
  static const _kUrl = 'pc_url', _kKey = 'pc_key', _kTreffer = 'cache_treffer', _kOhnePc = 'ohne_pc';

  final SharedPreferences prefs;
  Store(this.prefs);

  static Future<Store> open() async => Store(await SharedPreferences.getInstance());

  Connection? get connection {
    final u = prefs.getString(_kUrl), k = prefs.getString(_kKey);
    if (u == null || k == null) return null;
    final c = Connection(u, k);
    return c.isValid ? c : null;
  }

  Future<void> saveConnection(Connection c) async {
    await prefs.setString(_kUrl, c.url);
    await prefs.setString(_kKey, c.key);
  }

  Future<void> clearConnection() async {
    await prefs.remove(_kUrl);
    await prefs.remove(_kKey);
  }

  /// App wird ohne PC genutzt (nur Einkaufszettel).
  bool get ohnePc => prefs.getBool(_kOhnePc) ?? false;

  Future<void> setOhnePc(bool v) => prefs.setBool(_kOhnePc, v);

  List<Map<String, dynamic>> get cachedTrefferJson {
    final raw = prefs.getString(_kTreffer);
    if (raw == null) return [];
    return (jsonDecode(raw) as List).cast<Map<String, dynamic>>();
  }

  Future<void> cacheTrefferJson(List<Map<String, dynamic>> items) => prefs.setString(_kTreffer, jsonEncode(items));
}
