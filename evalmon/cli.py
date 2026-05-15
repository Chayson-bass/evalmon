import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(prog="evalmon", description="Simple LLM monitoring")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("dashboard", help="Launch the Streamlit dashboard")

    run = sub.add_parser("run-evals", help="Run evals against recent calls")
    run.add_argument("--last-n", type=int, default=20, help="Number of recent calls to evaluate")
    run.add_argument("--eval", dest="eval_names", nargs="*", help="Specific eval names")

    sub.add_parser("stats", help="Print summary statistics to the terminal")

    chk = sub.add_parser("check-alerts", help="Fire alerts if any evals regressed")
    chk.add_argument("--threshold", type=float, default=0.8)
    chk.add_argument("--hours", type=int, default=24)

    args = parser.parse_args()

    if args.cmd == "dashboard":
        _dashboard()
    elif args.cmd == "run-evals":
        _run_evals(args)
    elif args.cmd == "stats":
        _stats()
    elif args.cmd == "check-alerts":
        _alerts(args)
    else:
        parser.print_help()


def _dashboard() -> None:
    import subprocess
    dashboard = Path(__file__).parent / "dashboard.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(dashboard)], check=True)


def _run_evals(args) -> None:
    from evalmon.evals import run_evals
    print(f"Running evals on last {args.last_n} calls...")
    run_evals(last_n=args.last_n, eval_names=args.eval_names)


def _stats() -> None:
    from evalmon.storage import get_calls, get_eval_results
    calls = get_calls(limit=10_000)
    if not calls:
        print("No calls logged yet.")
        return

    total_cost = sum(c["cost_usd"] for c in calls)
    avg_latency = sum(c["latency_ms"] for c in calls) / len(calls)
    model_counts: dict[str, int] = {}
    for c in calls:
        model_counts[c["model"]] = model_counts.get(c["model"], 0) + 1

    print(f"Total calls  : {len(calls)}")
    print(f"Total cost   : ${total_cost:.4f}")
    print(f"Avg latency  : {avg_latency:.0f}ms")
    print("By model:")
    for m, n in sorted(model_counts.items(), key=lambda x: -x[1]):
        print(f"  {m}: {n}")

    results = get_eval_results()
    if results:
        passed = sum(r["passed"] for r in results)
        print(f"\nEval pass rate: {passed}/{len(results)}  ({passed/len(results):.1%})")


def _alerts(args) -> None:
    from evalmon.alerts import alert_on_regression
    failing = alert_on_regression(threshold=args.threshold, lookback_hours=args.hours)
    if failing:
        print(f"REGRESSION: {len(failing)} eval(s) below threshold")
        for f in failing:
            print(f"  {f['eval_name']}: {f['pass_rate']:.1%} (threshold {f['threshold']:.0%})")
        sys.exit(1)
    else:
        print("All evals passing.")


if __name__ == "__main__":
    main()
