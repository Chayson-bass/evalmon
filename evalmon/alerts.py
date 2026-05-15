import json
import os
import smtplib
import urllib.request
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText

from .storage import get_eval_results


def check_regression(
    eval_name: str | None = None,
    threshold: float = 0.8,
    lookback_hours: int = 24,
) -> list[dict]:
    """
    Return evals whose pass rate has dropped below threshold in the last lookback_hours.
    Empty list means everything is healthy.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).isoformat()
    results = get_eval_results()
    recent = [r for r in results if r["created_at"] >= cutoff]
    if eval_name:
        recent = [r for r in recent if r["eval_name"] == eval_name]

    by_eval: dict[str, list] = {}
    for r in recent:
        by_eval.setdefault(r["eval_name"], []).append(r)

    failing = []
    for name, res in by_eval.items():
        pass_rate = sum(r["passed"] for r in res) / len(res)
        if pass_rate < threshold:
            failing.append({
                "eval_name":   name,
                "pass_rate":   pass_rate,
                "threshold":   threshold,
                "sample_size": len(res),
            })
    return failing


def alert_on_regression(
    threshold: float = 0.8,
    lookback_hours: int = 24,
    slack_webhook: str | None = None,
    email: str | None = None,
) -> list[dict]:
    """
    Check for regressions and fire Slack / email alerts for any that are found.
    Reads EVALMON_SLACK_WEBHOOK and EVALMON_ALERT_EMAIL from env if not passed directly.
    """
    slack_webhook = slack_webhook or os.environ.get("EVALMON_SLACK_WEBHOOK")
    email = email or os.environ.get("EVALMON_ALERT_EMAIL")

    failing = check_regression(threshold=threshold, lookback_hours=lookback_hours)
    if not failing:
        return []

    lines = [f"evalmon regression alert — {len(failing)} eval(s) below {threshold:.0%}:\n"]
    for f in failing:
        lines.append(
            f"  • {f['eval_name']}: {f['pass_rate']:.1%} pass rate "
            f"({f['sample_size']} samples, threshold {f['threshold']:.0%})"
        )
    message = "\n".join(lines)

    if slack_webhook:
        _slack(slack_webhook, message)
    if email:
        _email(email, "evalmon: eval regression detected", message)

    return failing


def _slack(webhook_url: str, message: str) -> bool:
    payload = json.dumps({"text": message}).encode()
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


def _email(
    to: str,
    subject: str,
    body: str,
    smtp_host: str | None = None,
    smtp_port: int = 587,
    smtp_user: str | None = None,
    smtp_password: str | None = None,
) -> bool:
    host = smtp_host     or os.environ.get("EVALMON_SMTP_HOST", "")
    user = smtp_user     or os.environ.get("EVALMON_SMTP_USER", "")
    pw   = smtp_password or os.environ.get("EVALMON_SMTP_PASSWORD", "")

    if not (host and user and pw):
        print("Email skipped: EVALMON_SMTP_HOST / USER / PASSWORD not configured.")
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"]    = user
    msg["To"]      = to
    try:
        with smtplib.SMTP(host, smtp_port) as s:
            s.starttls()
            s.login(user, pw)
            s.sendmail(user, [to], msg.as_string())
        return True
    except Exception as e:
        print(f"Email alert failed: {e}")
        return False
