from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import dash
import pandas as pd
import plotly.express as px
from dash import Input, Output, dcc, html


ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "runs"
APP_TITLE = "研究看板（Research Dashboard）"
APP_DESCRIPTION = "只读 runs/ 里的实验结果，辅助比较研究候选与现有基线（Baseline）。"

METRIC_LABELS = {
    "mean_rank_ic": "平均排序相关性（Mean Rank IC）",
    "mean_nmi": "平均归一化互信息（Mean NMI）",
    "mean_top_bottom_spread": "平均多空价差（Mean Top-Bottom Spread）",
    "rank_ic": "排序相关性（Rank IC）",
    "top_bucket_mean_return": "顶部桶平均收益（Top Bucket Mean Return）",
    "bottom_bucket_mean_return": "底部桶平均收益（Bottom Bucket Mean Return）",
}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _find_scoreboards() -> list[Path]:
    return sorted(RUNS_DIR.glob("score_*/scoreboard_summary.json"), reverse=True)


def _find_pre_evals() -> list[Path]:
    return sorted(RUNS_DIR.glob("pre_*/pre_eval_summary.json"), reverse=True)


def _scoreboard_option(path: Path) -> dict[str, str]:
    payload = _load_json(path)
    label = f'{payload.get("scoreboard_id", path.parent.name)} | {payload.get("created_at", "")}'
    return {"label": label, "value": str(path)}


def _pre_eval_option(path: Path) -> dict[str, str]:
    payload = _load_json(path)
    factor_name = payload.get("factor_name", path.parent.name)
    created_at = payload.get("created_at", "")
    label = f"{factor_name} | {created_at}"
    return {"label": label, "value": str(path)}


