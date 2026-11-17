import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:flutter/foundation.dart';

import '../models.dart';
import 'source.dart';
import 'store.dart';

// ---------------------------------------------------------------- Menge und Kategorie

const _units = r'(?:kg|g|gr|ml|l|ltr|liter|stk\.?|stück|pck\.?|packungen?|pkg\.?|dosen?|fl\.?|flaschen?|bund|'
    r'becher|gläser|glas|beutel|netze?|rollen?|tafeln?|kästen|kasten|kisten?|sixpack|tüten?)';
final _front = RegExp(r'^(\d+(?:[.,]\d+)?)\s*(?:(?:x|×)|(' + _units + r')(?=\s))?\s+(.+)$',
    caseSensitive: false, unicode: true);
final _back = RegExp(r'^(.+?)\s+(\d+(?:[.,]\d+)?)\s*(?:x|×)$', caseSensitive: false, unicode: true);
final _spaces = RegExp(r'\s+');

/// „2 Milch“ → ("2", "Milch"), „500 g Hack“ → ("500 g", "Hack"), „Milch 2x“ → ("2", "Milch").
/// Gleiche Regeln wie am PC (angebotsbot/core/units.py split_quantity).
(String, String) splitQuantity(String text) {
  final t = text.trim().split(_spaces).join(' ');
  var m = _front.firstMatch(t);
  if (m != null) {
    final unit = m.group(2) ?? '';
    return (unit.isEmpty ? m.group(1)! : '${m.group(1)} $unit', m.group(3)!.trim());
  }
  m = _back.firstMatch(t);
  if (m != null) return (m.group(2)!, m.group(1)!.trim());
  return ('', t);
}

class Kategorie {
  final String name;
  final List<String> words;
  const Kategorie(this.name, this.words);
}

const sonstiges = 'Sonstiges';

/// Reihenfolge wie ein typischer Weg durch den Supermarkt.
const kategorien = <Kategorie>[
  Kategorie('Obst & Gemüse', [
    'apfel', 'äpfel', 'banane', 'birne', 'traube', 'orange', 'mandarine', 'clementine', 'zitrone', 'limette',
    'kiwi', 'beere', 'melone', 'ananas', 'mango', 'avocado', 'tomate', 'gurke', 'paprika', 'salat', 'karotte',
    'möhre', 'kartoffel', 'zwiebel', 'knoblauch', 'zucchini', 'aubergine', 'brokkoli', 'blumenkohl', 'kohl',
    'spinat', 'pilz', 'champignon', 'lauch', 'porree', 'sellerie', 'radieschen', 'ingwer', 'kräuter',
    'petersilie', 'schnittlauch', 'basilikum', 'obst', 'gemüse', 'rucola', 'mais', 'süßkartoffel', 'kürbis',
  ]),
  Kategorie('Brot & Backwaren', [
    'brot', 'brötchen', 'toast', 'baguette', 'croissant', 'brezel', 'laugen', 'kuchen', 'zwieback', 'knäcke',
    'wrap', 'tortilla', 'semmel',
  ]),
  Kategorie('Kühlregal', [
    'milch', 'butter', 'käse', 'joghurt', 'jogurt', 'quark', 'sahne', 'schmand', 'frischkäse', 'mozzarella',
    'feta', 'eier', 'margarine', 'pudding', 'skyr', 'kefir', 'buttermilch', 'wurst', 'salami', 'schinken',
    'aufschnitt', 'tofu', 'hefe', 'creme fraiche', 'crème fraîche', 'gouda', 'parmesan',
  ]),
  Kategorie('Fleisch & Fisch', [
    'fleisch', 'hack', 'hähnchen', 'huhn', 'pute', 'rind', 'schwein', 'steak', 'schnitzel', 'bratwurst',
    'würstchen', 'speck', 'lachs', 'fisch', 'thunfisch', 'garnele', 'forelle', 'hering', 'gulasch', 'filet',
    'kotelett', 'hähnchenbrust',
  ]),
  Kategorie('Tiefkühl', [
    'tiefkühl', 'pizza', 'eis', 'pommes', 'fischstäbchen', 'gefroren', 'eiscreme', 'vanilleeis', 'speiseeis',
    'schokoeis', 'tk-',
  ]),
  Kategorie('Vorrat', [
    'nudel', 'spaghetti', 'pasta', 'reis', 'mehl', 'zucker', 'salz', 'pfeffer', 'gewürz', 'speiseöl',
    'olivenöl', 'rapsöl', 'sonnenblumenöl', 'essig', 'konserve', 'bohnen', 'linsen', 'kichererbsen',
    'tomatenmark', 'passierte', 'soße', 'sauce', 'ketchup', 'senf', 'mayo', 'brühe', 'müsli', 'haferflocken',
    'cornflakes', 'marmelade', 'konfitüre', 'honig', 'nutella', 'kaffee', 'tee', 'kakao', 'backpulver',
    'vanille', 'öl',
  ]),
  Kategorie('Süßes & Snacks', [
    'schokolade', 'schoko', 'chips', 'keks', 'gummibär', 'bonbon', 'riegel', 'nüsse', 'erdnuss', 'salzstangen',
    'cracker', 'popcorn', 'praline', 'süßigkeit', 'butterkeks', 'milchschokolade',
  ]),
  Kategorie('Getränke', [
    'wasser', 'saft', 'cola', 'limo', 'sprudel', 'bier', 'wein', 'sekt', 'schorle', 'eistee', 'energy',
    'fanta', 'sprite', 'getränk', 'vodka', 'whisky', 'gin', 'rum', 'mineralwasser',
  ]),
  Kategorie('Drogerie', [
    'zahnpasta', 'zahnbürste', 'shampoo', 'duschgel', 'seife', 'deo', 'creme', 'rasier', 'klopapier',
    'toilettenpapier', 'taschentücher', 'windel', 'tampon', 'binden', 'wattestäbchen', 'pflaster',
    'sonnencreme', 'haargel', 'kosmetik', 'zahnseide', 'mundspülung',
  ]),
  Kategorie('Haushalt', [
    'spülmittel', 'waschmittel', 'weichspüler', 'reiniger', 'müllbeutel', 'müllsack', 'küchenrolle',
    'alufolie', 'frischhaltefolie', 'backpapier', 'schwamm', 'batterie', 'glühbirne', 'kerze', 'spültabs',
    'entkalker', 'putzmittel', 'gefrierbeutel',
  ]),
  Kategorie('Tier', [
    'katze', 'hund', 'tierfutter', 'katzenfutter', 'hundefutter', 'katzenstreu', 'streu', 'leckerli',
    'nassfutter', 'trockenfutter', "cat's best", 'whiskas', 'felix', 'sheba', 'pedigree', 'futter',
  ]),
];

