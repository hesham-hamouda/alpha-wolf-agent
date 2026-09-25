import asyncio
from playwright.async_api import async_playwright

async def test_frontend():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("http://127.0.0.1:8501/", wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)

        # Find the chat tab - look for text "Chat with Alpha Wolf"
        try:
            chat_tab = page.get_by_text("Chat with Alpha Wolf", exact=False).first
            if await chat_tab.is_visible():
                await chat_tab.click()
                await page.wait_for_timeout(3000)
                print("OK: Clicked Chat tab")
        except Exception as e:
            print(f"INFO: No chat tab found: {e}")

        # Look for chat input
        try:
            chat_input = page.locator("textarea").first
            if await chat_input.is_visible():
                print("OK: Found chat input textarea")
                await chat_input.fill("What is your name?")

                # Find Send button
                send_btn = None
                for selector in ["button:has-text('Send')", "button[kind='primaryFormSubmit']", "button:has-text('Submit')", "button[aria-label*='send']", "button:has-text('send')"]:
                    try:
                        btn = page.locator(selector).first
                        if await btn.is_visible():
                            send_btn = btn
                            break
                    except:
                        pass

                if send_btn:
                    print(f"OK: Found send button")
                    await send_btn.click()
                    await page.wait_for_timeout(15000)

                    # Get response
                    content = await page.content()
                    if "Alpha Wolf" in content:
                        print("OK_CHAT: Response contains 'Alpha Wolf'")

                    # Find the last message
                    try:
                        chat_messages = await page.locator("[data-testid='stChatMessage']").all()
                        if chat_messages:
                            last_msg = chat_messages[-1]
                            text = await last_msg.inner_text()
                            print(f"CHAT_RESPONSE: {text[:200]}")
                    except:
                        pass
                else:
                    print("INFO: No send button found, trying Enter key")
                    await chat_input.press("Enter")
                    await page.wait_for_timeout(15000)
            else:
                print("INFO: No chat input found")
        except Exception as e:
            print(f"ERROR: Chat test failed: {e}")

        # Take screenshot
        await page.screenshot(path="E:/Projects and systems managed by the team of experts/Alpha Wolf Agent/frontend_test_screenshot.png", full_page=True)
        print("OK: Screenshot saved")

        # Get page title
        title = await page.title()
        print(f"PAGE_TITLE: {title}")

        await browser.close()

asyncio.run(test_frontend())
