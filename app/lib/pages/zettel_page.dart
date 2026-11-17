import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import '../data/zettel.dart';
import '../main.dart';
import '../models.dart';
import 'prospekte_page.dart';

/// Einkaufsliste: liegt auf dem Handy, funktioniert ohne PC und WLAN und wird mit dem PC abgeglichen,
/// sobald er erreichbar ist. Unten eintippen („2 Milch“), antippen = abhaken, wischen = löschen,
/// lange drücken = bearbeiten.
class ZettelPage extends StatefulWidget {
  const ZettelPage({super.key});

  @override
  State<ZettelPage> createState() => _ZettelPageState();
}

class _ZettelPageState extends State<ZettelPage> {
  final _ctrl = TextEditingController();
  final _focus = FocusNode();

  @override
  void initState() {
    super.initState();
    _ctrl.addListener(() {
      if (mounted) setState(() {}); // Vorschläge passend zum Getippten
    });
  }

  @override
  void dispose() {
    _ctrl.dispose();
    _focus.dispose();
    super.dispose();
  }

  void _snack(String text, {SnackBarAction? action}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(text), action: action, duration: const Duration(seconds: 3)));
  }

  void _submit(ZettelRepo repo, [String? text]) {
    final t = (text ?? _ctrl.text).trim();
    if (t.isEmpty) return;
    final r = repo.add(t);
    switch (r) {
      case AddResult.exists:
        _snack('Steht schon auf der Liste');
      case AddResult.reopened:
        _snack('Wieder auf der Liste');
      default:
        break;
    }
    _ctrl.clear();
    _focus.requestFocus();
  }

  Future<String?> _askText(String title, {String initial = '', String hint = ''}) {
    final c = TextEditingController(text: initial);
    return showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: TextField(
          controller: c,
          autofocus: true,
          decoration: InputDecoration(hintText: hint),
          onSubmitted: (v) => Navigator.pop(ctx, v.trim()),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Abbrechen')),
          FilledButton(onPressed: () => Navigator.pop(ctx, c.text.trim()), child: const Text('OK')),
        ],
      ),
    );
  }

  Future<bool> _confirm(String text) async =>
      await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          content: Text(text),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Abbrechen')),
            FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Ja')),
          ],
        ),
      ) ??
      false;

  Future<void> _menu(String v, ZettelRepo repo) async {
    switch (v) {
      case 'whatsapp': {
        final text = repo.shareText();
        await launchUrl(Uri.parse('https://wa.me/?text=${Uri.encodeComponent(text)}'),
            mode: LaunchMode.externalApplication);
      }
      case 'kopieren': {
        await Clipboard.setData(ClipboardData(text: repo.shareText()));
        _snack('Liste kopiert – zum Einfügen z. B. in einen Chat');
      }
      case 'erledigte': {
        final n = repo.removeDone();
        _snack(n == 0 ? 'Nichts abgehakt' : '$n erledigte entfernt');
      }
      case 'neu': {
        final name = await _askText('Neue Liste', hint: 'z. B. Metro, Drogerie, Party');
        if (name != null && name.isNotEmpty && !repo.createList(name)) _snack('Diese Liste gibt es schon');
      }
      case 'umbenennen': {
        final name = await _askText('Liste umbenennen', initial: repo.current);
        if (name != null && name.isNotEmpty && name != repo.current && !repo.renameList(repo.current, name)) {
          _snack('Diese Liste gibt es schon');
        }
      }
      case 'leeren': {
        if (await _confirm('Alle Einträge von „${repo.current}“ löschen?')) repo.clearList();
      }
      case 'loeschen': {
        if (await _confirm('Liste „${repo.current}“ mit allen Einträgen löschen?')) repo.deleteList(repo.current);
      }
      case 'abgleich': {
        final ok = await repo.sync();
        if (mounted && !ok && repo.syncError.isNotEmpty) _snack(repo.syncError);
      }
    }
  }

  Future<void> _edit(ShopItem it) async {
    final repo = AppScope.of(context).zettel;
    final changed = await showModalBottomSheet<ShopItem>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => _EditSheet(item: it, category: repo.categoryOf(it), lists: repo.lists, shops: repo.shops),
    );
    if (changed == null || !mounted) return;
    if (changed.deleted) {
      _delete(repo, it);
    } else {
      repo.update(changed);
    }
  }

  void _delete(ZettelRepo repo, ShopItem it) {
    final prev = repo.delete(it.sid);
    if (prev == null) return;
    _snack('„${it.title}“ gelöscht',
        action: SnackBarAction(label: 'Rückgängig', onPressed: () => repo.restore(prev)));
  }

  @override
  Widget build(BuildContext context) {
    final repo = AppScope.of(context).zettel;
    return ListenableBuilder(listenable: repo, builder: (context, _) => _body(context, repo));
  }

  Widget _body(BuildContext context, ZettelRepo repo) {
    final theme = Theme.of(context);
    final all = repo.items();
    final open = all.where((x) => !x.done).toList();
    final done = all.where((x) => x.done).toList()..sort((a, b) => a.title.compareTo(b.title));
    final groups = repo.grouped(open);
    final sugg = (_focus.hasFocus || _ctrl.text.isNotEmpty) ? repo.suggestions(_ctrl.text) : const <String>[];
    final byLaden = repo.sortMode == 'laden';

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 4, 4, 0),
          child: Row(
            children: [
              Expanded(
                child: PopupMenuButton<String>(
                  tooltip: 'Liste wählen',
                  onSelected: (v) {
                    if (v == '+neu') {
                      _menu('neu', repo);
                    } else {
                      repo.setCurrent(v);
                    }
                  },
                  itemBuilder: (_) => [
                    for (final l in repo.lists)
                      CheckedPopupMenuItem(value: l, checked: l == repo.current, child: Text('$l (${repo.openCount(l)})')),
                    const PopupMenuDivider(),
                    const PopupMenuItem(value: '+neu', child: Text('Neue Liste …')),
                  ],
                  child: Row(mainAxisSize: MainAxisSize.min, children: [
                    Flexible(
                      child: Text(repo.current, style: theme.textTheme.titleMedium, overflow: TextOverflow.ellipsis),
                    ),
                    const Icon(Icons.arrow_drop_down),
                  ]),
                ),
              ),
              IconButton(
                tooltip: byLaden ? 'Nach Laden sortiert – umschalten auf Kategorie' : 'Nach Kategorie sortiert – umschalten auf Laden',
                icon: Icon(byLaden ? Icons.storefront_outlined : Icons.category_outlined),
                onPressed: () => repo.setSortMode(byLaden ? 'kategorie' : 'laden'),
              ),
              PopupMenuButton<String>(
                tooltip: 'Mehr',
                onSelected: (v) => _menu(v, repo),
                itemBuilder: (_) => [
                  const PopupMenuItem(value: 'whatsapp', child: Text('Per WhatsApp teilen')),
                  const PopupMenuItem(value: 'kopieren', child: Text('Als Text kopieren')),
                  const PopupMenuItem(value: 'erledigte', child: Text('Erledigte entfernen')),
                  const PopupMenuDivider(),
                  const PopupMenuItem(value: 'neu', child: Text('Neue Liste')),
                  if (repo.current != defaultList)
                    const PopupMenuItem(value: 'umbenennen', child: Text('Liste umbenennen')),
                  const PopupMenuItem(value: 'leeren', child: Text('Liste leeren')),
                  if (repo.current != defaultList) const PopupMenuItem(value: 'loeschen', child: Text('Liste löschen')),
                  if (repo.hasPc) const PopupMenuItem(value: 'abgleich', child: Text('Jetzt mit PC abgleichen')),
                ],
              ),
            ],
          ),
        ),
        _SyncLine(repo: repo),
        Expanded(
          child: RefreshIndicator(
            onRefresh: () async {
              if (repo.hasPc) await repo.sync();
            },
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              children: [
                if (all.isEmpty)
                  const Padding(
                    padding: EdgeInsets.all(32),
                    child: Center(
                      child: Text('Die Liste ist leer.\nUnten eintippen, z. B. „2 Milch“ oder „500 g Hackfleisch“.',
                          textAlign: TextAlign.center),
                    ),
                  ),
                for (final g in groups.entries) ...[
                  _Header(
                    text: g.key,
                    sum: g.value.fold<double>(0, (s, x) => s + (x.price ?? 0)),
                  ),
                  for (final it in g.value) _tile(repo, it, byLaden),
                ],
                if (done.isNotEmpty) ...[
                  Padding(
                    padding: const EdgeInsets.fromLTRB(16, 16, 4, 0),
                    child: Row(children: [
                      Expanded(child: Text('Im Wagen (${done.length})', style: theme.textTheme.titleSmall)),
                      TextButton(onPressed: () => _menu('erledigte', repo), child: const Text('Entfernen')),
                    ]),
                  ),
                  for (final it in done) _tile(repo, it, byLaden),
                ],
                const SizedBox(height: 16),
              ],
            ),
          ),
        ),
        if (sugg.isNotEmpty)
          SizedBox(
            height: 44,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 8),
              children: [
                for (final s in sugg)
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 4),
                    child: ActionChip(
                      label: Text(s),
                      onPressed: () {
                        final qty = splitQuantity(_ctrl.text).$1;
                        _submit(repo, qty.isEmpty ? s : '$qty $s');
                      },
                    ),
                  ),
              ],
            ),
          ),
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(12, 4, 8, 8),
            child: Row(children: [
              Expanded(
                child: TextField(
                  controller: _ctrl,
                  focusNode: _focus,
                  textInputAction: TextInputAction.send,
                  textCapitalization: TextCapitalization.sentences,
                  decoration: const InputDecoration(
                    hintText: 'Artikel hinzufügen, z. B. 2 Milch',
                    border: OutlineInputBorder(),
                    isDense: true,
                    prefixIcon: Icon(Icons.add_shopping_cart),
                  ),
                  onTap: () => setState(() {}), // Vorschläge zeigen
                  onSubmitted: (_) => _submit(repo),
                  onEditingComplete: () {}, // Tastatur bleibt offen für den nächsten Artikel
                ),
              ),
              const SizedBox(width: 4),
              IconButton.filled(
                tooltip: 'Hinzufügen',
                onPressed: () => _submit(repo),
                icon: const Icon(Icons.add),
              ),
            ]),
          ),
        ),
      ],
    );
  }

  Widget _tile(ZettelRepo repo, ShopItem it, bool byLaden) {
    final scheme = Theme.of(context).colorScheme;
    final sub = [
      if (byLaden) repo.categoryOf(it) else if (it.merchant.isNotEmpty) it.merchant,
      if (it.base.isNotEmpty) it.base,
      if (it.validTo.isNotEmpty) 'bis ${it.validTo}',
    ].join(' · ');
    return Dismissible(
      key: ValueKey('z-${it.sid}'),
      background: Container(
        color: scheme.errorContainer,
        alignment: Alignment.centerLeft,
        padding: const EdgeInsets.symmetric(horizontal: 20),
        child: Icon(Icons.delete_outline, color: scheme.onErrorContainer),
      ),
      secondaryBackground: Container(
        color: scheme.errorContainer,
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.symmetric(horizontal: 20),
        child: Icon(Icons.delete_outline, color: scheme.onErrorContainer),
      ),
      onDismissed: (_) => _delete(repo, it),
      child: ListTile(
        dense: true,
        leading: Checkbox(value: it.done, onChanged: (v) => repo.toggle(it.sid, v ?? false)),
        title: Text(
          it.text,
          style: TextStyle(
            fontSize: 16,
            decoration: it.done ? TextDecoration.lineThrough : null,
            color: it.done ? scheme.outline : null,
          ),
        ),
        subtitle: sub.isEmpty ? null : Text(sub, maxLines: 2, overflow: TextOverflow.ellipsis),
        trailing: it.price == null ? null : Text(euro(it.price)),
        onTap: () => repo.toggle(it.sid, !it.done),
        onLongPress: () => _edit(it),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  final String text;
  final double sum;
  const _Header({required this.text, required this.sum});

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 14, 16, 2),
        child: Text(sum > 0 ? '$text · ${euro(sum)}' : text,
            style: Theme.of(context).textTheme.titleSmall?.copyWith(color: Theme.of(context).colorScheme.primary)),
      );
}

