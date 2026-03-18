from __future__ import annotations

import re
from typing import Any, Optional


def simplify_dom_state(dom: dict[str, Any], visible_text: str) -> dict[str, Any]:
    buttons = _unique_texts(item.get("text", "") for item in dom.get("buttons", []))
    inputs = [
        {
            "selector": item.get("selector", ""),
            "type": item.get("type", "text"),
            "label": item.get("label", ""),
            "placeholder": item.get("placeholder", ""),
            "name": item.get("name", ""),
        }
        for item in dom.get("inputs", [])
    ]

    answers = _extract_answers(dom)
    question = _extract_question(dom, visible_text, answers)
    progress = _extract_progress(dom, visible_text)
    completion_detected = _is_completed(visible_text, dom.get("headings", []), progress)
    login_detected = _is_login_state(visible_text, inputs)

    return {
        "url": dom.get("url", ""),
        "title": dom.get("title", ""),
        "buttons": buttons,
        "inputs": inputs,
        "question": question,
        "answers": answers,
        "progress": progress,
        "completed": completion_detected,
        "login_detected": login_detected,
        "headings": dom.get("headings", []),
        "text_excerpt": visible_text[:4000],
    }


def _extract_answers(dom: dict[str, Any]) -> list[str]:
    radio_texts = [
        item.get("text", "").strip()
        for item in dom.get("radio_options", [])
        if item.get("type") == "radio"
    ]
    radio_texts = [text for text in radio_texts if text]
    if len(radio_texts) >= 2:
        return _unique_texts(radio_texts)

    text_blocks = dom.get("text_blocks", [])
    detected: list[str] = []
    for block in text_blocks:
        if re.match(r"^[A-D][\.\)]\s+.+", block):
            detected.append(block.strip())
    return _unique_texts(detected)


def _extract_question(dom: dict[str, Any], visible_text: str, answers: list[str]) -> Optional[str]:
    if _looks_like_identity_prompt(dom, visible_text):
        return None

    heading_candidates = [item for item in dom.get("headings", []) if _looks_like_question(item)]
    if heading_candidates:
        return heading_candidates[0]

    for block in dom.get("text_blocks", []):
        if _looks_like_question(block):
            return block.strip()

    if answers:
        lines = [line.strip() for line in visible_text.splitlines() if line.strip()]
        for line in lines:
            if _looks_like_question(line):
                return line
    return None


def _extract_progress(dom: dict[str, Any], visible_text: str) -> Optional[int]:
    progress = dom.get("progress")
    if isinstance(progress, (int, float)):
        value = int(progress)
        if 0 <= value <= 100:
            return value

    match = re.search(r"(\d{1,3})\s*%", visible_text)
    if match:
        value = int(match.group(1))
        if 0 <= value <= 100:
            return value
    return None


def _is_completed(visible_text: str, headings: list[str], progress: Optional[int]) -> bool:
    haystack = " ".join(headings + [visible_text]).lower()
    positive_patterns = [
        r"\btraining completed\b",
        r"\btraining complete\b",
        r"\bcourse completed\b",
        r"\bcourse complete\b",
        r"\bpathway completed\b",
        r"\byou completed\b",
        r"\bcompletion certificate\b",
        r"\bcongratulations\b",
        r"\byou passed\b",
    ]
    negative_patterns = [
        r"\bmark as completed\b",
        r"\bmark complete\b",
        r"\bcomplete this course\b",
        r"\bcomplete this training\b",
    ]
    if any(re.search(pattern, haystack) for pattern in negative_patterns):
        return progress == 100
    if any(re.search(pattern, haystack) for pattern in positive_patterns):
        return True
    return progress == 100


def _is_login_state(visible_text: str, inputs: list[dict[str, str]]) -> bool:
    haystack = visible_text.lower()
    if any(token in haystack for token in ("login", "log in", "sign in", "password", "stay signed in")):
        return True
    return any(item.get("type") == "password" for item in inputs)


def _looks_like_question(text: str) -> bool:
    normalized = text.strip()
    return normalized.endswith("?") or normalized.lower().startswith(
        ("question", "which", "what", "when", "where", "who", "select", "choose")
    )


def _looks_like_identity_prompt(dom: dict[str, Any], visible_text: str) -> bool:
    haystack = " ".join([dom.get("title", ""), visible_text]).lower()
    identity_tokens = [
        "sign in to your account",
        "enter a valid email address",
        "can't access your account",
        "stay signed in",
        "microsoft",
        "password",
    ]
    return any(token in haystack for token in identity_tokens)


def _unique_texts(items: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        value = str(item).strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
