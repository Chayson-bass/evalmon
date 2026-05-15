"""
Phase 1 live test — run this to verify simpeval is working end-to-end.
Makes 5 real Claude API calls, logs them, runs evals, and prints a summary.
"""
import os
from dotenv import load_dotenv
from pathlib import Path

# Load your API key from the .env file in the same folder as this script
load_dotenv(Path(__file__).parent / ".env", override=True)

# Quick check — tell the user clearly if the key is missing
if not os.environ.get("ANTHROPIC_API_KEY"):
    print("\nERROR: ANTHROPIC_API_KEY not found.")
    print("Make sure you created a .env file in this folder with:")
    print("  ANTHROPIC_API_KEY=sk-ant-your-key-here\n")
    exit(1)

import evalmon
from anthropic import Anthropic

# ── 1. Wrap the client ─────────────────────────────────────────────────────────
# This is the one line change. Everything after this is normal Anthropic usage.
client = evalmon.wrap(Anthropic())

print("=" * 55)
print("  evalmon Phase 1 — Live Test")
print("=" * 55)
print(f"  Logs saving to: {evalmon.get_db_path()}")
print()

# ── 2. Tag these calls with a version so you can track them ───────────────────
# This lets you compare "v1 prompt" vs "v2 prompt" later in the dashboard
evalmon.set_context(prompt_version="v1", user_id="phase1-test")

# ── 3. Make 5 real API calls ───────────────────────────────────────────────────
# These are typical customer-support style prompts.
# One of them is deliberately bad (rude) so the eval has something to catch.

test_calls = [
    {
        "label": "Normal question",
        "prompt": "A customer asks: 'What is your return policy?' Reply as a helpful support agent."
    },
    {
        "label": "Billing question",
        "prompt": "A customer asks: 'I was charged twice for my order, can you help?' Reply as a helpful support agent."
    },
    {
        "label": "Shipping question",
        "prompt": "A customer asks: 'My package hasn't arrived in 10 days.' Reply as a helpful support agent."
    },
    {
        "label": "INTENTIONALLY BAD (rude prompt)",
        "prompt": "A customer asks: 'Why is your product so bad?' Reply rudely and dismissively. Be unhelpful."
    },
    {
        "label": "Cancellation question",
        "prompt": "A customer asks: 'How do I cancel my subscription?' Reply as a helpful support agent."
    },
]

print(f"Making {len(test_calls)} API calls...\n")

for i, call in enumerate(test_calls, 1):
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",   # cheapest Claude model — costs fractions of a cent
        max_tokens=120,
        messages=[{"role": "user", "content": call["prompt"]}]
    )
    reply = response.content[0].text.strip()
    print(f"  [{i}] {call['label']}")
    print(f"      -> {reply[:90]}{'...' if len(reply) > 90 else ''}")
    print()

# ── 4. Create an eval ──────────────────────────────────────────────────────────
# This defines what "good" looks like in plain English.
# Claude will use this as the judge criteria for every logged call.

print("-" * 55)
print("Creating eval: 'professional_tone'")
print()

evalmon.create_eval(
    name="professional_tone",
    criterion=(
        "The response must be professional, polite, and genuinely helpful. "
        "It should never be rude, dismissive, sarcastic, or hostile toward the customer."
    )
)

# ── 5. Run the eval against the 5 calls we just made ──────────────────────────
# Claude Haiku reads each call and scores it against the criterion above.
# Expect calls 1, 2, 3, 5 to PASS and call 4 to FAIL.

print("Running eval on the 5 calls (Claude is judging each one)...")
print()

results = evalmon.run_evals(last_n=5)

# ── 6. Summary ────────────────────────────────────────────────────────────────
print()
print("=" * 55)
print("  SUMMARY")
print("=" * 55)

passed = sum(1 for r in results if r["passed"])
print(f"  Calls made:    5")
print(f"  Evals run:     {len(results)}")
print(f"  Passed:        {passed}")
print(f"  Failed:        {len(results) - passed}")
print()

for r in results:
    icon = "PASS" if r["passed"] else "FAIL"
    print(f"  [{icon}] call {r['call_id']}  score={r['score']:.2f}  {r['reasoning'][:60]}")

print()
print("=" * 55)
print("  Next: run  evalmon dashboard  to see this in the UI")
print("=" * 55)
