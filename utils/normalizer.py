from datetime import datetime

def normalize_product(raw: dict, source: str) -> dict:
    """Ensure every product follows the same schema regardless of source."""
    return {
        "source": source,
        "product_id": str(raw.get("product_id", "")),
        "name": str(raw.get("name", "")).strip(),
        "price": float(raw.get("price") or 0),
        "original_price": float(raw.get("original_price") or raw.get("price") or 0),
        "currency": raw.get("currency", "AED"),
        "category": raw.get("category", ""),
        "brand": raw.get("brand", ""),
        "image_url": raw.get("image_url", ""),
        "product_url": raw.get("product_url", ""),
        "in_stock": bool(raw.get("in_stock", True)),
        "rating": float(raw.get("rating") or 0),
        "scraped_at": raw.get("scraped_at", datetime.utcnow().isoformat()),
    }