final kategorieNamen = [for (final k in kategorien) k.name, sonstiges];

/// Kategorie aus dem Namen raten: das längste passende Stichwort gewinnt
/// („Reis“ → Vorrat statt „Eis“ → Tiefkühl, „Hackfleisch“ → Fleisch & Fisch).
String guessCategory(String title) {
  final t = title.toLowerCase();
  var best = sonstiges;
  var len = 0;
  for (final k in kategorien) {
    for (final w in k.words) {
      if (w.length > len && t.contains(w)) {
        best = k.name;
        len = w.length;
      }
    }
  }
  return best;
}

int kategorieIndex(String name) {
  final i = kategorieNamen.indexOf(name);
  return i < 0 ? kategorieNamen.length : i;
}

// ---------------------------------------------------------------- Liste

enum AddResult { added, exists, reopened, updated, empty }

enum SyncState { aus, ok, laeuft, fehler }

/// Einkaufslisten auf dem Handy. Funktioniert ohne PC; ist ein PC verbunden ([source]),
/// wird nach jeder Änderung kurz danach abgeglichen.
class ZettelRepo extends ChangeNotifier {
  static const _kItems = 'zettel_items', _kLists = 'zettel_lists', _kCurrent = 'zettel_current',
      _kSort = 'zettel_sort', _kHistory = 'zettel_history';

  final Store store;
  final Duration syncDelay;
  DataSource? _source;

  List<ShopItem> _all = [];
  final List<String> _lists = [];
  Map<String, dynamic> _history = {};
  String _current = defaultList;
  String _sort = 'kategorie';

  SyncState syncState = SyncState.aus;
  String syncError = '';
  DateTime? lastSync;
  bool _syncing = false, _again = false;
  Timer? _timer;

  ZettelRepo(this.store, {this.syncDelay = const Duration(milliseconds: 800)}) {
    _load();
  }

