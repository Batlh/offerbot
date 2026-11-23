import 'package:flutter/material.dart';

import 'package:url_launcher/url_launcher.dart';

import '../main.dart';
import '../models.dart';

class ProspektePage extends StatefulWidget {
  const ProspektePage({super.key});

  @override
  State<ProspektePage> createState() => _ProspektePageState();
}

class _ProspektePageState extends State<ProspektePage> {
  List<Prospekt>? _items;
  String _error = '';

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_items == null) _load();
  }

  Future<void> _load() async {
    try {
      final items = await AppScope.of(context).source.prospekte();
      if (mounted) setState(() {
        _items = items;
        _error = '';
      });
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    final items = _items;
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          if (_error.isNotEmpty) Padding(padding: const EdgeInsets.all(16), child: Text(_error)),
          if (items == null && _error.isEmpty)
            const Padding(padding: EdgeInsets.all(32), child: Center(child: CircularProgressIndicator())),
          if (items != null && items.isEmpty)
            const Padding(padding: EdgeInsets.all(32), child: Center(child: Text('Noch keine Prospekte'))),
          for (final p in items ?? const <Prospekt>[])
            ListTile(
              leading: const Icon(Icons.menu_book_outlined),
              title: Text('${p.retailer} – ${p.title}', maxLines: 2, overflow: TextOverflow.ellipsis),
              subtitle: Text([
                if (p.pages > 0) '${p.pages} Seiten',
                if (p.validTo.isNotEmpty) 'bis ${p.validTo}',
              ].join(' · ')),
              trailing: p.viewerUrl.isEmpty ? null : IconButton(
                tooltip: 'Vollständigen Prospekt online öffnen',
                icon: const Icon(Icons.open_in_browser),
                onPressed: () => launchUrl(Uri.parse(p.viewerUrl), mode: LaunchMode.externalApplication),
              ),
              onTap: p.pages == 0
                  ? null
                  : () => Navigator.of(context).push(MaterialPageRoute(
                      builder: (_) => ProspektViewer(prospektId: p.id, startPage: 1, title: p.retailer, pages: p.pages))),
            ),
        ],
      ),
    );
  }
}

/// Prospektseiten als Bilder vom PC, wischen zum Blättern, zwei Finger zum Zoomen.
class ProspektViewer extends StatefulWidget {
  final int prospektId;
  final int startPage;
  final String title;
  final int pages;
  const ProspektViewer({super.key, required this.prospektId, required this.startPage, this.title = '', this.pages = 0});

  @override
  State<ProspektViewer> createState() => _ProspektViewerState();
}

class _ProspektViewerState extends State<ProspektViewer> {
  late final PageController _ctrl = PageController(initialPage: widget.startPage - 1);
  late int _page = widget.startPage;

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final source = AppScope.of(context).source;
    final count = widget.pages > 0 ? widget.pages : 400;
    return Scaffold(
      appBar: AppBar(title: Text('${widget.title} · Seite $_page${widget.pages > 0 ? ' / ${widget.pages}' : ''}')),
      body: PageView.builder(
        controller: _ctrl,
        itemCount: count,
        onPageChanged: (i) => setState(() => _page = i + 1),
        itemBuilder: (context, i) => InteractiveViewer(
          maxScale: 5,
          child: Image.network(
            source.seitenBild(widget.prospektId, i + 1),
            headers: source.bildHeader,
            fit: BoxFit.contain,
            loadingBuilder: (c, child, p) => p == null ? child : const Center(child: CircularProgressIndicator()),
            errorBuilder: (c, e, s) => const Center(child: Text('Seite nicht verfügbar')),
          ),
        ),
      ),
    );
  }
}
