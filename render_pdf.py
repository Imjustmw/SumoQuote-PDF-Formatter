from io import BytesIO
from reportlab.lib.pagesizes import LETTER
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from pdf_images import resize_for_grid
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    PageBreak,
    Image as RLImage,
)

COLOR_MAP = {
    "blue": colors.HexColor("#cce5ff"),
    "grey": colors.HexColor("#eeeeee"),
    "lightyellow": colors.HexColor("#fff3cd"),
    "orange": colors.HexColor("#ffe5b4"),
    "red": colors.HexColor("#f8d7da"),
}

SECTION_TITLES = {
    "warranty": "WARRANTY ITEMS",
    "standard": "STANDARD SCOPE",
    "extra_work": "EXTRA WORK / MODIFICATIONS",
}

def render_pdf(project: dict, items: list, inspection_images: list, show_prices: bool) -> bytes:
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    elements = []

    # ─────────────────────────────────────
    # Title & Intent
    # ─────────────────────────────────────
    title = "Roof Scope Summary"
    subtitle = "Production Scope Summary – Approved Contract"

    elements.append(Paragraph(f"<b>{title}</b>", styles["Title"]))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(subtitle, styles["Italic"]))
    elements.append(Spacer(1, 10))

    full_address = (
        f"{project.get('address', '')}, "
        f"{project.get('city', '')}, "
        f"{project.get('state', '')} "
        f"{project.get('postal_code', '')}"
    ).strip().replace(" ,", ",")

    elements.append(Paragraph(
        f"<b>Customer:</b> {project.get('customer_name')}<br/>"
        f"<b>Address:</b> {full_address}",
        styles["Normal"]
    ))

    elements.append(Spacer(1, 16))

    # ─────────────────────────────────────
    # Group items by category
    # ─────────────────────────────────────
    grouped = {
        "warranty": [],
        "standard": [],
        "extra_work": []
    }

    for item in items:
        grouped[item["category"]].append(item)

    grand_total = 0.0

    # ─────────────────────────────────────
    # Render each section
    # ─────────────────────────────────────
    for category, section_items in grouped.items():
        if not section_items:
            continue

        elements.append(Spacer(1, 12))
        elements.append(Paragraph(
            f"<b>{SECTION_TITLES[category]}</b>",
            styles["Heading3"]
        ))
        elements.append(Spacer(1, 6))

        header = ["Description", "Qty"]
        if show_prices:
            header.append("Price")

        table_data = [header]
        row_colors = []

        for item in section_items:
            desc = item["final_description"]

            flags = []

            if item.get("modified"):
                flags.append("MODIFIED")

            if item["quantity"] == 0:
                flags.append("QTY = 0")

            if flags:
                desc += f" <font size=9><b>[{' | '.join(flags)}]</b></font>"


            row = [
                Paragraph(desc, styles["Normal"]),
                str(item["quantity"])
            ]

            if show_prices:
                row.append(f"${item['price']:.2f}")
                grand_total += item["price"]

            table_data.append(row)
            row_colors.append(COLOR_MAP[item["highlight_color"]])

        col_widths = [360, 60, 80] if show_prices else [420, 60]

        table = Table(table_data, colWidths=col_widths, repeatRows=1)

        style = TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (1, 0), (-1, 0), "CENTER"),
            ("ALIGN", (1, 1), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
        ])

        for i, bg in enumerate(row_colors, start=1):
            style.add("BACKGROUND", (0, i), (-1, i), bg)

        table.setStyle(style)
        elements.append(table)

    # ─────────────────────────────────────
    # Total
    # ─────────────────────────────────────
    if show_prices:
        total = grand_total
        extracted_total = project.get("extracted_total")

        # If prices are not present per-item, use extracted_total
        if (total == 0.0) and (extracted_total is not None):
            total = float(extracted_total)

        elements.append(Spacer(1, 20))
        elements.append(Paragraph(
            f"<b>Total Contract Value:</b> ${total:,.2f}",
            styles["Heading2"]
        ))
        
    # ─────────────────────────────────────
    # Inspection Summary
    # ─────────────────────────────────────
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("<b>INSPECTION SUMMARY</b>", styles["Heading3"]))
    elements.append(Spacer(1, 6))

    if inspection_images:
        inspection_text = (
            "Inspection photos were detected in the signed contract and have been "
            "condensed into the attached inspection snapshot section."
        )
    else:
        inspection_text = (
            "No inspection photo section was detected in the signed contract. "
            "This summary includes scope items only."
        )

    elements.append(Paragraph(inspection_text, styles["Normal"]))

    # ─────────────────────────────────────
    # Inspection Images Page
    # ─────────────────────────────────────
    if inspection_images:
        elements.append(PageBreak())
        elements.append(Paragraph("<b>INSPECTION REFERENCE SNAPSHOTS</b>", styles["Title"]))
        elements.append(Spacer(1, 8))

        row = []
        grid = []
        cols = 2

        for img_data in inspection_images:
            img = resize_for_grid(img_data["image"], 480, 360)
            buf = BytesIO()
            img.save(buf, format="JPEG")
            buf.seek(0)

            rl_img = RLImage(buf, width=img.width, height=img.height)
            row.append(rl_img)

            if len(row) == cols:
                grid.append(row)
                row = []

        if row:
            grid.append(row)

        if grid:  # 🔒 FINAL SAFETY CHECK
            img_table = Table(grid, hAlign="LEFT", colWidths=[300] * cols)
            img_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))

            elements.append(img_table)

    doc.build(elements)
    return buffer.getvalue()
