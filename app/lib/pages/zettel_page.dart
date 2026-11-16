import 'package:flutter/material.dart';

import '../main.dart';
import '../models.dart';

/// Einkaufszettel nach Läden. Funktioniert auch ohne WLAN mit dem zuletzt geladenen Stand.
class ZettelPage extends StatefulWidget {
  const ZettelPage({super.key});

  @override
  State<ZettelPage> createState() => _ZettelPageState();
}

class _ZettelPageState extends State<ZettelPage> {
  List<ShopItem>? _items;
  bool _offline = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_items == null) _load();
  }

  Future<void> _load() async {
    final scope = AppScope.of(context);
    try {
      final items = await scope.source.zettel();
      await scope.store.cacheZettel(items);
      if (mounted) setState(() {
        _items = items;
        _offline = false;
      });
    } catch (_) {
      if (mounted) setState(() {
        _items = scope.store.cachedZettel;
        _offline = true;
      });
    }
  }

  Future<void> _toggle(ShopItem it, bool done) async {
    final scope = AppScope.of(context);
    setState(() => _items = [for (final x in _items!) x.id == it.id ? x.copyWith(done: done) : x]);
    await scope.store.cacheZettel(_items!);
    try {
      await scope.source.zettelErledigt(it.id, done);
    } catch (_) {
      if (mounted) setState(() => _offline = true); // wird beim nächsten Laden vom PC abgeglichen
    }
  }

  Future<void> _add() async {
    final ctrl = TextEditingController();
    final title = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Artikel hinzufügen'),
        content: TextField(controller: ctrl, autofocus: true, decoration: const InputDecoration(hintText: 'z. B. Katzenstreu')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Abbrechen')),
          FilledButton(onPressed: () => Navigator.pop(ctx, ctrl.text.trim()), child: const Text('Hinzufügen')),
        ],
      ),
    );
    if (title == null || title.isEmpty || !mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    try {
      await AppScope.of(context).source.zettelHinzufuegen(titel: title);
      await _load();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  @override
  Widget build(BuildContext context) {
    final items = _items;
    final byStore = <String, List<ShopItem>>{};
    for (final it in items ?? const <ShopItem>[]) {
      byStore.putIfAbsent(it.merchant, () => []).add(it);
    }
    return Scaffold(
      floatingActionButton: FloatingActionButton(onPressed: _add, tooltip: 'Hinzufügen', child: const Icon(Icons.add)),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            if (_offline)
              const ListTile(
                leading: Icon(Icons.cloud_off),
                title: Text('Offline – letzter Stand vom PC'),
                dense: true,
              ),
            if (items == null) const Padding(padding: EdgeInsets.all(32), child: Center(child: CircularProgressIndicator())),
            if (items != null && items.isEmpty)
              const Padding(padding: EdgeInsets.all(32), child: Center(child: Text('Der Einkaufszettel ist leer'))),
            for (final e in byStore.entries) ...[
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
                child: Text(
                  '${e.key} · ${euro(e.value.where((x) => !x.done).fold<double>(0, (s, x) => s + (x.price ?? 0)))}',
                  style: Theme.of(context).textTheme.titleSmall,
                ),
              ),
              for (final it in e.value)
                CheckboxListTile(
                  value: it.done,
                  onChanged: (v) => _toggle(it, v ?? false),
                  controlAffinity: ListTileControlAffinity.leading,
                  title: Text(it.title,
                      style: TextStyle(decoration: it.done ? TextDecoration.lineThrough : null)),
                  subtitle: Text([if (it.base.isNotEmpty) it.base, if (it.validTo.isNotEmpty) 'bis ${it.validTo}']
                      .join(' · ')),
                  secondary: Text(euro(it.price)),
                ),
            ],
            const SizedBox(height: 80),
          ],
        ),
      ),
    );
  }
}
