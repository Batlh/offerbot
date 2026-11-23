"""Treffer als CSV (Excel) und HTML exportieren."""
from __future__ import annotations

import csv
import html
import re
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

from .prices import fmt_price

COLS = [("ts", "Gefunden"), ("watch_name", "Watchlist"), ("title", "Angebot"), ("price", "Preis"),
        ("old_price", "Vorher"), ("merchant", "Händler"), ("valid_from", "Gültig ab"), ("valid_to", "Gültig bis"),
        ("unit_price", "Grundpreis"), ("source_name", "Quelle"), ("temperature", "Grad"), ("url", "Link"), ("info", "Info")]


def export(rows, folder: Path, stamp: bool = True) -> tuple[Path, Path]:
    folder.mkdir(parents=True, exist_ok=True)
    suffix = datetime.now().strftime("_%Y-%m-%d_%H%M") if stamp else ""
    csv_path = folder / f"treffer{suffix}.csv"
    html_path = folder / f"treffer{suffix}.html"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig: Excel erkennt Umlaute
        w = csv.writer(f, delimiter=";")
        w.writerow([c[1] for c in COLS])
        for r in rows:
            w.writerow([(f"{r[k]:.2f}".replace(".", ",") if k in ("price", "old_price") and r[k] is not None
                         else ("" if r[k] is None else r[k])) for k, _ in COLS])
    body = []
    for r in rows:
        link = r["url"] or ""
        a = f'<a href="{html.escape(link)}">öffnen</a>' if link.startswith("http") else html.escape(link)
        body.append("<tr>" + "".join([
            f"<td>{html.escape(str(r['ts'] or '')[:16].replace('T', ' '))}</td>",
            f"<td>{html.escape(r['watch_name'] or '')}</td>",
            f"<td>{html.escape(r['title'] or '')}</td>",
            f"<td class=n>{fmt_price(r['price'])}</td>",
            f"<td class=n><s>{fmt_price(r['old_price'])}</s></td>",
            f"<td>{html.escape(r['merchant'] or '')}</td>",
            f"<td>{html.escape((r['valid_from'] or '') + ('–' + r['valid_to'] if r['valid_to'] else ''))}</td>",
            f"<td>{html.escape(r['source_name'] or '')}</td>",
            f"<td>{a}</td>"]) + "</tr>")
    html_path.write_text(f"""<!doctype html><meta charset="utf-8"><title>AngebotsBot Treffer</title>
<style>body{{font-family:Segoe UI,Arial;margin:20px}}table{{border-collapse:collapse;width:100%}}
td,th{{border-bottom:1px solid #ddd;padding:6px;text-align:left;font-size:14px}}th{{background:#f3f3f3}}.n{{text-align:right;white-space:nowrap}}</style>
<h2>AngebotsBot – Treffer ({datetime.now():%d.%m.%Y %H:%M})</h2>
<table><tr><th>Gefunden</th><th>Watchlist</th><th>Angebot</th><th>Preis</th><th>Vorher</th><th>Händler</th><th>Gültig</th><th>Quelle</th><th>Link</th></tr>
{''.join(body)}</table>""", encoding="utf-8")
    return csv_path, html_path


