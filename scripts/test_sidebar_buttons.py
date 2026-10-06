"""Test sidebar buttons on the actual UI."""
import asyncio
import json
import sys
from playwright.async_api import async_playwright

async def test_sidebar_buttons():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = await browser.new_context(viewport={'width': 1280, 'height': 720})
        page = await context.new_page()
        await page.goto('http://127.0.0.1:8501/', wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(5000)

        # 1. Click on a conversation in sidebar
        print("=== Test 1: Click conversation in sidebar ===", flush=True)
        conv_btns = await page.locator('[data-testid="stSidebar"] button').all()
        print(f"  Found {len(conv_btns)} buttons in sidebar", flush=True)
        for i, btn in enumerate(conv_btns[:10]):
            text = await btn.text_content()
            print(f"  Button {i}: '{text[:50]}'", flush=True)

        # 2. Click on Memory page
        print("\n=== Test 2: Click Memory page ===", flush=True)
        memory_btn = page.locator('button:has-text("Memory")').first
        if await memory_btn.count() > 0:
            await memory_btn.click()
            await page.wait_for_timeout(3000)
            print("  Clicked Memory", flush=True)
            # Take screenshot
            await page.screenshot(path=r'E:\Projects and systems managed by the team of experts\Alpha Wolf Agent\frontend\screenshots\memory_page.png', full_page=True)
            print("  Screenshot saved", flush=True)
        else:
            print("  Memory button not found", flush=True)

        # 3. Click on Tools page
        print("\n=== Test 3: Click Tools page ===", flush=True)
        tools_btn = page.locator('button:has-text("Tools")').first
        if await tools_btn.count() > 0:
            await tools_btn.click()
            await page.wait_for_timeout(3000)
            print("  Clicked Tools", flush=True)
            await page.screenshot(path=r'E:\Projects and systems managed by the team of experts\Alpha Wolf Agent\frontend\screenshots\tools_page.png', full_page=True)
            print("  Screenshot saved", flush=True)
        else:
            print("  Tools button not found", flush=True)

        # 4. Go back to Chat
        print("\n=== Test 4: Click Chat page ===", flush=True)
        chat_btn = page.locator('button:has-text("Chat")').first
        if await chat_btn.count() > 0:
            await chat_btn.click()
            await page.wait_for_timeout(2000)
            print("  Clicked Chat", flush=True)

        # 5. Click delete (trash icon)
        print("\n=== Test 5: Click delete (trash) on a conversation ===", flush=True)
        trash_btns = await page.locator('button[kind="secondary"]').filter(has_text="🗑").all()
        if trash_btns:
            print(f"  Found {len(trash_btns)} trash buttons", flush=True)
        else:
            print("  No trash buttons found", flush=True)

        await browser.close()

asyncio.run(test_sidebar_buttons())
