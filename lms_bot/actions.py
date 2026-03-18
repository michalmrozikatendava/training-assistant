from __future__ import annotations

import json
import random
import time

from playwright.sync_api import Page

from lms_bot.browser import BrowserSession
from lms_bot.config import settings
from lms_bot.llm import LLMClient


def click_button_by_text(browser: BrowserSession, text: str) -> bool:
    page = browser.require_page()
    locator_builders = [
        lambda: page.get_by_role("button", name=text, exact=True).first,
        lambda: page.locator(f"a[role='button']:has-text({json.dumps(text)})").first,
        lambda: page.locator(f"input[value={json.dumps(text)}]").first,
        lambda: page.get_by_text(text, exact=True).first,
    ]
    for build_locator in locator_builders:
        try:
            locator = build_locator()
            if locator.count() > 0:
                locator.wait_for(state="visible")
                box = locator.bounding_box()
                if box:
                    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=random.randint(8, 16))
                locator.click()
                _sleep_like_human()
                return True
        except Exception:
            continue
    return False


def fill_input(browser: BrowserSession, selector: str, value: str) -> None:
    browser.type(selector, value)
    _sleep_like_human()


def answer_question(browser: BrowserSession, llm: LLMClient, question_data: dict) -> bool:
    question = question_data.get("question")
    answers = question_data.get("answers", [])
    if not question or not answers:
        return False

    ordered_answers = _ordered_answers(llm, question, answers)
    for option_text in ordered_answers:
        print(f"ANSWER {option_text}")
        if _select_answer_option(browser.require_page(), option_text):
            _sleep_like_human()
            if click_button_by_text(browser, "Submit"):
                print("CLICK Submit")
            elif click_button_by_text(browser, "Check"):
                print("CLICK Check")
            elif click_button_by_text(browser, "Next"):
                print("CLICK Next")
            _sleep_like_human()
            if _answer_marked_incorrect(browser):
                print(f"RETRY Answer rejected for option: {option_text}")
                continue
            if click_button_by_text(browser, "Next"):
                print("CLICK Next")
            elif click_button_by_text(browser, "Continue"):
                print("CLICK Continue")
            return True
    return False


def fallback_click_by_selector(browser: BrowserSession, selector: str) -> bool:
    try:
        browser.click(selector)
        _sleep_like_human()
        return True
    except Exception:
        return False


def _ordered_answers(llm: LLMClient, question: str, answers: list[str]) -> list[str]:
    first_choice = llm.answer_question(question, answers)
    ordered = []
    for answer in [first_choice, *answers]:
        normalized = answer.strip()
        if normalized and normalized not in ordered:
            ordered.append(normalized)
    return ordered


def _select_answer_option(page: Page, option_text: str) -> bool:
    locator_builders = [
        lambda: page.get_by_label(option_text, exact=True).first,
        lambda: page.get_by_text(option_text, exact=True).first,
        lambda: page.locator(f"[role='radio']:has-text({json.dumps(option_text)})").first,
        lambda: page.locator(f"[role='checkbox']:has-text({json.dumps(option_text)})").first,
    ]
    for build_locator in locator_builders:
        try:
            locator = build_locator()
            if locator.count() > 0:
                locator.click()
                return True
        except Exception:
            continue
    return False


def _sleep_like_human() -> None:
    time.sleep(random.uniform(settings.loop_delay_min_seconds, settings.loop_delay_max_seconds))


def _answer_marked_incorrect(browser: BrowserSession) -> bool:
    feedback = browser.get_visible_text().lower()
    incorrect_tokens = [
        "incorrect",
        "wrong answer",
        "try again",
        "not correct",
        "incorrect answer",
    ]
    return any(token in feedback for token in incorrect_tokens)
