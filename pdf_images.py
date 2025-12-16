import fitz
import pytesseract
from PIL import Image
from io import BytesIO

START_KEYWORD = "INSPECTION"
END_KEYWORDS = [
    "PREFERRED PACKAGE",
    "STANDARD SCOPE",
    "DRY ROT & EXTRA WORK"
]

def extract_inspection_images(pdf_path: str):
    doc = fitz.open(pdf_path)

    inspection_start = None
    inspection_end = None

    # ───────────────
    # PASS 1: OCR scan for section boundaries
    # ───────────────
    for i in range(len(doc)):
        page = doc[i]
        pix = page.get_pixmap(dpi=150)
        img = Image.open(BytesIO(pix.tobytes("png")))

        ocr_text = pytesseract.image_to_string(img).upper()

        if inspection_start is None and START_KEYWORD in ocr_text:
            inspection_start = i
            continue

        if inspection_start is not None:
            for end_key in END_KEYWORDS:
                if end_key in ocr_text:
                    inspection_end = i
                    break

        if inspection_start is not None and inspection_end is not None:
            break

    if inspection_start is None:
        print("⚠️ Inspection section not detected via OCR.")
        return []

    if inspection_end is None:
        inspection_end = len(doc)

    # ───────────────
    # PASS 2: capture page snapshots
    # ───────────────
    images = []

    for page_index in range(inspection_start, inspection_end):
        page = doc[page_index]
        pix = page.get_pixmap(dpi=300)

        img = Image.open(
            BytesIO(pix.tobytes("jpeg"))
        ).convert("RGB")

        images.append({
            "page": page_index + 1,
            "image": img
        })

    return images

def merge_cover_with_summary(original_pdf_path: str, summary_pdf_bytes: bytes) -> bytes:
    original = fitz.open(original_pdf_path)
    summary = fitz.open(stream=summary_pdf_bytes, filetype="pdf")

    output = fitz.open()

    # Keep ONLY the first page of the original (cover)
    output.insert_pdf(original, from_page=0, to_page=0)

    # Append all pages from generated summary
    output.insert_pdf(summary)

    buf = BytesIO()
    output.save(buf)
    buf.seek(0)

    return buf.getvalue()

def resize_for_grid(image: Image.Image, max_width=160, max_height=120):
    img = image.copy()
    img.thumbnail((max_width, max_height))
    return img

