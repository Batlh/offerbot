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

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_items == null) _load();
  }

  Future<void> _load() async {
    try {
      final items = await AppScope.of(context).source.treffer(nurUngelesen: _nurNeu);
      if (mounted) setState(() {
        _items = items;
        _error = '';
      });
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    }
  }

  Future<void> _alleGelesen() async {
    await AppScope.of(context).source.gelesen(const [], alle: true);
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    final items = _items;
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
                  _load();
                },
              ),
              const Spacer(),
              TextButton(onPressed: _alleGelesen, child: const Text('Alle gelesen')),
            ]),
          ),
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