class _SyncLine extends StatelessWidget {
  final ZettelRepo repo;
  const _SyncLine({required this.repo});

  @override
  Widget build(BuildContext context) {
    final style = Theme.of(context).textTheme.bodySmall;
    var text = '';
    var icon = Icons.sync;
    switch (repo.syncState) {
      case SyncState.aus:
        return const SizedBox.shrink();
      case SyncState.laeuft:
        text = 'Gleiche mit dem PC ab …';
        icon = Icons.sync;
      case SyncState.ok:
        final t = repo.lastSync;
        text = t == null
            ? 'Mit dem PC abgeglichen'
            : 'Mit dem PC abgeglichen um ${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';
        icon = Icons.cloud_done_outlined;
      case SyncState.fehler:
        text = 'PC nicht erreichbar – Änderungen bleiben auf dem Handy und werden später abgeglichen';
        icon = Icons.cloud_off;
    }
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 4),
      child: Row(children: [
        Icon(icon, size: 14),
        const SizedBox(width: 6),
        Expanded(child: Text(text, style: style)),
      ]),
    );
  }
}

/// Eintrag bearbeiten: Name, Menge, Kategorie, Laden, Preis, Liste. Gibt den geänderten Eintrag zurück
/// (deleted = true heißt löschen).
class _EditSheet extends StatefulWidget {
  final ShopItem item;
  final String category;
  final List<String> lists;
  final List<String> shops;
  const _EditSheet({required this.item, required this.category, required this.lists, required this.shops});