# ---------------------------------------------------------------- Wochenbericht
def best_offers(db, watchlist, days: int = 8, top: int = 3) -> dict[str, list]:
    """Je Watchlist-Eintrag die günstigsten aktuellen Treffer (nach Grundpreis, sonst Preis)."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
    rows = [r for r in db.matches() if (r["last_seen"] or r["ts"] or "") >= cutoff
            and r["price"] is not None]
    out: dict[str, list] = {}
    for w in watchlist:
        items = [r for r in rows if r["watch_id"] == w.id]
        if not items:
            continue
        units = Counter(r["base_unit"] for r in items if r["base_unit"])
        main_unit = units.most_common(1)[0][0] if units else None

        def key(r):
            if main_unit and r["base_unit"] == main_unit and r["base_price"] is not None:
                return (0, r["base_price"])
            return (1, r["price"])
        seen, best = set(), []
        for r in sorted(items, key=key):
            k = (r["merchant"], (r["title"] or "").lower()[:60], r["price"])
            if k in seen:
                continue
            seen.add(k)
            best.append(r)
            if len(best) >= top:
                break
        out[w.name] = best
    return out


def weekly_report(db, watchlist, folder: Path) -> tuple[list[Path], str]:
    from .units import fmt_base
    folder.mkdir(parents=True, exist_ok=True)
    y, kw, _ = date.today().isocalendar()
    stem = f"Wochenbericht_KW{kw:02d}_{y}"
    best = best_offers(db, watchlist)
    winners = Counter(items[0]["merchant"] or "?" for items in best.values() if items)

    md = [f"# AngebotsBot – Wochenbericht KW {kw}/{y}", f"Erstellt: {datetime.now():%d.%m.%Y %H:%M}", ""]
    if winners:
        md.append("## Wo lohnt sich der Einkauf?")
        md += [f"- **{m}**: günstigster Anbieter bei {n} Eintrag/Einträgen" for m, n in winners.most_common()]
        md.append("")
    md.append("## Günstigste Angebote je Watchlist-Eintrag")
    rows_csv = []
    for name, items in best.items():
        md.append(f"### {name}")
        for i, r in enumerate(items, 1):
            base = fmt_base(r["base_price"], r["base_unit"])
            vf, vt = r["valid_from"] or "", r["valid_to"] or ""
            valid = f"{vf}–{vt}" if vf and vt else (f"bis {vt}" if vt else (f"ab {vf}" if vf else ""))
            src = r["info"] or r["source_name"] or ""
            md.append(f"{i}. **{fmt_price(r['price'])}**{f' ({base})' if base else ''} – {r['title']} · "
                      f"{r['merchant'] or '?'}{f' · gültig {valid}' if valid else ''}"
                      f"{' · ' + r['url'] if (r['url'] or '').startswith('http') else ''}")
            rows_csv.append([name, i, r["title"], f"{r['price']:.2f}".replace(".", ","), base, r["merchant"] or "",
                             valid, r["url"] or "", src])
        md.append("")
    if not best:
        md.append("Keine aktuellen Treffer – Watchlist prüfen oder Quellen abrufen.")
    md_path = folder / f"{stem}.md"
    md_path.write_text("\n".join(md), encoding="utf-8")
    csv_path = folder / f"{stem}.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f, delimiter=";")
        wr.writerow(["Watchlist", "Rang", "Angebot", "Preis", "Grundpreis", "Händler", "Gültig", "Link", "Info"])
        wr.writerows(rows_csv)
    html_path = folder / f"{stem}.html"
    body = []
    for line in md:
        t = html.escape(line)
        t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
        t = re.sub(r"(https?://\S+)", r'<a href="\1">Link</a>', t)
        if line.startswith("### "):
            body.append(f"<h3>{t[4:]}</h3>")
        elif line.startswith("## "):
            body.append(f"<h2>{t[3:]}</h2>")
        elif line.startswith("# "):
            body.append(f"<h1>{t[2:]}</h1>")
        elif line:
            body.append(f"<p>{t}</p>")
    html_path.write_text('<!doctype html><meta charset="utf-8"><title>Wochenbericht</title><style>'
                         'body{font-family:Segoe UI,Arial;max-width:900px;margin:24px auto;line-height:1.45}'
                         'h3{margin-bottom:4px}p{margin:3px 0}</style>' + "\n".join(body), encoding="utf-8")
    summary = "\n".join(f"{name}: {fmt_price(items[0]['price'])} bei {items[0]['merchant'] or '?'}"
                        for name, items in best.items() if items) or "Keine aktuellen Treffer"
    return [html_path, md_path, csv_path], summary
