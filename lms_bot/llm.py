from __future__ import annotations

import json

from openai import OpenAI

from lms_bot.config import settings


class LLMClient:
    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required for LLM features.")
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    def decide_next_action(self, state: dict) -> dict:
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You help control an LMS browser automation script. "
                        "Return only compact JSON with keys action, target_text, target_selector, value, reason. "
                        "Allowed actions: click, type, answer, wait, done. "
                        "Prefer deterministic actions and never invent elements that are not present in the state. "
                        "Only return action=done if the provided state explicitly shows completion, such as completed=true, "
                        "progress=100, or visible completion text."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(state, ensure_ascii=True),
                },
            ],
        )
        content = response.choices[0].message.content or "{}"
        return _safe_json_loads(content)

    def answer_question(self, question: str, answers: list[str]) -> str:
        prompt = (
            "Answer the following multiple choice question. "
            "Return ONLY the correct option text.\n\n"
            f"Question: {question}\n"
            "Options:\n"
            + "\n".join(f"- {answer}" for answer in answers)
        )
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": "Answer training quiz questions carefully. Return only one option exactly as written.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )
        return (response.choices[0].message.content or "").strip()


def _safe_json_loads(content: str) -> dict:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json\n", "", 1).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return {"action": "wait", "reason": f"Invalid JSON from model: {cleaned[:200]}"}
    return data if isinstance(data, dict) else {"action": "wait", "reason": "Model response was not an object."}
