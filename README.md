# LMS Training Bot MVP

Deterministic-first Python bot for automating LMS trainings with Playwright and OpenAI.

This project opens a training URL, handles common login screens, navigates the course UI, starts lesson media when pages are gated behind video playback, answers quiz questions with OpenAI when needed, and detects completion using explicit signals like completion text or `100%` progress.

## Goals

- Keep the controller loop simple and debuggable
- Prefer deterministic actions over LLM decisions
- Use the LLM only for quiz answering and unknown UI states
- Be practical enough for MVP usage without adding heavy frameworks

## Tech Stack

- Python
- Playwright for browser automation
- OpenAI Chat Completions API

## Project Structure

```text
lms_bot/
  main.py
  browser.py
  actions.py
  parser.py
  llm.py
  config.py
```

## How It Works

The controller in [lms_bot/main.py](/Users/michalmrozik/Documents/Training-Assistant/lms_bot/main.py) runs this loop:

```python
while not completed:
    state = parse_page()
    action = decide_next_step(state)
    execute(action)
```

Execution priority is:

1. Deterministic buttons like `Next`, `Start`, `Continue`, `Resume`
2. Login handling for common Microsoft-style sign-in flows
3. Media playback for video-gated lessons
4. Quiz answering with OpenAI
5. LLM fallback for unknown states

Completion is detected only from strong signals such as explicit completion language or `progress == 100`.

## Features

- Opens any supplied LMS training URL
- Saves and reuses Playwright session state in `.playwright-state.json`
- Detects login pages and can submit credentials from `.env`
- Detects visible HTML5 media and attempts to start playback automatically
- Extracts a simplified page state instead of sending raw HTML to the LLM
- Adds small random delays and light mouse movement before clicks
- Retries quiz answers if feedback indicates the selected answer was wrong
- Saves screenshots on failures to `artifacts/screenshots/`

## Requirements

- Python 3.9+ currently supported in code
- Playwright Chromium browser
- OpenAI API key for quiz answering and unknown-state fallback

Python 3.11+ is still the recommended target for production use.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Configuration

Create a local environment file:

```bash
cp .env.example .env
```

Then fill in values as needed:

```env
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

LMS_USERNAME=
LMS_PASSWORD=

HEADLESS=false
SLOW_MO_MS=0
DEFAULT_TIMEOUT_MS=15000

COOKIES_PATH=.playwright-state.json
SCREENSHOT_DIR=artifacts/screenshots

LOOP_DELAY_MIN_SECONDS=1
LOOP_DELAY_MAX_SECONDS=3
MAX_STEPS=200
```

Notes:

- `OPENAI_API_KEY` is required for quiz answering and LLM fallback
- `LMS_USERNAME` and `LMS_PASSWORD` are optional, but needed for automatic login
- `.env` is loaded automatically by [lms_bot/config.py](/Users/michalmrozik/Documents/Training-Assistant/lms_bot/config.py)

## Running

```bash
python -m lms_bot.main "https://your-lms.example/training"
```

Example:

```bash
python -m lms_bot.main "https://endavauniversity.edcast.com/pathways/leading-in-the-age-of-ai"
```

## Logging

The bot logs each step and action to stdout, for example:

```text
STEP 3
CLICK Next
ANSWER Option B
NAVIGATE Submitted login form.
COMPLETED Training completed.
```

## Module Responsibilities

- [lms_bot/main.py](/Users/michalmrozik/Documents/Training-Assistant/lms_bot/main.py): controller loop and action priority
- [lms_bot/browser.py](/Users/michalmrozik/Documents/Training-Assistant/lms_bot/browser.py): Playwright startup, page interaction, screenshots, cookie/session persistence
- [lms_bot/actions.py](/Users/michalmrozik/Documents/Training-Assistant/lms_bot/actions.py): clicking buttons, filling fields, quiz answer selection
- [lms_bot/parser.py](/Users/michalmrozik/Documents/Training-Assistant/lms_bot/parser.py): simplified DOM parsing and completion/login detection
- [lms_bot/llm.py](/Users/michalmrozik/Documents/Training-Assistant/lms_bot/llm.py): OpenAI calls for next-action fallback and quiz answers
- [lms_bot/config.py](/Users/michalmrozik/Documents/Training-Assistant/lms_bot/config.py): environment/config loading

## Simplified State Format

The parser reduces page state into a compact structure like:

```json
{
  "buttons": ["Next", "Submit", "Start"],
  "inputs": [
    {
      "selector": "#i0116",
      "type": "email",
      "label": "Email, phone, or Skype"
    }
  ],
  "question": "What is the correct answer?",
  "answers": ["A", "B", "C", "D"],
  "progress": 45,
  "completed": false
}
```

## Current Behavior and Limits

- The bot is deterministic-first, but LMS UIs vary a lot
- Login handling is basic and best-effort, not a full identity-platform integration
- Quiz answering depends on the OpenAI API and the quality of extracted question/answer text
- Some trainings may use canvas or deeply embedded iframe players that still need LMS-specific selectors
- The current implementation is sync Playwright for simplicity, not async

## Security Notes

- Do not commit `.env`
- Do not commit `.playwright-state.json`
- Session state may contain authentication cookies
- Review organization policies before using automation on corporate LMS platforms

## Troubleshooting

If the bot exits early:

- Check whether the page showed a redirect or login challenge
- Confirm `LMS_USERNAME` and `LMS_PASSWORD` are set when login is required
- Confirm `OPENAI_API_KEY` is set when quizzes or unknown states appear

If Playwright is missing Chromium:

```bash
playwright install chromium
```

If the bot gets stuck:

- Run with `HEADLESS=false`
- Inspect the latest screenshot in `artifacts/screenshots/`
- Review the printed `STEP` state and action logs

## Dependencies

See [requirements.txt](/Users/michalmrozik/Documents/Training-Assistant/requirements.txt).