  // ------------------------------------------------ Laden/Speichern
  void _load() {
    final p = store.prefs;
    try {
      final raw = p.getString(_kItems);
      if (raw != null) {
        _all = (jsonDecode(raw) as List).cast<Map<String, dynamic>>().map(ShopItem.fromJson).toList();
      }
      final h = p.getString(_kHistory);
      if (h != null) _history = jsonDecode(h) as Map<String, dynamic>;
    } catch (_) {
      // beschädigter Speicher: lieber leer starten als abstürzen
    }
    _lists.addAll(p.getStringList(_kLists) ?? const []);
    _current = p.getString(_kCurrent) ?? defaultList;
    _sort = p.getString(_kSort) ?? 'kategorie';
    // Gelöschte Einträge nach 30 Tagen endgültig vergessen
    final cutoff = DateTime.now().toUtc().subtract(const Duration(days: 30));
    _all.removeWhere((x) => x.deleted && x.updated.isBefore(cutoff));
    if (!lists.contains(_current)) _current = defaultList;
  }

  Future<void> _save() async {
    final p = store.prefs;
    await p.setString(_kItems, jsonEncode([for (final x in _all) x.toJson()]));
    await p.setStringList(_kLists, _lists);
    await p.setString(_kCurrent, _current);
    await p.setString(_kSort, _sort);
    await p.setString(_kHistory, jsonEncode(_history));
  }

  void _changed({bool sync = true}) {
    _save();
    notifyListeners();
    if (sync) _scheduleSync();
  }

  // ------------------------------------------------ Lesen
  String get current => _current;
  String get sortMode => _sort;
  bool get hasPc => _source != null;

  List<String> get lists {
    final names = <String>{..._lists, for (final x in _all) if (!x.deleted) x.liste}..remove(defaultList);
    final sorted = names.toList()..sort((a, b) => a.toLowerCase().compareTo(b.toLowerCase()));
    return [defaultList, ...sorted];
  }

  /// Einträge einer Liste (ohne gelöschte).
  List<ShopItem> items([String? liste]) {
    final l = liste ?? _current;
    return [for (final x in _all) if (!x.deleted && x.liste == l) x];
  }

  int openCount(String liste) => items(liste).where((x) => !x.done).length;

  ShopItem? bySid(String sid) {
    for (final x in _all) {
      if (x.sid == sid) return x;
    }
    return null;
  }

  /// Kategorie zum Sortieren: gespeichert, sonst geraten.
  String categoryOf(ShopItem it) => it.category.isEmpty ? guessCategory(it.title) : it.category;

  /// Vorschläge beim Eintippen: früher eingetragene Artikel, die gerade nicht offen auf der Liste stehen.
  List<String> suggestions(String text) {
    final q = splitQuantity(text).$2.toLowerCase();
    final open = {for (final x in items()) if (!x.done) x.title.toLowerCase()};
    final hits = _history.entries.where((e) => !open.contains(e.key) && (q.isEmpty || e.key.contains(q))).toList()
      ..sort((a, b) {
        if (q.isNotEmpty) {
          final sa = a.key.startsWith(q), sb = b.key.startsWith(q);
          if (sa != sb) return sa ? -1 : 1;
        }
        return ((b.value as Map)['n'] as int? ?? 0).compareTo((a.value as Map)['n'] as int? ?? 0);
      });
    return [for (final e in hits.take(8)) ((e.value as Map)['t'] as String?) ?? e.key];
  }

  /// Bekannte Läden (für Vorschläge beim Bearbeiten).
  List<String> get shops {
    final s = <String>{for (final x in _all) if (x.merchant.isNotEmpty) x.merchant};
    return s.toList()..sort();
  }

  // ------------------------------------------------ Ändern
  void _put(ShopItem it, {bool remember = false}) {
    final stamped = it.copyWith(updated: DateTime.now().toUtc());
    final i = _all.indexWhere((x) => x.sid == it.sid);
    if (i < 0) {
      _all.add(stamped);
    } else {
      _all[i] = stamped;
    }
    if (remember) _remember(stamped);
  }

  void _remember(ShopItem it) {
    final key = it.title.toLowerCase();
    final old = _history[key] as Map<String, dynamic>?;
    _history[key] = {
      't': it.title,
      'n': ((old?['n'] as int?) ?? 0) + 1,
      'c': it.category,
      'm': it.merchant,
    };
    if (_history.length > 400) {
      final weakest = _history.entries.reduce(
          (a, b) => ((a.value as Map)['n'] as int? ?? 0) <= ((b.value as Map)['n'] as int? ?? 0) ? a : b);
      _history.remove(weakest.key);
    }
  }

