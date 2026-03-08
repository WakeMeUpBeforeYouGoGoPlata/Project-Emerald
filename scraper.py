import asyncio
import sqlite3
from datetime import datetime
from playwright.async_api import async_playwright

# --- 1. DATABASE SETUP ---
def setup_db():
    conn = sqlite3.connect('dublin_properties.db')
    cursor = conn.cursor()
    # We store the first/last seen dates to calculate "Days on Market"
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS properties (
            prop_id TEXT PRIMARY KEY,
            address TEXT,
            first_seen DATE,
            last_seen DATE,
            asking_price INTEGER,
            status TEXT,
            days_on_market INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    return conn

# --- 2. SCRAPING LOGIC ---
async def scrape_dublin():
    properties = []
    async with async_playwright() as p:
        # Launching with specific arguments for GitHub Actions stability
browser = playwright.chromium.launch(headless=True)
        # Setting a realistic User-Agent to avoid being flagged as a bot
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        page = await context.new_page()

        print("Navigating to Daft.ie Dublin listings...")
        try:
            # Navigate to the Dublin City search results
            await page.goto("https://www.daft.ie/property-for-sale/dublin-city", wait_until="domcontentloaded", timeout=60000)
            
            # --- Anti-Block: Handle Cookie Banner ---
            try:
                await page.click('button:has-text("Accept All")', timeout=5000)
                print("Cookie banner cleared.")
            except:
                pass 

            # Wait for any property cards to load
            # Using a fuzzy selector that catches almost any property card type
            await page.wait_for_selector('[data-testid="card"], li[class*="Search"]', timeout=20000)
            
            # Select all listings on the page
            listings = await page.locator('[data-testid="card"], li[class*="Search"]').all()
            print(f"Found {len(listings)} potential listings on page.")

            for listing in listings:
                try:
                    # 1. Get Price (handling various potential tags)
                    price_element = listing.locator('[data-testid="price"], [class*="Price"]').first
                    raw_price = await price_element.inner_text()
                    
                    # Clean price: "€550,000" -> 550000
                    clean_price = int(''.join(filter(str.isdigit, raw_price)))
                    
                    # 2. Get Address
                    address_element = listing.locator('[data-testid="address"], [class*="Address"]').first
                    address = await address_element.inner_text()
                    
                    # 3. Get Unique Property ID from the URL
                    link_element = listing.locator('a[href*="/for-sale/"]').first
                    link = await link_element.get_attribute('href')
                    # Links look like /for-sale/house-dublin-8/1234567
                    prop_id = link.split('/')[-1]

                    if clean_price > 0:
                        properties.append({
                            "id": prop_id,
                            "address": address.strip(),
                            "price": clean_price
                        })
                except Exception:
                    # Skip this specific card if it's an ad or malformed
                    continue 

        except Exception as e:
            print(f"Critical error during scrape: {e}")
        
        await browser.close()
    return properties

# --- 3. SYNC DATA TO DATABASE ---
def update_database(conn, scraped_data):
    cursor = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')

    # Update or Insert active properties
    for item in scraped_data:
        cursor.execute('''
            INSERT INTO properties (prop_id, address, first_seen, last_seen, asking_price, status)
            VALUES (?, ?, ?, ?, ?, 'active')
            ON CONFLICT(prop_id) DO UPDATE SET
                last_seen = excluded.last_seen,
                asking_price = excluded.asking_price,
                status = 'active'
        ''', (item['id'], item['address'], today, today, item['price']))

    # If a property was 'active' yesterday but not found today, it's 'off-market'
    cursor.execute("UPDATE properties SET status = 'off-market' WHERE last_seen < ? AND status = 'active'", (today,))
    
    # Calculate Days on Market for everything
    cursor.execute('''
        UPDATE properties 
        SET days_on_market = CAST(julianday(last_seen) - julianday(first_seen) AS INTEGER)
    ''')
    
    conn.commit()
    print(f"Success! Database synced with {len(scraped_data)} active properties.")

# --- 4. MAIN RUNNER ---
async def main():
    db_conn = setup_db()
    data = await scrape_dublin()
    
    if data:
        update_database(db_conn, data)
    else:
        print("Scraper found 0 properties. Check the selectors or site URL.")
        
    db_conn.close()

if __name__ == "__main__":
    asyncio.run(main())
