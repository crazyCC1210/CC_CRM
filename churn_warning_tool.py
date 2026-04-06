import argparse
import csv
import html
import io
import json
import sys
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class UserBehavior:
    user_id: str
    monthly_logins: int
    feature_usage_count: int
    last_login_days_ago: int
    payment_last_30d: float
    total_paid: float
    last_payment_days_ago: int


@dataclass
class RiskResult:
    user_id: str
    risk_score: float
    risk_level: str
    reasons: List[str]
    retention_strategies: List[str]
    priority_score: float
    total_paid: float


def load_data(csv_path: str) -> List[UserBehavior]:
    users: List[UserBehavior] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            users.append(
                UserBehavior(
                    user_id=row["user_id"],
                    monthly_logins=int(row["monthly_logins"]),
                    feature_usage_count=int(row["feature_usage_count"]),
                    last_login_days_ago=int(row["last_login_days_ago"]),
                    payment_last_30d=float(row["payment_last_30d"]),
                    total_paid=float(row["total_paid"]),
                    last_payment_days_ago=int(row["last_payment_days_ago"]),
                )
            )
    return users


def evaluate_risk(user: UserBehavior) -> Tuple[float, List[str], List[str]]:
    score = 0.0
    reasons: List[str] = []
    tags: List[str] = []

    if user.monthly_logins < 5:
        score += 35
        reasons.append(f"登录频率偏低（近30天登录{user.monthly_logins}次）")
        tags.append("low_activity")
    elif user.monthly_logins < 9:
        score += 20
        reasons.append(f"登录频率下降（近30天登录{user.monthly_logins}次）")
        tags.append("mid_activity")

    if user.feature_usage_count < 8:
        score += 30
        reasons.append(f"核心功能使用不足（近30天功能使用{user.feature_usage_count}次）")
        tags.append("low_feature_adoption")
    elif user.feature_usage_count < 15:
        score += 15
        reasons.append(f"功能使用深度一般（近30天功能使用{user.feature_usage_count}次）")
        tags.append("mid_feature_adoption")

    if user.last_login_days_ago > 14:
        score += 25
        reasons.append(f"最近活跃距今较久（{user.last_login_days_ago}天未登录）")
        tags.append("inactivity")
    elif user.last_login_days_ago > 7:
        score += 10
        reasons.append(f"近期活跃走弱（{user.last_login_days_ago}天未登录）")
        tags.append("weak_inactivity")

    if user.payment_last_30d <= 0:
        score += 30
        reasons.append("近30天无付费记录")
        tags.append("payment_risk")

    if user.last_payment_days_ago > 45:
        score += 20
        reasons.append(f"付费间隔过长（距上次付费{user.last_payment_days_ago}天）")
        tags.append("payment_gap")
    elif user.last_payment_days_ago > 30:
        score += 10
        reasons.append(f"付费间隔偏长（距上次付费{user.last_payment_days_ago}天）")
        tags.append("payment_gap")

    score = min(score, 100)
    return score, reasons, tags


def risk_level(score: float) -> str:
    if score >= 65:
        return "高"
    if score >= 40:
        return "中"
    return "低"


def strategy_library() -> Dict[str, List[str]]:
    return {
        "low_activity": [
            "7天唤醒计划：每天推送一个3分钟可完成的关键动作",
            "客户成功经理发起1v1复盘，明确业务目标与使用路径",
        ],
        "mid_activity": [
            "推送周报，展示产品使用收益与待完成动作",
        ],
        "low_feature_adoption": [
            "开启新手引导任务流，重点训练2个核心功能",
            "提供行业模板与最佳实践，缩短配置门槛",
        ],
        "mid_feature_adoption": [
            "进行高级功能工作坊，引导从基础使用到流程自动化",
        ],
        "inactivity": [
            "触发高优先级召回：短信+邮件+客户经理电话三触点",
            "提供限时激励（如扩容包或功能试用）促使回流",
        ],
        "weak_inactivity": [
            "发送个性化提醒，推荐最适合当前业务阶段的功能",
        ],
        "payment_risk": [
            "提供分层折扣与续费礼包，降低续费决策阻力",
            "输出ROI报告，量化使用收益支撑续费谈判",
        ],
        "payment_gap": [
            "提前触发续费提醒，并给出年度计划优惠",
        ],
    }