  static String _newSid() {
    final r = Random.secure();
    return 'f:${List.generate(8, (_) => r.nextInt(256).toRadixString(16).padLeft(2, '0')).join()}';
  }

  /// Artikel eintragen, z. B. „2 Milch“. Steht er schon offen drauf, wird nichts verdoppelt.
  AddResult add(String text, {String? liste}) {
    var (qty, title) = splitQuantity(text);
    if (title.isEmpty) return AddResult.empty;
    title = title[0].toUpperCase() + title.substring(1);
    final l = liste ?? _current;
    final key = title.toLowerCase();
    ShopItem? existing;
    for (final x in items(l)) {
      if (x.title.toLowerCase() == key) existing = x;
    }
    AddResult result;
    if (existing != null && !existing.done) {
      if (qty.isEmpty || qty == existing.qty) return AddResult.exists;
      _put(existing.copyWith(qty: qty));
      result = AddResult.updated;
    } else if (existing != null) {
      _put(existing.copyWith(done: false, qty: qty.isNotEmpty ? qty : existing.qty), remember: true);
      result = AddResult.reopened;
    } else {
      final h = _history[key] as Map<String, dynamic>?;
      final cat = (h?['c'] as String?) ?? '';
      _put(
        ShopItem(
          sid: _newSid(),
          title: (h?['t'] as String?) ?? title,
          qty: qty,
          category: cat.isNotEmpty ? cat : guessCategory(title),
          liste: l,
          merchant: (h?['m'] as String?) ?? '',
        ),
        remember: true,
      );
      result = AddResult.added;
    }
    _changed();
    return result;
  }

  /// Angebot (Treffer, Suche, Amazon) auf die aktuelle Liste.
  AddResult addOffer(Offer o) {
    final sid = 'o:${o.uid}';
    final old = bySid(sid);
    if (old != null && !old.deleted && !old.done) {
      if (old.liste == _current) return AddResult.exists;
      _put(old.copyWith(liste: _current));
      _changed();
      return AddResult.updated;
    }
    if (old != null) {
      _put(old.copyWith(done: false, deleted: false, liste: _current));
      _changed();
      return AddResult.reopened;
    }
    _put(ShopItem(
      sid: sid,
      title: o.title,
      category: guessCategory(o.title),
      liste: _current,
      price: o.price,
      merchant: o.merchant,
      base: o.baseText,
      validTo: o.validTo,
      url: o.prospektId != null ? 'prospekt:${o.prospektId}#${o.page ?? 1}' : o.url,
    ));
    _changed();
    return AddResult.added;
  }

  void toggle(String sid, bool done) {
    final it = bySid(sid);
    if (it == null || it.done == done) return;
    _put(it.copyWith(done: done));
    _changed();
  }

  /// Eintrag geändert (Bearbeiten-Dialog). Neue Kategorie/Laden merkt sich die App für das nächste Mal.
  void update(ShopItem it) {
    _put(it);
    final key = it.title.toLowerCase();
    final h = _history[key] as Map<String, dynamic>?;
    _history[key] = {'t': it.title, 'n': (h?['n'] as int?) ?? 1, 'c': it.category, 'm': it.merchant};
    _changed();
  }

  /// Löscht einen Eintrag; gibt ihn zurück, damit „Rückgängig“ geht.
  ShopItem? delete(String sid) {
    final it = bySid(sid);
    if (it == null) return null;
    _put(it.copyWith(deleted: true));
    _changed();
    return it;
  }

  void restore(ShopItem it) {
    _put(it.copyWith(deleted: false));
    _changed();
  }

  int removeDone([String? liste]) {
    final done = items(liste).where((x) => x.done).toList();
    for (final x in done) {
      _put(x.copyWith(deleted: true));
    }
    if (done.isNotEmpty) _changed();
    return done.length;
  }

  void clearList([String? liste]) {
    for (final x in items(liste)) {
      _put(x.copyWith(deleted: true));
    }
    _changed();
  }

  void setCurrent(String liste) {
    _current = liste;
    if (liste != defaultList && !_lists.contains(liste)) _lists.add(liste);
    _changed(sync: false);
  }

  void setSortMode(String mode) {
    _sort = mode;
    _changed(sync: false);
  }

