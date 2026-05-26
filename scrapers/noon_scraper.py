import asyncio
import re
from datetime import datetime

from playwright.async_api import async_playwright

from utils.db import get_collection, upsert_product

NOON_BASE_URL = "https://www.noon.com/uae-en/"

NOON_CATEGORIES = [
    {
        "name": "Laptops",
        "url": "https://www.noon.com/uae-en/electronics-and-mobiles/computers-and-accessories/computers-new/laptops/"
    }
]

SELECTORS = {
    "product_card": 'div[data-qa="plp-product-box"]',
    "product_link": 'a[class*="productBoxLink"]',
    "product_title": 'h2[data-qa="plp-product-box-name"]',
    "unit_price": 'strong[class*="amount"]',
    "original_price": 'span[class*="oldPrice"]',
    "image_wrapper": 'div[class*="imageWrapper"] img',
    "rating": 'div[class*="textCtr"]',
    "pagination_next": 'li.next a[rel="next"]',
}


# ─────────────────────────────────────────────
# Cookie Consent
# ─────────────────────────────────────────────

async def handle_cookie_consent(page):
    try:
        accept_btn = await page.wait_for_selector(
            "button:has-text('ACCEPT ALL'), "
            "button:has-text('Accept All'), "
            "button:has-text('Accept')",
            timeout=5000
        )

        if accept_btn:
            await accept_btn.click()
            print("   ↳ ✅ Cookie consent accepted")
            await page.wait_for_timeout(2000)

    except Exception:
        pass


# ─────────────────────────────────────────────
# Product Builder
# ─────────────────────────────────────────────

def build_product(
    name,
    category,
    price=0.0,
    original_price=0.0,
    image_url="",
    product_url="",
    brand="",
    rating=0.0,
    in_stock=True,
    product_id=""
):
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


# ─────────────────────────────────────────────
# Extract Products From Current Page
# ─────────────────────────────────────────────

async def extract_from_html(page, category_name):
    products = []

    try:
        await page.wait_for_selector(
            SELECTORS["product_card"],
            timeout=15000
        )

        cards = await page.query_selector_all(
            SELECTORS["product_card"]
        )

        print(f"   ↳ Found {len(cards)} product cards")

        for card in cards:
            try:
                # ── Product URL ──
                product_url = ""

                el = await card.query_selector(
                    SELECTORS["product_link"]
                )

                if el:
                    href = await el.get_attribute("href") or ""

                    if href.startswith("http"):
                        product_url = href
                    else:
                        product_url = f"https://www.noon.com{href}"

                # ── Name ──
                name = ""

                el = await card.query_selector(
                    SELECTORS["product_title"]
                )

                if el:
                    name = (await el.inner_text()).strip()

                if not name:
                    continue

                # ── Current Price ──
                price = 0.0

                el = await card.query_selector(
                    SELECTORS["unit_price"]
                )

                if el:
                    raw = (await el.inner_text()).replace(",", "")
                    cleaned = re.sub(r"[^\d.]", "", raw)

                    if cleaned:
                        price = float(cleaned)

                # ── Original Price ──
                original_price = price

                el = await card.query_selector(
                    SELECTORS["original_price"]
                )

                if el:
                    raw = (await el.inner_text()).replace(",", "")
                    cleaned = re.sub(r"[^\d.]", "", raw)

                    if cleaned:
                        original_price = float(cleaned)

                # ── Image ──
                image_url = ""

                el = await card.query_selector(
                    SELECTORS["image_wrapper"]
                )

                if el:
                    image_url = (
                        await el.get_attribute("src")
                        or await el.get_attribute("data-src")
                        or ""
                    )

                # ── Rating ──
                rating = 0.0

                el = await card.query_selector(
                    SELECTORS["rating"]
                )

                if el:
                    raw = (await el.inner_text()).strip()

                    match = re.search(r"\d+(\.\d+)?", raw)

                    if match:
                        rating = float(match.group())

                # ── Product ID ──
                product_id = product_url.split("/")[-1]

                # ── Brand ──
                brand = name.split(" ")[0]

                products.append(
                    build_product(
                        name=name,
                        category=category_name,
                        price=price,
                        original_price=original_price,
                        image_url=image_url,
                        product_url=product_url,
                        brand=brand,
                        rating=rating,
                        product_id=product_id,
                    )
                )

            except Exception as e:
                print(f"      ⚠️ Product parse error: {e}")
                continue

    except Exception as e:
        print(f"   ⚠️ HTML extraction error: {e}")

    return products


# ─────────────────────────────────────────────
# Scrape Category With Pagination
# ─────────────────────────────────────────────

async def scrape_noon_category(
    page,
    category_url,
    category_name,
    collection
):
    total_saved = 0

    seen_products = set()

    page_number = 1

    while True:
        try:
            # ─────────────────────────────────
            # Build Pagination URL
            # ─────────────────────────────────

            if "?" in category_url:
                paginated_url = f"{category_url}&page={page_number}"
            else:
                paginated_url = f"{category_url}?page={page_number}"

            print(f"\n📄 Page {page_number}")
            print(f"   ↳ {paginated_url}")

            # ─────────────────────────────────
            # Open Page
            # ─────────────────────────────────

            await page.goto(
                paginated_url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            await page.wait_for_timeout(3000)

            # ─────────────────────────────────
            # Extract Products
            # ─────────────────────────────────

            products = await extract_from_html(
                page,
                category_name
            )

            # ─────────────────────────────────
            # Stop If No Products
            # ─────────────────────────────────

            if not products:
                print("   ↳ No products found. Stopping.")
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

                new_products += 1
                total_saved += 1

            print(f"   ↳ Extracted: {len(products)}")
            print(f"   ↳ New Saved: {new_products}")

            # ─────────────────────────────────
            # Stop If No New Products
            # ─────────────────────────────────

            if new_products == 0:
                print("   ↳ No new products found. Stopping.")
                break

            # ─────────────────────────────────
            # Check Next Page Exists
            # ─────────────────────────────────

            next_btn = await page.query_selector(
                SELECTORS["pagination_next"]
            )

            if not next_btn:
                print("   ↳ No next page button found.")
                break

            page_number += 1

        except Exception as e:
            print(f"   ⚠️ Pagination error: {e}")
            break

    return total_saved


# ─────────────────────────────────────────────
# Main Scraper
# ─────────────────────────────────────────────

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

            Object.defineProperty(
                navigator,
                'plugins',
                { get: () => [1, 2, 3] }
            );

            window.chrome = { runtime: {} };
        """)

        print("\n🔍 Starting Noon Scraper...\n")

        # ─────────────────────────────────
        # Homepage Visit
        # ─────────────────────────────────

        print("🍪 Opening homepage...")

        await page.goto(
            NOON_BASE_URL,
            wait_until="domcontentloaded",
            timeout=60000
        )

        await page.wait_for_timeout(3000)

        await handle_cookie_consent(page)

        print("✅ Ready\n")

        # ─────────────────────────────────
        # Categories
        # ─────────────────────────────────

        for i, category in enumerate(
            NOON_CATEGORIES[:max_categories]
        ):
            print(
                f"\n📦 [{i+1}/{max_categories}] "
                f"{category['name']}"
            )

            saved = await scrape_noon_category(
                page=page,
                category_url=category["url"],
                category_name=category["name"],
                collection=collection
            )

            total_saved += saved

            print(
                f"   ✅ Category complete: "
                f"{saved} products saved"
            )

        await browser.close()

    print("\n🎉 Noon Scraping Complete")
    print(f"✅ Total Products Saved: {total_saved}")

    return total_saved


# ─────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(scrape_noon())