import 'package:flutter/material.dart';

import 'data/source.dart';
import 'data/store.dart';
import 'models.dart';
import 'pages/home_page.dart';
import 'pages/setup_page.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final store = await Store.open();
  runApp(AngebotsBotApp(store: store));
}

/// Gibt Datenquelle und Speicher an alle Seiten weiter.
class AppScope extends InheritedWidget {
  final DataSource source;
  final Store store;
  final VoidCallback disconnect;

  const AppScope({super.key, required this.source, required this.store, required this.disconnect,
      required super.child});

  static AppScope of(BuildContext context) => context.dependOnInheritedWidgetOfExactType<AppScope>()!;

  @override
  bool updateShouldNotify(AppScope oldWidget) => source != oldWidget.source;
}

class AngebotsBotApp extends StatefulWidget {
  final Store store;
  final DataSource? source; // für Tests
  const AngebotsBotApp({super.key, required this.store, this.source});

  @override
  State<AngebotsBotApp> createState() => _AngebotsBotAppState();
}

class _AngebotsBotAppState extends State<AngebotsBotApp> {
  DataSource? source;

  @override
  void initState() {
    super.initState();
    final con = widget.store.connection;
    source = widget.source ?? (con != null ? PcSource(con) : null);
  }

  Future<void> _connected(Connection c) async {
    await widget.store.saveConnection(c);
    setState(() => source = PcSource(c));
  }

  Future<void> _disconnect() async {
    await widget.store.clearConnection();
    setState(() => source = null);
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
      home: source == null ? SetupPage(onConnected: _connected) : const HomePage(),
    );
    // AppScope liegt über der MaterialApp, damit auch geöffnete Seiten (Suche, Prospekt) die Quelle finden
    if (source == null) return app;
    return AppScope(source: source!, store: widget.store, disconnect: _disconnect, child: app);
  }
}
