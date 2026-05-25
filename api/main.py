from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from utils.db import connect_db, get_collection
from bson import ObjectId

app = FastAPI(title="Product Scraper API", version="1.0.0")

# Allow frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect DB on startup
@app.on_event("startup")
def startup():
    connect_db()


def serialize(doc):
    """Convert MongoDB doc to JSON-serializable dict."""
    doc["_id"] = str(doc["_id"])
    return doc


# ── GET /products ──────────────────────────────────────────
@app.get("/products")
def get_products(
    source: Optional[str]   = Query(None, description="noon | emax"),
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str]   = Query(None, description="Search in product name"),
    min_price: Optional[float] = Query(None, description="Minimum price"),
    max_price: Optional[float] = Query(None, description="Maximum price"),
    in_stock: Optional[bool]   = Query(None, description="Filter by stock status"),
    sort_by: Optional[str]     = Query("scraped_at", description="price | name | rating | scraped_at"),
    sort_order: Optional[str]  = Query("desc", description="asc | desc"),
    page: int   = Query(1, ge=1, description="Page number"),
    limit: int  = Query(20, ge=1, le=100, description="Results per page"),
):
    col = get_collection("products")
    query = {}

    if source:
        query["source"] = source.lower()
    if category:
        query["category"] = {"$regex": category, "$options": "i"}
    if search:
        query["name"] = {"$regex": search, "$options": "i"}
    if min_price is not None:
        query.setdefault("price", {})["$gte"] = min_price
    if max_price is not None:
        query.setdefault("price", {})["$lte"] = max_price
    if in_stock is not None:
        query["in_stock"] = in_stock

    sort_dir = -1 if sort_order == "desc" else 1
    skip = (page - 1) * limit

    total = col.count_documents(query)
    docs = list(col.find(query).sort(sort_by, sort_dir).skip(skip).limit(limit))

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": -(-total // limit),  # ceiling division
        "results": [serialize(d) for d in docs],
    }


# ── GET /products/:id ──────────────────────────────────────
@app.get("/products/{product_id}")
def get_product(product_id: str):
    col = get_collection("products")
    doc = col.find_one({"_id": ObjectId(product_id)})
    if not doc:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Product not found")
    return serialize(doc)


# ── GET /categories ────────────────────────────────────────
@app.get("/categories")
def get_categories(source: Optional[str] = Query(None)):
    col = get_collection("products")
    query = {}
    if source:
        query["source"] = source.lower()
    categories = col.distinct("category", query)
    return {"categories": sorted(categories)}


# ── GET /sources ───────────────────────────────────────────
@app.get("/sources")
def get_sources():
    col = get_collection("products")
    sources = col.distinct("source")
    return {"sources": sources}


# ── GET /stats ─────────────────────────────────────────────
@app.get("/stats")
def get_stats():
    col = get_collection("products")
    pipeline = [
        {"$group": {
            "_id": "$source",
            "total_products": {"$sum": 1},
            "avg_price": {"$avg": "$price"},
            "min_price": {"$min": "$price"},
            "max_price": {"$max": "$price"},
            "categories": {"$addToSet": "$category"},
        }},
        {"$project": {
            "source": "$_id",
            "total_products": 1,
            "avg_price": {"$round": ["$avg_price", 2]},
            "min_price": 1,
            "max_price": 1,
            "total_categories": {"$size": "$categories"},
        }}
    ]
    stats = list(col.aggregate(pipeline))
    for s in stats:
        s["_id"] = str(s["_id"])
    return {
        "total_products": col.count_documents({}),
        "by_source": stats
    }


# ── GET /compare ───────────────────────────────────────────
@app.get("/compare")
def compare_products(
    search: str = Query(..., description="Product name to search across all sources"),
    limit: int  = Query(5, ge=1, le=20),
):
    """Find the same/similar product across Noon and Emax and compare prices."""
    col = get_collection("products")
    query = {"name": {"$regex": search, "$options": "i"}}
    docs = list(col.find(query).limit(limit * 2))

    # Group by source
    grouped = {}
    for doc in docs:
        src = doc["source"]
        if src not in grouped:
            grouped[src] = []
        if len(grouped[src]) < limit:
            grouped[src].append(serialize(doc))

    return {
        "search": search,
        "results_by_source": grouped,
    }