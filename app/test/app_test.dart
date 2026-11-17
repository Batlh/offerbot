import 'package:angebotsbot/data/source.dart';
import 'package:angebotsbot/data/store.dart';
import 'package:angebotsbot/data/zettel.dart';
import 'package:angebotsbot/main.dart';
import 'package:angebotsbot/models.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Spielt den PC: hält einen eigenen Zettel und gleicht wie angebotsbot/core/db.py shopping_sync ab.
class FakeSource implements DataSource {
  final pcZettel = <String, ShopItem>{
    'o:a': ShopItem(
        sid: 'o:a', title: 'Kerrygold Butter 250 g', price: 1.69, merchant: 'Lidl', base: '6,76 €/kg',
        updated: DateTime.utc(2026, 11, 1)),
  };
  int geprueft = 0;
  int syncs = 0;

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
  Future<List<ShopItem>> zettelSync(List<ShopItem> items) async {
    syncs++;
    for (final i in items) {
      final old = pcZettel[i.sid];
      if (old == null || i.updated.isAfter(old.updated)) pcZettel[i.sid] = i;
    }
    return pcZettel.values.toList();
  }
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
    // Zettel kam beim Start per Abgleich vom PC, sortiert nach Kategorie
    expect(find.textContaining('Kühlregal'), findsWidgets);
    expect(find.textContaining('Lidl'), findsWidgets);
    await tester.tap(find.byType(Checkbox).first);
    await tester.pump(const Duration(seconds: 1));
    await tester.pumpAndSettle();
    expect(fake.pcZettel['o:a']!.done, isTrue); // Haken ist beim PC angekommen
    expect(find.textContaining('Im Wagen'), findsOneWidget);

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
    expect(find.text('Ohne PC nutzen – nur Einkaufsliste'), findsOneWidget);
  });

  testWidgets('Einkaufsliste ohne PC: eintippen, doppelt, abhaken, wischen', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final store = await Store.open();
    await tester.pumpWidget(AngebotsBotApp(store: store));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Ohne PC nutzen – nur Einkaufsliste'));
    await tester.pumpAndSettle();
    expect(find.text('Einkaufsliste'), findsOneWidget);

    Future<void> eintippen(String t) async {
      await tester.enterText(find.byType(TextField), t);
      await tester.testTextInput.receiveAction(TextInputAction.send);
      await tester.pumpAndSettle();
    }

    await eintippen('2 milch');
    await eintippen('500 g Hackfleisch');
    expect(find.text('2× Milch'), findsOneWidget);
    expect(find.text('500 g Hackfleisch'), findsOneWidget);
    expect(find.text('Kühlregal'), findsOneWidget);
    expect(find.text('Fleisch & Fisch'), findsOneWidget);

    await eintippen('Milch');
    expect(find.text('Steht schon auf der Liste'), findsOneWidget);
    expect(find.text('2× Milch'), findsOneWidget);

    await tester.tap(find.text('2× Milch'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Im Wagen (1)'), findsOneWidget);

    await tester.drag(find.text('500 g Hackfleisch'), const Offset(-600, 0));
    await tester.pumpAndSettle();
    expect(find.text('500 g Hackfleisch'), findsNothing);
    expect(find.text('Rückgängig'), findsOneWidget);

    // nach Neustart noch da (gespeichert auf dem Handy)
    final repo = ZettelRepo(store);
    expect(repo.items().map((x) => x.text).toList(), ['2× Milch']);
    expect(repo.items().first.done, isTrue);
    repo.dispose();
  });

  test('Menge und Kategorie erkennen', () {
    expect(splitQuantity('2 Milch'), ('2', 'Milch'));
    expect(splitQuantity('2x Milch'), ('2', 'Milch'));
    expect(splitQuantity('500g Hackfleisch'), ('500 g', 'Hackfleisch'));
    expect(splitQuantity('Milch 2x'), ('2', 'Milch'));
    expect(splitQuantity('2 Pck. Butter'), ('2 Pck.', 'Butter'));
    expect(splitQuantity('Cola 1,5'), ('', 'Cola 1,5'));
    expect(splitQuantity('7up'), ('', '7up'));
    expect(guessCategory('Reis'), 'Vorrat');
    expect(guessCategory('Vanilleeis'), 'Tiefkühl');
    expect(guessCategory('Hackfleisch gemischt'), 'Fleisch & Fisch');
    expect(guessCategory('Katzenstreu'), 'Tier');
    expect(guessCategory('Vollmilch'), 'Kühlregal');
    expect(guessCategory('Olivenöl'), 'Vorrat');
    expect(guessCategory('Irgendwas'), 'Sonstiges');
  });

  test('Abgleich: neuere Änderung gewinnt, Listen, Teilen', () async {
    SharedPreferences.setMockInitialValues({});
    final store = await Store.open();
    final repo = ZettelRepo(store, syncDelay: const Duration(hours: 1)); // Abgleich hier nur von Hand
    final fake = FakeSource();
    repo.source = fake;
    expect(await repo.sync(), isTrue);
    expect(repo.items().single.title, 'Kerrygold Butter 250 g');

    // Am PC abgehakt (neuer) → kommt aufs Handy
    fake.pcZettel['o:a'] = fake.pcZettel['o:a']!.copyWith(done: true, updated: DateTime.now().toUtc());
    await repo.sync();
    expect(repo.items().single.done, isTrue);

    // Alte Änderung vom PC verliert gegen die neuere auf dem Handy
    repo.toggle('o:a', false);
    final stale = repo.bySid('o:a')!.copyWith(done: true, updated: DateTime.utc(2000));
    repo.merge([stale], DateTime.now().toUtc());
    expect(repo.bySid('o:a')!.done, isFalse);

    // Weitere Liste
    expect(repo.createList('Metro'), isTrue);
    expect(repo.current, 'Metro');
    repo.add('3 Paprika');
    expect(repo.items().single.text, '3× Paprika');
    expect(repo.shareText(), contains('☐ 3× Paprika'));
    expect(repo.lists, ['Einkaufszettel', 'Metro']);
    await repo.sync();
    expect(fake.pcZettel.values.where((x) => x.liste == 'Metro').length, 1);
    expect(repo.renameList('Metro', 'Großeinkauf'), isTrue);
    expect(repo.items('Großeinkauf').single.title, 'Paprika');

    // Angebot auf die Liste, Vorschläge aus dem Verlauf
    final r = repo.addOffer(const Offer(uid: 'b', title: 'Rinderhack 500 g', price: 4.99, merchant: 'Aldi'));
    expect(r, AddResult.added);
    expect(repo.addOffer(const Offer(uid: 'b', title: 'Rinderhack 500 g')), AddResult.exists);
    repo.delete(repo.items().firstWhere((x) => x.title == 'Paprika').sid);
    expect(repo.suggestions('pap'), ['Paprika']);
    repo.dispose();
  });
}
