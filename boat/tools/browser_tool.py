from . import tool

@tool("browser.open", "Open a URL headless and return visible text + links.",
      {"type": "object", "properties": {"url": {"type":"string"}}, "required": ["url"]})
async def browser_open(url):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        pg = await b.new_page()
        await pg.goto(url, wait_until="domcontentloaded", timeout=45000)
        text = await pg.inner_text("body")
        links = await pg.eval_on_selector_all("a", "els => els.slice(0,80).map(e => ({t:e.innerText.trim(), h:e.href}))")
        await b.close()
        return {"url": url, "text": text[:8000], "links": links}

@tool("browser.register",
      "Register on a site by filling selectors. Use only where automation is permitted.",
      {"type": "object", "properties": {"url": {"type":"string"},
                                        "fields": {"type":"object"},
                                        "submit_selector": {"type":"string"},
                                        "wait_after_ms": {"type":"integer","default":3000}},
       "required": ["url", "fields"]}, danger="high")
async def browser_register(url, fields, submit_selector=None, wait_after_ms=3000):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True)
        pg = await b.new_page()
        await pg.goto(url, wait_until="domcontentloaded", timeout=45000)
        for sel, val in fields.items():
            try: await pg.fill(sel, str(val), timeout=8000)
            except Exception as e: return {"ok": False, "at": sel, "error": str(e)}
        if submit_selector: await pg.click(submit_selector)
        await pg.wait_for_timeout(wait_after_ms)
        final = pg.url; text = (await pg.inner_text("body"))[:3000]
        await b.close()
        return {"ok": True, "final_url": final, "text": text}
