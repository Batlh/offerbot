"""PDF-Werkzeuge: öffnen, prüfen, Text holen, Seiten als Bild, Bilder zu PDF.

Grundlage sind pypdfium2 (PDFium, Apache-2.0/BSD-3-Clause) und Pillow (MIT-CMU). Damit bleibt die
verteilte EXE frei von AGPL-Bibliotheken (früher PyMuPDF).
"""
from __future__ import annotations

import io
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

PdfQuelle = Path | str | bytes


def _open(src: PdfQuelle) -> pdfium.PdfDocument:
    if isinstance(src, (bytes, bytearray)) and not bytes(src[:5]).startswith(b"%PDF-"):
        raise ValueError("Die Datei ist keine PDF.")
    try:
        return pdfium.PdfDocument(bytes(src) if isinstance(src, bytearray) else src)
    except pdfium.PdfiumError as e:
        if "password" in str(e).lower():
            raise ValueError("Die PDF ist mit einem Passwort geschützt.") from e
        raise ValueError(f"Die PDF ist nicht lesbar ({e}).") from e


def page_count(src: PdfQuelle) -> int:
    """Seitenzahl; ValueError bei kaputter, verschlüsselter oder leerer PDF."""
    with _open(src) as pdf:
        n = len(pdf)
    if not n:
        raise ValueError("Die PDF enthält keine Seiten.")
    return n


def _render(pdf: pdfium.PdfDocument, index: int, zoom: float) -> Image.Image:
    page = pdf[index]
    try:
        return page.render(scale=zoom).to_pil().convert("RGB")
    finally:
        page.close()


def _text(pdf: pdfium.PdfDocument, index: int) -> str:
    page = pdf[index]
    try:
        textpage = page.get_textpage()
        try:
            return textpage.get_text_range().replace("\r\n", "\n").replace("\r", "\n")
        finally:
            textpage.close()
    finally:
        page.close()


def _encode(image: Image.Image, fmt: str, **kw) -> bytes:
    out = io.BytesIO()
    image.save(out, fmt, **kw)
    return out.getvalue()


def page_image(src: PdfQuelle, page_no: int, zoom: float = 2.0, fmt: str = "PNG", **kw) -> bytes:
    """Seite (1-basiert) als PNG oder JPEG."""
    with _open(src) as pdf:
        return _encode(_render(pdf, page_no - 1, zoom), fmt, **kw)


def pages(src: PdfQuelle, zoom: float = 2.0):
    """Je Seite (Nummer, Seitenzahl, Text, Funktion → PNG der Seite)."""
    with _open(src) as pdf:
        n = len(pdf)
        for i in range(n):
            yield i + 1, n, _text(pdf, i), lambda i=i: _encode(_render(pdf, i, zoom), "PNG")


def images_to_pdf(images: list[bytes], target: Path | None = None) -> bytes:
    """Bilder (JPEG unverändert übernommen, andere Formate verlustfrei) als PDF, eine Seite je Bild."""
    pdf = pdfium.PdfDocument.new()
    try:
        for data in images:
            with Image.open(io.BytesIO(data)) as im:
                width, height = im.size
                fmt = im.format
                bitmap_source = None if fmt == "JPEG" else im.convert("RGB")
            obj = pdfium.PdfImage.new(pdf)
            if bitmap_source is None:
                obj.load_jpeg(io.BytesIO(data), inline=True)
            else:
                obj.set_bitmap(pdfium.PdfBitmap.from_pil(bitmap_source))
            obj.set_matrix(pdfium.PdfMatrix().scale(width, height))
            page = pdf.new_page(width, height)
            page.insert_obj(obj)
            page.gen_content()
            page.close()
        out = io.BytesIO()
        pdf.save(out)
    finally:
        pdf.close()
    data = out.getvalue()
    if target is not None:
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return data
