import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models.dart';

/// Woher die App ihre Daten bekommt.
///
/// Heute: [PcSource] (der AngebotsBot auf dem PC im WLAN).
/// Option B (eventuell geplant, docs/ANDROID.md): eine eigene Quelle direkt auf dem Handy,
/// die dieselbe Schnittstelle erfüllt – die Seiten der App bleiben dann gleich.
abstract class DataSource {
  Future<Status> status();
  Future<List<Offer>> treffer({bool nurUngelesen = false});
  Future<void> gelesen(List<String> uids, {bool alle = false});
  Future<List<Offer>> suche(String text);
  Future<List<ShopItem>> zettel();
  Future<void> zettelHinzufuegen({String? uid, String? titel});
  Future<void> zettelErledigt(int id, bool erledigt);
  Future<void> zettelLoeschen(int id);
  Future<List<WatchEntry>> watchlist();
  Future<WatchEntry> watchSpeichern(WatchEntry w);
  Future<void> watchLoeschen(String id);
  Future<List<Prospekt>> prospekte();
  String seitenBild(int prospektId, int seite);
  Map<String, String> get bildHeader;
  Future<void> pruefen();
  Future<List<Offer>> amazon(String watchId);
}

class SourceException implements Exception {
  final String message;
  const SourceException(this.message);
  @override
  String toString() => message;
}

class PcSource implements DataSource {
  final Connection con;
  final http.Client client;

  PcSource(this.con, {http.Client? client}) : client = client ?? http.Client();

  @override
  Map<String, String> get bildHeader => {'X-Key': con.key};

  Uri _u(String path, [Map<String, String>? q]) {
    final base = Uri.parse(con.url);
    return base.replace(path: path, queryParameters: q);
  }

  Future<Map<String, dynamic>> _req(String method, String path,
      {Map<String, String>? q, Object? body, Duration timeout = const Duration(seconds: 15)}) async {
    final headers = {'X-Key': con.key, 'Content-Type': 'application/json'};
    late http.Response r;
    try {
      final uri = _u(path, q);
      final data = body == null ? null : jsonEncode(body);
      switch (method) {
        case 'POST':
          r = await client.post(uri, headers: headers, body: data ?? '{}').timeout(timeout);
        case 'DELETE':
          r = await client.delete(uri, headers: headers).timeout(timeout);
        default:
          r = await client.get(uri, headers: headers).timeout(timeout);
      }
    } catch (e) {
      throw const SourceException('PC nicht erreichbar – läuft der AngebotsBot und bist du im selben WLAN?');
    }
    if (r.statusCode == 401) throw const SourceException('Schlüssel passt nicht – bitte neu verbinden (QR-Code)');
    if (r.statusCode >= 400) {
      throw SourceException('Fehler vom PC (${r.statusCode})');
    }
    return jsonDecode(utf8.decode(r.bodyBytes)) as Map<String, dynamic>;
  }

  List<Map<String, dynamic>> _items(Map<String, dynamic> j) =>
      ((j['items'] as List?) ?? const []).cast<Map<String, dynamic>>();

  @override
  Future<Status> status() async => Status.fromJson(await _req('GET', '/api/status'));

  @override
  Future<List<Offer>> treffer({bool nurUngelesen = false}) async =>
      _items(await _req('GET', '/api/treffer', q: nurUngelesen ? {'ungelesen': '1'} : null))
          .map(Offer.fromJson)
          .toList();

  @override
  Future<void> gelesen(List<String> uids, {bool alle = false}) =>
      _req('POST', '/api/treffer/gelesen', body: {'uids': uids, 'alle': alle});

  @override
  Future<List<Offer>> suche(String text) async =>
      _items(await _req('GET', '/api/suche', q: {'q': text})).map(Offer.fromJson).toList();

  @override
  Future<List<ShopItem>> zettel() async =>
      _items(await _req('GET', '/api/zettel')).map(ShopItem.fromJson).toList();

  @override
  Future<void> zettelHinzufuegen({String? uid, String? titel}) =>
      _req('POST', '/api/zettel', body: uid != null ? {'uid': uid} : {'title': titel ?? ''});

  @override
  Future<void> zettelErledigt(int id, bool erledigt) =>
      _req('POST', '/api/zettel/$id/erledigt', body: {'done': erledigt});

  @override
  Future<void> zettelLoeschen(int id) => _req('DELETE', '/api/zettel/$id');

  @override
  Future<List<WatchEntry>> watchlist() async =>
      _items(await _req('GET', '/api/watchlist')).map(WatchEntry.fromJson).toList();

  @override
  Future<WatchEntry> watchSpeichern(WatchEntry w) async {
    final j = await _req('POST', '/api/watchlist', body: w.toJson());
    if (j['ok'] != true) throw SourceException(j['error']?.toString() ?? 'Speichern fehlgeschlagen');
    return WatchEntry.fromJson(j['item'] as Map<String, dynamic>);
  }

  @override
  Future<void> watchLoeschen(String id) => _req('DELETE', '/api/watchlist/$id');

  @override
  Future<List<Prospekt>> prospekte() async =>
      _items(await _req('GET', '/api/prospekte')).map(Prospekt.fromJson).toList();

  @override
  String seitenBild(int prospektId, int seite) => _u('/api/prospekt/$prospektId/seite/$seite.jpg').toString();

  @override
  Future<void> pruefen() => _req('POST', '/api/pruefen');

  @override
  Future<List<Offer>> amazon(String watchId) async =>
      _items(await _req('POST', '/api/amazon/$watchId', timeout: const Duration(seconds: 90)))
          .map(Offer.fromJson)
          .toList();
}
