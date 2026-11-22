import 'package:flutter/material.dart';

import '../main.dart';
import '../models.dart';
import 'home_page.dart';

class TrefferPage extends StatefulWidget {
  const TrefferPage({super.key});

  @override
  State<TrefferPage> createState() => _TrefferPageState();
}

class _TrefferPageState extends State<TrefferPage> {
  List<Offer>? _items;
  String _error = '';
  bool _nurNeu = false;
  bool _offline = false;
  int _request = 0;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_items == null) _load();
  }

  Future<void> _load() async {
    final scope = AppScope.of(context);
    final request = ++_request;
    if (_items == null && scope.store.hasCachedTreffer) {
      _items = scope.store.cachedTrefferJson.map(Offer.fromJson).toList();
      _offline = true;
    }
    try {
      final items = await scope.source.treffer();
      if (!mounted || request != _request || AppScope.of(context).pcSource != scope.pcSource) return;
      await scope.store.cacheTrefferJson(items.map((item) => item.toJson()).toList());
      if (mounted) setState(() {
        _offline = false;
        _items = items;
        _error = '';
      });
    } catch (e) {
      if (mounted && request == _request) setState(() { _offline = true; _error = e.toString(); });
    }
  }

  Future<void> _alleGelesen() async {
    try {
      await AppScope.of(context).source.gelesen(const [], alle: true);
      if (mounted) await _load();
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    final items = _nurNeu ? _items?.where((o) => !o.seen).toList() : _items;
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 8, 0),
            child: Row(children: [
              FilterChip(
                label: const Text('Nur neue'),
                selected: _nurNeu,
                onSelected: (v) {
                  setState(() => _nurNeu = v);
                },
              ),
              const Spacer(),
              TextButton(onPressed: _offline ? null : _alleGelesen, child: const Text('Alle gelesen')),
            ]),
          ),
          if (_offline && items != null) const ListTile(leading: Icon(Icons.offline_pin), title: Text('Gespeicherte Treffer')),
          if (_error.isNotEmpty) Padding(padding: const EdgeInsets.all(16), child: Text(_error)),
          if (items == null && _error.isEmpty)
            const Padding(padding: EdgeInsets.all(32), child: Center(child: CircularProgressIndicator())),
          if (items != null && items.isEmpty)
            const Padding(padding: EdgeInsets.all(32), child: Center(child: Text('Keine Treffer'))),
          if (items != null) ..._grouped(items),
          const Padding(
            padding: EdgeInsets.all(16),
            child: Text('Tippen öffnet das Angebot, lange drücken setzt es auf den Einkaufszettel.',
                style: TextStyle(fontSize: 12)),
          ),
        ],
      ),
    );
  }

  List<Widget> _grouped(List<Offer> items) {
    final byWatch = <String, List<Offer>>{};
    for (final o in items) {
      byWatch.putIfAbsent(o.watchName.isEmpty ? 'Sonstige' : o.watchName, () => []).add(o);
    }
    return [
      for (final e in byWatch.entries) ...[
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
          child: Text('${e.key} (${e.value.length})', style: Theme.of(context).textTheme.titleSmall),
        ),
        for (final o in e.value) OfferTile(offer: o, bold: !o.seen),
      ],
    ];
  }
}
