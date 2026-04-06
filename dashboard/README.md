# Dash Research Dashboard

这个目录放研究辅助可视化，不修改固定 harness。

设计原则：

- 只读 `runs/` 下的实验产物
- 不改 evaluator 与实验接口
- 优先服务研究筛选和证伪
- 默认采用中英双语文案，方便研究和业务同事共同查看

当前面板入口：

```bash
python3 dashboard/research_dashboard_app.py
```

如果本机还没装依赖，可先安装：

```bash
pip install -e ".[dashboard]"
```

面板当前支持：

- 浏览最新 `scoreboard_summary.json`
- 按因子家族和关键词筛选候选
- 切换散点图横纵轴指标，快速看不同前沿
- 生成筛选后榜单，按指定指标排序
- 比较两个因子的总体指标与 per-date 表现
- 复用已有 `comparison_summary.json`，直接看相关性与 Top overlap
- 查看 regime slice 表现
- 读取单个 pre-eval summary 并画时间序列/条形图

可选环境变量：

- `HK_FACTOR_RUNS_DIR=/abs/path/to/runs`：改成读取别的 `runs/` 目录
- `HK_FACTOR_DASH_DEBUG=1`：需要 Dash debug/reloader 时再显式打开

这层适合做：

- 新候选与 baseline 对比
- 看某个候选在哪类 regime 更强
- 快速判断一个新想法是不是只是已有 baseline 的换皮
