import json
from typing import Any

import anthropic

from .storage import (
    delete_eval_by_name,
    get_calls,
    get_evals,
    get_eval_results,
    insert_eval,
    insert_eval_result,
)
from .tracker import get_judge_model


def create_eval(name: str, criterion: str) -> dict:
    """
    Define a quality criterion for your LLM calls.

    Args:
        name:      Short identifier, e.g. "always_polite"
        criterion: Plain English, e.g. "The response should always be polite and professional"
    """
    eval_id = insert_eval(name, criterion)
    return {"id": eval_id, "name": name, "criterion": criterion}


def list_evals() -> list[dict]:
    return get_evals()


def delete_eval(name: str) -> bool:
    return delete_eval_by_name(name)


def run_evals(
    call_ids: list[int] | None = None,
    eval_names: list[str] | None = None,
    last_n: int = 20,
) -> list[dict]:
    """
    Run evals against recent (or specified) calls using Claude as judge.

    Args:
        call_ids:   Specific call IDs to evaluate. Uses last_n if omitted.
        eval_names: Specific eval names to run. Runs all evals if omitted.
        last_n:     How many recent calls to pull when call_ids is not given.

    Returns:
        List of result dicts with keys: eval_name, call_id, passed, score, reasoning.
    """
    evals = get_evals()
    if eval_names:
        evals = [e for e in evals if e["name"] in eval_names]
    if not evals:
        print("No evals defined. Create one with simpeval.create_eval().")
        return []

    calls = (
        [c for c in get_calls(limit=10_000) if c["id"] in call_ids]
        if call_ids
        else get_calls(limit=last_n)
    )
    if not calls:
        print("No calls to evaluate.")
        return []

    results = []
    for call in calls:
        for ev in evals:
            judgment = _judge(ev, call)
            insert_eval_result(
                eval_id=ev["id"],
                call_id=call["id"],
                passed=judgment["passed"],
                score=judgment["score"],
                reasoning=judgment["reasoning"],
            )
            status = "PASS" if judgment["passed"] else "FAIL"
            print(f"  [{status}] eval={ev['name']}  call={call['id']}  score={judgment['score']:.2f}")
            results.append({
                "eval_name": ev["name"],
                "call_id":   call["id"],
                "model":     call["model"],
                **judgment,
            })

    passed = sum(r["passed"] for r in results)
    print(f"\n{passed}/{len(results)} passed")
    return results


def compare_versions(version_a: str, version_b: str) -> dict:
    """
    Compare eval pass rates between two prompt versions.
    Tag calls with simpeval.set_context(prompt_version="v2") before making them.
    """
    all_calls = get_calls(limit=10_000)
    ids_a = {c["id"] for c in all_calls if c.get("prompt_version") == version_a}
    ids_b = {c["id"] for c in all_calls if c.get("prompt_version") == version_b}
    all_results = get_eval_results()

    summary = {}
    for ev in get_evals():
        r_a = [r for r in all_results if r["eval_id"] == ev["id"] and r["call_id"] in ids_a]
        r_b = [r for r in all_results if r["eval_id"] == ev["id"] and r["call_id"] in ids_b]
        pa = sum(r["passed"] for r in r_a) / len(r_a) if r_a else None
        pb = sum(r["passed"] for r in r_b) / len(r_b) if r_b else None
        summary[ev["name"]] = {
            f"{version_a}_pass_rate": pa,
            f"{version_b}_pass_rate": pb,
            "delta": (pb - pa) if (pa is not None and pb is not None) else None,
        }
    return summary


# ── Internal judge ─────────────────────────────────────────────────────────────

def _judge(ev: dict, call: dict) -> dict:
    try:
        messages = json.loads(call["messages"])
        response_data = json.loads(call["response"])
        response_text = _extract_text(response_data, call["provider"])
    except Exception as e:
        return {"passed": False, "score": 0.0, "reasoning": f"Parse error: {e}"}

    prompt = f"""You are an AI quality evaluator. Determine whether the AI response meets the criterion.

Criterion: {ev["criterion"]}

Conversation:
{json.dumps(messages, indent=2)}

AI Response:
{response_text}

Reply with a JSON object containing exactly:
- "passed": boolean
- "score": float 0.0–1.0
- "reasoning": string (one sentence)

Reply with the JSON only, no surrounding text."""

    try:
        # Safety net: ensure .env is loaded no matter how this function is invoked
        try:
            from dotenv import load_dotenv
            from pathlib import Path
            load_dotenv(Path(__file__).parent.parent / ".env", override=True)
        except ImportError:
            pass

        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=get_judge_model(),
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        data = json.loads(raw)
        return {
            "passed":    bool(data.get("passed", False)),
            "score":     float(data.get("score", 0.0)),
            "reasoning": str(data.get("reasoning", "")),
        }
    except Exception as e:
        return {"passed": False, "score": 0.0, "reasoning": f"Judge error: {e}"}


def _extract_text(response_data: dict, provider: str) -> str:
    try:
        if provider == "openai":
            return response_data["choices"][0]["message"]["content"] or ""
        if provider == "anthropic":
            content = response_data.get("content", [])
            if isinstance(content, list):
                return " ".join(b.get("text", "") for b in content if b.get("type") == "text")
            return str(content)
    except Exception:
        pass
    return str(response_data)
