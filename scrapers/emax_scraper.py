import asyncio
import re
import requests
from playwright.async_api import async_playwright
from utils.db import get_collection
from datetime import datetime
from utils.db import upsert_product

EMAX_BASE_URL = "https://uae.emaxme.com"

EMAX_CATEGORIES = [
    {"name": "Laptops",            "url": "https://uae.emaxme.com/shop-laptoptabletandcomputeraccessories-laptops"}
]


async def scrape_emax_category(page, category_url, category_name):
    products = []
    api_responses = []

    async def handle_response(response):
        try:
            url = response.url
            content_type = response.headers.get("content-type", "")
            if response.status == 200 and "json" in content_type:
                # Log every JSON response URL for debugging
                data = await response.json()
                api_responses.append((url, data))
                print(f"   ↳ 🌐 JSON response: {url[:100]}")
                print(f"      Keys: {list(data.keys())[:10]}")
        except Exception:
            pass

    page.on("response", handle_response)

    try:
        print(f"   ↳ Navigating to {category_url}")
        await page.goto(category_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)

        # Scroll to trigger all API calls
        for scroll_y in [400, 800, 1200, 1800]:
            await page.evaluate(f"window.scrollTo(0, {scroll_y})")
            await page.wait_for_timeout(1000)

        await page.wait_for_timeout(2000)

        # Try to extract from intercepted API calls
        for url, data in api_responses:
            extracted = parse_emax_products(data, category_name)
            if extracted:
                print(f"   ↳ ✅ Got {len(extracted)} products from: {url[:80]}")
                products.extend(extracted)

        # If API interception got nothing, fall back to HTML
        if not products:
            print("   ↳ No API data, trying HTML extraction...")
            products = await extract_from_html(page, category_name)

    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    finally:
        page.remove_listener("response", handle_response)

    return products


def parse_emax_products(data, category_name):
    """Try all known response shapes to extract products."""
    products = []
    try:
        # Try different keys the API might use
        items = (
            data.get("products", []) or
            data.get("items", []) or
            data.get("hits", []) or
            data.get("results", []) or
            data.get("data", []) or
            []
        )

        # Sometimes nested under a key
        if not items and isinstance(data.get("data"), dict):
            items = data["data"].get("products", []) or data["data"].get("items", []) or []

        if not items:
            return []

        for item in items:
            try:
                name = item.get("name") or item.get("title") or item.get("productName") or ""
                if not name:
                    continue

                price = float(
                    item.get("price") or
                    item.get("salePrice") or
                    item.get("sale_price") or
                    item.get("sellingPrice") or 0
                )
                original_price = float(
                    item.get("originalPrice") or
                    item.get("original_price") or
                    item.get("regularPrice") or
                    item.get("mrp") or
                    price
                )

                # Image
                images = item.get("images") or []
                if isinstance(images, list) and images:
                    img = images[0]
                    image_url = img if isinstance(img, str) else img.get("url", "")
                else:
                    image_url = item.get("image") or item.get("thumbnail") or item.get("imageUrl") or ""

                # URL
                slug = item.get("slug") or item.get("url") or ""
                product_url = f"{EMAX_BASE_URL}/{slug}" if slug and not slug.startswith("http") else slug

                products.append({
                    "source": "emax",
                    "product_id": str(item.get("id") or item.get("sku") or item.get("productId") or ""),
                    "name": name.strip(),
                    "price": price,
                    "original_price": original_price,
                    "currency": "AED",
                    "category": category_name,
                    "brand": item.get("brand") or item.get("brandName") or item.get("manufacturer") or "",
                    "image_url": image_url,
                    "product_url": product_url,
                    "in_stock": bool(item.get("inStock", True) or item.get("availability", True)),
                    "rating": float(item.get("rating") or item.get("averageRating") or 0),
                    "scraped_at": datetime.utcnow().isoformat(),
                })
            except Exception:
                continue

    except Exception as e:
        print(f"   ⚠️  Parse error: {e}")

    return products


