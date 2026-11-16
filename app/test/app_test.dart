import 'package:angebotsbot/data/source.dart';
import 'package:angebotsbot/data/store.dart';
import 'package:angebotsbot/main.dart';
import 'package:angebotsbot/models.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class FakeSource implements DataSource {
  final zettelItems = <ShopItem>[
    const ShopItem(id: 1, title: 'Kerrygold Butter 250 g', price: 1.69, merchant: 'Lidl', base: '6,76 €/kg'),
  ];
  int geprueft = 0;

  @override
  Map<String, String> get bildHeader => const {};
  @override
  Future<Status> status() async => const Status(version: '1.9.0', unread: 1);
  @override
  Future<List<Offer>> treffer({bool nurUngelesen = false}) async => [
        const Offer(uid: 'a', title: 'Kerrygold Butter 250 g', price: 1.69, oldPrice: 1.99, refPrice: 1.49,
            merchant: 'Lidl', base: '6,76 €/kg', validTo: '21.11.', watchName: 'Butter', seen: false),
      ];
  @override
  Future<void> gelesen(List<String> uids, {bool alle = false}) async {}
  @override
  Future<List<Offer>> suche(String text) async => [];
  @override
  Future<List<ShopItem>> zettel() async => zettelItems;
  @override
  Future<void> zettelHinzufuegen({String? uid, String? titel}) async {}
  @override
  Future<void> zettelErledigt(int id, bool erledigt) async {}
  @override
  Future<void> zettelLoeschen(int id) async {}
  @override
  Future<List<WatchEntry>> watchlist() async => [const WatchEntry(id: 'w1', name: 'Butter', maxPrice: 1.5)];
  @override
  Future<WatchEntry> watchSpeichern(WatchEntry w) async => w;
  @override
  Future<void> watchLoeschen(String id) async {}
  @override
  Future<List<Prospekt>> prospekte() async => [const Prospekt(id: 1, retailer: 'Lidl', title: 'Aktionsprospekt', pages: 3)];
  @override
  String seitenBild(int prospektId, int seite) => 'http://127.0.0.1:1/x.jpg';
  @override
  Future<void> pruefen() async => geprueft++;
  @override
  Future<List<Offer>> amazon(String watchId) async => [];
}

void main() {
  test('QR-Code wird gelesen', () {
    final c = Connection.parse('angebotsbot://verbinden?url=http://192.168.1.20:8765&key=abc_123');
    expect(c, isNotNull);
    expect(c!.url, 'http://192.168.1.20:8765');
    expect(c.key, 'abc_123');
    expect(Connection.parse('https://example.com'), isNull);
  });

  test('JSON vom PC und Preis-Check', () {
    final o = Offer.fromJson({
      'uid': 'u', 'title': 'Butter', 'price': 1.69, 'ref_price': 1.49, 'merchant': 'Lidl',
      'prospekt_id': 3, 'page': 7, 'base': '6,76 €/kg', 'valid_to': '21.11.', 'seen': false,
    });
    expect(o.prospektId, 3);
    expect(o.page, 7);
    expect(o.priceCheck, startsWith('✘ 13 %'));
    expect(o.validText, 'bis 21.11.');
    expect(euro(1.5), '1,50 €');
    final w = WatchEntry.fromJson({'id': 'x', 'name': 'Kaffee', 'max_price': 9.99, 'in_prospekte': true});
    expect(w.toJson()['max_price'], 9.99);
    expect(w.inProspekte, isTrue);
  });

  testWidgets('App zeigt Treffer, Zettel und Prüfen', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final store = await Store.open();
    final fake = FakeSource();
    await tester.pumpWidget(AngebotsBotApp(store: store, source: fake));
    await tester.pumpAndSettle();
    expect(find.text('Kerrygold Butter 250 g'), findsWidgets);
    expect(find.textContaining('6,76 €/kg'), findsWidgets);
    expect(find.text('1,69 €'), findsWidgets);

    await tester.tap(find.byIcon(Icons.refresh));
    await tester.pumpAndSettle();
    expect(fake.geprueft, 1);

    await tester.tap(find.text('Zettel'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Lidl ·'), findsWidgets);
    await tester.tap(find.byType(Checkbox).first);
    await tester.pumpAndSettle();
    expect(store.cachedZettel.first.done, isTrue);

    await tester.tap(find.text('Prospekte'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Aktionsprospekt'), findsWidgets);
  });

  testWidgets('Ohne Verbindung kommt die Einrichtung', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final store = await Store.open();
    await tester.pumpWidget(AngebotsBotApp(store: store));
    await tester.pumpAndSettle();
    expect(find.text('QR-Code scannen'), findsOneWidget);
  });
}
