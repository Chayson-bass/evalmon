import json
import sys
from pathlib import Path

# Importable whether run via `evalmon dashboard` or `streamlit run dashboard.py`
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

import evalmon
from evalmon.evals import create_eval, delete_eval, run_evals
from evalmon.storage import get_calls, get_eval_results, get_evals, init_db

st.set_page_config(page_title="evalmon", page_icon="🔍", layout="wide")

# ── Header ─────────────────────────────────────────────────────────────────────
st.title("evalmon")
st.caption(f"DB: `{evalmon.get_db_path()}`")

init_db()

# ── Sidebar filters ────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filters")
    provider_sel  = st.selectbox("Provider", ["All", "openai", "anthropic"])
    model_filter  = st.text_input("Model contains", placeholder="gpt-4o, claude…")
    version_filter = st.text_input("Prompt version", placeholder="v1, v2…")
    call_limit    = st.slider("Max calls to load", 50, 2000, 500, step=50)
    st.divider()
    if st.button("Refresh"):
        st.rerun()

# ── Load & filter calls ────────────────────────────────────────────────────────
calls_raw = get_calls(
    limit=call_limit,
    provider=provider_sel if provider_sel != "All" else None,
    model=model_filter or None,
)
if version_filter:
    calls_raw = [c for c in calls_raw if c.get("prompt_version") == version_filter]

df = pd.DataFrame(calls_raw) if calls_raw else pd.DataFrame(
    columns=["id","timestamp","provider","model","prompt_version",
             "input_tokens","output_tokens","cost_usd","latency_ms","user_id"]
)

# ── Top KPIs ───────────────────────────────────────────────────────────────────
k1, k2, k3, k4, k5 = st.columns(5)
if not df.empty:
    k1.metric("Calls",        f"{len(df):,}")
    k2.metric("Total Cost",   f"${df['cost_usd'].sum():.4f}")
    k3.metric("Avg Latency",  f"{df['latency_ms'].mean():.0f} ms")
    k4.metric("Total Tokens", f"{(df['input_tokens']+df['output_tokens']).sum():,}")
    models_used = df["model"].nunique()
    k5.metric("Models Used",  models_used)
else:
    for col, label in zip([k1,k2,k3,k4,k5], ["Calls","Total Cost","Avg Latency","Total Tokens","Models Used"]):
        col.metric(label, "—")

st.divider()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_log, tab_cost, tab_evals = st.tabs(["📋 Call Log", "💰 Cost & Usage", "🧪 Evals"])


# ── Tab 1: Call Log ────────────────────────────────────────────────────────────
with tab_log:
    if df.empty:
        st.info(
            "No calls logged yet.\n\n"
            "```python\n"
            "import evalmon\n"
            "from anthropic import Anthropic\n\n"
            "client = evalmon.wrap(Anthropic())\n"
            "# All calls now auto-logged\n"
            "```"
        )
    else:
        show_cols = [c for c in
            ["id","timestamp","provider","model","prompt_version",
             "input_tokens","output_tokens","cost_usd","latency_ms","user_id"]
            if c in df.columns]
        st.dataframe(
            df[show_cols].rename(columns={
                "cost_usd":    "cost ($)",
                "latency_ms":  "latency (ms)",
                "input_tokens":  "in_tok",
                "output_tokens": "out_tok",
            }),
            use_container_width=True,
            height=380,
        )

        # ── Inspect a single call ──────────────────────────────────────────────
        st.subheader("Inspect call")
        min_id = int(df["id"].min())
        max_id = int(df["id"].max())
        call_id = st.number_input("Call ID", min_value=min_id, max_value=max_id,
                                   value=max_id, step=1)
        row = df[df["id"] == call_id]
        if not row.empty:
            r = row.iloc[0]
            col_prompt, col_resp = st.columns(2)

            with col_prompt:
                st.markdown("**Prompt**")
                try:
                    for m in json.loads(r["messages"]):
                        role = m.get("role", "?")
                        content = m.get("content", "")
                        if isinstance(content, list):
                            content = " ".join(
                                b.get("text", "") for b in content if isinstance(b, dict)
                            )
                        st.markdown(f"`{role}` — {content}")
                except Exception:
                    st.text(r["messages"])

            with col_resp:
                st.markdown("**Response**")
                try:
                    resp = json.loads(r["response"])
                    if r["provider"] == "openai":
                        text = resp["choices"][0]["message"]["content"] or ""
                    else:
                        content = resp.get("content", [])
                        text = " ".join(
                            b.get("text","") for b in content
                            if isinstance(b, dict) and b.get("type") == "text"
                        ) if isinstance(content, list) else str(content)
                    st.text_area("", value=text, height=220, label_visibility="collapsed")
                except Exception:
                    st.text(r["response"])

            meta_cols = ["provider","model","input_tokens","output_tokens","cost_usd","latency_ms","prompt_version","user_id","session_id"]
            st.json({k: r.get(k) for k in meta_cols if k in r.index})


