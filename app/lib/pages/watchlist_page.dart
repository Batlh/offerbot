import 'package:flutter/material.dart';

import '../main.dart';
import '../models.dart';
import 'home_page.dart';

class WatchlistPage extends StatefulWidget {
  const WatchlistPage({super.key});

  @override
  State<WatchlistPage> createState() => _WatchlistPageState();
}

class _WatchlistPageState extends State<WatchlistPage> {
  List<WatchEntry>? _items;
  String _error = '';

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_items == null) _load();
  }

  Future<void> _load() async {
    try {
      final items = await AppScope.of(context).source.watchlist();
      if (mounted) setState(() {
        _items = items;
        _error = '';
      });
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    }
  }

  Future<void> _edit([WatchEntry? w]) async {
    final saved = await showModalBottomSheet<WatchEntry>(
      context: context,
      isScrollControlled: true,
      builder: (_) => _WatchEditor(entry: w),
    );
    if (saved == null || !mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    try {
      await AppScope.of(context).source.watchSpeichern(saved);
      await _load();
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  Future<void> _delete(WatchEntry w) async {
    await AppScope.of(context).source.watchLoeschen(w.id);
    await _load();
  }

  Future<void> _amazon(WatchEntry w) async {
    final source = AppScope.of(context).source;
    await Navigator.of(context).push(MaterialPageRoute(
      builder: (_) => Scaffold(
        appBar: AppBar(title: Text('Amazon: ${w.name}')),
        body: FutureBuilder<List<Offer>>(
          future: source.amazon(w.id),
          builder: (context, snap) {
            if (snap.hasError) return Center(child: Padding(padding: const EdgeInsets.all(24), child: Text(snap.error.toString())));
            if (!snap.hasData) {
              return const Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
                CircularProgressIndicator(),
                SizedBox(height: 12),
                Text('Der PC sucht bei Amazon …'),
              ]));
            }
            final items = [...snap.data!]..sort((a, b) => (b.hit ? 1 : 0) - (a.hit ? 1 : 0));
            if (items.isEmpty) return const Center(child: Text('Keine Ergebnisse'));
            return ListView(children: [
              const Padding(
                padding: EdgeInsets.all(12),
                child: Text('Fett = passt zu Stichwörtern und Höchstpreis.', style: TextStyle(fontSize: 12)),
              ),
              for (final o in items) OfferTile(offer: o, bold: o.hit),
            ]);
          },
        ),
      ),
    ));
  }

  @override
  Widget build(BuildContext context) {
    final items = _items;
    return Scaffold(
      floatingActionButton: FloatingActionButton(onPressed: () => _edit(), tooltip: 'Neu', child: const Icon(Icons.add)),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            if (_error.isNotEmpty) Padding(padding: const EdgeInsets.all(16), child: Text(_error)),
            if (items == null && _error.isEmpty)
              const Padding(padding: EdgeInsets.all(32), child: Center(child: CircularProgressIndicator())),
            for (final w in items ?? const <WatchEntry>[])
              ListTile(
                title: Text(w.name, style: TextStyle(color: w.enabled ? null : Colors.grey)),
                subtitle: Text([
                  if (w.maxPrice != null && w.maxPrice! > 0) '≤ ${euro(w.maxPrice)}',
                  if (w.inDeals) 'Deals',
                  if (w.inProspekte) 'Prospekte',
                  if (w.keywords.isNotEmpty) w.keywords,
                ].join(' · ')),
                onTap: () => _edit(w),
                trailing: PopupMenuButton<String>(
                  onSelected: (v) => v == 'amazon' ? _amazon(w) : _delete(w),
                  itemBuilder: (_) => const [
                    PopupMenuItem(value: 'amazon', child: Text('Amazon prüfen')),
                    PopupMenuItem(value: 'del', child: Text('Löschen')),
                  ],
                ),
              ),
            const SizedBox(height: 80),
          ],
        ),
      ),
    );
  }
}

class _WatchEditor extends StatefulWidget {
  final WatchEntry? entry;
  const _WatchEditor({this.entry});

  @override
  State<_WatchEditor> createState() => _WatchEditorState();
}

class _WatchEditorState extends State<_WatchEditor> {
  late final _name = TextEditingController(text: widget.entry?.name ?? '');
  late final _kw = TextEditingController(text: widget.entry?.keywords ?? '');
  late final _query = TextEditingController(text: widget.entry?.query ?? '');
  late final _max = TextEditingController(
      text: widget.entry?.maxPrice == null ? '' : widget.entry!.maxPrice!.toStringAsFixed(2).replaceAll('.', ','));
  late bool _deals = widget.entry?.inDeals ?? true;
  late bool _prospekte = widget.entry?.inProspekte ?? false;
  late bool _enabled = widget.entry?.enabled ?? true;

  @override
  Widget build(BuildContext context) {
    final e = widget.entry;
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 20, 20, MediaQuery.of(context).viewInsets.bottom + 20),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(e == null ? 'Neuer Eintrag' : 'Eintrag bearbeiten', style: Theme.of(context).textTheme.titleLarge),
            TextField(controller: _name, decoration: const InputDecoration(labelText: 'Name')),
            TextField(
                controller: _kw,
                decoration: const InputDecoration(
                    labelText: 'Stichwörter', helperText: 'a|b = oder, -wort = ausschließen, leer = Name')),
            TextField(controller: _query, decoration: const InputDecoration(labelText: 'Suchtext (kaufDA, Amazon …)')),
            TextField(
              controller: _max,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(labelText: 'Höchstpreis in € (leer = egal)'),
            ),
            SwitchListTile(value: _deals, onChanged: (v) => setState(() => _deals = v), title: const Text('Deals & Shops')),
            SwitchListTile(value: _prospekte, onChanged: (v) => setState(() => _prospekte = v), title: const Text('Prospekte')),
            SwitchListTile(value: _enabled, onChanged: (v) => setState(() => _enabled = v), title: const Text('Aktiv')),
            const SizedBox(height: 8),
            FilledButton(
              onPressed: () {
                if (_name.text.trim().isEmpty) return;
                final max = double.tryParse(_max.text.trim().replaceAll(',', '.'));
                Navigator.pop(
                  context,
                  WatchEntry(
                    id: e?.id ?? '',
                    name: _name.text.trim(),
                    keywords: _kw.text.trim(),
                    query: _query.text.trim(),
                    maxPrice: max,
                    category: e?.category ?? 'Allgemein',
                    inDeals: _deals,
                    inProspekte: _prospekte,
                    enabled: _enabled,
                  ),
                );
              },
              child: const Text('Speichern'),
            ),
          ],
        ),
      ),
    );
  }
}