  bool createList(String name) {
    name = name.trim();
    if (name.isEmpty || lists.contains(name)) return false;
    _lists.add(name);
    _current = name;
    _changed(sync: false);
    return true;
  }

  bool renameList(String from, String to) {
    to = to.trim();
    if (from == defaultList || to.isEmpty || lists.contains(to)) return false;
    for (final x in items(from)) {
      _put(x.copyWith(liste: to));
    }
    _lists
      ..remove(from)
      ..add(to);
    if (_current == from) _current = to;
    _changed();
    return true;
  }

  /// Liste samt Einträgen löschen. Die Standardliste wird nur geleert.
  void deleteList(String name) {
    for (final x in items(name)) {
      _put(x.copyWith(deleted: true));
    }
    if (name != defaultList) _lists.remove(name);
    if (_current == name) _current = defaultList;
    _changed();
  }

  /// Text zum Teilen (WhatsApp, Zwischenablage): nur offene Einträge, sortiert wie auf dem Bildschirm.
  String shareText() {
    final groups = grouped(items().where((x) => !x.done).toList());
    final b = StringBuffer('🛒 $_current\n');
    for (final g in groups.entries) {
      b.write('\n${g.key}\n');
      for (final x in g.value) {
        b.write('☐ ${x.text}${x.price != null ? ' – ${euro(x.price)}' : ''}\n');
      }
    }
    return b.toString().trim();
  }

  /// Nach Kategorie (Supermarkt-Reihenfolge) oder Laden gruppiert, innerhalb alphabetisch.
  Map<String, List<ShopItem>> grouped(List<ShopItem> list) {
    final byLaden = _sort == 'laden';
    final map = <String, List<ShopItem>>{};
    for (final x in list) {
      map.putIfAbsent(byLaden ? x.shop : categoryOf(x), () => []).add(x);
    }
    final keys = map.keys.toList()
      ..sort((a, b) {
        if (byLaden) {
          if (a == 'Sonstige' || b == 'Sonstige') return a == 'Sonstige' ? 1 : (b == 'Sonstige' ? -1 : 0);
          return a.toLowerCase().compareTo(b.toLowerCase());
        }
        return kategorieIndex(a).compareTo(kategorieIndex(b));
      });
    return {
      for (final k in keys) k: map[k]!..sort((a, b) => a.title.toLowerCase().compareTo(b.title.toLowerCase())),
    };
  }

  // ------------------------------------------------ Abgleich mit dem PC
  set source(DataSource? s) {
    _source = s;
    _timer?.cancel();
    syncState = s == null ? SyncState.aus : syncState;
    notifyListeners();
  }

  void _scheduleSync() {
    if (_source == null) return;
    _timer?.cancel();
    _timer = Timer(syncDelay, sync);
  }

  /// Gleicht mit dem PC ab. Gibt false zurück, wenn kein PC da ist oder er nicht erreichbar war.
  Future<bool> sync() async {
    final src = _source;
    if (src == null) return false;
    if (_syncing) {
      _again = true;
      return false;
    }
    _syncing = true;
    syncState = SyncState.laeuft;
    notifyListeners();
    var ok = false;
    try {
      final started = DateTime.now().toUtc();
      final remote = await src.zettelSync(List.of(_all));
      merge(remote, started);
      lastSync = DateTime.now();
      syncError = '';
      syncState = SyncState.ok;
      ok = true;
    } catch (e) {
      syncError = e.toString();
      syncState = SyncState.fehler;
    } finally {
      _syncing = false;
      await _save();
      notifyListeners();
    }
    if (_again) {
      _again = false;
      return sync();
    }
    return ok;
  }

  /// Stand vom PC einarbeiten: pro Eintrag gewinnt die neuere Änderung.
  @visibleForTesting
  void merge(List<ShopItem> remote, DateTime started) {
    final map = {for (final x in _all) x.sid: x};
    final seen = <String>{};
    for (final r in remote) {
      seen.add(r.sid);
      final l = map[r.sid];
      if (l == null || r.updated.isAfter(l.updated)) map[r.sid] = r;
    }
    // Was der PC nicht mehr kennt (dort endgültig weggeräumt) und hier seit dem Abgleich-Start
    // nicht geändert wurde, fällt weg.
    map.removeWhere((sid, x) => !seen.contains(sid) && !x.updated.isAfter(started));
    _all = map.values.toList();
    if (!lists.contains(_current)) _current = defaultList;
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }
}
