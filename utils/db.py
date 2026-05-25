import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

client = None
db = None

def connect_db():
    global client, db
    try:
        mongo_uri = os.getenv("MONGO_URI")
        db_name = os.getenv("MONGO_DB_NAME", "food_scraper")
        client = MongoClient(mongo_uri)
        db = client[db_name]
        # Ping to confirm connection
        client.admin.command("ping")
        print(f"✅ Connected to MongoDB — database: '{db_name}'")
        return db
    except Exception as e:
        print(f"❌ MongoDB connection failed: {e}")
        raise

def get_collection(name: str):
    if db is None:
        connect_db()
    return db[name]

def upsert_product(collection, product):
    """Upsert a product using the most stable unique key available."""
    # Best key: source + product_url (truly unique per platform)
    # Fallback: source + name
    if product.get("product_url"):
        filter_key = {
            "source": product["source"],
            "product_url": product["product_url"]
        }
    else:
        filter_key = {
            "source": product["source"],
            "name": product["name"]
        }

    collection.update_one(filter_key, {"$set": product}, upsert=True)