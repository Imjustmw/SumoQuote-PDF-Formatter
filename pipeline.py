from processing import process_line_items
from render_pdf import render_pdf
from pdf_images import extract_inspection_images, merge_cover_with_summary
from pathlib import Path

def run_pipeline(payload: dict, signed_pdf_path: str | None = None):
    project = payload["project"]
    raw_items = payload["line_items"]

    processed_items = process_line_items(raw_items)

    inspection_images = []
    if signed_pdf_path:
        inspection_images = extract_inspection_images(signed_pdf_path)

    qty_pdf = render_pdf(
        project,
        processed_items,
        inspection_images,
        show_prices=False
    )

    price_pdf = render_pdf(
        project,
        processed_items,
        inspection_images,
        show_prices=True
    )

    Path("output").mkdir(exist_ok=True)

    final_qty_pdf = merge_cover_with_summary(
        signed_pdf_path,
        qty_pdf
    )

    final_price_pdf = merge_cover_with_summary(
        signed_pdf_path,
        price_pdf
    )

    with open("output/roof_scope_quantity.pdf", "wb") as f:
        f.write(final_qty_pdf)

    with open("output/roof_scope_price.pdf", "wb") as f:
        f.write(final_price_pdf)

    print("PDF generation complete.")