def build_strategies(tags: List[str], library: Dict[str, List[str]]) -> List[str]:
    strategies: List[str] = []
    for tag in tags:
        for strategy in library.get(tag, []):
            if strategy not in strategies:
                strategies.append(strategy)
    return strategies


def priority_score(level: str, total_paid: float) -> float:
    risk_weight = {"高": 1.0, "中": 0.6, "低": 0.25}[level]
    return round(risk_weight * total_paid, 2)


def analyze(users: List[UserBehavior]) -> List[RiskResult]:
    results: List[RiskResult] = []
    library = strategy_library()

    for user in users:
        score, reasons, tags = evaluate_risk(user)
        level = risk_level(score)
        strategies = build_strategies(tags, library)
        p_score = priority_score(level, user.total_paid)

        results.append(
            RiskResult(
                user_id=user.user_id,
                risk_score=round(score, 1),
                risk_level=level,
                reasons=reasons,
                retention_strategies=strategies,
                priority_score=p_score,
                total_paid=user.total_paid,
            )
        )

    results.sort(key=lambda x: x.priority_score, reverse=True)
    return results


def retention_framework_text() -> str:
    return (
        "1) 活跃度下降：轻量任务驱动 + 客户成功经理跟进，先恢复使用习惯\n"
        "2) 功能采纳不足：新手引导 + 模板扶持，让用户快速获得可见价值\n"
        "3) 付费风险：分层优惠 + ROI量化，降低续费阻力并强化商业价值认知\n"
        "4) 长期未活跃：多触点召回 + 限时激励，优先争取回流再做深度运营"
    )


def print_report(results: List[RiskResult]) -> None:
    print("=" * 80)
    print("客户流失预警分析结果")
    print("=" * 80)
    print("用户\t风险等级\t风险分\t优先级分\t累计付费")
    for r in results:
        print(f"{r.user_id}\t{r.risk_level}\t{r.risk_score}\t{r.priority_score}\t{r.total_paid}")

    print("\n" + "=" * 80)
    print("高风险用户原因与建议")
    print("=" * 80)
    high_risk_users = [r for r in results if r.risk_level == "高"]
    if not high_risk_users:
        print("当前无高风险用户")
    for r in high_risk_users:
        print(f"\n[{r.user_id}] 风险分: {r.risk_score}, 优先级分: {r.priority_score}")
        print("风险因素:")
        for reason in r.reasons:
            print(f"- {reason}")
        print("挽留建议:")
        for strategy in r.retention_strategies:
            print(f"- {strategy}")

    print("\n" + "=" * 80)
    print("优先挽留TOP 5（综合风险与累计付费）")
    print("=" * 80)
    for idx, r in enumerate(results[:5], start=1):
        print(
            f"{idx}. {r.user_id} | 风险:{r.risk_level}({r.risk_score}) | "
            f"累计付费:{r.total_paid} | 优先级分:{r.priority_score}"
        )

    print("\n" + "=" * 80)
    print("挽留策略框架")
    print("=" * 80)
    print(retention_framework_text())


def results_to_payload(results: List[RiskResult]) -> List[Dict[str, object]]:
    return [
        {
            "user_id": r.user_id,
            "risk_level": r.risk_level,
            "risk_score": r.risk_score,
            "priority_score": r.priority_score,
            "total_paid": r.total_paid,
            "reasons": r.reasons,
            "retention_strategies": r.retention_strategies,
        }
        for r in results
    ]


def parse_users_from_csv_text(csv_text: str) -> List[UserBehavior]:
    users: List[UserBehavior] = []
    reader = csv.DictReader(io.StringIO(csv_text))

    required_columns = {
        "user_id",
        "monthly_logins",
        "feature_usage_count",
        "last_login_days_ago",
        "payment_last_30d",
        "total_paid",
        "last_payment_days_ago",
    }
    if not reader.fieldnames or not required_columns.issubset(set(reader.fieldnames)):
        missing = required_columns - set(reader.fieldnames or [])
        raise ValueError(f"CSV缺少必要字段: {', '.join(sorted(missing))}")

    for row in reader:
        users.append(
            UserBehavior(
                user_id=row["user_id"],
                monthly_logins=int(row["monthly_logins"]),
                feature_usage_count=int(row["feature_usage_count"]),
                last_login_days_ago=int(row["last_login_days_ago"]),
                payment_last_30d=float(row["payment_last_30d"]),
                total_paid=float(row["total_paid"]),
                last_payment_days_ago=int(row["last_payment_days_ago"]),
            )
        )
    return users


