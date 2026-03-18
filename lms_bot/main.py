from __future__ import annotations

import argparse
import json
import time
from typing import Callable, Optional, Union

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from lms_bot.actions import answer_question, click_button_by_text, fallback_click_by_selector
from lms_bot.browser import BrowserSession
from lms_bot.config import settings
from lms_bot.llm import LLMClient
from lms_bot.parser import simplify_dom_state

DETERMINISTIC_BUTTONS = ["Next", "Start", "Continue", "Resume", "Launch", "Begin"]


def main() -> int:
    args = parse_args()
    browser = BrowserSession()
    llm = None

    try:
        browser.start()
        browser.open_url(args.url)
        llm = _build_llm_client()
        if llm is None:
            print("INFO OPENAI_API_KEY not set. Quiz answering and unknown-state fallback are disabled.")
        run_controller_loop(browser, llm)
        return 0
    except KeyboardInterrupt:
        print("Stopped by user.")
        return 130
    except Exception as exc:
        print(f"ERROR {exc}")
        try:
            screenshot_path = browser.screenshot("error.png")
            print(f"SCREENSHOT {screenshot_path}")
        except Exception:
            pass
        return 1
    finally:
        browser.stop()


def run_controller_loop(browser: BrowserSession, llm: Optional[LLMClient]) -> None:
    for step in range(1, settings.max_steps + 1):
        dom = browser.get_dom()
        visible_text = browser.get_visible_text()
        state = simplify_dom_state(dom, visible_text)

        print(f"STEP {step}")
        print(json.dumps({k: state[k] for k in ('url', 'title', 'buttons', 'question', 'answers', 'progress', 'completed')}, ensure_ascii=True))

        if state["completed"]:
            print("COMPLETED Training completed.")
            return

        if state["login_detected"] and browser.is_login_page():
            if browser.attempt_login():
                print("NAVIGATE Submitted login form.")
                time.sleep(2)
                continue
            print("WAIT Login page detected. Provide LMS_USERNAME/LMS_PASSWORD or complete authentication manually.")
            time.sleep(settings.loop_delay_max_seconds)
            continue

        if _try_deterministic_buttons(browser, state):
            continue

        media_state = state.get("media", {})
        if (media_state.get("present") or state.get("video_gate_detected")) and not media_state.get("completed"):
            if browser.play_media():
                print(
                    "PLAY Media playback started or resumed."
                    f" ({media_state.get('current_time', 0)}/{media_state.get('duration', 0)}s)"
                )
            else:
                print(
                    "WAIT Media detected and likely in progress."
                    f" ({media_state.get('current_time', 0)}/{media_state.get('duration', 0)}s)"
                )
            time.sleep(settings.loop_delay_max_seconds)
            continue

        if state["question"] and state["answers"]:
            if llm is None:
                raise RuntimeError("OPENAI_API_KEY is required to answer quiz questions.")
            if answer_question(browser, llm, state):
                continue

        if llm is None:
            print("WAIT No LLM configured and no deterministic action matched.")
            time.sleep(settings.loop_delay_max_seconds)
            continue

        llm_result = _run_llm_fallback(browser, llm, state)
        if llm_result == "done":
            print("COMPLETED LLM marked the training as done.")
            return
        if llm_result:
            continue

        print("WAIT No action executed.")
        time.sleep(settings.loop_delay_max_seconds)

    raise RuntimeError(f"Reached max steps ({settings.max_steps}) without completion.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deterministic-first LMS training bot")
    parser.add_argument("url", help="Training URL to open")
    return parser.parse_args()


def _build_llm_client() -> Optional[LLMClient]:
    if settings.openai_api_key:
        return LLMClient()
    return None


def _try_deterministic_buttons(browser: BrowserSession, state: dict) -> bool:
    available_buttons = {text.lower(): text for text in state.get("buttons", [])}
    for preferred in DETERMINISTIC_BUTTONS:
        if preferred.lower() in available_buttons and click_button_by_text(browser, available_buttons[preferred.lower()]):
            print(f"CLICK {available_buttons[preferred.lower()]}")
            return True

    extra_rules: list[tuple[Callable[[str], bool], str]] = [
        (lambda text: "next" in text.lower(), "Next"),
        (lambda text: "continue" in text.lower(), "Continue"),
        (lambda text: "start" in text.lower() or "begin" in text.lower(), "Start"),
    ]
    for matcher, label in extra_rules:
        for button_text in state.get("buttons", []):
            if matcher(button_text) and click_button_by_text(browser, button_text):
                print(f"CLICK {button_text or label}")
                return True
    return False


def _run_llm_fallback(browser: BrowserSession, llm: LLMClient, state: dict) -> Union[bool, str]:
    decision = llm.decide_next_action(state)
    action = str(decision.get("action", "wait")).lower()
    target_text = str(decision.get("target_text", "")).strip()
    target_selector = str(decision.get("target_selector", "")).strip()
    value = str(decision.get("value", "")).strip()

    print(f"LLM {json.dumps(decision, ensure_ascii=True)}")

    if action == "done":
        if state.get("completed") or state.get("progress") == 100:
            return "done"
        print("WAIT Ignoring premature LLM done decision.")
        return True

    if not state.get("buttons") and not state.get("inputs") and not state.get("question"):
        print("WAIT Sparse page state; waiting for more UI to render.")
        time.sleep(settings.loop_delay_max_seconds)
        return True

    if action == "click":
        if target_text and click_button_by_text(browser, target_text):
            print(f"CLICK {target_text}")
            return True
        if target_selector and fallback_click_by_selector(browser, target_selector):
            print(f"CLICK {target_selector}")
            return True

    if action == "type" and target_selector and value:
        browser.type(target_selector, value)
        print(f"TYPE {target_selector}")
        return True

    if action == "answer" and state.get("question") and state.get("answers"):
        return answer_question(browser, llm, state)

    if action == "wait":
        time.sleep(settings.loop_delay_max_seconds)
        return True

    return False


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PlaywrightTimeoutError as exc:
        print(f"ERROR Timeout: {exc}")
        raise SystemExit(1)
