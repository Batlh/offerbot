"""Öffentliche WooCommerce-Produktsuche für die Watchlist."""
from html import unescape
from urllib.parse import urlencode, urlsplit
from urllib.robotparser import RobotFileParser

from ..models import Offer
from ..net import FetchError
from .base import FieldSpec, SourceType, register


class StoreApiUnavailable(FetchError):
    """Der konfigurierte Shop stellt diesen Endpunkt nicht bereit."""


def run(ctx, source):
    return search(ctx, source, source.settings.get("shop", ""))


def search(ctx, source, shop):
    shop = shop.strip().rstrip("/")
    address = urlsplit(shop)
    if (address.scheme != "https" or not address.hostname or address.username is not None
            or address.password is not None or address.query or address.fragment):
        raise ValueError("Öffentliche HTTPS-Shopadresse ohne Zugangsdaten oder Abfrage angeben.")
    endpoint = shop + "/wp-json/wc/store/v1/products"
    robots = RobotFileParser()
    try:
        rules = ctx.fetcher.get(f"https://{address.netloc}/robots.txt")
    except FetchError as error:
        if not str(error).startswith("HTTP 404 "):
            raise
        rules = ""
    robots.parse(rules.splitlines())
    offers = []
    for watch in ctx.watch_for_search():
        if ctx.cancel():
            break
        if not watch.in_deals:
            continue
        url = endpoint + "?" + urlencode({"search": watch.search_text, "per_page": 50})
        if not robots.can_fetch(ctx.settings.get("user_agent") or "*", url):
            raise ValueError("Die robots.txt schließt diese Produktsuche aus.")
        try:
            products = ctx.fetcher.get(url, as_json=True)
        except FetchError as error:
            if str(error).startswith("HTTP 404 "):
                raise StoreApiUnavailable("WooCommerce Store API fehlt.") from error
            raise
        if not isinstance(products, list):
            raise ValueError("Die Store API hat keine Produktliste geliefert.")
        for product in products:
            prices = product.get("prices") or {}
            if prices.get("currency_code") != "EUR" or not product.get("name") or not product.get("permalink"):
                continue
            if not str(prices.get("price", "")).isdigit():
                continue
            scale = 10 ** int(prices["currency_minor_unit"])
            price = int(prices["price"]) / scale
            regular = str(prices.get("regular_price", ""))
            old = int(regular) / scale if regular.isdigit() else None
            offers.append(Offer(source_id=source.id, source_name=source.name, title=unescape(product["name"]),
                                url=product["permalink"], merchant=address.hostname, price=price,
                                old_price=old if old and old > price else None, watch_id=watch.id))
    return offers


register(SourceType(
    key="woocommerce_api", label="API – WooCommerce-Produktsuche", group="Deals",
    description="Sucht je aktivem Deal-Suchbegriff bis zu 50 Produkte über die öffentliche Store API. "
                "Übernimmt Europreise. Nur für Shops verwenden, die diesen Abruf erlauben.",
    fields=[FieldSpec("shop", "Shop-Adresse", help="HTTPS-Basisadresse des WooCommerce-Shops, ohne API-Schlüssel.")],
    run=run,
))
