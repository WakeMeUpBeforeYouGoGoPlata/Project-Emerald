import asyncio
import sqlite3
from datetime import datetime
from playwright.async_api import async_playwright

# --- 1. DATABASE SETUP ---
def setup_db():
    conn = sqlite3.connect('dublin_properties.db')
    cursor = conn.cursor()
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
        # Launching with specific arguments to avoid GitHub Action crashes
        browser = await p.chromium.launch(headless=True)
        
        # Using a realistic User-Agent is the #1 way to avoid "Exit Code 1"
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        print("Navigating to Daft.ie...")
        try:
            # We use a wait_until to ensure the page actually loads before we scrape
            await page.goto("https://www.daft.ie/property-for-sale/dublin-city", wait_until="domcontentloaded", timeout=60000)
            
            # Wait for the property cards to appear
            await page.wait_for_selector('data-testid=card', timeout=10000)
            
            listings = await page.locator('data-testid=card').all()
            
            for listing in listings:
                try:
                    # Extract Price
                    raw_price = await listing.locator('data-testid=price').inner_text()
                    # Clean price: "€550,000" -> 550000
                    clean_price = int(''.join(filter(str.isdigit, raw_price)))
                    
                    # Extract Address
                    address = await listing.locator('data-testid=address').inner_text()
                    
                    # Extract ID from the link
                    link = await listing.locator('a').get_attribute('href')
                    prop_id = link.split('/')[-1]

                    properties.append({
                        "id": prop_id,
                        "address": address,
                        "price": clean_price
                    })
                except:
                    continue # Skip cards that don't match (like ads)

        except Exception as e:
            print(f"Error during scrape: {e}")
        
        await browser.close()
    return properties

# --- 3. SYNC DATA TO DATABASE ---
def update_database(conn, scraped_data):
    cursor = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')

    # Mark new/updated listings as active
    for item in scraped_data:
        cursor.execute('''
            INSERT INTO properties (prop_id, address, first_seen, last_seen, asking_price, status)
            VALUES (?, ?, ?, ?, ?, 'active')
            ON CONFLICT(prop_id) DO UPDATE SET
                last_seen = excluded.last_seen,
                asking_price = excluded.asking_price,
                status = 'active'
        ''', (item['id'], item['address'], today, today, item['price']))

    # Mark disappeared listings as 'off-market'
    cursor.execute("UPDATE properties SET status = 'off-market' WHERE last_seen < ?", (today,))
    
    # Calculate Days on Market
    cursor.execute('''
        UPDATE properties 
        SET days_on_market = CAST(julianday(last_seen) - julianday(first_seen) AS INTEGER)
    ''')
    
    conn.commit()
    print(f"Database updated with {len(scraped_data)} properties.")

# --- 4. MAIN EXECUTION ---
async def main():
    db_conn = setup_db()
    data = await scrape_dublin()
    if data:
        update_database(db_conn, data)
    else:
        print("No data found. Scraper might be blocked or selectors changed.")
    db_conn.close()

if __name__ == "__main__":
    asyncio.run(main())
