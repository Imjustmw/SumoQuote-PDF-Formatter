from typing import List, Dict

COLOR_CODES = {
    "warranty": "blue",
    "standard": "grey",
    "modified": "lightyellow",
    "extra_work": "orange",
    "zero_qty": "red"
}

def is_warranty(code: str) -> bool:
    return code.upper().startswith("WTY")

def is_extra_work(code: str) -> bool:
    return code.upper().startswith("EW")

def is_modified(item: Dict) -> bool:
    return (
        item.get("description") != item.get("default_description")
        or item.get("price") != item.get("unit_price")
    )

def trim_description(desc: str) -> str:
    return desc.split("---")[0].strip()

def process_line_items(items: List[Dict]) -> List[Dict]:
    processed = []

    for item in items:
        qty = item["quantity"]
        modified = False

        if is_warranty(item["code"]):
            category = "warranty"
        elif is_extra_work(item["code"]):
            category = "extra_work"
        else:
            category = "standard"
            modified = is_modified(item)

        final_desc = item["description"]
        if category == "standard" and not modified:
            final_desc = trim_description(final_desc)

        if qty == 0:
            color = COLOR_CODES["zero_qty"]
        elif modified:
            color = COLOR_CODES["modified"]
        else:
            color = COLOR_CODES[category]

        processed.append({
            **item,
            "final_description": final_desc,
            "category": category,
            "modified": modified,
            "highlight_color": color
        })

    order = {"warranty": 0, "standard": 1, "extra_work": 2}
    processed.sort(key=lambda x: order[x["category"]])
    return processed
