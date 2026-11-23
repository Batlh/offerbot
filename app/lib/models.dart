// Datenmodelle der App – entsprechen den JSON-Antworten des PC-Bots (angebotsbot/core/api.py).

double? _d(dynamic v) => v == null ? null : (v as num).toDouble();
String _s(dynamic v) => v == null ? '' : v.toString();

String euro(double? v) {
  if (v == null) return '';
  final s = v.toStringAsFixed(2).replaceAll('.', ',');
  return '$s €';
}

class Offer {
  final String uid;
  final String title;
  final double? price;
  final double? oldPrice;
  final double? refPrice;
  final String merchant;
  final String kind;
  final String url;
  final int? prospektId;
  final int? page;
  final String base;
  final String unitPrice;
  final String expires;
  final String validFrom;
  final String validTo;
  final String info;
  final String source;
  final String watchName;
  final bool seen;
  final bool hit;

  const Offer({
    required this.uid,
    required this.title,
    this.price,
    this.oldPrice,
    this.refPrice,
    this.merchant = '',
    this.kind = '',
    this.url = '',
    this.prospektId,
    this.page,
    this.base = '',
    this.unitPrice = '',
    this.expires = '',
    this.validFrom = '',
    this.validTo = '',
    this.info = '',
    this.source = '',
    this.watchName = '',
    this.seen = true,
    this.hit = false,
  });

  factory Offer.fromJson(Map<String, dynamic> j) => Offer(
        uid: _s(j['uid']),
        title: _s(j['title']),
        price: _d(j['price']),
        oldPrice: _d(j['old_price']),
        refPrice: _d(j['ref_price']),
        merchant: _s(j['merchant']),
        kind: _s(j['kind']),
        url: _s(j['url']),
        prospektId: j['prospekt_id'] as int?,
        page: j['page'] as int?,
        base: _s(j['base']),
        unitPrice: _s(j['unit_price']),
        expires: _s(j['expires']),
        validFrom: _s(j['valid_from']),
        validTo: _s(j['valid_to']),
        info: _s(j['info']),
        source: _s(j['source']),
        watchName: _s(j['watch_name']),
        seen: j['seen'] != false,
        hit: j['hit'] == true,
      );

  Map<String, dynamic> toJson() => {
    'uid': uid, 'title': title, 'price': price, 'old_price': oldPrice, 'ref_price': refPrice,
    'merchant': merchant, 'kind': kind, 'url': url, 'prospekt_id': prospektId, 'page': page,
    'expires': expires, 'base': base, 'unit_price': unitPrice, 'valid_from': validFrom, 'valid_to': validTo,
    'info': info, 'source': source, 'watch_name': watchName, 'seen': seen, 'hit': hit,
  };

  /// Grundpreis zum Anzeigen: berechnet, sonst Angabe aus dem Prospekt.
  String get baseText => base.isNotEmpty ? base : unitPrice;

  String get validText {
    if (validFrom.isNotEmpty && validTo.isNotEmpty) return '$validFrom – $validTo';
    if (validTo.isNotEmpty) return 'bis $validTo';
    return validFrom;
  }

  /// „Preis-Check“ wie am PC: Vergleich mit dem bisherigen 30-Tage-Tiefstpreis.
  String get priceCheck {
    final p = price, r = refPrice;
    if (p == null || r == null || r <= 0) return '';
    if (p < r - 0.005) return '✔ ${((1 - p / r) * 100).round()} % unter bisher';
    if ((p - r).abs() < 0.005) return '✔ gleich Tiefstpreis';
    return '✘ ${((p / r - 1) * 100).round()} % über 30-T.-Tief';
  }
}

/// Name der Standardliste (am PC: leeres Feld „liste“).
const defaultList = 'Einkaufszettel';

final _numOnly = RegExp(r'^\d+([.,]\d+)?$');

/// Ein Eintrag auf einem Einkaufszettel. Liegt auf dem Handy und wird mit dem PC abgeglichen:
/// [sid] ist auf beiden Seiten gleich, [updated] entscheidet („neuere Änderung gewinnt“),
/// [deleted] merkt sich das Löschen, damit die andere Seite es mitbekommt.
class ShopItem {
  final String sid;
  final String title;
  final String qty;
  final String category;
  final String liste;
  final double? price;
  final String merchant;
  final String base;
  final String validTo;
  final String url;
  final bool done;
  final bool deleted;
  final DateTime updated;

  ShopItem({
    required this.sid,
    required this.title,
    this.qty = '',
    this.category = '',
    this.liste = defaultList,
    this.price,
    this.merchant = '',
    this.base = '',
    this.validTo = '',
    this.url = '',
    this.done = false,
    this.deleted = false,
    DateTime? updated,
  }) : updated = updated ?? DateTime.fromMillisecondsSinceEpoch(0, isUtc: true);

  /// „2× Milch“ bzw. „500 g Hackfleisch“.
  String get text {
    if (qty.isEmpty) return title;
    return _numOnly.hasMatch(qty) ? '$qty× $title' : '$qty $title';
  }

