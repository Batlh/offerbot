import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

import '../data/source.dart';
import '../models.dart';

/// Erste Einrichtung: QR-Code vom PC scannen (Einstellungen → Handy-App → QR-Code anzeigen)
/// oder Adresse und Schlüssel von Hand eintragen.
class SetupPage extends StatefulWidget {
  final Future<void> Function(Connection) onConnected;

  /// „Ohne PC nutzen“ – nur angeboten, solange die App noch nie ohne PC gestartet wurde.
  final Future<void> Function()? onOhnePc;
  const SetupPage({super.key, required this.onConnected, this.onOhnePc});

  @override
  State<SetupPage> createState() => _SetupPageState();
}

class _SetupPageState extends State<SetupPage> {
  final _url = TextEditingController(text: 'http://192.168.');
  final _key = TextEditingController();
  bool _busy = false;
  String _error = '';

  Future<void> _try(Connection c) async {
    setState(() {
      _busy = true;
      _error = '';
    });
    try {
      await PcSource(c).status();
      await widget.onConnected(c);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _scan() async {
    final raw = await Navigator.of(context).push<String>(MaterialPageRoute(builder: (_) => const _ScanPage()));
    if (raw == null) return;
    final c = Connection.parse(raw);
    if (c == null) {
      setState(() => _error = 'Das ist kein AngebotsBot-QR-Code.');
      return;
    }
    _url.text = c.url;
    _key.text = c.key;
    await _try(c);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('AngebotsBot verbinden')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const Text(
            'Am PC im AngebotsBot: Einstellungen → Handy-App → Schnittstelle einschalten, speichern und '
            '„QR-Code anzeigen“. Handy und PC müssen im selben WLAN sein.',
          ),
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: _busy ? null : _scan,
            icon: const Icon(Icons.qr_code_scanner),
            label: const Text('QR-Code scannen'),
          ),
          const SizedBox(height: 28),
          const Text('Oder von Hand:', style: TextStyle(fontWeight: FontWeight.bold)),
          TextField(controller: _url, decoration: const InputDecoration(labelText: 'Adresse, z. B. http://192.168.1.20:8765')),
          TextField(controller: _key, decoration: const InputDecoration(labelText: 'Schlüssel')),
          const SizedBox(height: 12),
          OutlinedButton(
            onPressed: _busy ? null : () => _try(Connection(_url.text.trim(), _key.text.trim())),
            child: const Text('Verbinden'),
          ),
          if (widget.onOhnePc != null) ...[
            const SizedBox(height: 28),
            const Divider(),
            const SizedBox(height: 8),
            const Text('Kein PC? Die App taugt auch allein als Einkaufsliste – verbinden geht später jederzeit.'),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              onPressed: _busy ? null : widget.onOhnePc,
              icon: const Icon(Icons.checklist),
              label: const Text('Ohne PC nutzen – nur Einkaufsliste'),
            ),
          ],
          if (_busy) const Padding(padding: EdgeInsets.all(16), child: Center(child: CircularProgressIndicator())),
          if (_error.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 16),
              child: Text(_error, style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ),
        ],
      ),
    );
  }
}

class _ScanPage extends StatefulWidget {
  const _ScanPage();

  @override
  State<_ScanPage> createState() => _ScanPageState();
}

class _ScanPageState extends State<_ScanPage> {
  bool _done = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('QR-Code scannen')),
      body: MobileScanner(
        onDetect: (capture) {
          if (_done) return;
          for (final b in capture.barcodes) {
            final v = b.rawValue;
            if (v != null && v.startsWith('angebotsbot://')) {
              _done = true;
              Navigator.of(context).pop(v);
              return;
            }
          }
        },
      ),
    );
  }
}