  @override
  State<_EditSheet> createState() => _EditSheetState();
}

class _EditSheetState extends State<_EditSheet> {
  late final _title = TextEditingController(text: widget.item.title);
  late final _qty = TextEditingController(text: widget.item.qty);
  late final _shop = TextEditingController(text: widget.item.merchant);
  late final _price = TextEditingController(
      text: widget.item.price == null ? '' : widget.item.price!.toStringAsFixed(2).replaceAll('.', ','));
  late String _cat = kategorieNamen.contains(widget.category) ? widget.category : sonstiges;
  late String _liste = widget.item.liste;

  @override
  void dispose() {
    _title.dispose();
    _qty.dispose();
    _shop.dispose();
    _price.dispose();
    super.dispose();
  }

  void _save() {
    final title = _title.text.trim();
    if (title.isEmpty) return;
    final p = double.tryParse(_price.text.trim().replaceAll('€', '').replaceAll(',', '.').trim());
    Navigator.pop(
      context,
      widget.item.copyWith(
        title: title,
        qty: _qty.text.trim(),
        category: _cat,
        merchant: _shop.text.trim() == 'Sonstige' ? '' : _shop.text.trim(),
        price: p,
        clearPrice: p == null,
        liste: _liste,
      ),
    );
  }

  Future<void> _open() async {
    final url = widget.item.url;
    if (url.startsWith('prospekt:')) {
      final parts = url.substring(9).split('#');
      final id = int.tryParse(parts[0]);
      if (id == null) return;
      await Navigator.of(context).push(MaterialPageRoute(
          builder: (_) => ProspektViewer(
              prospektId: id, startPage: int.tryParse(parts.length > 1 ? parts[1] : '') ?? 1, title: widget.item.shop)));
    } else if (url.startsWith('http')) {
      await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
    }
  }

