# Angebotsdaten für Offerbot

Stand 22.11.2026. Für dieselben Angebote eine freigegebene API oder einen Feed bevorzugen. Ein vorhandener Händlerzugang kann andere Daten abdecken als der örtliche Prospekt. Zugangsdaten aus Apps sind keine Quelle.

| Anbieter | Welche Daten sind zugänglich? | Zugang, Kosten und Einsatz |
|---|---|---|
| WooCommerce | Öffentliche Produktsuche des jeweiligen Shops | Ohne Anmeldung. Nutzungsbedingungen und Abruflimits des Shops gelten. In Offerbot als API-Quelle für Euro-Angebote wählbar. [Store API](https://developer.woocommerce.com/docs/apis/store-api/) |
| mydealz | Öffentlicher RSS-Feed mit Deal, Preis und Händler, soweit angegeben | Vorhandene RSS-Quelle ohne Schlüssel nutzen. Die Watchlist filtert nach Stichwörtern und Preis. |
| Keepa | Amazon-Preishistorie, Deals und Tracking | Eigener kostenpflichtiger Zugang mit API-Schlüssel und Token-Budget. Für einen freiwilligen Amazon-Abruf technisch geeignet. Für die Standardinstallation ist kein Zugang vorausgesetzt. [Tarife und Verbrauch](https://keepa.com/api-docs/plans-tokens.html) |
| kaufDA/Bonial | Bonial dokumentiert die Anlieferung von Angebotsdaten durch Kunden | In den geprüften Unterlagen ist kein öffentlicher Lesezugang für private regionale Preisabfragen mit Konditionen belegt. Regionale Begriffsseiten bleiben die Quelle. [Bonial-Spezifikation](https://corporate.bonial.com/hubfs/Specs_DynamicOffers_Stand_11_2022.pdf) |
| marktguru | Datenprodukte für Handel und Hersteller | Private API-Nutzung, Schlüsselvergabe und Preis sind ungeklärt. [Anbieterinformation](https://presse.marktguru.de/pressreleases/marktguru-verstaerkt-data-insights-business-und-holt-martin-langhauser-als-regional-sales-lead-3396110) |
| Publitas | Verwaltung eigener Publikationen | REST API v2 im Enterprise-Angebot. Diese Dokumentation belegt keinen Lesezugang für beliebige Händlerprospekte. [Publitas](https://support.publitas.com/rest-api-v2) |
| Kaufland | Produkte und Bestände des Online-Marktplatzes | Signierte Anfragen mit Händlerkonto. Regionale Filialangebote sind ein anderer Datenbestand. [Seller API](https://sellerapi.kaufland.com/?page=rest-api) |
| Geizhals | Preislisten der Shops zur Aufnahme in den Preisvergleich | Dokumentiert ist die Anlieferung. Konditionen für einen privaten Lesezugang zum vollständigen Preisbestand sind ungeklärt. [Preisübernahme](https://unternehmen.geizhals.at/haendler/technische-details/) |

## Trierer Stichprobe

Am 22.11.2026 lieferte die [Butter-Seite für Trier](https://www.kaufda.de/Trier/Angebote/Butter) im normalen Seitenabruf 16 Angebote, davon vier von Netto Marken-Discount. Der Parser erkannte acht Händler: Decathlon, E center, EDEKA, GLOBUS, Kaufland, Lidl, Netto Marken-Discount und REWE. Für den Watchlist-Eintrag „Butter“ ohne Preisgrenze hatten sieben davon Treffer. Decathlon erschien in den Quelldaten, aber ohne passenden Artikel.

Der Filter „Nur diese Händler“ prüft Teilnamen. „Netto“ findet „Netto Marken-Discount“. Das Seitenlimit greift danach. „Zusätzliche Händler bundesweit“ umfasst separate Händlerseiten außerhalb der regionalen Suche. Die Liste im PDF-Import liefert ausschließlich Vorschläge für manuell importierte Prospekte. Im Quellen-Test stehen die gefundenen Händler und diejenigen ohne Treffer für die aktuelle Watchlist. Die Stichprobe erfasst einen Suchbegriff und einen Zeitpunkt.
