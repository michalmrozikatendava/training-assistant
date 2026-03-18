from __future__ import annotations

import json
import random
import time
from typing import Any, Optional

from playwright.sync_api import Browser, BrowserContext, Error, Page, Playwright, TimeoutError, sync_playwright

from lms_bot.config import settings


class BrowserSession:
    def __init__(self) -> None:
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

    def start(self) -> None:
        state_path = settings.cookies_path if settings.cookies_path.exists() else None
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=settings.headless,
            slow_mo=settings.slow_mo_ms,
        )
        self._context = self._browser.new_context(storage_state=state_path)
        self._context.set_default_timeout(settings.default_timeout_ms)
        self.page = self._context.new_page()

    def stop(self) -> None:
        if self._context is not None:
            self.save_cookies()
            self._context.close()
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()

    def open_url(self, url: str) -> None:
        page = self.require_page()
        page.goto(url, wait_until="domcontentloaded")
        self.wait_until_stable()

    def click(self, selector: str) -> None:
        page = self.require_page()
        locator = page.locator(selector).first
        locator.wait_for(state="visible")
        box = locator.bounding_box()
        if box:
            target_x = box["x"] + min(max(box["width"] * 0.5, 4), box["width"] - 2)
            target_y = box["y"] + min(max(box["height"] * 0.5, 4), box["height"] - 2)
            jitter_x = random.uniform(-8, 8)
            jitter_y = random.uniform(-8, 8)
            page.mouse.move(target_x + jitter_x, target_y + jitter_y, steps=random.randint(8, 16))
            time.sleep(random.uniform(0.1, 0.3))
        locator.click()

    def type(self, selector: str, text: str) -> None:
        locator = self.require_page().locator(selector).first
        locator.wait_for(state="visible")
        locator.click()
        locator.fill("")
        locator.type(text, delay=random.randint(35, 90))

    def get_dom(self) -> dict[str, Any]:
        page = self.require_page()
        for _ in range(3):
            try:
                self.wait_until_stable()
                return page.evaluate(
                    """
                    () => {
                      const isVisible = (el) => {
                        const style = window.getComputedStyle(el);
                        const rect = el.getBoundingClientRect();
                        return style.visibility !== "hidden" &&
                               style.display !== "none" &&
                               rect.width > 0 &&
                               rect.height > 0;
                      };

                      const cssPath = (el) => {
                        if (el.id) return `#${CSS.escape(el.id)}`;
                        const parts = [];
                        let node = el;
                        while (node && node.nodeType === Node.ELEMENT_NODE && parts.length < 4) {
                          let part = node.tagName.toLowerCase();
                          if (node.classList.length) {
                            part += "." + Array.from(node.classList).slice(0, 2).map((c) => CSS.escape(c)).join(".");
                          }
                          const parent = node.parentElement;
                          if (parent) {
                            const siblings = Array.from(parent.children).filter((child) => child.tagName === node.tagName);
                            if (siblings.length > 1) {
                              part += `:nth-of-type(${siblings.indexOf(node) + 1})`;
                            }
                          }
                          parts.unshift(part);
                          node = parent;
                        }
                        return parts.join(" > ");
                      };

                      const textOf = (el) => (el.innerText || el.textContent || "").trim().replace(/\\s+/g, " ");
                      const labelOf = (el) => {
                        if (el.labels && el.labels.length) return textOf(el.labels[0]);
                        const aria = el.getAttribute("aria-label");
                        return aria ? aria.trim() : "";
                      };

                      const buttons = Array.from(document.querySelectorAll("button, a[role='button'], input[type='button'], input[type='submit']"))
                        .filter(isVisible)
                        .map((el) => ({
                          text: textOf(el) || el.getAttribute("value") || "",
                          selector: cssPath(el)
                        }))
                        .filter((item) => item.text);

                      const inputs = Array.from(document.querySelectorAll("input, textarea"))
                        .filter(isVisible)
                        .map((el) => ({
                          selector: cssPath(el),
                          type: (el.getAttribute("type") || "text").toLowerCase(),
                          placeholder: el.getAttribute("placeholder") || "",
                          label: labelOf(el),
                          name: el.getAttribute("name") || ""
                        }));

                      const radioOptions = Array.from(document.querySelectorAll("input[type='radio'], input[type='checkbox']"))
                        .filter(isVisible)
                        .map((el) => {
                          const label = labelOf(el) || textOf(el.closest("label") || el.parentElement || el);
                          return {
                            selector: cssPath(el),
                            type: el.getAttribute("type"),
                            text: label
                          };
                        })
                        .filter((item) => item.text);

                      const headings = Array.from(document.querySelectorAll("h1, h2, h3, legend, [role='heading']"))
                        .filter(isVisible)
                        .map((el) => textOf(el))
                        .filter(Boolean);

                      const textBlocks = Array.from(document.querySelectorAll("p, li, div, span"))
                        .filter(isVisible)
                        .map((el) => textOf(el))
                        .filter((text) => text && text.length > 20)
                        .slice(0, 80);

                      const progressEl = document.querySelector("progress, [role='progressbar'], .progress, .progress-bar");
                      let progress = null;
                      if (progressEl) {
                        const raw = progressEl.getAttribute("aria-valuenow") ||
                          progressEl.getAttribute("value") ||
                          textOf(progressEl).match(/(\\d{1,3})\\s*%/)?.[1] ||
                          null;
                        progress = raw ? Number(raw) : null;
                      }

                      return {
                        url: window.location.href,
                        title: document.title,
                        buttons,
                        inputs,
                        radio_options: radioOptions,
                        headings,
                        text_blocks: textBlocks,
                        progress
                      };
                    }
                    """
                )
            except Error as exc:
                if "Execution context was destroyed" not in str(exc):
                    raise
                time.sleep(1)
        raise RuntimeError("Unable to extract DOM after repeated navigation transitions.")

    def get_visible_text(self) -> str:
        page = self.require_page()
        for _ in range(3):
            try:
                self.wait_until_stable()
                body = page.locator("body")
                return body.inner_text(timeout=3000).strip()
            except Error as exc:
                if "Execution context was destroyed" not in str(exc):
                    return ""
                time.sleep(1)
            except Exception:
                return ""
        return ""

    def screenshot(self, name: Optional[str] = None) -> str:
        page = self.require_page()
        settings.screenshot_dir.mkdir(parents=True, exist_ok=True)
        file_name = name or f"screenshot-{int(time.time())}.png"
        path = settings.screenshot_dir / file_name
        page.screenshot(path=str(path), full_page=True)
        return str(path)

    def save_cookies(self) -> None:
        if self._context is None:
            return
        settings.cookies_path.parent.mkdir(parents=True, exist_ok=True)
        self._context.storage_state(path=str(settings.cookies_path))

    def load_cookies(self) -> None:
        if self._context is None or not settings.cookies_path.exists():
            return
        state = json.loads(settings.cookies_path.read_text())
        self._context.add_cookies(state.get("cookies", []))

    def is_login_page(self) -> bool:
        text = self.get_visible_text().lower()
        if any(token in text for token in ("sign in", "log in", "login", "password")):
            return True
        dom = self.get_dom()
        input_types = {item.get("type", "") for item in dom.get("inputs", [])}
        return "password" in input_types

    def attempt_login(self) -> bool:
        if not settings.lms_username or not settings.lms_password:
            return False

        page = self.require_page()
        username_selectors = [
            "input[type='email']",
            "input[name='email']",
            "input[name='username']",
            "input[id*='user']",
            "input[type='text']",
        ]
        password_selectors = [
            "input[type='password']",
        ]
        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Sign in')",
            "button:has-text('Log in')",
            "button:has-text('Login')",
        ]

        username_selector = self._first_existing_selector(page, username_selectors)
        password_selector = self._first_existing_selector(page, password_selectors)
        submit_selector = self._first_existing_selector(page, submit_selectors)

        if username_selector and self._input_is_empty(page, username_selector):
            self.type(username_selector, settings.lms_username)
            if submit_selector:
                self.click(submit_selector)
            else:
                page.keyboard.press("Enter")
            return True

        if password_selector:
            self.type(password_selector, settings.lms_password)
            if submit_selector:
                self.click(submit_selector)
            else:
                page.keyboard.press("Enter")
            return True

        return False

    def _first_existing_selector(self, page: Page, selectors: list[str]) -> Optional[str]:
        for selector in selectors:
            try:
                if page.locator(selector).first.count() > 0:
                    return selector
            except Exception:
                continue
        return None

    def require_page(self) -> Page:
        if self.page is None:
            raise RuntimeError("Browser session has not been started.")
        return self.page

    def _input_is_empty(self, page: Page, selector: str) -> bool:
        try:
            value = page.locator(selector).first.input_value(timeout=1000)
            return not value.strip()
        except Exception:
            return True

    def wait_until_stable(self) -> None:
        page = self.require_page()
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except TimeoutError:
            pass
        try:
            page.wait_for_load_state("networkidle", timeout=3000)
        except TimeoutError:
            pass
