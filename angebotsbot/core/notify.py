"""Benachrichtigungen aufs Handy: ntfy (App „ntfy“, kostenlos, ohne Konto) oder Telegram-Bot."""
from __future__ import annotations

import logging

import requests

LOG = logging.getLogger("angebotsbot.notify")


class NotifyError(Exception):
    pass


def _telegram_token() -> str:
    try:
        import keyring
        return keyring.get_password("AngebotsBot", "telegram") or ""
    except Exception:
        return ""


def set_telegram_token(token: str) -> bool:
    try:
        import keyring
        if token:
            keyring.set_password("AngebotsBot", "telegram", token)
        else:
            try:
                keyring.delete_password("AngebotsBot", "telegram")
            except Exception:
                pass
        return True
    except Exception:
        return False


def has_telegram_token() -> bool:
    return bool(_telegram_token())


def send(settings: dict, title: str, message: str, click_url: str = "") -> None:
    cfg = settings.get("phone") or {}
    mode = cfg.get("mode", "aus")
    if mode == "aus":
        return
    errors = []
    if mode in ("ntfy", "beide"):
        try:
            _send_ntfy(cfg, title, message, click_url)
        except NotifyError as e:
            errors.append(str(e))
    if mode in ("telegram", "beide"):
        try:
            _send_telegram(cfg, title, message)
        except NotifyError as e:
            errors.append(str(e))
    if mode not in ("ntfy", "telegram", "beide"):
        raise NotifyError(f"Unbekannte Art: {mode}")
    if errors:
        raise NotifyError("; ".join(errors))
    LOG.info("Handy-Benachrichtigung gesendet (%s): %s", mode, title)


def _post(url: str, **kw):
    try:
        r = requests.post(url, timeout=15, **kw)
    except requests.RequestException as e:
        LOG.warning("Handy-Benachrichtigung fehlgeschlagen: %s", e)
        raise NotifyError(f"Senden fehlgeschlagen: {e}") from e
    if r.status_code >= 400:
        LOG.warning("Handy-Benachrichtigung: HTTP %s %s", r.status_code, r.text[:200])
        raise NotifyError(f"Senden fehlgeschlagen: HTTP {r.status_code} {r.text[:150]}")
    return r


def _send_ntfy(cfg: dict, title: str, message: str, click_url: str) -> None:
    topic = (cfg.get("ntfy_topic") or "").strip()
    if not topic:
        raise NotifyError("Kein ntfy-Thema eingetragen")
    server = (cfg.get("ntfy_server") or "https://ntfy.sh").rstrip("/")
    body = {"topic": topic, "title": title, "message": message[:3900], "tags": ["shopping_cart"]}
    if click_url.startswith("http"):
        body["click"] = click_url
    _post(server, json=body)  # JSON-Variante: Umlaute im Titel kein Problem


def telegram_recipients(cfg: dict) -> list[str]:
    ids = [str(cfg.get("telegram_chat_id") or "").strip()] + [str(s["id"]) for s in cfg.get("telegram_subscribers", [])]
    out = []
    for i in ids:
        if i and i not in out:
            out.append(i)
    return out


def _send_telegram(cfg: dict, title: str, message: str) -> None:
    token = _telegram_token()
    chats = telegram_recipients(cfg)
    if not token:
        raise NotifyError("Telegram: Bot-Token fehlt")
    if not chats:
        raise NotifyError("Telegram: noch niemand angemeldet (/start <Code> an den Bot schicken)")
    for chat in chats:
        _post(f"https://api.telegram.org/bot{token}/sendMessage",
              json={"chat_id": chat, "text": f"{title}\n\n{message}"[:4000], "disable_web_page_preview": True})
