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
    try:
        if mode == "ntfy":
            topic = (cfg.get("ntfy_topic") or "").strip()
            if not topic:
                raise NotifyError("Kein ntfy-Thema eingetragen")
            server = (cfg.get("ntfy_server") or "https://ntfy.sh").rstrip("/")
            body = {"topic": topic, "title": title, "message": message[:3900], "tags": ["shopping_cart"]}
            if click_url.startswith("http"):
                body["click"] = click_url
            r = requests.post(server, json=body, timeout=15)  # JSON-Variante: Umlaute im Titel kein Problem
        elif mode == "telegram":
            token, chat = _telegram_token(), (cfg.get("telegram_chat_id") or "").strip()
            if not token or not chat:
                raise NotifyError("Telegram: Bot-Token oder Chat-ID fehlt")
            r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", timeout=15,
                              json={"chat_id": chat, "text": f"{title}\n\n{message}"[:4000],
                                    "disable_web_page_preview": True})
        else:
            raise NotifyError(f"Unbekannte Art: {mode}")
    except requests.RequestException as e:
        LOG.warning("Handy-Benachrichtigung fehlgeschlagen: %s", e)
        raise NotifyError(f"Senden fehlgeschlagen: {e}") from e
    if r.status_code >= 400:
        LOG.warning("Handy-Benachrichtigung: HTTP %s %s", r.status_code, r.text[:200])
        raise NotifyError(f"Senden fehlgeschlagen: HTTP {r.status_code} {r.text[:150]}")
    LOG.info("Handy-Benachrichtigung gesendet (%s): %s", mode, title)
