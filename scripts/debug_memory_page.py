"""Debug Memory page render."""
import asyncio
from playwright.async_api import async_playwright

async def debug_memory():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = await browser.new_context(viewport={'width': 1280, 'height': 720})
        page = await context.new_page()

        # Capture console logs
        page.on("console", lambda msg: print(f"  [CONSOLE.{msg.type}] {msg.text[:200]}", flush=True))
        page.on("pageerror", lambda exc: print(f"  [PAGEERROR] {str(exc)[:300]}", flush=True))

        await page.goto('http://127.0.0.1:8501/', wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(4000)

        # Click Memory page
        print("=== Clicking Memory page ===", flush=True)
        try:
            await page.locator('button:has-text("Memory")').first.click(timeout=5000)
            print("  Clicked Memory", flush=True)
        except Exception as e:
            print(f"  Click failed: {e}", flush=True)

        await page.wait_for_timeout(5000)

        # Check current page state
        page_state = await page.evaluate("""() => {
            return {
                'url': window.location.href,
                'sidebarText': document.querySelector('[data-testid="stSidebar"]')?.innerText || '',
                'mainText': document.querySelector('section.main')?.innerText || '',
                'mainHTML': document.querySelector('section.main')?.innerHTML || '',
            };
        }""")
        print("=== PAGE STATE ===", flush=True)
        print(f"Sidebar text length: {len(page_state['sidebarText'])}", flush=True)
        print(f"Main text length: {len(page_state['mainText'])}", flush=True)
        print(f"Main HTML length: {len(page_state['mainHTML'])}", flush=True)
        print(f"Main text first 500: {page_state['mainText'][:500]}", flush=True)
        print(f"Main HTML first 500: {page_state['mainHTML'][:500]}", flush=True)

        # Save debug log
        with open(r"E:\Projects and systems managed by the team of experts\Alpha Wolf Agent\logs\memory_page_debug.log", "w") as f:
            f.write(f"URL: {page_state['url']}\n\n")
            f.write(f"Sidebar:\n{page_state['sidebarText']}\n\n")
            f.write(f"Main text:\n{page_state['mainText']}\n\n")
            f.write(f"Main HTML:\n{page_state['mainHTML']}\n")
        print("Debug log saved", flush=True)
        print("\n=== PAGE STATE ===", flush=True)
        print(f"Body: {page_state['bodyText'][:300]}", flush=True)
        print(f"Main: {page_state['mainText'][:300]}", flush=True)

        # Look for any error text on page
        error_elements = await page.locator('.stAlert, [data-testid="stException"]').all()
        for el in error_elements:
            text = await el.text_content()
            print(f"  ERROR on page: {text[:200]}", flush=True)

        await browser.close()

asyncio.run(debug_memory())
