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


async def scrape_emax_category(
    page,
    category_url,
    category_name,
    collection
):
    total_saved = 0

    seen_products = set()

    page_number = 1

    print(f"\n📦 Category: {category_name}")

    # ─────────────────────────────────
    # Open Initial Page
    # ─────────────────────────────────

    await page.goto(
        category_url,
        wait_until="domcontentloaded",
        timeout=60000
    )

    await page.wait_for_timeout(4000)

    while True:

        print(f"\n📄 Page {page_number}")

        # ─────────────────────────────────
        # Wait For Products
        # ─────────────────────────────────

        try:
            await page.wait_for_selector(
                '.product_wrapper',
                timeout=15000
            )
        except:
            print("No product cards found")
            break

        # ─────────────────────────────────
        # Extract Products
        # ─────────────────────────────────

        products = await extract_from_html(
            page,
            category_name
        )

        if not products:
            print("No products extracted")
            break

        # ─────────────────────────────────
        # Deduplicate + Save
        # ─────────────────────────────────

        new_products = 0

        for product in products:

            unique_key = (
                product["product_url"]
                or product["product_id"]
            )

            if unique_key in seen_products:
                continue

            seen_products.add(unique_key)

            upsert_product(collection, product)

            total_saved += 1
            new_products += 1

        print(f"   ↳ Extracted: {len(products)}")
        print(f"   ↳ New Saved: {new_products}")

        # ─────────────────────────────────
        # Find Load More Button
        # ─────────────────────────────────

        load_more_btn = await page.query_selector(
            '#category-loadmore-layout a[href*="?p="]'
        )

        if not load_more_btn:
            print("No more pages found")
            break

        # ─────────────────────────────────
        # Get Next Page URL
        # ─────────────────────────────────

        next_url = await load_more_btn.get_attribute(
            "href"
        )

        if not next_url:
            print("Next URL missing")
            break

        # Convert relative URL to absolute
        if not next_url.startswith("http"):
            next_url = f"{EMAX_BASE_URL}{next_url}"

        print(f"   ↳ Next Page: {next_url}")

        # ─────────────────────────────────
        # Open Next Page
        # ─────────────────────────────────

        await page.goto(
            next_url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        await page.wait_for_timeout(4000)

        page_number += 1

    return total_saved


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
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled"
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

        # ─────────────────────────────────
        # Anti Bot
        # ─────────────────────────────────

        await page.add_init_script("""
            Object.defineProperty(
                navigator,
                'webdriver',
                { get: () => undefined }
            );

            Object.defineProperty(
                navigator,
                'languages',
                { get: () => ['en-US', 'en'] }
            );

            window.chrome = { runtime: {} };
        """)

        print("\n🛒 Starting Emax Scraper...\n")

        # ─────────────────────────────────
        # Homepage Visit
        # ─────────────────────────────────

        print("🏠 Opening homepage...")

        await page.goto(
            EMAX_BASE_URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        await page.wait_for_timeout(3000)

        print("✅ Ready\n")

        # ─────────────────────────────────
        # Categories
        # ─────────────────────────────────

        for i, cat in enumerate(
            EMAX_CATEGORIES[:max_categories]
        ):

            print(
                f"\n📦 [{i+1}/{max_categories}] "
                f"{cat['name']}"
            )

            saved = await scrape_emax_category(
                page=page,
                category_url=cat["url"],
                category_name=cat["name"],
                collection=collection
            )

            total_saved += saved

            print(
                f"   ✅ Category complete: "
                f"{saved} products saved"
            )

        await browser.close()

    print("\n🎉 Emax Scraping Complete")
    print(f"✅ Total Products Saved: {total_saved}")

    return total_saved