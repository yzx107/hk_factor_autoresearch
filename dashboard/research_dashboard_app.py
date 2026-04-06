from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import dash
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html
from plotly.subplots import make_subplots


ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = Path(os.environ.get("HK_FACTOR_RUNS_DIR", str(ROOT / "runs"))).expanduser().resolve()
DEBUG_MODE = os.environ.get("HK_FACTOR_DASH_DEBUG", "").strip().lower() in {"1", "true", "yes"}
APP_TITLE = "研究看板（Research Dashboard）"
APP_DESCRIPTION = "只读 runs/ 里的实验结果，辅助比较研究候选与现有基线（Baseline）。"
DEFAULT_X_METRIC = "mean_rank_ic"
DEFAULT_Y_METRIC = "mean_top_bottom_spread"
DEFAULT_RANK_METRIC = "mean_abs_rank_ic"

METRIC_LABELS = {
    "mean_rank_ic": "平均排序相关性（Mean Rank IC）",
    "mean_abs_rank_ic": "平均绝对排序相关性（Mean Abs Rank IC）",
    "mean_normalized_mutual_info": "平均归一化互信息（Mean NMI）",
    "mean_top_bottom_spread": "平均多空价差（Mean Top-Bottom Spread）",
    "mean_coverage_ratio": "平均覆盖率（Mean Coverage Ratio）",
    "joined_rows": "样本行数（Joined Rows）",
    "rank_ic": "排序相关性（Rank IC）",
    "top_bucket_mean_return": "顶部桶平均收益（Top Bucket Mean Return）",
    "bottom_bucket_mean_return": "底部桶平均收益（Bottom Bucket Mean Return）",
    "pearson_corr": "皮尔逊相关性（Pearson Corr）",
    "top_overlap_count": "Top 重叠数（Top Overlap Count）",
}

METRIC_OPTIONS = [
    {"label": METRIC_LABELS["mean_rank_ic"], "value": "mean_rank_ic"},
    {"label": METRIC_LABELS["mean_abs_rank_ic"], "value": "mean_abs_rank_ic"},
    {"label": METRIC_LABELS["mean_normalized_mutual_info"], "value": "mean_normalized_mutual_info"},
    {"label": METRIC_LABELS["mean_top_bottom_spread"], "value": "mean_top_bottom_spread"},
    {"label": METRIC_LABELS["mean_coverage_ratio"], "value": "mean_coverage_ratio"},
    {"label": METRIC_LABELS["joined_rows"], "value": "joined_rows"},
]

LEADERBOARD_COLUMNS = [
    ("factor_name", "因子（Factor）"),
    ("factor_family", "家族（Family）"),
    ("transform_name", "变换（Transform）"),
    ("mean_rank_ic", METRIC_LABELS["mean_rank_ic"]),
    ("mean_abs_rank_ic", METRIC_LABELS["mean_abs_rank_ic"]),
    ("mean_normalized_mutual_info", METRIC_LABELS["mean_normalized_mutual_info"]),
    ("mean_top_bottom_spread", METRIC_LABELS["mean_top_bottom_spread"]),
    ("mean_coverage_ratio", METRIC_LABELS["mean_coverage_ratio"]),
    ("joined_rows", METRIC_LABELS["joined_rows"]),
]


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _find_scoreboards() -> list[Path]:
    return sorted(RUNS_DIR.glob("score_*/scoreboard_summary.json"), reverse=True)


def _find_pre_evals() -> list[Path]:
    return sorted(RUNS_DIR.glob("pre_*/pre_eval_summary.json"), reverse=True)


def _find_comparisons() -> list[Path]:
    return sorted(RUNS_DIR.glob("cmp_*/comparison_summary.json"), reverse=True)


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


