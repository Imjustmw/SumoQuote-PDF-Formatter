# pdf_line_items.py
import fitz
import pytesseract
from PIL import Image
from io import BytesIO
import re

START_HEADING = "PREFERRED PACKAGE"
END_HEADINGS = [
    "AUTHORIZATION PAGE",
    "OPTIONAL ITEMS",
    "DRY ROT & EXTRA WORK",
]

TOTAL_PATTERNS = [
    r"FINAL PRICE\s*\$?\s*([0-9,]+\.\d{2})",
    r"\bTOTAL\s*\$?\s*([0-9,]+\.\d{2})",
    r"ADJUSTED SUBTOTAL\s*\$?\s*([0-9,]+\.\d{2})",
    r"QUOTE SUBTOTAL\s*\$?\s*([0-9,]+\.\d{2})",
]

NOISE_LINES = {
    "PREFERRED PACKAGE",
    "DESCRIPTION",
    "QUOTE SUBTOTAL",
    "ADJUSTED SUBTOTAL",
    "TOTAL",
    "AUTHORIZATION PAGE",
    "OPTIONAL ITEMS",
}

def _ocr_lines(page, dpi=150) -> list[str]:
    pix = page.get_pixmap(dpi=dpi)
    img = Image.open(BytesIO(pix.tobytes("png")))
    text = pytesseract.image_to_string(img)
    lines = [re.sub(r"\s+", " ", l).strip() for l in text.splitlines()]
    return [l for l in lines if l]

def _has_heading(lines: list[str], heading: str) -> bool:
    h = heading.strip().upper()
    for l in lines:
        lu = l.upper().strip().strip(":")
        if lu == h:
            return True
    return False

def _find_total(text_upper: str) -> float | None:
    for pat in TOTAL_PATTERNS:
        m = re.search(pat, text_upper)
        if m:
            return float(m.group(1).replace(",", ""))
    return None

def extract_preferred_package_items(pdf_path: str):
    """
    Returns: (items, extracted_total)
    items are compatible with process_line_items()
    """
    doc = fitz.open(pdf_path)

    # OCR pass but only keep pages that matter
    page_lines = []
    page_text_upper = []

    for i in range(len(doc)):
        lines = _ocr_lines(doc[i], dpi=150)
        page_lines.append(lines)
        page_text_upper.append("\n".join(lines).upper())

    # Find preferred package start page
    start_page = None
    for i, lines in enumerate(page_lines):
        if _has_heading(lines, START_HEADING):
            start_page = i
            break

    if start_page is None:
        print("⚠️ Preferred Package heading not found.")
        return [], None

    # Find end page
    end_page = None
    for i in range(start_page + 1, len(doc)):
        lines = page_lines[i]
        for h in END_HEADINGS:
            if _has_heading(lines, h):
                end_page = i
                break
        if end_page is not None:
            break

    if end_page is None:
        end_page = len(doc)

    # Flatten relevant section lines
    section_lines = []
    for i in range(start_page, end_page):
        section_lines.extend(page_lines[i])

    # Extract total from relevant pages as well (and/or later pages if needed)
    extracted_total = None
    for i in range(start_page, min(len(doc), start_page + 8)):
        extracted_total = _find_total(page_text_upper[i])
        if extracted_total is not None:
            break
    if extracted_total is None:
        # fallback: scan whole doc quickly
        for t in page_text_upper:
            extracted_total = _find_total(t)
            if extracted_total is not None:
                break

    # Remove noise headers
    cleaned = []
    for l in section_lines:
        lu = l.upper().strip().strip(":")
        if lu in NOISE_LINES:
            continue
        if lu.startswith("GOGREEN"):
            continue
        cleaned.append(l)

    # Parse into items.
    # Heuristics:
    # - New item starts when line looks like a scope “title line”
    #   (often begins with capital letter, is not crazy long, and doesn’t look like price/financing)
    # - If line contains " - " treat left as title, rest as description start.
    items = []
    current_title = None
    desc_buf = []

    def flush():
        nonlocal current_title, desc_buf
        if not current_title:
            return
        desc = " ".join(desc_buf).strip()
        full_desc = f"{current_title} - {desc}" if desc else current_title
        full_desc = re.sub(r"\s+", " ", full_desc).strip()

        items.append({
            "code": "STRD",
            "section": "Preferred Package",
            "description": full_desc,
            "default_description": full_desc,
            "quantity": 1,
            "unit_price": 0.0,
            "price": 0.0,
        })
        current_title = None
        desc_buf = []

    def looks_like_title(line: str) -> bool:
        if not line:
            return False
        if re.search(r"\$[0-9]", line):
            return False
        if re.search(r"\bmo\b", line.lower()):
            return False
        if len(line) > 140:
            return False
        # starts with letter and looks like a scope label
        return bool(re.match(r"^[A-Z][A-Za-z0-9(]", line.strip()))

    for line in cleaned:
        # Stop if we hit money summary area
        if re.search(r"(QUOTE SUBTOTAL|ADJUSTED SUBTOTAL|FINAL PRICE|\bTOTAL\b)", line.upper()):
            break

        if " - " in line and looks_like_title(line.split(" - ", 1)[0].strip()):
            flush()
            left, right = line.split(" - ", 1)
            current_title = left.strip()
            desc_buf = [right.strip()] if right.strip() else []
            continue

        if looks_like_title(line):
            # if this is a new title-ish line and we already have a current title,
            # treat it as new item start
            if current_title is None:
                current_title = line.strip()
                desc_buf = []
            else:
                # If current title exists and this line is short-ish, likely new item.
                if len(line) < 90:
                    flush()
                    current_title = line.strip()
                    desc_buf = []
                else:
                    desc_buf.append(line.strip())
            continue

        if current_title:
            desc_buf.append(line.strip())

    flush()
    return items, extracted_total