def run_gui(default_csv_path: str) -> None:
    from tkinter import BOTH, END, LEFT, RIGHT, X, Y, StringVar, Text, Tk
    from tkinter import filedialog, messagebox, ttk

    root = Tk()
    root.title("客户流失预警分析工具")
    root.geometry("1180x760")

    path_var = StringVar(value=default_csv_path)
    status_var = StringVar(value="请选择或确认数据文件后，点击“开始分析”")
    summary_var = StringVar(value="风险分布：高 0 | 中 0 | 低 0")
    priority_var = StringVar(value="优先挽留TOP3：-")

    result_map: Dict[str, RiskResult] = {}

    top_frame = ttk.Frame(root, padding=10)
    top_frame.pack(fill=X)

    ttk.Label(top_frame, text="数据文件:").pack(side=LEFT)
    path_entry = ttk.Entry(top_frame, textvariable=path_var, width=80)
    path_entry.pack(side=LEFT, padx=8)

    def browse_csv() -> None:
        selected = filedialog.askopenfilename(
            title="选择用户行为数据CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if selected:
            path_var.set(selected)

    ttk.Button(top_frame, text="浏览", command=browse_csv).pack(side=LEFT)

    info_frame = ttk.Frame(root, padding=(10, 0, 10, 10))
    info_frame.pack(fill=X)
    ttk.Label(info_frame, textvariable=summary_var).pack(side=LEFT)
    ttk.Label(info_frame, textvariable=priority_var).pack(side=RIGHT)

    main_frame = ttk.Frame(root, padding=(10, 0, 10, 10))
    main_frame.pack(fill=BOTH, expand=True)

    table_frame = ttk.Frame(main_frame)
    table_frame.pack(side=LEFT, fill=BOTH, expand=True)

    columns = ("user_id", "risk_level", "risk_score", "priority_score", "total_paid")
    table = ttk.Treeview(table_frame, columns=columns, show="headings", height=20)
    table.heading("user_id", text="用户")
    table.heading("risk_level", text="风险等级")
    table.heading("risk_score", text="风险分")
    table.heading("priority_score", text="优先级分")
    table.heading("total_paid", text="累计付费")

    table.column("user_id", width=90, anchor="center")
    table.column("risk_level", width=80, anchor="center")
    table.column("risk_score", width=90, anchor="center")
    table.column("priority_score", width=110, anchor="center")
    table.column("total_paid", width=100, anchor="center")

    table.pack(side=LEFT, fill=BOTH, expand=True)

    table_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview)
    table_scroll.pack(side=RIGHT, fill=Y)
    table.configure(yscrollcommand=table_scroll.set)

    detail_frame = ttk.Frame(main_frame)
    detail_frame.pack(side=RIGHT, fill=BOTH, expand=True, padx=(10, 0))

    ttk.Label(detail_frame, text="用户详情（风险因素 + 挽留建议）").pack(anchor="w")
    detail_text = Text(detail_frame, wrap="word", font=("Arial", 12))
    detail_text.pack(fill=BOTH, expand=True)

    ttk.Label(root, textvariable=status_var, padding=(10, 0, 10, 10)).pack(anchor="w")

    framework_frame = ttk.LabelFrame(root, text="挽留策略框架", padding=10)
    framework_frame.pack(fill=X, padx=10, pady=(0, 10))
    framework_text = Text(framework_frame, height=5, wrap="word", font=("Arial", 11))
    framework_text.insert("1.0", retention_framework_text())
    framework_text.configure(state="disabled")
    framework_text.pack(fill=X)

    def refresh_detail(user_id: str) -> None:
        detail_text.delete("1.0", END)
        result = result_map.get(user_id)
        if not result:
            return

        detail_text.insert(END, f"用户: {result.user_id}\n")
        detail_text.insert(END, f"风险等级: {result.risk_level}\n")
        detail_text.insert(END, f"风险分: {result.risk_score}\n")
        detail_text.insert(END, f"优先级分: {result.priority_score}\n")
        detail_text.insert(END, f"累计付费: {result.total_paid}\n\n")

        detail_text.insert(END, "风险因素:\n")
        if result.reasons:
            for reason in result.reasons:
                detail_text.insert(END, f"- {reason}\n")
        else:
            detail_text.insert(END, "- 暂无明显风险因素\n")

        detail_text.insert(END, "\n挽留建议:\n")
        if result.retention_strategies:
            for strategy in result.retention_strategies:
                detail_text.insert(END, f"- {strategy}\n")
        else:
            detail_text.insert(END, "- 当前无需重点挽留动作\n")

    def on_row_select(_: object) -> None:
        selected_items = table.selection()
        if not selected_items:
            return
        values = table.item(selected_items[0], "values")
        if values:
            refresh_detail(str(values[0]))

    table.bind("<<TreeviewSelect>>", on_row_select)

    def start_analysis() -> None:
        csv_path = path_var.get().strip()
        if not csv_path:
            messagebox.showerror("路径缺失", "请先选择CSV数据文件")
            return

        try:
            users = load_data(csv_path)
            results = analyze(users)
        except Exception as exc:
            messagebox.showerror("分析失败", f"处理数据时出错:\n{exc}")
            return

        for item in table.get_children():
            table.delete(item)

        result_map.clear()
        high_count = 0
        mid_count = 0
        low_count = 0

        for result in results:
            result_map[result.user_id] = result
            table.insert(
                "",
                END,
                values=(
                    result.user_id,
                    result.risk_level,
                    result.risk_score,
                    result.priority_score,
                    result.total_paid,
                ),
            )
            if result.risk_level == "高":
                high_count += 1
            elif result.risk_level == "中":
                mid_count += 1
            else:
                low_count += 1

        summary_var.set(f"风险分布：高 {high_count} | 中 {mid_count} | 低 {low_count}")
        top3 = "、".join([r.user_id for r in results[:3]]) if results else "-"
        priority_var.set(f"优先挽留TOP3：{top3}")

        if len(users) != 10:
            status_var.set(f"分析完成：共{len(users)}位用户（提示：原始样例目标为10位）")
        else:
            status_var.set("分析完成：已加载10位用户")

        if results:
            first_id = results[0].user_id
            refresh_detail(first_id)
            first_item = table.get_children()[0]
            table.selection_set(first_item)

    ttk.Button(top_frame, text="开始分析", command=start_analysis).pack(side=LEFT, padx=10)
    root.mainloop()


