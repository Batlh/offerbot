"""Text aus Prospekt-PDFs holen: eingebetteter Text, sonst Texterkennung (OCR)."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from . import pdfwerk

_ocr_engine = None
_ocr_lock = threading.Lock()
MIN_TEXT = 60  # weniger Zeichen auf einer Seite → OCR versuchen


def ocr_available() -> bool:
    try:
        import rapidocr_onnxruntime  # noqa: F401
        return True
    except ImportError:
        return False


def _engine():
    global _ocr_engine
    with _ocr_lock:
        if _ocr_engine is None:
            from rapidocr_onnxruntime import RapidOCR
            _ocr_engine = RapidOCR()
    return _ocr_engine


def page_png(pdf: Path | str, page_no: int, zoom: float = 2.0) -> bytes:
    return pdfwerk.page_image(pdf, page_no, zoom)


def ocr_png(png: bytes) -> str:
    result, _ = _engine()(png)
    if not result:
        return ""
    # nach Zeilen sortieren (y), dann x
    boxes = []
    for box, text, score in result:
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        boxes.append((min(ys), max(ys), min(xs), text))
    boxes.sort(key=lambda b: (b[0], b[2]))
    lines: list[list[tuple]] = []
    for b in boxes:
        if lines and abs(lines[-1][0][0] - b[0]) < (b[1] - b[0]) * 0.6:
            lines[-1].append(b)
        else:
            lines.append([b])
    return "\n".join(" ".join(t[3] for t in sorted(line, key=lambda t: t[2])) for line in lines)


def index_pdf(pdf: Path | str, use_ocr: bool = True, progress: Callable[[int, int], None] | None = None,
              cancel: Callable[[], bool] = lambda: False) -> list[tuple[int, str, bool]]:
    out: list[tuple[int, str, bool]] = []
    can_ocr = use_ocr and ocr_available()
    for i, n, text, png in pdfwerk.pages(pdf, zoom=2.0):
            if cancel():
                break
            used_ocr = False
            if len(text.strip()) < MIN_TEXT and can_ocr:
                try:
                    text = ocr_png(png())
                    used_ocr = True
                except Exception as e:  # OCR-Fehler auf einer Seite nicht fatal
                    text = text + f"\n[OCR-Fehler: {e}]"
            out.append((i, text, used_ocr))
            if progress:
                progress(i, n)
    return out
