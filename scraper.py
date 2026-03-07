import asyncio
from playwright.async_api import async_playwright
import pandas as pd

async def scrape_dublin_properties():
    async with async_playwright() as p:
        # Launch browser (headless=True means it runs in the background)
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Set a User-Agent to look like a standard browser
        await page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

        # Navigate to the Dublin Sale listings
        # Note: In a real scenario, you'd loop through pagination pages
        url = "https://www.daft.ie/property-for-sale/dublin-city"
        print(f"Navigating to {url}...")
        await page.goto(url, wait_until="networkidle")

        # Locate property cards using the data-testid attribute (standard for modern sites)
        listings = await page.locator('data-testid=card').all()
        
        property_data = []

        for listing in listings:
            try:
                # Extracting specific elements
                price = await listing.locator('data-testid=price').inner_text()
                address = await listing.locator('data-testid=address').inner_text()
                
                # Extract the URL to get the unique Property ID
                link_element = listing.locator('a')
                link = await link_element.get_attribute('href')
                prop_id = link.split('/')[-1] if link else "N/A"

                property_data.append({
                    "id": prop_id,
                    "price": price.replace('€', '').replace(',', '').strip(),
                    "address": address,
                    "link": f"https://www.daft.ie{link}"
                })
            except Exception as e:
                continue

        await browser.close()
        
        # Save to DataFrame for analysis
        df = pd.DataFrame(property_data)
        print(f"Successfully scraped {len(df)} properties.")
        return df

# Run the script
if __name__ == "__main__":
    df_results = asyncio.run(scrape_dublin_properties())
    print(df_results.head())
    # df_results.to_csv("dublin_properties.csv", index=False)
