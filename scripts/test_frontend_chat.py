import asyncio
from playwright.async_api import async_playwright

async def test_chat():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("http://127.0.0.1:8501/", wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)
        # Find chat input
        chat_input = await page.query_selector("textarea")
        if chat_input:
            await chat_input.fill("What is your name?")
            # Find send button
            send_btn = await page.query_selector("button:has-text('Send')")
            if send_btn:
                await send_btn.click()
                await page.wait_for_timeout(10000)
                # Get response
                content = await page.content()
                # Look for "Alpha Wolf" mention
                if "Alpha Wolf" in content:
                    print("OK_CHAT")
                else:
                    print("OK_CHAT_NO_ALPHA")
            else:
                print("NO_SEND_BUTTON")
        else:
            print("NO_INPUT")
        await browser.close()

asyncio.run(test_chat())