# ── Tab 2: Cost & Usage ────────────────────────────────────────────────────────
with tab_cost:
    if df.empty:
        st.info("No data yet.")
    else:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df_sorted = df.sort_values("timestamp")

        row1_l, row1_r = st.columns(2)

        with row1_l:
            st.subheader("Cumulative cost over time")
            df_sorted = df_sorted.copy()
            df_sorted["cumulative_cost"] = df_sorted["cost_usd"].cumsum()
            fig = px.area(
                df_sorted, x="timestamp", y="cumulative_cost",
                labels={"cumulative_cost": "Cumulative Cost ($)", "timestamp": ""},
            )
            fig.update_layout(margin=dict(l=0,r=0,t=20,b=0))
            st.plotly_chart(fig, use_container_width=True)

        with row1_r:
            st.subheader("Calls by model")
            model_counts = df["model"].value_counts().reset_index()
            model_counts.columns = ["model", "calls"]
            fig2 = px.pie(model_counts, names="model", values="calls", hole=0.4)
            fig2.update_layout(margin=dict(l=0,r=0,t=20,b=0))
            st.plotly_chart(fig2, use_container_width=True)

        row2_l, row2_r = st.columns(2)

        with row2_l:
            st.subheader("Latency distribution (ms)")
            fig3 = px.histogram(df, x="latency_ms", nbins=40,
                                labels={"latency_ms": "Latency (ms)"})
            fig3.update_layout(margin=dict(l=0,r=0,t=20,b=0))
            st.plotly_chart(fig3, use_container_width=True)

        with row2_r:
            st.subheader("Cost by model")
            cost_by_model = df.groupby("model")["cost_usd"].sum().reset_index()
            cost_by_model.columns = ["model", "total_cost"]
            cost_by_model = cost_by_model.sort_values("total_cost", ascending=False)
            fig4 = px.bar(cost_by_model, x="model", y="total_cost",
                          labels={"total_cost": "Total Cost ($)"})
            fig4.update_layout(margin=dict(l=0,r=0,t=20,b=0))
            st.plotly_chart(fig4, use_container_width=True)


# ── Tab 3: Evals ───────────────────────────────────────────────────────────────
with tab_evals:
    left, right = st.columns([1, 2])

    # ── Left: manage evals ────────────────────────────────────────────────────
    with left:
        st.subheader("Create eval")
        with st.form("new_eval_form"):
            new_name = st.text_input("Name", placeholder="always_polite")
            new_criterion = st.text_area(
                "Criterion (plain English)",
                placeholder="The response should always be polite and professional, never rude.",
                height=100,
            )
            if st.form_submit_button("Create", type="primary"):
                if new_name and new_criterion:
                    create_eval(new_name.strip(), new_criterion.strip())
                    st.success(f"Created: {new_name}")
                    st.rerun()
                else:
                    st.warning("Name and criterion are both required.")

        st.subheader("Existing evals")
        evals = get_evals()
        if not evals:
            st.caption("No evals yet.")
        for ev in evals:
            with st.expander(ev["name"]):
                st.write(ev["criterion"])
                if st.button("Delete", key=f"del_{ev['id']}"):
                    delete_eval(ev["name"])
                    st.rerun()

    # ── Right: run & results ──────────────────────────────────────────────────
    with right:
        st.subheader("Run evals")
        run_n = st.slider("Evaluate last N calls", 5, 100, 20)
        if st.button("Run now", type="primary", disabled=not get_evals()):
            with st.spinner("Running — Claude is judging your calls..."):
                results = run_evals(last_n=run_n)
            if results:
                passed = sum(r["passed"] for r in results)
                rate = passed / len(results)
                color = "green" if rate >= 0.8 else "orange" if rate >= 0.6 else "red"
                st.markdown(
                    f"**:{color}[{passed}/{len(results)} passed ({rate:.0%})]**"
                )
            else:
                st.warning("No results — check that evals and calls both exist.")
            st.rerun()

        st.subheader("Results")
        results_raw = get_eval_results()
        if not results_raw:
            st.info("No eval results yet. Click 'Run now' above.")
        else:
            df_res = pd.DataFrame(results_raw)

            # Pass rate bar chart per eval
            summary = (
                df_res.groupby("eval_name")["passed"]
                .agg(passed=("sum"), total=("count"))
                .reset_index()
            )
            summary["pass_rate"] = summary["passed"] / summary["total"]
            fig_ev = px.bar(
                summary, x="eval_name", y="pass_rate",
                color="pass_rate",
                color_continuous_scale=["#e74c3c","#f39c12","#2ecc71"],
                range_color=[0,1],
                labels={"pass_rate": "Pass Rate", "eval_name": "Eval"},
                text=summary["pass_rate"].map("{:.0%}".format),
            )
            fig_ev.update_layout(
                yaxis_tickformat=".0%",
                coloraxis_showscale=False,
                margin=dict(l=0,r=0,t=20,b=0),
            )
            st.plotly_chart(fig_ev, use_container_width=True)

            # Detailed results table
            show = df_res[["eval_name","call_id","passed","score","judge_reasoning","created_at"]].copy()
            show["passed"] = show["passed"].map({1: "✅ Pass", 0: "❌ Fail"})
            show["score"] = show["score"].map("{:.2f}".format)
            st.dataframe(show, use_container_width=True, height=280)
