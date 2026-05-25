import asyncio
import re
from playwright.async_api import async_playwright
from utils.db import get_collection
from datetime import datetime
from utils.db import upsert_product

NOON_BASE_URL = "https://www.noon.com/uae-en/"

NOON_CATEGORIES = [
    {"name":"Laptops", "url":"https://www.noon.com/uae-en/electronics-and-mobiles/computers-and-accessories/computers-new/laptops/"}
    # {"name": "Fashion",            "url": "https://www.noon.com/uae-en/fashion/"},
    # {"name": "Home & Kitchen",     "url": "https://www.noon.com/uae-en/home-and-kitchen/"},
    # {"name": "Sports & Outdoors",  "url": "https://www.noon.com/uae-en/sports-and-outdoors/"},
]

# ── Exact selectors derived from class name diagnostic ──
SELECTORS = {
    "product_card":   'div[data-qa="plp-product-box"]',
    "product_link":   'a[class*="productBoxLink"]',
    "product_title":  'h2[data-qa="plp-product-box-name"]',
    "unit_price":     'strong[class*="amount"]',
    "original_price": 'span[class*="oldPrice"]',
    "image_wrapper":  'div[class*="imageWrapper"] img',
    "rating":         'div[class*="textCtr"]',
}


async def handle_cookie_consent(page):
    try:
        accept_btn = await page.wait_for_selector(
            "button:has-text('ACCEPT ALL'), button:has-text('Accept All'), button:has-text('Accept')",
            timeout=5000
        )
        if accept_btn:
            await accept_btn.click()
            print("   ↳ ✅ Cookie consent accepted")
            await page.wait_for_timeout(2000)
    except Exception:
        pass


