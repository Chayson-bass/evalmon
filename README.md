# simpeval

**Know when your AI product breaks — before your users do.**

simpeval logs every LLM call your app makes, lets you write quality checks in plain English, and alerts you the moment your product starts degrading. Two lines of code. Works with OpenAI and Anthropic. Free to start.

---

## The Problem

You built an AI product. Users are paying. But every time you change a prompt, you have no idea if it got better or worse. When something breaks, your customer finds out before you do.

simpeval fixes that.

---

## Install

```bash
pip install simpeval
```

---

## Quickstart

Add **one line** to your existing code. Everything else stays exactly the same.

```python
import simpeval
from anthropic import Anthropic

# Before
client = Anthropic()

# After — one line change, everything else identical
client = simpeval.wrap(Anthropic())

# Your existing code unchanged
response = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=200,
    messages=[{"role": "user", "content": "Hello!"}]
)
```

Every call is now automatically logged with the prompt, response, model, cost, and latency.

Works the same way with OpenAI:

```python
from openai import OpenAI
client = simpeval.wrap(OpenAI())
```

---

## Dashboard

See all your logged calls, cost charts, and eval results in one place:

```bash
simpeval dashboard
```

Opens in your browser at `http://localhost:8501`

![simpeval dashboard showing call log, cost charts, and eval results]

---

## Evals — Quality Checks in Plain English

Define what "good" looks like for your product. No code required.

```python
# Create an eval once
simpeval.create_eval(
    name="always_professional",
    criterion="The response must be professional and helpful. Never rude or dismissive."
)

# Run it against your last 50 calls
simpeval.run_evals(last_n=50)
```

Claude reads each call and scores it against your criterion. You see exactly which calls passed, which failed, and why.

---

## Track Prompt Versions

Tag your calls so you can compare prompt versions side by side:

```python
# Tag all calls with the current prompt version
simpeval.set_context(prompt_version="v2", user_id="user_123")

# After running evals on both versions, compare them
simpeval.compare_versions("v1", "v2")
```

---

## Regression Alerts

Get notified automatically when your eval pass rate drops:

```python
# Check if anything regressed in the last 24 hours
# Fires a Slack message if pass rate drops below 80%
simpeval.alert_on_regression(
    threshold=0.8,
    lookback_hours=24,
    slack_webhook="https://hooks.slack.com/services/..."
)
```

Or run it from the terminal on a schedule:

```bash
simpeval check-alerts --threshold 0.8 --hours 24
```

---

## CLI Commands

```bash
simpeval dashboard        # open the visual dashboard
simpeval run-evals        # run all evals against recent calls
simpeval run-evals --last-n 100   # evaluate last 100 calls
simpeval stats            # print summary to terminal
simpeval check-alerts     # check for regressions and fire alerts
```

---

## Configuration

Create a `.env` file in your project root:

```bash
# Required for eval judging
ANTHROPIC_API_KEY=your_key_here

# Optional
OPENAI_API_KEY=your_key_here
SIMPEVAL_SLACK_WEBHOOK=https://hooks.slack.com/services/...
SIMPEVAL_ALERT_EMAIL=you@example.com
SIMPEVAL_DB_PATH=~/.simpeval/simpeval.db
```

Or configure in code:

```python
simpeval.configure(
    enabled=True,
    judge_model="claude-haiku-4-5-20251001",
    db_path="~/.simpeval/simpeval.db",
)
```

---

## What Gets Logged

Every call automatically captures:

| Field | Description |
|-------|-------------|
| `timestamp` | When the call was made |
| `provider` | `openai` or `anthropic` |
| `model` | Exact model name |
| `messages` | Full prompt sent |
| `response` | Full response received |
| `input_tokens` | Tokens in |
| `output_tokens` | Tokens out |
| `cost_usd` | Cost in dollars |
| `latency_ms` | Response time in milliseconds |
| `prompt_version` | Your version tag (optional) |
| `user_id` | User identifier (optional) |

Stored locally in SQLite at `~/.simpeval/simpeval.db`. Your data never leaves your machine.

---

## Supported Models

Cost tracking built in for 20+ models including:

- `gpt-4o`, `gpt-4o-mini`, `o3`, `o4-mini`
- `claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5`
- `gpt-4-turbo`, `gpt-3.5-turbo`, `o1`, `o1-mini`

Unknown models are logged with `cost = $0.00` and a note to add pricing.

---

## Pricing

| Tier | Price | Calls | Evals | Alerts |
|------|-------|-------|-------|--------|
| Free | $0 | 500/month | 1 | — |
| Indie | $29/mo | Unlimited | 10 | Slack |
| Studio | $79/mo | Unlimited | Unlimited | Slack + Email |

---

## License

MIT