async def extract_from_html(page, category_name):
    products = []
    try:
        cards = await page.query_selector_all('.product_wrapper')
        print(f"   ↳ Found {len(cards)} product cards")

        if not cards:
            return []

        for card in cards:
            try:
                # ── Name — from the title link ──
                name = ""
                el = await card.query_selector('a[id*="prodItemTitleLink"]')
                if el:
                    name = (await el.inner_text()).strip()
                if not name:
                    continue

                # ── Image — from the product image link, NOT the wishlist button ──
                image_url = ""
                el = await card.query_selector('a[id*="prodItemImgLink"] img')
                if el:
                    image_url = await el.get_attribute("src") or ""

                # ── Product URL ──
                product_url = ""
                el = await card.query_selector('a[id*="prodItemImgLink"]')
                if el:
                    href = await el.get_attribute("href") or ""
                    product_url = href if href.startswith("http") else f"{EMAX_BASE_URL}{href}"

                # ── Selling price (current price) ──
                price = 0.0
                original_price = 0.0

                price_data = await page.evaluate("""(card) => {
                    const descDiv = card.querySelector('.product-desc');
                    if (!descDiv) return { price: 0, original_price: 0 };
                    
                    const priceDiv = descDiv.nextElementSibling;
                    if (!priceDiv) return { price: 0, original_price: 0 };
                    
                    const numbers = [];
                    priceDiv.querySelectorAll('div, span').forEach(el => {
                        const text = el.childNodes[0]?.textContent?.trim().replace(/,/g, '') || '';
                        if (/^\d+(\.\d+)?$/.test(text)) {
                            const num = parseFloat(text);
                            if (num >= 100) {  // ← ignore discount % (always < 100)
                                numbers.push(num);
                            }
                        }
                    });
                    
                    if (numbers.length === 0) return { price: 0, original_price: 0 };
                    return {
                        price: Math.min(...numbers),
                        original_price: Math.max(...numbers),
                    };
                }""", card)

                price = float(price_data.get("price", 0))
                original_price = float(price_data.get("original_price", 0)) or price

                # ── Brand — extract first word from product name ──
                brand = name.split(" ")[0] if name else ""

                # ── Product ID — from the card's color-id attribute ──
                product_id = await card.get_attribute("color-id") or ""

                products.append({
                    "source": "emax",
                    "product_id": product_id,
                    "name": name,
                    "price": price,
                    "original_price": original_price,
                    "currency": "AED",
                    "category": category_name,
                    "brand": brand,
                    "image_url": image_url,
                    "product_url": product_url,
                    "in_stock": True,
                    "rating": 0.0,
                    "scraped_at": datetime.utcnow().isoformat(),
                })

            except Exception:
                continue

        print(f"   ↳ Extracted {len(products)} products")

    except Exception as e:
        print(f"   ⚠️  HTML extraction error: {e}")

    return products


async def scrape_emax(max_categories=3):
    collection = get_collection("products")
    total_saved = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="Asia/Dubai",
        )

        page = await context.new_page()

        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            window.chrome = { runtime: {} };
        """)

        print("🛒 Starting Emax scraper...\n")

        # Visit homepage first to get cookies
        print("🏠 Visiting homepage to get session cookies...")
        await page.goto(EMAX_BASE_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        print("✅ Ready\n")

        for i, cat in enumerate(EMAX_CATEGORIES[:max_categories]):
            print(f"📦 [{i+1}/{max_categories}] Category: {cat['name']}")
            products = await scrape_emax_category(page, cat["url"], cat["name"])
            print(f"   ↳ Total extracted: {len(products)}")

            if products:
                for p_data in products:
                    upsert_product(collection, p_data)
                total_saved += len(products)
                print(f"   ✅ Saved {len(products)} to MongoDB\n")
            else:
                print("   ⚠️  No products found\n")

        await browser.close()

    print(f"🎉 Emax scraping complete! Total saved: {total_saved}")
    return total_saved