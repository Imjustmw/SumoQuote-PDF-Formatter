# pdf_images.py
import fitz
import pytesseract
from PIL import Image
from io import BytesIO
import re

START_HEADING = "INSPECTION"
END_HEADINGS = [
    "PREFERRED PACKAGE",
    "STANDARD SCOPE",
    "DRY ROT & EXTRA WORK",
    "AUTHORIZATION PAGE",
]

def _ocr_lines(page, dpi=150) -> list[str]:
    pix = page.get_pixmap(dpi=dpi)
    img = Image.open(BytesIO(pix.tobytes("png")))
    text = pytesseract.image_to_string(img)
    # normalize lines
    lines = [re.sub(r"\s+", " ", l).strip() for l in text.splitlines()]
    return [l for l in lines if l]

def _has_heading(lines: list[str], heading: str) -> bool:
    # Heading must appear as its own line (or extremely close)
    h = heading.strip().upper()
    for l in lines:
        lu = l.upper().strip().strip(":")
        if lu == h:
            return True
    return False

def extract_inspection_images(pdf_path: str):
    doc = fitz.open(pdf_path)

    inspection_start = None
    inspection_end = None

    # PASS 1: find inspection section strictly by standalone heading line
    ocr_cache = []

    for i in range(len(doc)):
        lines = _ocr_lines(doc[i], dpi=150)
        ocr_cache.append(lines)

        if inspection_start is None and _has_heading(lines, START_HEADING):
            inspection_start = i
            continue

        if inspection_start is not None and i > inspection_start:
            # end when a section heading appears as standalone heading
            for end_h in END_HEADINGS:
                if _has_heading(lines, end_h):
                    inspection_end = i
                    break

        if inspection_start is not None and inspection_end is not None:
            break

    if inspection_start is None:
        # No inspection heading at all
        return []

    if inspection_end is None:
        inspection_end = len(doc)

    # PASS 2: snapshot pages, BUT also guard against false positives:
    # inspection pages usually have very little OCR text (mostly images).
    images = []
    for page_index in range(inspection_start, inspection_end):
        lines = ocr_cache[page_index] if page_index < len(ocr_cache) else _ocr_lines(doc[page_index])
        word_count = sum(len(l.split()) for l in lines)

        # If this page has tons of text, it's probably NOT an inspection photo page
        # (common false positive: "inspection" appears in scope text)
        if word_count > 120:
            continue

        page = doc[page_index]
        pix = page.get_pixmap(dpi=250)
        img = Image.open(BytesIO(pix.tobytes("jpeg"))).convert("RGB")

        images.append({"page": page_index + 1, "image": img})

    return images

def merge_cover_with_summary(original_pdf_path: str, summary_pdf_bytes: bytes) -> bytes:
    original = fitz.open(original_pdf_path)
    summary = fitz.open(stream=summary_pdf_bytes, filetype="pdf")

    output = fitz.open()
    output.insert_pdf(original, from_page=0, to_page=0)
    output.insert_pdf(summary)

    buf = BytesIO()
    output.save(buf)
    buf.seek(0)
    return buf.getvalue()

def resize_for_grid(image: Image.Image, max_width=160, max_height=120):
    img = image.copy()
    img.thumbnail((max_width, max_height))
    return img
