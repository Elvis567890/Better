"""Browser tool."""
from . import tool


@tool("browser.open", "Open URL headless and return text.",
      {"type": "object", "properties": {"url": {"type": "string"}},
       "required": ["url"]})
async def browser_open(url):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        pg = await b.new_page()
        await pg.goto(url, wait_until="domcontentloaded", timeout=45000)
        text = await pg.inner_text("body")
        await b.close()
        return {"url": url, "text": text[:8000]}