def _comparison_catalog_entry(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    return {
        "path": str(path),
        "comparison_id": payload.get("comparison_id", path.parent.name),
        "created_at": payload.get("created_at", ""),
        "left_factor_name": payload.get("left", {}).get("factor_name", ""),
        "right_factor_name": payload.get("right", {}).get("factor_name", ""),
        "left_experiment_id": payload.get("left", {}).get("experiment_id", ""),
        "right_experiment_id": payload.get("right", {}).get("experiment_id", ""),
    }


def _load_comparison_catalog() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in _find_comparisons():
        try:
            entries.append(_comparison_catalog_entry(path))
        except (OSError, json.JSONDecodeError):
            continue
    return entries


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
                    "mean_abs_rank_ic": item.get("mean_abs_rank_ic"),
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


def _metric_label(metric_key: str) -> str:
    return METRIC_LABELS.get(metric_key, metric_key)


def _empty_figure(title: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(
        title=title,
        template="plotly_white",
        margin={"l": 48, "r": 24, "t": 64, "b": 48},
        annotations=[
            {
                "text": "暂无可显示数据（No Data）",
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
                "font": {"size": 15, "color": "#5d6c63"},
            }
        ],
    )
    return figure


def _family_filter_options(frame: pd.DataFrame) -> list[dict[str, str]]:
    if frame.empty or "factor_family" not in frame:
        return []
    families = sorted({str(value) for value in frame["factor_family"].dropna().tolist() if str(value)})
    return [{"label": family, "value": family} for family in families]


def _apply_factor_filters(
    frame: pd.DataFrame,
    family_values: list[str] | None,
    search_text: str | None,
) -> pd.DataFrame:
    filtered = frame.copy()
    selected_families = set(family_values or [])
    if selected_families:
        filtered = filtered[filtered["factor_family"].isin(selected_families)]
    query = (search_text or "").strip().casefold()
    if query:
        mask = (
            filtered["factor_name"].fillna("").str.casefold().str.contains(query)
            | filtered["factor_family"].fillna("").str.casefold().str.contains(query)
            | filtered["transform_name"].fillna("").str.casefold().str.contains(query)
        )
        filtered = filtered[mask]
    return filtered


def _sorted_factor_options(frame: pd.DataFrame, rank_metric: str) -> list[dict[str, str]]:
    if frame.empty:
        return []
    ranked = frame.sort_values(rank_metric, ascending=False, na_position="last")
    return [{"label": name, "value": name} for name in ranked["factor_name"].tolist()]


def _format_table_value(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _render_leaderboard(frame: pd.DataFrame, rank_metric: str) -> html.Div:
    if frame.empty:
        return html.Div("当前筛选条件下没有候选因子（No Factors Matched）。", className="empty-note")

    ranked = frame.sort_values(rank_metric, ascending=False, na_position="last").head(12)
    header = html.Thead(
        html.Tr([html.Th("排名（Rank）")] + [html.Th(label) for _, label in LEADERBOARD_COLUMNS])
    )
    body_rows = []
    for index, record in enumerate(ranked.to_dict("records"), start=1):
        cells = [html.Td(str(index))]
        for column_name, _ in LEADERBOARD_COLUMNS:
            cells.append(html.Td(_format_table_value(record.get(column_name))))
        body_rows.append(html.Tr(cells))
    caption = (
        f"筛选后共 {len(frame)} 个因子，榜单按 {_metric_label(rank_metric)} 排序，展示前 {len(ranked)} 个。"
    )
    return html.Div(
        [
            html.Div(caption, className="table-caption"),
            html.Table([header, html.Tbody(body_rows)], className="leaderboard-table"),
        ]
    )


def _build_comparison_diagnostics_frame(payload: dict[str, Any]) -> pd.DataFrame:
    rows_by_date: dict[str, dict[str, Any]] = {}
    for item in payload.get("per_date", []):
        date = item.get("date")
        if not date:
            continue
        rows_by_date.setdefault(date, {})["date"] = date
        rows_by_date[date]["pearson_corr"] = item.get("pearson_corr")
        rows_by_date[date]["common_rows"] = item.get("common_rows")
    for item in payload.get("top_overlap", []):
        date = item.get("date")
        if not date:
            continue
        rows_by_date.setdefault(date, {})["date"] = date
        rows_by_date[date]["top_overlap_count"] = item.get("top_overlap_count")
    if not rows_by_date:
        return pd.DataFrame()
    return pd.DataFrame(sorted(rows_by_date.values(), key=lambda row: row["date"]))


def _find_best_comparison(
    left_factor: dict[str, Any],
    right_factor: dict[str, Any],
    comparison_catalog: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, str | None]:
    left_experiment = left_factor.get("experiment_id", "")
    right_experiment = right_factor.get("experiment_id", "")
    exact_matches = []
    factor_matches = []
    for entry in comparison_catalog:
        experiments = {entry.get("left_experiment_id", ""), entry.get("right_experiment_id", "")}
        factors = {entry.get("left_factor_name", ""), entry.get("right_factor_name", "")}
        if experiments == {left_experiment, right_experiment}:
            exact_matches.append(entry)
        elif factors == {left_factor.get("factor_name", ""), right_factor.get("factor_name", "")}:
            factor_matches.append(entry)
    if exact_matches:
        return exact_matches[0], "精确实验匹配（Exact Experiment Match）"
    if factor_matches:
        return factor_matches[0], "因子名匹配（Factor Name Match）"
    return None, None


scoreboard_options = [_scoreboard_option(path) for path in _find_scoreboards()]
pre_eval_options = [_pre_eval_option(path) for path in _find_pre_evals()]
comparison_catalog = _load_comparison_catalog()

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
        html.Div(
            [
                html.Div(
                    [
                        html.Label("家族筛选（Family Filter）"),
                        dcc.Dropdown(id="family-filter-dropdown", multi=True, placeholder="不过滤家族"),
                    ],
                    className="panel",
                ),
                html.Div(
                    [
                        html.Label("因子搜索（Factor Search）"),
                        dcc.Input(
                            id="factor-search-input",
                            type="text",
                            debounce=True,
                            placeholder="按因子名 / 家族 / 变换搜索",
                            className="text-input",
                        ),
                    ],
                    className="panel",
                ),
                html.Div(
                    [
                        html.Label("横轴指标（X Metric）"),
                        dcc.Dropdown(
                            id="x-metric-dropdown",
                            options=METRIC_OPTIONS,
                            value=DEFAULT_X_METRIC,
                            clearable=False,
                        ),
                    ],
                    className="panel",
                ),
                html.Div(
                    [
                        html.Label("纵轴指标（Y Metric）"),
                        dcc.Dropdown(
                            id="y-metric-dropdown",
                            options=METRIC_OPTIONS,
                            value=DEFAULT_Y_METRIC,
                            clearable=False,
                        ),
                    ],
                    className="panel",
                ),
                html.Div(
                    [
                        html.Label("榜单排序（Leaderboard Metric）"),
                        dcc.Dropdown(
                            id="leaderboard-metric-dropdown",
                            options=METRIC_OPTIONS,
                            value=DEFAULT_RANK_METRIC,
                            clearable=False,
                        ),
                    ],
                    className="panel",
                ),
            ],
            className="controls controls-dense",
        ),
        html.Div(id="scoreboard-metrics", className="metric-grid"),
        dcc.Graph(id="scoreboard-factor-scatter"),
        html.Div(
            [
                html.Div("筛选后榜单（Filtered Leaderboard）", className="section-title"),
                html.Div(id="factor-leaderboard", className="table-shell"),
            ],
            className="panel",
        ),
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
        html.Div(id="comparison-metrics", className="metric-grid"),
        dcc.Graph(id="factor-compare-diagnostics"),
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
    Output("family-filter-dropdown", "options"),
    Output("factor-leaderboard", "children"),
    Output("left-factor-dropdown", "options"),
    Output("right-factor-dropdown", "options"),
    Input("scoreboard-dropdown", "value"),
    Input("family-filter-dropdown", "value"),
    Input("factor-search-input", "value"),
    Input("x-metric-dropdown", "value"),
    Input("y-metric-dropdown", "value"),
    Input("leaderboard-metric-dropdown", "value"),
)
def update_scoreboard(
    scoreboard_path: str | None,
    family_values: list[str] | None,
    search_text: str | None,
    x_metric: str | None,
    y_metric: str | None,
    rank_metric: str | None,
):
    if not scoreboard_path:
        return [], _empty_figure("因子前沿（Factor Frontier）"), [], html.Div(), [], []

    x_metric = x_metric or DEFAULT_X_METRIC
    y_metric = y_metric or DEFAULT_Y_METRIC
    rank_metric = rank_metric or DEFAULT_RANK_METRIC

    payload = _load_json(Path(scoreboard_path))
    frame = _build_factor_frame(payload)
    family_options = _family_filter_options(frame)
    filtered = _apply_factor_filters(frame, family_values, search_text)

    cards = [
        _metric_card("候选板 ID（Scoreboard ID）", payload.get("scoreboard_id")),
        _metric_card("全部因子数（All Factors）", payload.get("factor_count")),
        _metric_card("筛选后因子数（Filtered Factors）", len(filtered)),
        _metric_card("基线数量（Baseline Count）", len(payload.get("baseline_factors", []))),
        _metric_card("预评估数量（Pre-Eval Count）", payload.get("pre_eval_count")),
        _metric_card("比较条目数（Comparison Count）", payload.get("comparison_count")),
    ]

    if filtered.empty:
        figure = _empty_figure("因子前沿（Factor Frontier）")
        leaderboard = _render_leaderboard(filtered, rank_metric)
        return cards, figure, family_options, leaderboard, [], []

    scatter_frame = filtered.copy()
    figure = px.scatter(
        scatter_frame,
        x=x_metric,
        y=y_metric,
        color="factor_family",
        hover_name="factor_name",
        size="mean_abs_rank_ic",
        size_max=36,
        custom_data=[
            "factor_name",
            "factor_family",
            "transform_name",
            "mean_rank_ic",
            "mean_abs_rank_ic",
            "mean_normalized_mutual_info",
            "mean_top_bottom_spread",
            "mean_coverage_ratio",
            "joined_rows",
        ],
        title=f"因子前沿（Factor Frontier）：{_metric_label(x_metric)} vs {_metric_label(y_metric)}",
    )
    figure.update_layout(
        xaxis_title=_metric_label(x_metric),
        yaxis_title=_metric_label(y_metric),
        legend_title_text="因子家族（Factor Family）",
        margin={"l": 48, "r": 24, "t": 72, "b": 48},
    )
    figure.update_traces(
        hovertemplate=(
            "因子（Factor）=%{customdata[0]}<br>"
            "家族（Family）=%{customdata[1]}<br>"
            "变换方式（Transform）=%{customdata[2]}<br>"
            "平均排序相关性（Mean Rank IC）=%{customdata[3]:.4f}<br>"
            "平均绝对排序相关性（Mean Abs Rank IC）=%{customdata[4]:.4f}<br>"
            "平均归一化互信息（Mean NMI）=%{customdata[5]:.4f}<br>"
            "平均多空价差（Mean Top-Bottom Spread）=%{customdata[6]:.4f}<br>"
            "平均覆盖率（Mean Coverage Ratio）=%{customdata[7]:.4f}<br>"
            "样本行数（Joined Rows）=%{customdata[8]}<extra></extra>"
        )
    )

    leaderboard = _render_leaderboard(filtered, rank_metric)
    factor_options = _sorted_factor_options(filtered, rank_metric)
    return cards, figure, family_options, leaderboard, factor_options, factor_options


@app.callback(
    Output("left-factor-dropdown", "value"),
    Output("right-factor-dropdown", "value"),
    Input("left-factor-dropdown", "options"),
    State("left-factor-dropdown", "value"),
    State("right-factor-dropdown", "value"),
)
def sync_factor_pair(
    options: list[dict[str, str]] | None,
    current_left: str | None,
    current_right: str | None,
):
    values = [item["value"] for item in options or []]
    if not values:
        return None, None

    left_value = current_left if current_left in values else values[0]
    available_right = [value for value in values if value != left_value]
    if current_right in available_right:
        right_value = current_right
    elif available_right:
        right_value = available_right[0]
    else:
        right_value = left_value
    return left_value, right_value


@app.callback(
    Output("comparison-metrics", "children"),
    Output("factor-compare-diagnostics", "figure"),
    Output("factor-compare-bars", "figure"),
    Output("factor-compare-per-date", "figure"),
    Input("scoreboard-dropdown", "value"),
    Input("left-factor-dropdown", "value"),
    Input("right-factor-dropdown", "value"),
)
def compare_factors(scoreboard_path: str | None, left_factor_name: str | None, right_factor_name: str | None):
    if not scoreboard_path or not left_factor_name or not right_factor_name:
        empty = _empty_figure("因子对比（Factor Comparison）")
        return [], empty, empty, empty

    payload = _load_json(Path(scoreboard_path))
    by_name = {item.get("factor_name"): item for item in payload.get("factors", [])}
    left_factor = by_name.get(left_factor_name)
    right_factor = by_name.get(right_factor_name)
    if not left_factor or not right_factor:
        empty = _empty_figure("因子对比（Factor Comparison）")
        return [], empty, empty, empty

    left_pre = left_factor.get("pre_eval", {})
    right_pre = right_factor.get("pre_eval", {})

    compare_frame = pd.DataFrame(
        [
            {
                "factor_name": left_factor_name,
                "metric": "mean_rank_ic",
                "value": left_pre.get("mean_rank_ic"),
            },
            {
                "factor_name": left_factor_name,
                "metric": "mean_normalized_mutual_info",
                "value": left_pre.get("mean_normalized_mutual_info"),
            },
            {
                "factor_name": left_factor_name,
                "metric": "mean_top_bottom_spread",
                "value": left_pre.get("mean_top_bottom_spread"),
            },
            {
                "factor_name": right_factor_name,
                "metric": "mean_rank_ic",
                "value": right_pre.get("mean_rank_ic"),
            },
            {
                "factor_name": right_factor_name,
                "metric": "mean_normalized_mutual_info",
                "value": right_pre.get("mean_normalized_mutual_info"),
            },
            {
                "factor_name": right_factor_name,
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
        tickvals=["mean_rank_ic", "mean_normalized_mutual_info", "mean_top_bottom_spread"],
        ticktext=[
            _metric_label("mean_rank_ic"),
            _metric_label("mean_normalized_mutual_info"),
            _metric_label("mean_top_bottom_spread"),
        ],
        title="评估指标（Metrics）",
    )
    bar_figure.update_layout(
        yaxis_title="指标值（Metric Value）",
        legend_title_text="因子（Factor）",
        margin={"l": 48, "r": 24, "t": 72, "b": 72},
    )

    per_date_rows: list[dict[str, Any]] = []
    for factor_name, pre_eval in ((left_factor_name, left_pre), (right_factor_name, right_pre)):
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
    if per_date_frame.empty:
        line_figure = _empty_figure("逐日排序相关性对比（Per-Date Rank IC Comparison）")
    else:
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
            margin={"l": 48, "r": 24, "t": 72, "b": 48},
        )

    comparison_entry, match_level = _find_best_comparison(left_factor, right_factor, comparison_catalog)
    if comparison_entry is None:
        comparison_cards = [
            _metric_card("比较产物（Comparison Artifact）", "未找到（Not Found）"),
            _metric_card("匹配方式（Match Level）", "n/a"),
            _metric_card("共同日期数（Common Dates）", "n/a"),
            _metric_card("共同样本行数（Common Rows）", "n/a"),
        ]
        diagnostics_figure = _empty_figure("已有 comparison 结果（Existing Comparison Artifact）")
        return comparison_cards, diagnostics_figure, bar_figure, line_figure

    comparison_payload = _load_json(Path(comparison_entry["path"]))
    diagnostics_frame = _build_comparison_diagnostics_frame(comparison_payload)
    mean_pearson = diagnostics_frame["pearson_corr"].dropna().mean() if "pearson_corr" in diagnostics_frame else None
    mean_overlap = (
        diagnostics_frame["top_overlap_count"].dropna().mean()
        if "top_overlap_count" in diagnostics_frame
        else None
    )
    comparison_cards = [
        _metric_card("比较产物 ID（Comparison ID）", comparison_payload.get("comparison_id")),
        _metric_card("匹配方式（Match Level）", match_level),
        _metric_card("共同日期数（Common Dates）", len(comparison_payload.get("common_dates", []))),
        _metric_card("共同样本行数（Common Rows）", comparison_payload.get("common_rows")),
        _metric_card("平均皮尔逊相关性（Mean Pearson Corr）", mean_pearson),
        _metric_card("平均 Top 重叠数（Mean Top Overlap）", mean_overlap),
    ]

    if diagnostics_frame.empty:
        diagnostics_figure = _empty_figure("已有 comparison 结果（Existing Comparison Artifact）")
    else:
        diagnostics_figure = make_subplots(specs=[[{"secondary_y": True}]])
        diagnostics_figure.add_trace(
            go.Scatter(
                x=diagnostics_frame["date"],
                y=diagnostics_frame.get("pearson_corr"),
                mode="lines+markers",
                name=_metric_label("pearson_corr"),
                line={"color": "#1f5f8b", "width": 3},
            ),
            secondary_y=False,
        )
        diagnostics_figure.add_trace(
            go.Bar(
                x=diagnostics_frame["date"],
                y=diagnostics_frame.get("top_overlap_count"),
                name=_metric_label("top_overlap_count"),
                marker_color="#b88746",
                opacity=0.38,
            ),
            secondary_y=True,
        )
        diagnostics_figure.update_layout(
            title="已有 comparison 结果（Existing Comparison Artifact）",
            legend_title_text="指标（Metrics）",
            margin={"l": 48, "r": 48, "t": 72, "b": 48},
        )
        diagnostics_figure.update_xaxes(title_text="日期（Date）")
        diagnostics_figure.update_yaxes(title_text=_metric_label("pearson_corr"), secondary_y=False)
        diagnostics_figure.update_yaxes(title_text=_metric_label("top_overlap_count"), secondary_y=True)

    return comparison_cards, diagnostics_figure, bar_figure, line_figure


@app.callback(
    Output("pre-eval-per-date", "figure"),
    Output("pre-eval-regimes", "figure"),
    Output("selection-summary", "children"),
    Input("pre-eval-dropdown", "value"),
)
def update_pre_eval(pre_eval_path: str | None):
    if not pre_eval_path:
        return (
            _empty_figure("逐日结果（Per-Date Outcome）"),
            _empty_figure("状态切片（Regime Slice）"),
            "尚未选择预评估（Pre-Eval）。",
        )

    payload = _load_json(Path(pre_eval_path))
    per_date = _build_per_date_frame(payload)
    regime_frame = _build_regime_frame(payload)

    if per_date.empty:
        per_date_figure = _empty_figure("逐日结果（Per-Date Outcome）")
    else:
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
            margin={"l": 48, "r": 24, "t": 72, "b": 48},
        )
        for trace in per_date_figure.data:
            trace.name = METRIC_LABELS.get(trace.name, trace.name)

    if regime_frame.empty:
        regime_figure = _empty_figure("状态切片（Regime Slice）")
    else:
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
            margin={"l": 48, "r": 24, "t": 72, "b": 48},
        )

    summary = json.dumps(
        {
            "因子名称（Factor Name）": payload.get("factor_name"),
            "实验 ID（Experiment ID）": payload.get("experiment_id"),
            "平均排序相关性（Mean Rank IC）": payload.get("mean_rank_ic"),
            "平均绝对排序相关性（Mean Abs Rank IC）": payload.get("mean_abs_rank_ic"),
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
            .controls-dense { grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
            .panel { background: rgba(255,255,255,0.82); border: 1px solid #c9d4c5; border-radius: 16px; padding: 16px; box-shadow: 0 10px 30px rgba(23,33,33,0.06); }
            .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 18px; }
            .metric-card { background: rgba(255,255,255,0.82); border: 1px solid #c9d4c5; border-radius: 16px; padding: 14px 16px; }
            .metric-label { font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; color: #5d6c63; margin-bottom: 6px; }
            .metric-value { font-size: 20px; font-weight: 700; color: #172121; }
            .section-title { font-size: 18px; font-weight: 700; margin-bottom: 12px; }
            .table-shell { overflow-x: auto; }
            .table-caption { color: #5d6c63; margin-bottom: 10px; }
            .leaderboard-table { width: 100%; border-collapse: collapse; min-width: 980px; }
            .leaderboard-table th, .leaderboard-table td { padding: 10px 12px; border-bottom: 1px solid #dbe2d7; text-align: left; }
            .leaderboard-table th { background: rgba(234, 240, 232, 0.95); position: sticky; top: 0; }
            .empty-note { color: #5d6c63; }
            .text-input { width: 100%; padding: 11px 12px; border-radius: 10px; border: 1px solid #c9d4c5; box-sizing: border-box; }
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
    app.run(debug=DEBUG_MODE)
