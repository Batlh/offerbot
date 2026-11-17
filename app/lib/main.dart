import 'package:flutter/material.dart';

import 'data/source.dart';
import 'data/store.dart';
import 'data/zettel.dart';
import 'models.dart';
import 'pages/home_page.dart';
import 'pages/setup_page.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final store = await Store.open();
  runApp(AngebotsBotApp(store: store));
}

/// Gibt Datenquelle, Speicher und Einkaufsliste an alle Seiten weiter.
class AppScope extends InheritedWidget {
  /// Der AngebotsBot am PC – null, wenn die App ohne PC (nur Einkaufszettel) läuft.
  final DataSource? pcSource;
  final Store store;
  final ZettelRepo zettel;
  final VoidCallback disconnect;
  final Future<void> Function(Connection) connect;

  const AppScope({
    super.key,
    required this.pcSource,
    required this.store,
    required this.zettel,
    required this.disconnect,
    required this.connect,
    required super.child,
  });

  bool get hasPc => pcSource != null;

  /// Für Seiten, die nur mit PC angezeigt werden (Treffer, Watchlist, Prospekte).
  DataSource get source => pcSource!;

  static AppScope of(BuildContext context) => context.dependOnInheritedWidgetOfExactType<AppScope>()!;

  @override
  bool updateShouldNotify(AppScope oldWidget) => pcSource != oldWidget.pcSource;
}

class AngebotsBotApp extends StatefulWidget {
  final Store store;
  final DataSource? source; // für Tests
  final Duration syncDelay; // für Tests
  const AngebotsBotApp({super.key, required this.store, this.source, this.syncDelay = const Duration(milliseconds: 800)});

  @override
  State<AngebotsBotApp> createState() => _AngebotsBotAppState();
}

class _AngebotsBotAppState extends State<AngebotsBotApp> {
  DataSource? source;
  late final ZettelRepo zettel = ZettelRepo(widget.store, syncDelay: widget.syncDelay);

  @override
  void initState() {
    super.initState();
    final con = widget.store.connection;
    source = widget.source ?? (con != null ? PcSource(con) : null);
    zettel.source = source;
    if (source != null) zettel.sync();
  }

  @override
  void dispose() {
    zettel.dispose();
    super.dispose();
  }

  Future<void> _connected(Connection c) async {
    await widget.store.saveConnection(c);
    setState(() => source = PcSource(c));
    zettel.source = source;
    await zettel.sync();
  }

  Future<void> _disconnect() async {
    await widget.store.clearConnection();
    setState(() => source = null);
    zettel.source = null;
  }

  Future<void> _ohnePc() async {
    await widget.store.setOhnePc(true);
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final scheme = ColorScheme.fromSeed(seedColor: const Color(0xFFE4572E));
    final app = MaterialApp(
      title: 'AngebotsBot',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(colorScheme: scheme, useMaterial3: true),
      darkTheme: ThemeData(
          colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFFE4572E), brightness: Brightness.dark),
          useMaterial3: true),
      home: source != null || widget.store.ohnePc
          ? const HomePage()
          : SetupPage(onConnected: _connected, onOhnePc: _ohnePc),
    );
    // AppScope liegt über der MaterialApp, damit auch geöffnete Seiten (Suche, Prospekt) die Quelle finden
    return AppScope(
      pcSource: source,
      store: widget.store,
      zettel: zettel,
      disconnect: _disconnect,
      connect: _connected,
      child: app,
    );
  }
}
