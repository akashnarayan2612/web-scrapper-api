import asyncio
from utils.db import connect_db
from scrapers.noon_scraper import scrape_noon
from scrapers.emax_scraper import scrape_emax
from datetime import datetime

async def run_all_scrapers():
    print("🚀 Starting all scrapers...\n")
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    print("=" * 50)

    connect_db()

    results = {}

    # ── Noon ──
    print("\n📦 NOON SCRAPER")
    print("-" * 50)
    try:
        noon_total = await scrape_noon(max_categories=5)
        results["noon"] = {"status": "✅ success", "saved": noon_total}
    except Exception as e:
        print(f"❌ Noon scraper failed: {e}")
        results["noon"] = {"status": "❌ failed", "saved": 0, "error": str(e)}

    print("\n" + "=" * 50)

    # ── Emax ──
    print("\n🛒 EMAX SCRAPER")
    print("-" * 50)
    try:
        emax_total = await scrape_emax(max_categories=5)
        results["emax"] = {"status": "✅ success", "saved": emax_total}
    except Exception as e:
        print(f"❌ Emax scraper failed: {e}")
        results["emax"] = {"status": "❌ failed", "saved": 0, "error": str(e)}

    # ── Summary ──
    print("\n" + "=" * 50)
    print("📊 SCRAPING SUMMARY")
    print("=" * 50)
    total = 0
    for source, result in results.items():
        print(f"  {source.upper():<10} {result['status']}  →  {result['saved']} products saved")
        total += result["saved"]
    print(f"\n  {'TOTAL':<10}                {total} products")
    print(f"\n⏰ Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(run_all_scrapers())