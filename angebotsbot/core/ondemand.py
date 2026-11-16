"""Sofort-Suche auf Knopfdruck (nie automatisch nach Zeitplan).

Der Nutzer löst jede Suche selbst aus – ein einzelner Seitenaufruf, so wie im eigenen Browser.
Zeigt die Seite ein Captcha oder blockt, wird abgebrochen (nichts wird umgangen).
"""
from __future__ import annotations

import re
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from .models import Offer
from .net import FetchError
from .prices import parse_price

AMAZON_SOURCE = "amazon-suche"
CAPTCHA_HINTS = ("validatecaptcha", "geben sie die zeichen", "captcha", "robot check", "api-services-support@amazon")


def amazon_url(query: str) -> str:
    return "https://www.amazon.de/s?k=" + quote_plus(query)


def parse_amazon(html_text: str, include_sponsored: bool = False, max_results: int = 30) -> list[Offer]:
    soup = BeautifulSoup(html_text, "lxml")
    items = soup.select('div[data-component-type="s-search-result"]')
    if not items:
        low = html_text.lower()
        if any(h in low for h in CAPTCHA_HINTS):
            raise FetchError("Amazon zeigt eine Sicherheitsabfrage (Captcha) – bitte im Browser ansehen")
        return []
    out: list[Offer] = []
    for el in items:
        asin = el.get("data-asin") or ""
        if not asin:
            continue
        sponsored = el.select_one(".puis-sponsored-label-text, .s-sponsored-label-text") is not None
        if sponsored and not include_sponsored:
            continue
        h2 = el.select_one("h2")
        title = " ".join((h2.get_text(" ", strip=True) if h2 else "").split())
        if not title:
            continue
        price = None
        for p in el.select(".a-price"):
            if p.get("data-a-strike") or "a-text-price" in (p.get("class") or []):
                continue
            off = p.select_one(".a-offscreen")
            price = parse_price(off.get_text() if off else p.get_text())
            if price is not None:
                break
        info = []
        if price is None:  # nur andere Anbieter ("Andere Angebote … 29,99 €")
            sec = el.find(string=re.compile(r"Andere Angebote|Keine hervorgehobenen Angebote"))
            if sec:
                nxt = sec.find_parent().find_next("span", class_="a-color-base")
                if nxt:
                    price = parse_price(nxt.get_text())
                    info.append("nur andere Anbieter")
        strike = el.select_one('.a-price[data-a-strike="true"] .a-offscreen')
        old = parse_price(strike.get_text()) if strike else None
        if old is not None and strike.find_parent("div") and "UVP" in strike.find_parent("div").get_text():
            info.append("Streichpreis = UVP")
        unit = ""
        for sp in el.select("span.a-size-base.a-color-base"):
            tp = sp.select_one(".a-price.a-text-price .a-offscreen")
            txt = sp.get_text(" ", strip=True)
            if tp and "/" in txt:
                unit = f"{tp.get_text(strip=True).replace(chr(160), ' ')}/{txt.rsplit('/', 1)[-1].strip(' )')}"
                break
        badges = " ".join(b.get_text(" ", strip=True) for b in el.select(".a-badge-text"))
        if badges:
            info.insert(0, " ".join(badges.split()))
        coupon = el.select_one(".s-coupon-unclipped")
        if coupon:
            ctext = " ".join(coupon.get_text(" ", strip=True).split())
            pm = re.search(r"(\d+(?:,\d+)?)\s*%", ctext)
            if re.search(r"Abonnement|Spar-Abo", ctext, re.I) and pm and price:
                pct = float(pm.group(1).replace(",", "."))
                abo = round(price * (1 - pct / 100), 2)
                first = "1. Lieferung " if re.search(r"erste", ctext, re.I) else ""
                info.append(f"Spar-Abo {first}−{pm.group(1)} % ≈ {abo:.2f} €".replace(f"{abo:.2f}", f"{abo:.2f}".replace(".", ",")))
            else:
                info.append("Coupon: " + ctext)
        else:
            sm = el.find(string=re.compile(r"Spar-Abo", re.I))
            if sm:
                info.append(" ".join(sm.find_parent().get_text(" ", strip=True).split())[:80])
        if sponsored:
            info.append("Gesponsert")
        out.append(Offer(source_id=AMAZON_SOURCE, source_name="Amazon (Sofort-Suche)", kind="preis", title=title,
                         url=f"https://www.amazon.de/dp/{asin}", price=price,
                         old_price=old if old and price and old > price else None,
                         merchant="Amazon", unit_price=unit, info=" · ".join(info)))
        if len(out) >= max_results:
            break
    return out


def amazon_search(fetcher, query: str, use_browser: bool, include_sponsored: bool = False) -> list[Offer]:
    url = amazon_url(query)
    html_text = fetcher.render(url, wait_selector='div[data-component-type="s-search-result"]', wait_ms=800) \
        if use_browser else fetcher.get(url)
    return parse_amazon(html_text, include_sponsored)
