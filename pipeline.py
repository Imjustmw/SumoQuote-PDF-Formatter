# pipeline.py
from processing import process_line_items
from render_pdf import render_pdf
from pdf_images import extract_inspection_images, merge_cover_with_summary
from pdf_line_items import extract_preferred_package_items
from pathlib import Path

def run_pipeline(payload: dict, signed_pdf_path: str | None = None):
    project = payload["project"]
    raw_items = payload.get("line_items", [])

    extracted_total = None

    if (not raw_items) and signed_pdf_path:
        print("No line items in payload, extracting from PDF...")
        raw_items, extracted_total = extract_preferred_package_items(signed_pdf_path)

    # store total if we found it
    if extracted_total is not None:
        project["extracted_total"] = extracted_total

    processed_items = process_line_items(raw_items)

    inspection_images = []
    if signed_pdf_path:
        inspection_images = extract_inspection_images(signed_pdf_path)

    qty_pdf = render_pdf(project, processed_items, inspection_images, show_prices=False)
    price_pdf = render_pdf(project, processed_items, inspection_images, show_prices=True)

    Path("output").mkdir(exist_ok=True)

    if signed_pdf_path:
        final_qty_pdf = merge_cover_with_summary(signed_pdf_path, qty_pdf)
        final_price_pdf = merge_cover_with_summary(signed_pdf_path, price_pdf)
    else:
        final_qty_pdf = qty_pdf
        final_price_pdf = price_pdf

    with open("output/roof_scope_quantity.pdf", "wb") as f:
        f.write(final_qty_pdf)

    with open("output/roof_scope_price.pdf", "wb") as f:
        f.write(final_price_pdf)

    print("PDF generation complete.")
