"""Capture full HTML of Memory page after fresh load + click."""
import asyncio
from playwright.async_api import async_playwright

async def capture_full():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = await browser.new_context(viewport={'width': 1280, 'height': 720})
        page = await context.new_page()
        await page.goto('http://127.0.0.1:8501/', wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(5000)

        # Click Memory
        try:
            await page.locator('button:has-text("Memory")').first.click(timeout=5000)
            print("Clicked Memory", flush=True)
        except Exception as e:
            print(f"Click failed: {e}", flush=True)
        await page.wait_for_timeout(8000)  # Long wait for rerun

        # Save full HTML
        html = await page.content()
        with open(r"E:\Projects and systems managed by the team of experts\Alpha Wolf Agent\logs\memory_full.html", "w", encoding="utf-8") as f:
            f.write(html)
        print(f"HTML saved ({len(html)} bytes)", flush=True)

        # Check what the page actually shows
        main = await page.evaluate("""() => {
            const m = document.querySelector('section.main');
            if (!m) return 'no section.main found';
            return {
                text: m.innerText,
                childCount: m.children.length,
                innerHTML_len: m.innerHTML.length
            };
        }""")
        print(f"Main content: {main}", flush=True)

        await browser.close()

asyncio.run(capture_full())
