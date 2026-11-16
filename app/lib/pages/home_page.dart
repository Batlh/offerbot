import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../main.dart';
import '../models.dart';
import 'prospekte_page.dart';
import 'treffer_page.dart';
import 'watchlist_page.dart';
import 'zettel_page.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  int _tab = 0;
  final _keys = [GlobalKey(), GlobalKey(), GlobalKey(), GlobalKey()];

  static const _titles = ['Treffer', 'Einkaufszettel', 'Watchlist', 'Prospekte'];

  Future<void> _pruefen() async {
    final scope = AppScope.of(context);
    final messenger = ScaffoldMessenger.of(context);
    try {
      await scope.source.pruefen();
      messenger.showSnackBar(const SnackBar(content: Text('Prüfung am PC gestartet – neue Treffer kommen gleich.')));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  void _menu(String v) {
    final scope = AppScope.of(context);
    if (v == 'suche') {
      showSearch(context: context, delegate: OfferSearch());
    } else if (v == 'trennen') {
      scope.disconnect();
    }
  }

  @override
  Widget build(BuildContext context) {
    final pages = [
      TrefferPage(key: _keys[0]),
      ZettelPage(key: _keys[1]),
      WatchlistPage(key: _keys[2]),
      ProspektePage(key: _keys[3]),
    ];
    return Scaffold(
      appBar: AppBar(
        title: Text(_titles[_tab]),
        actions: [
          IconButton(tooltip: 'Jetzt prüfen', icon: const Icon(Icons.refresh), onPressed: _pruefen),
          PopupMenuButton<String>(
            onSelected: _menu,
            itemBuilder: (_) => const [
              PopupMenuItem(value: 'suche', child: Text('In allen Angeboten suchen')),
              PopupMenuItem(value: 'trennen', child: Text('Vom PC trennen')),
            ],
          ),
        ],
      ),
      body: IndexedStack(index: _tab, children: pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() => _tab = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.local_offer_outlined), label: 'Treffer'),
          NavigationDestination(icon: Icon(Icons.checklist), label: 'Zettel'),
          NavigationDestination(icon: Icon(Icons.visibility_outlined), label: 'Watchlist'),
          NavigationDestination(icon: Icon(Icons.menu_book_outlined), label: 'Prospekte'),
        ],
      ),
    );
  }
}

/// Öffnet ein Angebot: Link im Browser oder Prospektseite in der App.
Future<void> openOffer(BuildContext context, Offer o) async {
  if (o.prospektId != null) {
    await Navigator.of(context).push(MaterialPageRoute(
        builder: (_) => ProspektViewer(prospektId: o.prospektId!, startPage: o.page ?? 1, title: o.merchant)));
  } else if (o.url.startsWith('http')) {
    await launchUrl(Uri.parse(o.url), mode: LaunchMode.externalApplication);
  }
}

class OfferSearch extends SearchDelegate<Offer?> {
  OfferSearch() : super(searchFieldLabel: 'z. B. butter');

  @override
  List<Widget> buildActions(BuildContext context) => [
        IconButton(icon: const Icon(Icons.clear), onPressed: () => query = ''),
      ];

  @override
  Widget buildLeading(BuildContext context) =>
      IconButton(icon: const Icon(Icons.arrow_back), onPressed: () => close(context, null));

  @override
  Widget buildSuggestions(BuildContext context) =>
      const Center(child: Text('Suchbegriff eingeben und bestätigen'));

  @override
  Widget buildResults(BuildContext context) {
    final source = AppScope.of(context).source;
    return FutureBuilder<List<Offer>>(
      future: source.suche(query),
      builder: (context, snap) {
        if (snap.hasError) return Center(child: Text(snap.error.toString()));
        if (!snap.hasData) return const Center(child: CircularProgressIndicator());
        final items = snap.data!;
        if (items.isEmpty) return const Center(child: Text('Nichts gefunden'));
        return ListView(children: [for (final o in items) OfferTile(offer: o)]);
      },
    );
  }
}

/// Eine Zeile für ein Angebot (Treffer, Suche, Amazon).
class OfferTile extends StatelessWidget {
  final Offer offer;
  final bool bold;
  const OfferTile({super.key, required this.offer, this.bold = false});

  @override
  Widget build(BuildContext context) {
    final o = offer;
    final scheme = Theme.of(context).colorScheme;
    final sub = [
      o.merchant,
      if (o.baseText.isNotEmpty) o.baseText,
      if (o.validText.isNotEmpty) o.validText,
      if (o.priceCheck.isNotEmpty) o.priceCheck,
      if (o.info.isNotEmpty && o.source.startsWith('Amazon')) o.info,
    ].where((s) => s.isNotEmpty).join(' · ');
    return ListTile(
      title: Text(o.title, maxLines: 2, overflow: TextOverflow.ellipsis,
          style: TextStyle(fontWeight: bold ? FontWeight.bold : FontWeight.normal)),
      subtitle: Text(sub, maxLines: 3, overflow: TextOverflow.ellipsis),
      trailing: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Text(euro(o.price), style: TextStyle(fontWeight: FontWeight.bold, color: scheme.primary)),
          if (o.oldPrice != null)
            Text(euro(o.oldPrice), style: const TextStyle(decoration: TextDecoration.lineThrough, fontSize: 12)),
        ],
      ),
      onTap: () => openOffer(context, o),
      onLongPress: () async {
        final messenger = ScaffoldMessenger.of(context);
        try {
          await AppScope.of(context).source.zettelHinzufuegen(uid: o.uid);
          messenger.showSnackBar(const SnackBar(content: Text('Auf den Einkaufszettel gesetzt')));
        } catch (e) {
          messenger.showSnackBar(SnackBar(content: Text(e.toString())));
        }
      },
    );
  }
}
