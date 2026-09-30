"""Regenerate the PDF regression corpus (dev-only; outputs are committed).

    python backend/tests/fixtures/pdf/generate.py

Needs reportlab + Pillow + pypdf and a CJK TTF (Windows SimHei). Tests only
read the committed files, so CI does not need any of these.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _canvas(path: Path):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    pdfmetrics.registerFont(TTFont("CJK", "C:/Windows/Fonts/simhei.ttf"))
    return canvas.Canvas(str(path), pagesize=A4), A4


def _lines(c, lines: list[str], size: int = 12, top: float = 780) -> None:
    c.setFont("CJK", size)
    y = top
    for line in lines:
        c.drawString(60, y, line)
        y -= size * 1.6


def build() -> dict:
    manifest: dict[str, dict] = {}

    c, _ = _canvas(HERE / "normal.pdf")
    c.setTitle("Normal Resume")
    _lines(c, ["Zhang San - Backend Engineer", "Built an order service handling 3000 QPS with Redis caching."])
    c.showPage(); c.save()
    manifest["normal.pdf"] = {"pages": 1, "expect": {1: ["Backend Engineer", "3000 QPS"]}}

    c, _ = _canvas(HERE / "multipage.pdf")
    for i in range(1, 4):
        _lines(c, [f"Page {i} marker PAGE-{i}", f"Section {i}: distributed systems notes."])
        c.showPage()
    c.save()
    manifest["multipage.pdf"] = {"pages": 3, "expect": {i: [f"PAGE-{i}"] for i in range(1, 4)}}

    c, _ = _canvas(HERE / "chinese.pdf")
    _lines(c, ["张三 后端开发工程师", "负责订单系统重构，把接口延迟从 800 毫秒降到 120 毫秒。", "熟悉消息队列、缓存一致性。"])
    c.showPage(); c.save()
    manifest["chinese.pdf"] = {"pages": 1, "expect": {1: ["后端开发工程师", "订单系统重构", "缓存一致性"]}}

    c, _ = _canvas(HERE / "english.pdf")
    _lines(c, ["Experience", "Designed a rate limiter for the public API gateway.", "Migrated batch jobs to Kafka streams."])
    c.showPage(); c.save()
    manifest["english.pdf"] = {"pages": 1, "expect": {1: ["rate limiter", "Kafka streams"]}}

    c, _ = _canvas(HERE / "mixed.pdf")
    _lines(c, ["项目：RAG pipeline 检索增强", "用 Redis + Kafka 做 exactly once 消费，QPS 提升 3 倍。"])
    c.showPage(); c.save()
    manifest["mixed.pdf"] = {"pages": 1, "expect": {1: ["RAG pipeline", "exactly once", "检索增强"]}}

    c, _ = _canvas(HERE / "table.pdf")
    c.setFont("CJK", 11)
    rows = [("技能", "年限", "等级"), ("Python", "5", "精通"), ("Go", "2", "熟练"), ("Redis", "4", "精通")]
    for r, row in enumerate(rows):
        for col, cell in enumerate(row):
            x, y = 60 + col * 120, 760 - r * 24
            c.rect(x - 4, y - 7, 120, 24)
            c.drawString(x, y, cell)
    c.showPage(); c.save()
    manifest["table.pdf"] = {"pages": 1, "expect": {1: ["技能", "Python", "精通"]}}

    c, _ = _canvas(HERE / "empty_page.pdf")
    _lines(c, ["First page has text FIRST-PAGE"])
    c.showPage()
    c.showPage()  # page 2 intentionally blank
    _lines(c, ["Third page has text THIRD-PAGE"])
    c.showPage(); c.save()
    manifest["empty_page.pdf"] = {"pages": 3, "expect": {1: ["FIRST-PAGE"], 3: ["THIRD-PAGE"]}, "empty_pages": [2]}

    # Scanned: an image of text, no text layer.
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1240, 1754), "white")
    draw = ImageDraw.Draw(img)
    draw.text((100, 100), "SCANNED RESUME 扫描件", fill="black", font=ImageFont.truetype("C:/Windows/Fonts/simhei.ttf", 48))
    img.save(HERE / "scanned.pdf", "PDF", resolution=150)
    manifest["scanned.pdf"] = {"pages": 1, "expect": {}, "empty_pages": [1], "scanned": True}

    # Damaged: a valid header followed by a truncated body.
    good = (HERE / "normal.pdf").read_bytes()
    (HERE / "damaged.pdf").write_bytes(good[: len(good) // 3])
    manifest["damaged.pdf"] = {"damaged": True}

    # Encrypted with a user password (unsupported on purpose).
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for page in PdfReader(str(HERE / "normal.pdf")).pages:
        writer.add_page(page)
    writer.encrypt(user_password="secret", owner_password="owner", algorithm="RC4-128")
    buf = io.BytesIO()
    writer.write(buf)
    (HERE / "encrypted.pdf").write_bytes(buf.getvalue())
    manifest["encrypted.pdf"] = {"encrypted": True}

    (HERE / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
