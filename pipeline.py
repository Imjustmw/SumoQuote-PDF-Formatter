import os
import tempfile
from pathlib import Path

import requests

from processing import process_line_items
from render_pdf import render_pdf
from pdf_images import extract_inspection_images, merge_cover_with_summary
from pdf_line_items import extract_preferred_package_items

try:
    from odoo_client import upload_pdfs_to_odoo
except Exception:  # noqa: BLE001 keep optional import
    upload_pdfs_to_odoo = None


DEFAULT_OUTPUT_QTY = Path("output/roof_scope_quantity.pdf")
DEFAULT_OUTPUT_PRICE = Path("output/roof_scope_price.pdf")
DEFAULT_SIGNED_PDF = Path("data/signed1.pdf")


def _download_signed_pdf(download_url: str) -> str:
    resp = requests.get(download_url, timeout=30)
    resp.raise_for_status()
    content_type = resp.headers.get("content-type", "").lower()
    if "pdf" not in content_type and not resp.content.startswith(b"%PDF"):
        raise ValueError(f"Download did not return a PDF (content-type: {content_type or 'unknown'})")
    fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
    with os.fdopen(fd, "wb") as f:
        f.write(resp.content)
    return tmp_path


def _resolve_signed_pdf_path(payload: dict, signed_pdf_path: str | None):
    cleanup_paths: list[str] = []

    if signed_pdf_path:
        return signed_pdf_path, cleanup_paths

    env_path = os.getenv("SIGNED_PDF_PATH")
    if env_path:
        path = Path(env_path)
        if not path.exists():
            raise FileNotFoundError(f"SIGNED_PDF_PATH points to a missing file: {env_path}")
        return str(path), cleanup_paths

    if DEFAULT_SIGNED_PDF.exists():
        return str(DEFAULT_SIGNED_PDF), cleanup_paths

    download_url = payload.get("signed_pdf", {}).get("download_url") if isinstance(payload, dict) else None
    if download_url:
        tmp_path = _download_signed_pdf(download_url)
        cleanup_paths.append(tmp_path)
        return tmp_path, cleanup_paths

    return None, cleanup_paths


def run_pipeline(payload: dict, signed_pdf_path: str | None = None):
    signed_pdf_path, cleanup_paths = _resolve_signed_pdf_path(payload, signed_pdf_path)

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

    qty_path = DEFAULT_OUTPUT_QTY
    price_path = DEFAULT_OUTPUT_PRICE

    qty_path.write_bytes(final_qty_pdf)
    price_path.write_bytes(final_price_pdf)

    print("PDF generation complete.")

    if upload_pdfs_to_odoo is None:
        print("Odoo client not available; skipping upload.")
        return

    if os.getenv("ODOO_UPLOAD_ENABLED", "true").lower() == "false":
        print("Odoo upload disabled by ODOO_UPLOAD_ENABLED.")
        return

    try:
        results = upload_pdfs_to_odoo(str(qty_path), str(price_path))
        print(f"Odoo upload results: {results}")
    except ValueError as cfg_err:
        # Missing env vars, so skip silently but log
        print(f"Odoo upload skipped (config missing): {cfg_err}")
    except Exception as exc:  # noqa: BLE001 keep broad so pipeline still completes
        print(f"Odoo upload failed: {exc}")
    finally:
        for p in cleanup_paths:
            try:
                Path(p).unlink(missing_ok=True)
            except Exception as exc:  # noqa: BLE001 cleanup best-effort
                print(f"Warning: failed to delete temp file {p}: {exc}")