  @override
  Widget build(BuildContext context) {
    final hasPc = AppScope.of(context).hasPc;
    final url = widget.item.url;
    final canOpen = url.startsWith('http') || (url.startsWith('prospekt:') && hasPc);
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 0, 20, MediaQuery.of(context).viewInsets.bottom + 20),
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextField(controller: _title, decoration: const InputDecoration(labelText: 'Artikel')),
            Row(children: [
              Expanded(
                child: TextField(controller: _qty, decoration: const InputDecoration(labelText: 'Menge (z. B. 2 oder 500 g)')),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: TextField(
                  controller: _price,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(labelText: 'Preis (€)'),
                ),
              ),
            ]),
            const SizedBox(height: 12),
            const Text('Kategorie', style: TextStyle(fontSize: 12)),
            DropdownButton<String>(
              isExpanded: true,
              value: _cat,
              items: [for (final k in kategorieNamen) DropdownMenuItem(value: k, child: Text(k))],
              onChanged: (v) => setState(() => _cat = v ?? _cat),
            ),
            TextField(controller: _shop, decoration: const InputDecoration(labelText: 'Laden (optional)')),
            if (widget.shops.isNotEmpty)
              Wrap(spacing: 6, children: [
                for (final s in widget.shops.take(8))
                  ActionChip(label: Text(s), onPressed: () => setState(() => _shop.text = s)),
              ]),
            if (widget.lists.length > 1) ...[
              const SizedBox(height: 12),
              const Text('Liste', style: TextStyle(fontSize: 12)),
              DropdownButton<String>(
                isExpanded: true,
                value: widget.lists.contains(_liste) ? _liste : widget.lists.first,
                items: [for (final l in widget.lists) DropdownMenuItem(value: l, child: Text(l))],
                onChanged: (v) => setState(() => _liste = v ?? _liste),
              ),
            ],
            const SizedBox(height: 16),
            Row(children: [
              TextButton.icon(
                onPressed: () => Navigator.pop(context, widget.item.copyWith(deleted: true)),
                icon: const Icon(Icons.delete_outline),
                label: const Text('Löschen'),
              ),
              if (canOpen) TextButton(onPressed: _open, child: const Text('Angebot öffnen')),
              const Spacer(),
              FilledButton(onPressed: _save, child: const Text('Speichern')),
            ]),
          ],
        ),
      ),
    );
  }
}