def build_web_html(results: List[RiskResult]) -> str:
    payload = results_to_payload(results)
    framework_html = html.escape(retention_framework_text()).replace("\n", "<br>")
    data_json = json.dumps(payload, ensure_ascii=False)

    return f"""<!doctype html>
<html lang='zh-CN'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>客户流失预警分析工具</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif; margin: 0; background: #f5f7fa; }}
    .wrap {{ max-width: 1240px; margin: 0 auto; padding: 20px; }}
    .title {{ font-size: 24px; font-weight: 700; margin-bottom: 8px; }}
    .sub {{ color: #667085; margin-bottom: 16px; }}
    .card {{ background: #fff; border-radius: 12px; padding: 16px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(16,24,40,.1); }}
    .toolbar {{ display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 12px; }}
    .toolbar input[type='text'], .toolbar select {{
      border: 1px solid #d0d5dd; border-radius: 8px; padding: 7px 10px; font-size: 14px;
    }}
    .toolbar button {{
      border: 1px solid #1570ef; background: #1570ef; color: #fff; border-radius: 8px; padding: 7px 12px; cursor: pointer;
    }}
    .toolbar button.secondary {{ background: #fff; color: #344054; border-color: #d0d5dd; }}
    .row {{ display: flex; gap: 16px; align-items: stretch; }}
    .left {{ flex: 1.2; min-width: 0; }}
    .right {{ flex: 1; min-width: 0; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 10px 8px; border-bottom: 1px solid #eef2f6; text-align: left; font-size: 14px; }}
    th {{ color: #344054; background: #fafcff; }}
    tr:hover {{ background: #f9fafb; cursor: pointer; }}
    .badge {{ display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12px; }}
    .high {{ background: #fee4e2; color: #b42318; }}
    .mid {{ background: #fef0c7; color: #b54708; }}
    .low {{ background: #d1fadf; color: #027a48; }}
    ul {{ margin: 6px 0 0 16px; padding: 0; }}
    li {{ margin: 4px 0; }}
    .muted {{ color: #667085; }}
    .small {{ font-size: 12px; color: #667085; }}
    .dataset {{ margin-left: auto; }}
    #status {{ margin-top: 6px; }}
  </style>
</head>
<body>
  <div class='wrap'>
    <div class='title'>客户流失预警分析工具（Web界面）</div>
    <div id='summary' class='sub'>准备就绪</div>

    <div class='card'>
      <div class='toolbar'>
        <input id='searchInput' type='text' placeholder='按用户ID筛选，如 U00'>
        <select id='riskFilter'>
          <option value='全部'>全部风险等级</option>
          <option value='高'>仅高风险</option>
          <option value='中'>仅中风险</option>
          <option value='低'>仅低风险</option>
        </select>
        <button id='applyFilterBtn'>应用筛选</button>
        <button id='resetFilterBtn' class='secondary'>重置筛选</button>
        <div class='dataset'>
          <input id='datasetInput' type='file' accept='.csv'>
          <button id='uploadBtn'>上传并分析</button>
        </div>
      </div>
      <div id='status' class='small'>当前数据集：默认样例（10位用户）</div>
    </div>

    <div class='row'>
      <div class='left card'>
        <table>
          <thead>
            <tr>
              <th>用户</th>
              <th>风险等级</th>
              <th>风险分</th>
              <th>优先级分</th>
              <th>累计付费</th>
            </tr>
          </thead>
          <tbody id='rows'></tbody>
        </table>
      </div>
      <div class='right card'>
        <div id='detail' class='muted'>点击左侧用户查看风险因素和挽留建议</div>
      </div>
    </div>

    <div class='card'>
      <div style='font-weight:600; margin-bottom:8px;'>挽留策略框架</div>
      <div>{framework_html}</div>
    </div>
  </div>

  <script>
    let fullData = {data_json};
    let filteredData = [...fullData];
    const rows = document.getElementById('rows');
    const detail = document.getElementById('detail');
    const summary = document.getElementById('summary');
    const statusText = document.getElementById('status');
    const searchInput = document.getElementById('searchInput');
    const riskFilter = document.getElementById('riskFilter');
    const datasetInput = document.getElementById('datasetInput');

    function levelClass(level) {{
      if (level === '高') return 'high';
      if (level === '中') return 'mid';
      return 'low';
    }}

    function updateSummary(data) {{
      const high = data.filter(x => x.risk_level === '高').length;
      const mid = data.filter(x => x.risk_level === '中').length;
      const low = data.filter(x => x.risk_level === '低').length;
      const top3 = data.slice(0, 3).map(x => x.user_id).join('、') || '-';
      summary.textContent = `风险分布：高 ${{high}} | 中 ${{mid}} | 低 ${{low}} ｜ 优先挽留TOP3：${{top3}}`;
    }}

    function renderDetail(item) {{
      if (!item) {{
        detail.innerHTML = "<span class='muted'>当前筛选结果为空</span>";
        return;
      }}
      const reasons = item.reasons.length
        ? '<ul>' + item.reasons.map(x => `<li>${{x}}</li>`).join('') + '</ul>'
        : '<ul><li>暂无明显风险因素</li></ul>';
      const acts = item.retention_strategies.length
        ? '<ul>' + item.retention_strategies.map(x => `<li>${{x}}</li>`).join('') + '</ul>'
        : '<ul><li>当前无需重点挽留动作</li></ul>';

      detail.innerHTML = `
        <div><b>用户:</b> ${{item.user_id}}</div>
        <div><b>风险等级:</b> ${{item.risk_level}}</div>
        <div><b>风险分:</b> ${{item.risk_score}}</div>
        <div><b>优先级分:</b> ${{item.priority_score}}</div>
        <div><b>累计付费:</b> ${{item.total_paid}}</div>
        <div style='margin-top:8px;'><b>风险因素</b>${{reasons}}</div>
        <div style='margin-top:8px;'><b>挽留建议</b>${{acts}}</div>
      `;
    }}

    function renderTable(data) {{
      rows.innerHTML = '';
      data.forEach(item => {{
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${{item.user_id}}</td>
          <td><span class="badge ${{levelClass(item.risk_level)}}">${{item.risk_level}}</span></td>
          <td>${{item.risk_score}}</td>
          <td>${{item.priority_score}}</td>
          <td>${{item.total_paid}}</td>
        `;
        tr.onclick = () => renderDetail(item);
        rows.appendChild(tr);
      }});
      renderDetail(data[0]);
      updateSummary(data);
    }}

    function applyFilters() {{
      const keyword = searchInput.value.trim().toLowerCase();
      const level = riskFilter.value;
      filteredData = fullData.filter(item => {{
        const matchKeyword = keyword === '' || item.user_id.toLowerCase().includes(keyword);
        const matchLevel = level === '全部' || item.risk_level === level;
        return matchKeyword && matchLevel;
      }});
      renderTable(filteredData);
      statusText.textContent = `当前数据集：共${{fullData.length}}位用户，筛选后${{filteredData.length}}位`;
    }}

    async function uploadDataset() {{
      const file = datasetInput.files[0];
      if (!file) {{
        alert('请先选择CSV文件');
        return;
      }}
      const csvText = await file.text();
      try {{
        const resp = await fetch('/analyze', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ csv_text: csvText }})
        }});
        const payload = await resp.json();
        if (!resp.ok) {{
          throw new Error(payload.error || '上传分析失败');
        }}

        fullData = payload.results;
        filteredData = [...fullData];
        searchInput.value = '';
        riskFilter.value = '全部';
        renderTable(filteredData);
        statusText.textContent = `当前数据集：${{file.name}}（${{fullData.length}}位用户）`;
      }} catch (err) {{
        alert(`上传失败：${{err.message}}`);
      }}
    }}

    document.getElementById('applyFilterBtn').onclick = applyFilters;
    document.getElementById('resetFilterBtn').onclick = () => {{
      searchInput.value = '';
      riskFilter.value = '全部';
      filteredData = [...fullData];
      renderTable(filteredData);
      statusText.textContent = `当前数据集：共${{fullData.length}}位用户`;
    }};
    document.getElementById('uploadBtn').onclick = uploadDataset;

    renderTable(filteredData);
  </script>
</body>
</html>
"""


