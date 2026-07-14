"""Minimal PDF writer (stdlib only) — Latin-1 / WinAnsi for DE texts."""
from __future__ import annotations

from datetime import datetime


def _pdf_escape(text: str) -> str:
    raw = (text or "").encode("latin-1", "replace").decode("latin-1")
    return raw.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_text_pdf(
    *,
    title: str,
    subtitle: str | None,
    sections: list[tuple[str, list[str]]],
    footer: str | None = None,
) -> bytes:
    """Erzeugt ein einfaches mehrseitiges PDF mit Überschriften und Zeilen."""
    page_w, page_h = 595, 842  # A4
    margin = 50
    line_h = 16
    max_y = page_h - margin
    min_y = 60

    pages_content: list[list[str]] = []
    ops: list[str] = []
    y = max_y

    def new_page():
        nonlocal ops, y
        if ops:
            pages_content.append(ops)
        ops = []
        y = max_y

    def ensure_space(needed: float = line_h):
        nonlocal y
        if y - needed < min_y:
            new_page()

    def draw_text(text: str, size: int = 11, leading: float | None = None):
        nonlocal y
        lead = leading if leading is not None else size + 4
        ensure_space(lead)
        ops.append(f"BT /F1 {size} Tf {margin} {y:.1f} Td ({_pdf_escape(text)}) Tj ET")
        y -= lead

    def draw_rule():
        nonlocal y
        ensure_space(10)
        ops.append(f"{margin} {y:.1f} m {page_w - margin} {y:.1f} l S")
        y -= 12

    draw_text(title, size=16, leading=22)
    if subtitle:
        draw_text(subtitle, size=11, leading=16)
    draw_text(f"Erstellt: {datetime.now().strftime('%d.%m.%Y %H:%M')}", size=9, leading=14)
    draw_rule()

    for heading, lines in sections:
        ensure_space(28)
        draw_text(heading, size=12, leading=18)
        for line in lines:
            # wrap roughly at ~90 chars
            chunk = line or "—"
            while len(chunk) > 95:
                draw_text(chunk[:95], size=10, leading=14)
                chunk = chunk[95:]
            draw_text(chunk, size=10, leading=14)
        y -= 6

    if footer:
        ensure_space(30)
        draw_rule()
        draw_text(footer, size=9, leading=12)

    if ops:
        pages_content.append(ops)

    # Assemble PDF
    objects: list[bytes] = []

    def add_obj(body: str | bytes) -> int:
        if isinstance(body, str):
            body = body.encode("latin-1", "replace")
        objects.append(body)
        return len(objects)

    add_obj("<< /Type /Catalog /Pages 2 0 R >>")
    kids_placeholder = len(objects)  # obj 2 = Pages — filled later
    add_obj("PLACEHOLDER_PAGES")
    add_obj("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")

    page_obj_ids: list[int] = []
    for content_ops in pages_content:
        stream = "\n".join(content_ops).encode("latin-1", "replace")
        content_id = add_obj(
            f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1")
            + stream
            + b"\nendstream"
        )
        page_id = add_obj(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_w} {page_h}] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        )
        page_obj_ids.append(page_id)

    kids = " ".join(f"{i} 0 R" for i in page_obj_ids)
    objects[kids_placeholder] = (
        f"<< /Type /Pages /Kids [{kids}] /Count {len(page_obj_ids)} >>"
    ).encode("latin-1")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode("latin-1"))
        out.extend(obj if isinstance(obj, (bytes, bytearray)) else str(obj).encode("latin-1"))
        out.extend(b"\nendobj\n")
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    out.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF\n".encode("latin-1")
    )
    return bytes(out)