async def scrape_noon_category(page, category_url, category_name):
    products = []
    api_responses = []

    # Keep trying to intercept API responses
    async def handle_response(response):
        try:
            url = response.url
            if response.status == 200 and "json" in response.headers.get("content-type", ""):
                if any(x in url for x in ["api.noon.com", "catalog", "/search", "graphql"]):
                    data = await response.json()
                    api_responses.append((url, data))
        except Exception:
            pass

    page.on("response", handle_response)

    try:
        print(f"   ↳ Navigating to {category_url}")
        await page.goto(category_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        await handle_cookie_consent(page)

        # Scroll progressively to trigger lazy-loaded products
        for scroll_y in [400, 800, 1200, 1800, 2400]:
            await page.evaluate(f"window.scrollTo(0, {scroll_y})")
            await page.wait_for_timeout(1000)

        # Wait for product cards to appear
        try:
            await page.wait_for_selector(SELECTORS["product_card"], timeout=10000)
        except Exception:
            print("   ↳ Product cards did not appear after scrolling")

        # Try API interception first
        for url, data in api_responses:
            extracted = extract_from_api_response(data, category_name)
            if extracted:
                print(f"   ↳ API hit: {url[:80]} → {len(extracted)} products")
                products.extend(extracted)

        # Fall back to HTML extraction using precise selectors
        if not products:
            print("   ↳ Trying HTML extraction with precise selectors...")
            products = await extract_from_html(page, category_name)

    except Exception as e:
        print(f"   ⚠️  Error on {category_url}: {e}")
    finally:
        page.remove_listener("response", handle_response)

    return products


def extract_from_api_response(data, category_name):
    products = []
    try:
        items = (
            data.get("hits", []) or
            data.get("products", []) or
            data.get("items", []) or
            (data.get("data") or {}).get("hits", []) or
            []
        )
        for item in items:
            try:
                price_obj = item.get("price") or {}
                price = float(
                    price_obj.get("now") or
                    price_obj.get("sale_price") or
                    item.get("sale_price") or 0
                )
                original = float(
                    price_obj.get("was") or
                    price_obj.get("price") or
                    item.get("price") or price
                )
                name = item.get("name") or item.get("title") or ""
                if not name:
                    continue
                products.append(build_product(
                    name=name.strip(),
                    price=price,
                    original_price=original,
                    brand=item.get("brand") or "",
                    image_url=(item.get("image_keys") or [None])[0] or item.get("thumbnail") or "",
                    product_url=f"https://www.noon.com/uae-en/{item.get('slug', '')}",
                    in_stock=item.get("inStock", True),
                    rating=float(item.get("averageRating") or 0),
                    category=category_name,
                    product_id=str(item.get("id") or item.get("sku") or ""),
                ))
            except Exception:
                continue
    except Exception:
        pass
    return products


async def extract_from_html(page, category_name):
    products = []
    try:
        cards = await page.query_selector_all(SELECTORS["product_card"])
        print(f"   ↳ Found {len(cards)} product cards")

        if not cards:
            await page.screenshot(path="debug_noon_empty.png")
            print("   ↳ Screenshot saved → debug_noon_empty.png (no cards found)")
            return []

# ── TEMP DIAGNOSTIC: print first card's HTML ──
        if cards:
            first_card_html = await cards[0].inner_html()
            print(f"\n   ── FIRST CARD HTML ──\n{first_card_html[:3000]}\n   ────────────────────\n")
        for card in cards:
            try:
                # ── Name ──
                name = ""
                el = await card.query_selector(SELECTORS["product_title"])
                if el:
                    name = (await el.inner_text()).strip()
                if not name:
                    continue

                # ── Price ──
                price = 0.0
                el = await card.query_selector(SELECTORS["unit_price"])
                if el:
                    raw = (await el.inner_text()).replace(",", "")
                    cleaned = re.sub(r"[^\d.]", "", raw)
                    price = float(cleaned) if cleaned else 0.0

                # ── Original price ──
                original_price = price
                el = await card.query_selector(SELECTORS["original_price"])
                if el:
                    raw = (await el.inner_text()).replace(",", "")
                    cleaned = re.sub(r"[^\d.]", "", raw)
                    original_price = float(cleaned) if cleaned else price

                # ── Image ──
                image_url = ""
                el = await card.query_selector(SELECTORS["image_wrapper"])
                if el:
                    image_url = (
                        await el.get_attribute("src") or
                        await el.get_attribute("data-src") or ""
                    )

                # ── Product URL ──
                product_url = ""
                el = await card.query_selector(SELECTORS["product_link"])
                if el:
                    href = await el.get_attribute("href") or ""
                    product_url = href if href.startswith("http") else f"https://www.noon.com{href}"

                # ── Rating ──
                rating = 0.0
                el = await card.query_selector(SELECTORS["rating"])
                if el:
                    raw = (await el.inner_text()).strip()
                    cleaned = re.sub(r"[^\d.]", "", raw)
                    rating = float(cleaned) if cleaned else 0.0

                products.append(build_product(
                    name=name,
                    price=price,
                    original_price=original_price,
                    image_url=image_url,
                    product_url=product_url,
                    rating=rating,
                    category=category_name,
                ))

            except Exception:
                continue

        print(f"   ↳ Extracted {len(products)} products with full details")

    except Exception as e:
        print(f"   ⚠️  HTML extraction error: {e}")

    return products


def build_product(name, category, price=0.0, original_price=0.0,
                  image_url="", product_url="", brand="",
                  rating=0.0, in_stock=True, product_id=""):
    return {
        "source": "noon",
        "product_id": product_id,
        "name": name,
        "price": price,
        "original_price": original_price,
        "currency": "AED",
        "category": category,
        "brand": brand,
        "image_url": image_url,
        "product_url": product_url,
        "in_stock": in_stock,
        "rating": rating,
        "scraped_at": datetime.utcnow().isoformat(),
    }


async def scrape_noon(max_categories=3):
    collection = get_collection("products")
    total_saved = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ]
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
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            window.chrome = { runtime: {} };
        """)

        print("🔍 Starting Noon scraper...\n")

        print("🍪 Visiting homepage to handle cookie consent...")
        await page.goto(NOON_BASE_URL, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(3000)
        await handle_cookie_consent(page)
        print("✅ Ready to scrape categories\n")

        for i, cat in enumerate(NOON_CATEGORIES[:max_categories]):
            print(f"📦 [{i+1}/{max_categories}] Category: {cat['name']}")
            products = await scrape_noon_category(page, cat["url"], cat["name"])
            print(f"   ↳ Total extracted: {len(products)}")

            if products:
                for p_data in products:
                    upsert_product(collection, p_data)
                total_saved += len(products)
                print(f"   ✅ Saved {len(products)} to MongoDB\n")
            else:
                print("   ⚠️  No products found for this category\n")

        await browser.close()

    print(f"🎉 Done! Total saved: {total_saved}")
    return total_saved