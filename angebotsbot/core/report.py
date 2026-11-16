"""Treffer als CSV (Excel) und HTML exportieren."""
from __future__ import annotations

import csv
import html
from datetime import datetime
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