def run_web_ui(results: List[RiskResult], host: str = "127.0.0.1", port: int = 8765) -> None:
    initial_page = build_web_html(results).encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def _send_json(self, payload: Dict[str, object], status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path != "/":
                self.send_error(404, "Not Found")
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(initial_page)))
            self.end_headers()
            self.wfile.write(initial_page)

        def do_POST(self) -> None:
            if self.path != "/analyze":
                self.send_error(404, "Not Found")
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(content_length)
            try:
                body = json.loads(raw.decode("utf-8"))
                csv_text = str(body.get("csv_text", "")).strip()
                if not csv_text:
                    raise ValueError("csv_text 不能为空")
                users = parse_users_from_csv_text(csv_text)
                analyzed = analyze(users)
                self._send_json({"results": results_to_payload(analyzed), "count": len(users)})
            except Exception as exc:
                self._send_json({"error": str(exc)}, status=400)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}"

    print(f"Web界面已启动：{url}")
    print("按 Ctrl+C 可停止服务")
    webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nWeb服务已停止")
    finally:
        server.server_close()


def should_use_web_by_default() -> bool:
    return sys.platform == "darwin" and Path(sys.executable).as_posix() == "/usr/bin/python3"


def main() -> None:
    parser = argparse.ArgumentParser(description="客户流失预警分析工具")
    parser.add_argument("--csv", default="simulated_users.csv", help="用户行为数据CSV路径")
    parser.add_argument("--cli", action="store_true", help="使用命令行模式输出分析结果")
    parser.add_argument("--gui", action="store_true", help="使用桌面窗口模式（tkinter）")
    parser.add_argument("--web", action="store_true", help="使用浏览器Web界面模式")
    parser.add_argument("--port", type=int, default=8765, help="Web模式端口，默认8765")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    csv_candidate = Path(args.csv).expanduser()
    csv_path = str(csv_candidate if csv_candidate.is_absolute() else script_dir / csv_candidate)
    users = load_data(csv_path)
    results = analyze(users)

    if args.cli:
        print_report(results)
        return

    if args.web or (not args.gui and should_use_web_by_default()):
        run_web_ui(results, port=args.port)
        return

    run_gui(csv_path)


if __name__ == "__main__":
    main()
