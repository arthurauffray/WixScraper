from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from typing import Any, Optional

from playwright.async_api import async_playwright


def _pick_executable_path(requested_path: Optional[str]) -> Optional[str]:
    if requested_path and os.path.exists(requested_path):
        return requested_path

    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ]

    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate

    for binary in ("google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(binary)
        if found:
            return found

    return None


@dataclass
class _ElementHandleWrapper:
    handle: Any

    async def click(self):
        await self.handle.click()

    async def querySelector(self, selector: str):
        element = await self.handle.query_selector(selector)
        return _ElementHandleWrapper(element) if element is not None else None

    async def querySelectorAllEval(self, selector: str, expression: str):
        return await self.handle.evaluate(
            """
            (root, payload) => {
                const [selector, fnSource] = payload;
                const nodes = Array.from(root.querySelectorAll(selector));
                const fn = eval(fnSource);
                return fn(nodes);
            }
            """,
            [selector, expression],
        )


@dataclass
class _PageWrapper:
    page: Any

    @property
    def url(self):
        return self.page.url

    async def goto(self, url: str, wait_until: str | None = None, timeout: int | None = None):
        kwargs = {}
        if wait_until is not None:
            kwargs["wait_until"] = wait_until
        if timeout is not None:
            kwargs["timeout"] = timeout
        return await self.page.goto(url, **kwargs)

    async def setDefaultNavigationTimeout(self, timeout_ms: int):
        self.page.set_default_navigation_timeout(timeout_ms)

    async def evaluate(self, expression: str, arg: Any = None):
        if isinstance(arg, _ElementHandleWrapper):
            arg = arg.handle
        return await self.page.evaluate(expression, arg)

    async def addScriptTag(self, url: str = None, content: str = None):
        kwargs = {}
        if url is not None:
            kwargs["url"] = url
        if content is not None:
            kwargs["content"] = content
        return await self.page.add_script_tag(**kwargs)

    async def addStyleTag(self, url: str = None, content: str = None):
        kwargs = {}
        if url is not None:
            kwargs["url"] = url
        if content is not None:
            kwargs["content"] = content
        return await self.page.add_style_tag(**kwargs)

    async def querySelector(self, selector: str):
        element = await self.page.query_selector(selector)
        return _ElementHandleWrapper(element) if element is not None else None

    async def querySelectorAll(self, selector: str):
        elements = await self.page.query_selector_all(selector)
        return [_ElementHandleWrapper(element) for element in elements]

    async def querySelectorAllEval(self, selector: str, expression: str):
        return await self.page.eval_on_selector_all(selector, expression)


class _BrowserWrapper:
    def __init__(self, playwright, browser):
        self._playwright = playwright
        self._browser = browser

    async def newPage(self):
        page = await self._browser.new_page()
        return _PageWrapper(page)

    async def close(self):
        await self._browser.close()
        await self._playwright.stop()


async def launch(*args, **kwargs):
    headless = kwargs.pop("headless", False)
    kwargs.pop("defaultViewport", None)
    requested_path = kwargs.pop("executablePath", None)
    browser_args = kwargs.pop("args", None) or []

    executable_path = _pick_executable_path(requested_path)

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=headless,
        executable_path=executable_path,
        args=browser_args,
    )
    return _BrowserWrapper(playwright, browser)