  /// Laden zum Sortieren; ohne Angabe „Sonstige“.
  String get shop => merchant.isEmpty ? 'Sonstige' : merchant;

  factory ShopItem.fromJson(Map<String, dynamic> j) => ShopItem(
        sid: j['sid'] == null ? 'pc:${j['id']}' : _s(j['sid']),
        title: _s(j['title']),
        qty: _s(j['qty']),
        category: _s(j['category']),
        liste: _s(j['liste']).isEmpty ? defaultList : _s(j['liste']),
        price: _d(j['price']),
        merchant: _s(j['merchant']) == 'Sonstige' ? '' : _s(j['merchant']),
        base: _s(j['base']),
        validTo: _s(j['valid_to']),
        url: _s(j['url']),
        done: j['done'] == true,
        deleted: j['deleted'] == true,
        updated: DateTime.tryParse(_s(j['updated']))?.toUtc(),
      );

  Map<String, dynamic> toJson() => {
        'sid': sid, 'title': title, 'qty': qty, 'category': category, 'liste': liste, 'price': price,
        'merchant': merchant, 'base': base, 'valid_to': validTo, 'url': url, 'done': done, 'deleted': deleted,
        'updated': updated.toUtc().toIso8601String(),
      };

  ShopItem copyWith({
    String? title,
    String? qty,
    String? category,
    String? liste,
    double? price,
    bool clearPrice = false,
    String? merchant,
    bool? done,
    bool? deleted,
    DateTime? updated,
  }) =>
      ShopItem(
        sid: sid,
        title: title ?? this.title,
        qty: qty ?? this.qty,
        category: category ?? this.category,
        liste: liste ?? this.liste,
        price: clearPrice ? null : (price ?? this.price),
        merchant: merchant ?? this.merchant,
        base: base,
        validTo: validTo,
        url: url,
        done: done ?? this.done,
        deleted: deleted ?? this.deleted,
        updated: updated ?? this.updated,
      );
}

class WatchEntry {
  final String id;
  final String name;
  final String keywords;
  final String query;
  final double? maxPrice;
  final String category;
  final bool inDeals;
  final bool inProspekte;
  final bool enabled;

  const WatchEntry({
    this.id = '',
    required this.name,
    this.keywords = '',
    this.query = '',
    this.maxPrice,
    this.category = 'Allgemein',
    this.inDeals = true,
    this.inProspekte = false,
    this.enabled = true,
  });

  factory WatchEntry.fromJson(Map<String, dynamic> j) => WatchEntry(
        id: _s(j['id']),
        name: _s(j['name']),
        keywords: _s(j['keywords']),
        query: _s(j['query']),
        maxPrice: _d(j['max_price']),
        category: _s(j['category']),
        inDeals: j['in_deals'] != false,
        inProspekte: j['in_prospekte'] == true,
        enabled: j['enabled'] != false,
      );

  Map<String, dynamic> toJson() => {
        if (id.isNotEmpty) 'id': id,
        'name': name,
        'keywords': keywords,
        'query': query,
        'max_price': maxPrice,
        'category': category,
        'in_deals': inDeals,
        'in_prospekte': inProspekte,
        'enabled': enabled,
      };
}

class Prospekt {
  final int id;
  final String retailer;
  final String title;
  final int pages;
  final String validFrom;
  final String validTo;

  final String viewerUrl;

  const Prospekt({
    this.viewerUrl = '',
    required this.id,
    required this.retailer,
    required this.title,
    this.pages = 0,
    this.validFrom = '',
    this.validTo = '',
  });

  factory Prospekt.fromJson(Map<String, dynamic> j) => Prospekt(
        id: j['id'] as int,
        viewerUrl: _s(j['viewer_url']),
        retailer: _s(j['retailer']),
        title: _s(j['title']),
        pages: (j['pages'] as int?) ?? 0,
        validFrom: _s(j['valid_from']),
        validTo: _s(j['valid_to']),
      );
}

class Status {
  final String version;
  final int unread;
  final String lastRun;

  final List<String> checks;
  const Status({this.version = '', this.unread = 0, this.lastRun = '', this.checks = const []});

  factory Status.fromJson(Map<String, dynamic> j) =>
      Status(version: _s(j['version']), unread: (j['unread'] as int?) ?? 0, lastRun: _s(j['last_run']),
          checks: (j['checks'] as List? ?? const []).whereType<String>().toList());
}

/// Verbindung zum PC: aus dem QR-Code `angebotsbot://verbinden?url=http://…:8765&key=…`.
class Connection {
  final String url;
  final String key;

  const Connection(this.url, this.key);

  bool get isValid => url.startsWith('http') && key.isNotEmpty;

  static Connection? parse(String raw) {
    final text = raw.trim();
    final uri = Uri.tryParse(text);
    if (uri == null) return null;
    if (uri.scheme == 'angebotsbot') {
      final u = uri.queryParameters['url'] ?? '';
      final k = uri.queryParameters['key'] ?? '';
      final c = Connection(u.replaceAll(RegExp(r'/+$'), ''), k);
      return c.isValid ? c : null;
    }
    return null;
  }
}