def _build_factor_frame(scoreboard: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for factor in scoreboard.get("factors", []):
        pre_eval = factor.get("pre_eval", {})
        rows.append(
            {
                "factor_name": factor.get("factor_name", ""),
                "factor_family": factor.get("factor_family", ""),
                "transform_name": factor.get("transform_name", ""),
                "mean_rank_ic": pre_eval.get("mean_rank_ic"),
                "mean_abs_rank_ic": pre_eval.get("mean_abs_rank_ic"),
                "mean_normalized_mutual_info": pre_eval.get("mean_normalized_mutual_info"),
                "mean_top_bottom_spread": pre_eval.get("mean_top_bottom_spread"),
                "mean_coverage_ratio": pre_eval.get("mean_coverage_ratio"),
                "joined_rows": pre_eval.get("joined_rows"),
                "experiment_id": factor.get("experiment_id", ""),
                "run_dir": factor.get("run_dir", ""),
            }
        )
    return pd.DataFrame(rows)


def _build_regime_frame(pre_eval: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for regime_name, slices in pre_eval.get("regime_slices", {}).items():
        for item in slices:
            rows.append(
                {
                    "regime_name": regime_name,
                    "slice_value": item.get("slice_value", ""),
                    "date_count": item.get("date_count"),
                    "mean_rank_ic": item.get("mean_rank_ic"),
                    "mean_normalized_mutual_info": item.get("mean_normalized_mutual_info"),
                    "mean_top_bottom_spread": item.get("mean_top_bottom_spread"),
                    "mean_coverage_ratio": item.get("mean_coverage_ratio"),
                }
            )
    return pd.DataFrame(rows)


def _build_per_date_frame(pre_eval: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(pre_eval.get("per_date", []))


def _metric_card(title: str, value: Any) -> html.Div:
    if value is None or value == "":
        display = "n/a"
    elif isinstance(value, float):
        display = f"{value:.4f}"
    else:
        display = str(value)
    return html.Div(
        [
            html.Div(title, className="metric-label"),
            html.Div(display, className="metric-value"),
        ],
        className="metric-card",
    )


scoreboard_options = [_scoreboard_option(path) for path in _find_scoreboards()]
pre_eval_options = [_pre_eval_option(path) for path in _find_pre_evals()]

app = dash.Dash(__name__)
app.title = APP_TITLE

app.layout = html.Div(
    [
        html.H1(APP_TITLE),
        html.P(APP_DESCRIPTION),
        html.Div(
            [
                html.Div(
                    [
                        html.Label("候选板（Scoreboard）"),
                        dcc.Dropdown(
                            id="scoreboard-dropdown",
                            options=scoreboard_options,
                            value=scoreboard_options[0]["value"] if scoreboard_options else None,
                            clearable=False,
                        ),
                    ],
                    className="panel",
                ),
                html.Div(
                    [
                        html.Label("单因子预评估（Standalone Pre-Eval）"),
                        dcc.Dropdown(
                            id="pre-eval-dropdown",
                            options=pre_eval_options,
                            value=pre_eval_options[0]["value"] if pre_eval_options else None,
                            clearable=False,
                        ),
                    ],
                    className="panel",
                ),
            ],
            className="controls",
        ),
        html.Div(id="scoreboard-metrics", className="metric-grid"),
        dcc.Graph(id="scoreboard-factor-scatter"),
        html.Div(
            [
                html.Div(
                    [
                        html.Label("左侧因子（Left Factor）"),
                        dcc.Dropdown(id="left-factor-dropdown", clearable=False),
                    ],
                    className="panel",
                ),
                html.Div(
                    [
                        html.Label("右侧因子（Right Factor）"),
                        dcc.Dropdown(id="right-factor-dropdown", clearable=False),
                    ],
                    className="panel",
                ),
            ],
            className="controls",
        ),
        dcc.Graph(id="factor-compare-bars"),
        dcc.Graph(id="factor-compare-per-date"),
        dcc.Graph(id="pre-eval-per-date"),
        dcc.Graph(id="pre-eval-regimes"),
        html.Pre(id="selection-summary", className="summary-box"),
    ],
    className="app-shell",
)


@app.callback(
    Output("scoreboard-metrics", "children"),
    Output("scoreboard-factor-scatter", "figure"),
    Output("left-factor-dropdown", "options"),
    Output("left-factor-dropdown", "value"),
    Output("right-factor-dropdown", "options"),
    Output("right-factor-dropdown", "value"),
    Input("scoreboard-dropdown", "value"),
)
def update_scoreboard(scoreboard_path: str | None):
    if not scoreboard_path:
        return [], px.scatter(), [], None, [], None

    payload = _load_json(Path(scoreboard_path))
    frame = _build_factor_frame(payload)
    if frame.empty:
        return [], px.scatter(), [], None, [], None

    cards = [
        _metric_card("候选板 ID（Scoreboard ID）", payload.get("scoreboard_id")),
        _metric_card("因子数量（Factor Count）", payload.get("factor_count")),
        _metric_card("预评估数量（Pre-Eval Count）", payload.get("pre_eval_count")),
        _metric_card("比较条目数（Comparison Count）", payload.get("comparison_count")),
    ]
    figure = px.scatter(
        frame,
        x="mean_rank_ic",
        y="mean_top_bottom_spread",
        color="factor_family",
        hover_name="factor_name",
        size="mean_normalized_mutual_info",
        custom_data=["factor_name", "transform_name", "joined_rows"],
        title="因子前沿（Factor Frontier）：排序相关性与多空价差",
    )
    figure.update_layout(
        xaxis_title="平均排序相关性（Mean Rank IC）",
        yaxis_title="平均多空价差（Mean Top-Bottom Spread）",
        legend_title_text="因子家族（Factor Family）",
    )
    figure.update_traces(
        hovertemplate=(
            "因子（Factor）=%{customdata[0]}<br>"
            "变换方式（Transform）=%{customdata[1]}<br>"
            "样本行数（Joined Rows）=%{customdata[2]}<br>"
            "排序相关性（Rank IC）=%{x:.4f}<br>"
            "多空价差（Top-Bottom Spread）=%{y:.4f}<br>"
            "归一化互信息（NMI）=%{marker.size:.4f}<extra></extra>"
        )
    )
    options = [{"label": name, "value": name} for name in frame["factor_name"].tolist()]
    left = options[0]["value"] if options else None
    right = options[1]["value"] if len(options) > 1 else left
    return cards, figure, options, left, options, right


@app.callback(
    Output("factor-compare-bars", "figure"),
    Output("factor-compare-per-date", "figure"),
    Input("scoreboard-dropdown", "value"),
    Input("left-factor-dropdown", "value"),
    Input("right-factor-dropdown", "value"),
)
def compare_factors(scoreboard_path: str | None, left_factor: str | None, right_factor: str | None):
    if not scoreboard_path or not left_factor or not right_factor:
        return px.bar(), px.line()

    payload = _load_json(Path(scoreboard_path))
    by_name = {item.get("factor_name"): item for item in payload.get("factors", [])}
    left = by_name.get(left_factor)
    right = by_name.get(right_factor)
    if not left or not right:
        return px.bar(), px.line()

    left_pre = left.get("pre_eval", {})
    right_pre = right.get("pre_eval", {})
    compare_frame = pd.DataFrame(
        [
            {
                "factor_name": left_factor,
                "metric": "mean_rank_ic",
                "value": left_pre.get("mean_rank_ic"),
            },
            {
                "factor_name": left_factor,
                "metric": "mean_nmi",
                "value": left_pre.get("mean_normalized_mutual_info"),
            },
            {
                "factor_name": left_factor,
                "metric": "mean_top_bottom_spread",
                "value": left_pre.get("mean_top_bottom_spread"),
            },
            {
                "factor_name": right_factor,
                "metric": "mean_rank_ic",
                "value": right_pre.get("mean_rank_ic"),
            },
            {
                "factor_name": right_factor,
                "metric": "mean_nmi",
                "value": right_pre.get("mean_normalized_mutual_info"),
            },
            {
                "factor_name": right_factor,
                "metric": "mean_top_bottom_spread",
                "value": right_pre.get("mean_top_bottom_spread"),
            },
        ]
    )
    bar_figure = px.bar(
        compare_frame,
        x="metric",
        y="value",
        color="factor_name",
        barmode="group",
        title="因子对比快照（Factor Comparison Snapshot）",
    )
    bar_figure.update_xaxes(
        tickvals=list(METRIC_LABELS.keys())[:3],
        ticktext=[METRIC_LABELS[key] for key in list(METRIC_LABELS.keys())[:3]],
        title="评估指标（Metrics）",
    )
    bar_figure.update_layout(
        yaxis_title="指标值（Metric Value）",
        legend_title_text="因子（Factor）",
    )

    per_date_rows: list[dict[str, Any]] = []
    for factor_name, pre_eval in ((left_factor, left_pre), (right_factor, right_pre)):
        for item in pre_eval.get("per_date", []):
            per_date_rows.append(
                {
                    "factor_name": factor_name,
                    "date": item.get("date"),
                    "rank_ic": item.get("rank_ic"),
                    "top_bottom_spread": item.get("top_bottom_spread"),
                    "normalized_mutual_info": item.get("normalized_mutual_info"),
                }
            )
    per_date_frame = pd.DataFrame(per_date_rows)
    line_figure = px.line(
        per_date_frame,
        x="date",
        y="rank_ic",
        color="factor_name",
        markers=True,
        title="逐日排序相关性对比（Per-Date Rank IC Comparison）",
    )
    line_figure.update_layout(
        xaxis_title="日期（Date）",
        yaxis_title="排序相关性（Rank IC）",
        legend_title_text="因子（Factor）",
    )
    return bar_figure, line_figure


@app.callback(
    Output("pre-eval-per-date", "figure"),
    Output("pre-eval-regimes", "figure"),
    Output("selection-summary", "children"),
    Input("pre-eval-dropdown", "value"),
)
def update_pre_eval(pre_eval_path: str | None):
    if not pre_eval_path:
        return px.bar(), px.bar(), "尚未选择预评估（Pre-Eval）。"

    payload = _load_json(Path(pre_eval_path))
    per_date = _build_per_date_frame(payload)
    regime_frame = _build_regime_frame(payload)

    per_date_figure = px.bar(
        per_date,
        x="date",
        y=["rank_ic", "top_bucket_mean_return", "bottom_bucket_mean_return"],
        barmode="group",
        title=f'逐日结果（Per-Date Outcome）：{payload.get("factor_name", "")}',
    )
    per_date_figure.update_layout(
        xaxis_title="日期（Date）",
        yaxis_title="数值（Value）",
        legend_title_text="指标（Metric）",
    )
    for trace in per_date_figure.data:
        trace.name = METRIC_LABELS.get(trace.name, trace.name)

    regime_figure = px.bar(
        regime_frame,
        x="slice_value",
        y="mean_rank_ic",
        color="regime_name",
        barmode="group",
        title="不同状态分组下的平均排序相关性（Regime Slice Mean Rank IC）",
    )
    regime_figure.update_layout(
        xaxis_title="分组取值（Slice Value）",
        yaxis_title="平均排序相关性（Mean Rank IC）",
        legend_title_text="状态维度（Regime Dimension）",
    )

    summary = json.dumps(
        {
            "因子名称（Factor Name）": payload.get("factor_name"),
            "实验 ID（Experiment ID）": payload.get("experiment_id"),
            "平均排序相关性（Mean Rank IC）": payload.get("mean_rank_ic"),
            "平均归一化互信息（Mean Normalized Mutual Information）": payload.get("mean_normalized_mutual_info"),
            "平均多空价差（Mean Top-Bottom Spread）": payload.get("mean_top_bottom_spread"),
            "因子日期（Factor Dates）": payload.get("factor_dates"),
            "跳过日期（Skipped Dates）": payload.get("skipped_dates"),
        },
        ensure_ascii=False,
        indent=2,
    )
    return per_date_figure, regime_figure, summary


app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            body { font-family: "Iowan Old Style", "Palatino Linotype", serif; background: linear-gradient(180deg, #f8f6ef 0%, #eef2ea 100%); color: #172121; margin: 0; }
            .app-shell { max-width: 1280px; margin: 0 auto; padding: 24px; }
            .controls { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; margin-bottom: 16px; }
            .panel { background: rgba(255,255,255,0.82); border: 1px solid #c9d4c5; border-radius: 16px; padding: 16px; box-shadow: 0 10px 30px rgba(23,33,33,0.06); }
            .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 18px; }
            .metric-card { background: rgba(255,255,255,0.82); border: 1px solid #c9d4c5; border-radius: 16px; padding: 14px 16px; }
            .metric-label { font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; color: #5d6c63; margin-bottom: 6px; }
            .metric-value { font-size: 20px; font-weight: 700; color: #172121; }
            .summary-box { background: #172121; color: #f8f6ef; border-radius: 16px; padding: 16px; overflow-x: auto; }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
"""


if __name__ == "__main__":
    app.run(debug=True)
