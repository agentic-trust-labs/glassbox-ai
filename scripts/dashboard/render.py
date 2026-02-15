"""Renders the HTML dashboard from fetched data."""

import html
import math
import re
from datetime import datetime, timezone
from typing import Dict, List

from .config import REPO


class DashboardRenderer:
    """Generates a complete HTML dashboard from agent data."""

    def __init__(self, data: Dict):
        self._data = data
        self._now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def _esc(self, text: str) -> str:
        return html.escape(str(text))

    # ── Metrics ──────────────────────────────────────────────────────────

    def _metrics(self) -> Dict:
        agent = self._data["agent_issues"]
        runs = self._data["runs"]

        total_agent = len(agent)
        merged = sum(1 for i in agent if i["outcome"] == "merged")
        failed = sum(1 for i in agent if i["outcome"] in ("failed", "closed"))
        open_pr = sum(1 for i in agent if i["outcome"] == "open_pr")
        by_label = sum(1 for i in agent if i["trigger"] == "label")
        by_mention = sum(1 for i in agent if i["trigger"] == "mention")
        analyzed = sum(1 for i in agent if i.get("comment_count", 0) >= 1)
        pr_created = sum(1 for i in agent if i["outcome"] in ("merged", "open_pr", "closed"))
        success_rate = (merged / total_agent * 100) if total_agent > 0 else 0

        total_runs = len(runs)
        run_success = sum(1 for r in runs if r.get("conclusion") == "success")
        run_fail = sum(1 for r in runs if r.get("conclusion") == "failure")

        # Failure pattern analysis
        patterns = {}
        for i in agent:
            msg = i.get("failure_msg", "")
            if not msg:
                continue
            if "IndentationError" in msg:
                patterns.setdefault("IndentationError", []).append(i["number"])
            elif "OperationalError" in msg or "SQL" in msg.lower() or "DEFAULT_TRUST" in msg:
                patterns.setdefault("SQL / Variable", []).append(i["number"])
            elif "AttributeError" in msg:
                patterns.setdefault("AttributeError", []).append(i["number"])
            elif "SyntaxError" in msg or "Syntax error" in msg:
                patterns.setdefault("SyntaxError", []).append(i["number"])
            elif "Tests failed" in msg:
                patterns.setdefault("Test Failure", []).append(i["number"])
            elif "Debate could not approve" in msg:
                patterns.setdefault("Debate Rejection", []).append(i["number"])
            else:
                patterns.setdefault("Other", []).append(i["number"])

        return {
            "total_agent": total_agent, "merged": merged, "failed": failed,
            "open_pr": open_pr, "analyzed": analyzed, "pr_created": pr_created,
            "by_label": by_label, "by_mention": by_mention,
            "success_rate": success_rate, "total_runs": total_runs,
            "run_success": run_success, "run_fail": run_fail, "patterns": patterns,
        }

    # ── CSS ───────────────────────────────────────────────────────────────

    def _css(self) -> str:
        return """
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; background: #0d1117; color: #e6edf3; line-height: 1.6; }
        .container { max-width: 1280px; margin: 0 auto; padding: 32px 24px; }

        .header { text-align: center; margin-bottom: 48px; }
        .header h1 { font-size: 32px; font-weight: 800; letter-spacing: -0.5px; }
        .header .subtitle { color: #8b949e; font-size: 14px; margin-top: 8px; }
        .header .version { display: inline-block; background: #238636; color: #fff; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; margin-left: 8px; vertical-align: middle; }

        .section { margin-bottom: 48px; }
        .section-header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; padding-bottom: 12px; border-bottom: 1px solid #30363d; }
        .section-header h2 { font-size: 20px; font-weight: 700; }
        .section-header .badge { background: #30363d; color: #8b949e; padding: 2px 10px; border-radius: 10px; font-size: 12px; }

        .card { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; }
        .card-grid { display: grid; gap: 16px; }
        .card-grid-2 { grid-template-columns: 1fr 1fr; }
        .card-grid-4 { grid-template-columns: repeat(4, 1fr); }

        .metric { text-align: center; padding: 24px 16px; }
        .metric .icon { font-size: 24px; margin-bottom: 8px; }
        .metric .value { font-size: 36px; font-weight: 800; letter-spacing: -1px; }
        .metric .label { font-size: 11px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.8px; margin-top: 4px; }

        table { width: 100%; border-collapse: collapse; }
        th { text-align: left; padding: 12px 16px; background: #0d1117; border-bottom: 2px solid #30363d; font-size: 11px; color: #8b949e; text-transform: uppercase; letter-spacing: 0.8px; font-weight: 600; }
        td { padding: 10px 16px; border-bottom: 1px solid #21262d; font-size: 13px; }
        tr:hover { background: #1c2128; }

        .pill { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; white-space: nowrap; }
        .pill-green { background: #12261e; color: #3fb950; border: 1px solid #238636; }
        .pill-red { background: #2d1215; color: #f85149; border: 1px solid #da3633; }
        .pill-amber { background: #2d2200; color: #d29922; border: 1px solid #9e6a03; }
        .pill-blue { background: #0d2039; color: #58a6ff; border: 1px solid #1f6feb; }
        .pill-purple { background: #1c1433; color: #bc8cff; border: 1px solid #8957e5; }
        .pill-gray { background: #21262d; color: #8b949e; border: 1px solid #30363d; }

        a { color: #58a6ff; text-decoration: none; }
        a:hover { text-decoration: underline; }

        .flow { display: flex; align-items: center; justify-content: center; gap: 0; padding: 20px 0; flex-wrap: wrap; }
        .flow-node { text-align: center; padding: 14px 18px; border-radius: 12px; min-width: 100px; }
        .flow-arrow { color: #30363d; font-size: 20px; padding: 0 6px; }

        .text-green { color: #3fb950; }
        .text-red { color: #f85149; }
        .text-amber { color: #d29922; }
        .text-muted { color: #8b949e; }
        .text-center { text-align: center; }
        .font-mono { font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace; }
        code { background: #21262d; padding: 2px 8px; border-radius: 4px; font-size: 11px; color: #79c0ff; }
        .updated { color: #8b949e; font-size: 12px; text-align: center; margin-top: 32px; padding-top: 16px; border-top: 1px solid #21262d; }

        @media (max-width: 900px) {
            .card-grid-4 { grid-template-columns: repeat(2, 1fr); }
            .card-grid-2 { grid-template-columns: 1fr; }
            .flow { gap: 4px; }
        }
        """

    # ── Section 1: Success Pipeline ──────────────────────────────────────

    def _section_success(self, agent_issues: List[Dict], m: Dict) -> str:
        total = m["total_agent"]
        if total == 0:
            return ""

        stages = [
            ("Assigned", total, "#58a6ff", "&#x1f4e5;"),
            ("Analyzed", m["analyzed"], "#79c0ff", "&#x1f50d;"),
            ("PR Created", m["pr_created"], "#d29922", "&#x1f4dd;"),
            ("Merged", m["merged"], "#3fb950", "&#x2705;"),
        ]

        funnel_bars = ""
        for label, count, color, emoji in stages:
            pct = (count / total * 100) if total > 0 else 0
            bar_pct = max(15, pct)
            funnel_bars += f'''
            <div style="display:flex;align-items:center;gap:16px;margin:8px 0">
                <div style="min-width:100px;text-align:right;font-size:13px;color:#8b949e">{emoji} {label}</div>
                <div style="flex:1;background:#21262d;border-radius:6px;height:32px;overflow:hidden">
                    <div style="width:{bar_pct}%;height:100%;background:{color};border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:#fff;min-width:50px;transition:width 0.5s">
                        {count} ({pct:.0f}%)
                    </div>
                </div>
            </div>'''

        rate = m["success_rate"]
        rate_color = "#3fb950" if rate >= 50 else "#d29922" if rate >= 30 else "#f85149"

        chart = self._svg_success_chart(agent_issues)

        return f'''
        <div class="section">
            <div class="section-header">
                <h2>&#x1f3af; Success Pipeline</h2>
                <span class="badge">{m["merged"]}/{total} merged</span>
            </div>
            <div class="card-grid card-grid-2">
                <div class="card">
                    <div style="font-size:14px;font-weight:600;margin-bottom:16px">&#x1f4ca; Conversion Funnel</div>
                    {funnel_bars}
                    <div style="text-align:center;margin-top:20px;padding-top:14px;border-top:1px solid #30363d">
                        <span style="font-size:32px;font-weight:800;color:{rate_color}">{rate:.0f}%</span>
                        <div style="font-size:12px;color:#8b949e;margin-top:2px">end-to-end success rate</div>
                    </div>
                </div>
                <div class="card">
                    <div style="font-size:14px;font-weight:600;margin-bottom:12px">&#x1f4c8; Success Rate Over Time</div>
                    {chart}
                </div>
            </div>
        </div>'''

    def _svg_success_chart(self, agent_issues: List[Dict]) -> str:
        sorted_issues = sorted(agent_issues, key=lambda x: x.get("created_at", ""))
        if not sorted_issues:
            return '<div class="text-muted text-center" style="padding:40px">No data yet</div>'

        points = []
        total = merged = 0
        for i in sorted_issues:
            total += 1
            if i["outcome"] == "merged":
                merged += 1
            points.append((total, (merged / total) * 100))

        w, h = 560, 200
        pl, pr_, pt, pb = 42, 12, 12, 30
        cw, ch = w - pl - pr_, h - pt - pb
        mx = max(total, 1)

        def sx(v): return pl + (v / mx) * cw
        def sy(v): return pt + ch - (v / 100) * ch

        grid = ""
        for pct in [0, 25, 50, 75, 100]:
            y = sy(pct)
            grid += f'<line x1="{pl}" y1="{y}" x2="{w - pr_}" y2="{y}" stroke="#21262d" stroke-width="1"/>'
            grid += f'<text x="{pl - 6}" y="{y + 4}" fill="#8b949e" font-size="9" text-anchor="end">{pct}%</text>'

        path_d = " ".join(f"{'M' if i == 0 else 'L'}{sx(x):.1f},{sy(y):.1f}" for i, (x, y) in enumerate(points))
        area_d = path_d + f" L{sx(points[-1][0]):.1f},{sy(0):.1f} L{sx(points[0][0]):.1f},{sy(0):.1f} Z"

        cur = points[-1][1]
        color = "#3fb950" if cur >= 50 else "#d29922" if cur >= 30 else "#f85149"

        dots = ""
        show_dots = points[-15:] if len(points) > 15 else points
        for x, y in show_dots:
            dc = "#3fb950" if y >= 50 else "#d29922" if y >= 30 else "#f85149"
            dots += f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="3" fill="{dc}" stroke="#161b22" stroke-width="1.5"/>'

        return f'''
        <svg width="100%" viewBox="0 0 {w} {h}" style="max-width:{w}px">
            <defs><linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="{color}" stop-opacity="0.25"/>
                <stop offset="100%" stop-color="{color}" stop-opacity="0.0"/>
            </linearGradient></defs>
            {grid}
            <path d="{area_d}" fill="url(#sg)"/>
            <path d="{path_d}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            {dots}
            <text x="{w // 2}" y="{h - 5}" fill="#8b949e" font-size="9" text-anchor="middle">Issue # (chronological) - Current: {cur:.0f}%</text>
        </svg>'''

    # ── Section 2: Metrics Grid + Architecture Flow ──────────────────────

    def _section_metrics(self, m: Dict, avg_tat: int) -> str:
        def card(emoji, value, label, color="#e6edf3"):
            return f'''
            <div class="card metric">
                <div class="icon">{emoji}</div>
                <div class="value" style="color:{color}">{value}</div>
                <div class="label">{label}</div>
            </div>'''

        rate = m["success_rate"]
        rc = "#3fb950" if rate >= 50 else "#d29922" if rate >= 30 else "#f85149"
        tc = "#3fb950" if avg_tat <= 35 else "#d29922" if avg_tat <= 50 else "#f85149" if avg_tat > 0 else "#8b949e"

        flow = '''
        <div class="card" style="margin-top:16px">
            <div style="font-size:14px;font-weight:600;margin-bottom:8px">&#x1f3d7;&#xfe0f; Architecture Flow</div>
            <div class="flow">
                <div class="flow-node" style="background:#0d2039;border:1px solid #1f6feb">
                    <div style="font-size:18px">&#x1f4e5;</div>
                    <div style="font-size:11px;font-weight:700;color:#58a6ff">Issue</div>
                    <div style="font-size:9px;color:#8b949e">labeled</div>
                </div>
                <div class="flow-arrow">&#x27a1;&#xfe0f;</div>
                <div class="flow-node" style="background:#1c1433;border:1px solid #8957e5">
                    <div style="font-size:18px">&#x1f3af;</div>
                    <div style="font-size:11px;font-weight:700;color:#bc8cff">Manager</div>
                    <div style="font-size:9px;color:#8b949e">classify + brief</div>
                </div>
                <div class="flow-arrow">&#x27a1;&#xfe0f;</div>
                <div class="flow-node" style="background:#2d2200;border:1px solid #9e6a03">
                    <div style="font-size:18px">&#x1f527;</div>
                    <div style="font-size:11px;font-weight:700;color:#d29922">JuniorDev</div>
                    <div style="font-size:9px;color:#8b949e">generate fix</div>
                </div>
                <div class="flow-arrow">&#x27a1;&#xfe0f;</div>
                <div class="flow-node" style="background:#0d2818;border:1px solid #238636">
                    <div style="font-size:18px">&#x1f9ea;</div>
                    <div style="font-size:11px;font-weight:700;color:#3fb950">Tester</div>
                    <div style="font-size:9px;color:#8b949e">validate</div>
                </div>
                <div class="flow-arrow">&#x27a1;&#xfe0f;</div>
                <div class="flow-node" style="background:#12261e;border:1px solid #238636">
                    <div style="font-size:18px">&#x2705;</div>
                    <div style="font-size:11px;font-weight:700;color:#3fb950">PR</div>
                    <div style="font-size:9px;color:#8b949e">merge</div>
                </div>
            </div>
        </div>'''

        return f'''
        <div class="section">
            <div class="section-header">
                <h2>&#x1f4ca; Overview</h2>
            </div>
            <div class="card-grid card-grid-4">
                {card("&#x1f41b;", str(m["total_agent"]), "Total Issues")}
                {card("&#x2705;", str(m["merged"]), "Merged", "#3fb950")}
                {card("&#x274c;", str(m["failed"]), "Failed", "#f85149")}
                {card("&#x1f4c8;", f'{rate:.0f}%', "Success Rate", rc)}
            </div>
            <div class="card-grid card-grid-4" style="margin-top:16px">
                {card("&#x23f1;&#xfe0f;", f'{avg_tat}s' if avg_tat else '-', "Avg TAT", tc)}
                {card("&#x26a1;", str(m["total_runs"]), "Workflow Runs")}
                {card("&#x1f3f7;&#xfe0f;", str(m["by_label"]), "Via Label", "#58a6ff")}
                {card("&#x1f4ac;", str(m["by_mention"]), "Via @mention", "#bc8cff")}
            </div>
            {flow}
        </div>'''

    # ── Section 3: Turnaround Time ───────────────────────────────────────

    def _section_tat(self, run_timings: List[Dict]) -> str:
        if not run_timings:
            return ""

        durations = [t.get("duration_s", 0) for t in run_timings if t.get("duration_s", 0) > 0]
        if not durations:
            return ""

        avg = int(sum(durations) / len(durations))
        latest = durations[0] if durations else 0
        best = min(durations)
        worst = max(durations)

        # Aggregate step timing for pie chart
        step_totals = {}
        for rt in run_timings:
            for job in rt.get("jobs", []):
                for step in job.get("steps", []):
                    name = step.get("name", "")
                    dur = step.get("duration_s", 0)
                    if dur == 0:
                        continue
                    if any(k in name.lower() for k in ["checkout", "set up python", "cache", "install", "activate", "configure"]):
                        cat = "Setup"
                    elif "agent" in name.lower() or "run agent" in name.lower():
                        cat = "Agent"
                    elif "ack" in name.lower() or "post instant" in name.lower():
                        cat = "Ack"
                    else:
                        cat = "Overhead"
                    step_totals[cat] = step_totals.get(cat, 0) + dur

        n_runs = len(run_timings)
        segments = []
        colors_map = {"Setup": "#58a6ff", "Agent": "#d29922", "Ack": "#bc8cff", "Overhead": "#8b949e"}
        emoji_map = {"Setup": "&#x2699;&#xfe0f;", "Agent": "&#x1f916;", "Ack": "&#x1f4ac;", "Overhead": "&#x1f504;"}
        for cat in ["Setup", "Agent", "Ack", "Overhead"]:
            if cat in step_totals:
                avg_s = round(step_totals[cat] / n_runs, 1)
                segments.append((cat, avg_s, colors_map.get(cat, "#8b949e"), emoji_map.get(cat, "")))

        pie = self._svg_pie_chart(segments, 170)

        total_seg = sum(s[1] for s in segments)
        legend = ""
        for label, val, color, emoji in segments:
            pct = (val / total_seg * 100) if total_seg > 0 else 0
            legend += f'''
            <div style="display:flex;align-items:center;gap:8px;margin:6px 0;font-size:12px">
                <div style="width:10px;height:10px;border-radius:3px;background:{color};flex-shrink:0"></div>
                <span style="color:#8b949e">{emoji} {label}</span>
                <span style="color:#e6edf3;font-weight:600;margin-left:auto">{val:.0f}s ({pct:.0f}%)</span>
            </div>'''

        trend = self._svg_tat_chart(run_timings)

        lc = "#3fb950" if latest <= 35 else "#d29922" if latest <= 50 else "#f85149"
        ac = "#3fb950" if avg <= 35 else "#d29922" if avg <= 50 else "#f85149"

        return f'''
        <div class="section">
            <div class="section-header">
                <h2>&#x23f1;&#xfe0f; Turnaround Time</h2>
                <span class="badge">last {len(run_timings)} runs</span>
            </div>
            <div class="card-grid card-grid-2">
                <div class="card">
                    <div style="display:flex;align-items:center;gap:24px">
                        <div style="flex-shrink:0">{pie}</div>
                        <div style="flex:1">
                            <div style="font-size:14px;font-weight:600;margin-bottom:12px">&#x1f967; Time Breakdown (avg)</div>
                            {legend}
                            <div style="margin-top:14px;padding-top:14px;border-top:1px solid #30363d">
                                <div style="display:flex;justify-content:space-between;font-size:12px;margin:3px 0">
                                    <span style="color:#8b949e">&#x23f1;&#xfe0f; Latest</span>
                                    <span style="color:{lc};font-weight:700">{latest}s</span>
                                </div>
                                <div style="display:flex;justify-content:space-between;font-size:12px;margin:3px 0">
                                    <span style="color:#8b949e">&#x1f4ca; Average</span>
                                    <span style="color:{ac};font-weight:700">{avg}s</span>
                                </div>
                                <div style="display:flex;justify-content:space-between;font-size:12px;margin:3px 0">
                                    <span style="color:#8b949e">&#x1f3c6; Best / Worst</span>
                                    <span style="color:#e6edf3;font-weight:600">{best}s / {worst}s</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="card">
                    <div style="font-size:14px;font-weight:600;margin-bottom:12px">&#x1f4c9; TAT Trend</div>
                    {trend}
                </div>
            </div>
        </div>'''

    def _svg_pie_chart(self, segments: list, size: int = 170) -> str:
        total = sum(v for _, v, _, _ in segments)
        if total == 0:
            return ""
        cx, cy = size / 2, size / 2
        ro = size / 2 - 5
        ri = ro * 0.6

        paths = ""
        start = -90
        for _, value, color, _ in segments:
            if value == 0:
                continue
            sweep = (value / total) * 360
            end = start + sweep
            sa, ea = math.radians(start), math.radians(end)

            x1o, y1o = cx + ro * math.cos(sa), cy + ro * math.sin(sa)
            x2o, y2o = cx + ro * math.cos(ea), cy + ro * math.sin(ea)
            x1i, y1i = cx + ri * math.cos(ea), cy + ri * math.sin(ea)
            x2i, y2i = cx + ri * math.cos(sa), cy + ri * math.sin(sa)

            large = 1 if sweep > 180 else 0
            d = (f"M{x1o:.1f},{y1o:.1f} A{ro:.1f},{ro:.1f} 0 {large} 1 {x2o:.1f},{y2o:.1f} "
                 f"L{x1i:.1f},{y1i:.1f} A{ri:.1f},{ri:.1f} 0 {large} 0 {x2i:.1f},{y2i:.1f} Z")
            paths += f'<path d="{d}" fill="{color}" opacity="0.85" stroke="#161b22" stroke-width="2"/>'
            start = end

        avg_t = int(total)
        center = f'''
            <text x="{cx}" y="{cy - 6}" fill="#e6edf3" font-size="18" font-weight="800" text-anchor="middle">{avg_t}s</text>
            <text x="{cx}" y="{cy + 10}" fill="#8b949e" font-size="9" text-anchor="middle">avg total</text>'''

        return f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">{paths}{center}</svg>'

    def _svg_tat_chart(self, run_timings: List[Dict]) -> str:
        timings = list(reversed(run_timings))
        points = [(i + 1, t.get("duration_s", 0)) for i, t in enumerate(timings) if t.get("duration_s", 0) > 0]
        if not points:
            return '<div class="text-muted text-center" style="padding:40px">No data</div>'

        w, h = 560, 200
        pl, pr_, pt, pb = 48, 12, 12, 30
        cw, ch = w - pl - pr_, h - pt - pb
        mx = max(p[0] for p in points)
        my = max(max(p[1] for p in points), 10)

        def sx(v): return pl + (v / mx) * cw if mx > 0 else pl
        def sy(v): return pt + ch - (v / my) * ch

        grid = ""
        step_y = max(1, int(my) // 4)
        for s in range(0, int(my) + 1, step_y):
            y = sy(s)
            grid += f'<line x1="{pl}" y1="{y}" x2="{w - pr_}" y2="{y}" stroke="#21262d" stroke-width="1"/>'
            grid += f'<text x="{pl - 6}" y="{y + 4}" fill="#8b949e" font-size="9" text-anchor="end">{s}s</text>'

        if my >= 55:
            y60 = sy(60)
            grid += f'<line x1="{pl}" y1="{y60}" x2="{w - pr_}" y2="{y60}" stroke="#f85149" stroke-width="1" stroke-dasharray="5,4" opacity="0.5"/>'
            grid += f'<text x="{w - pr_ - 2}" y="{y60 - 5}" fill="#f85149" font-size="8" text-anchor="end">60s baseline</text>'

        if my >= 28:
            y32 = sy(32)
            grid += f'<line x1="{pl}" y1="{y32}" x2="{w - pr_}" y2="{y32}" stroke="#3fb950" stroke-width="1" stroke-dasharray="5,4" opacity="0.35"/>'
            grid += f'<text x="{w - pr_ - 2}" y="{y32 - 5}" fill="#3fb950" font-size="8" text-anchor="end">32s target</text>'

        path_d = " ".join(f"{'M' if i == 0 else 'L'}{sx(x):.1f},{sy(y):.1f}" for i, (x, y) in enumerate(points))
        area_d = path_d + f" L{sx(points[-1][0]):.1f},{sy(0):.1f} L{sx(points[0][0]):.1f},{sy(0):.1f} Z"

        latest = points[-1][1]
        color = "#3fb950" if latest <= 35 else "#d29922" if latest <= 50 else "#f85149"

        dots = ""
        for x, y in points:
            dc = "#3fb950" if y <= 35 else "#d29922" if y <= 50 else "#f85149"
            dots += f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="3.5" fill="{dc}" stroke="#161b22" stroke-width="1.5"/>'

        return f'''
        <svg width="100%" viewBox="0 0 {w} {h}" style="max-width:{w}px">
            <defs><linearGradient id="tg" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="{color}" stop-opacity="0.2"/>
                <stop offset="100%" stop-color="{color}" stop-opacity="0.0"/>
            </linearGradient></defs>
            {grid}
            <path d="{area_d}" fill="url(#tg)"/>
            <path d="{path_d}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            {dots}
            <text x="{w // 2}" y="{h - 5}" fill="#8b949e" font-size="9" text-anchor="middle">Recent runs (chronological) - Latest: {latest}s</text>
        </svg>'''

    # ── Section 4: Recent Issues Table ───────────────────────────────────

    def _section_issues(self, agent_issues: List[Dict]) -> str:
        recent = sorted(agent_issues, key=lambda x: x["number"], reverse=True)[:30]
        if not recent:
            return ""

        rows = ""
        for issue in recent:
            n = issue["number"]
            title = self._esc(issue["title"][:55])
            url = issue.get("html_url", f"https://github.com/{REPO}/issues/{n}")

            # Type from title prefix
            t = issue.get("title", "").lower()
            if t.startswith("[fix]") or "fix:" in t[:15]:
                tp = '<span class="pill pill-blue">&#x1f527; Fix</span>'
            elif t.startswith("[bug]") or "bug" in t[:15]:
                tp = '<span class="pill pill-red">&#x1f41b; Bug</span>'
            elif t.startswith("[feature]") or "feature" in t[:15]:
                tp = '<span class="pill pill-purple">&#x2728; Feature</span>'
            else:
                tp = '<span class="pill pill-gray">&#x1f4cb; Other</span>'

            # Template from linked PR body
            template = '<span class="text-muted">-</span>'
            pr = issue.get("linked_pr")
            if pr:
                body = (pr.get("body") or "").lower()
                if "typo_fix" in body:
                    template = '<span class="pill pill-green">typo_fix</span>'
                elif "wrong_value" in body:
                    template = '<span class="pill pill-amber">wrong_value</span>'
                elif "wrong_name" in body:
                    template = '<span class="pill pill-blue">wrong_name</span>'
                elif "swapped_args" in body:
                    template = '<span class="pill pill-purple">swapped_args</span>'

            # Pipeline stage indicators
            outcome = issue.get("outcome", "not_triggered")
            cc = issue.get("comment_count", 0)

            classify = "&#x2705;" if cc >= 1 else "&#x2796;"
            fix = "&#x2705;" if pr else ("&#x274c;" if cc >= 1 else "&#x2796;")
            test = "&#x2705;" if pr else "&#x2796;"

            pr_cell = '<span class="text-muted">-</span>'
            if pr:
                pn = pr["number"]
                pu = pr.get("html_url", f"https://github.com/{REPO}/pull/{pn}")
                pr_cell = f'<a href="{pu}" target="_blank">#{pn}</a>'

            result_map = {
                "merged": '<span class="pill pill-green">&#x2705; Merged</span>',
                "closed": '<span class="pill pill-red">&#x274c; Closed</span>',
                "failed": '<span class="pill pill-red">&#x1f6ab; Failed</span>',
                "open_pr": '<span class="pill pill-amber">&#x1f7e1; Open</span>',
                "not_triggered": '<span class="pill pill-gray">&#x2796; -</span>',
            }
            result = result_map.get(outcome, '<span class="pill pill-gray">?</span>')

            rows += f'''
            <tr>
                <td><a href="{url}" target="_blank" style="font-weight:600">#{n}</a></td>
                <td style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{title}</td>
                <td>{tp}</td>
                <td>{template}</td>
                <td class="text-center">{classify}</td>
                <td class="text-center">{fix}</td>
                <td class="text-center">{test}</td>
                <td>{pr_cell}</td>
                <td>{result}</td>
            </tr>'''

        return f'''
        <div class="section">
            <div class="section-header">
                <h2>&#x1f527; Recent Issues</h2>
                <span class="badge">last {len(recent)}</span>
            </div>
            <div class="card" style="overflow-x:auto">
                <table>
                    <tr>
                        <th>#</th>
                        <th>Title</th>
                        <th>Type</th>
                        <th>Template</th>
                        <th class="text-center">&#x1f3af; Classify</th>
                        <th class="text-center">&#x1f527; Fix</th>
                        <th class="text-center">&#x1f9ea; Test</th>
                        <th>PR</th>
                        <th>Result</th>
                    </tr>
                    {rows}
                </table>
            </div>
        </div>'''

    # ── Section 5: Pull Requests ─────────────────────────────────────────

    def _section_prs(self, prs: List[Dict]) -> str:
        recent = sorted(prs, key=lambda x: x["number"], reverse=True)[:30]
        if not recent:
            return ""

        rows = ""
        for pr in recent:
            n = pr["number"]
            title = self._esc(pr["title"][:50])
            url = pr.get("html_url", f"https://github.com/{REPO}/pull/{n}")
            branch = self._esc(pr.get("head", ""))
            merged = pr.get("merged_at")
            state = "merged" if merged else pr["state"]

            # Linked issue
            body = pr.get("body") or ""
            issue_link = '<span class="text-muted">-</span>'
            m = re.search(r'#(\d+)', body)
            if not m:
                bm = re.search(r'issue-(\d+)', branch)
                if bm:
                    issue_link = f'<a href="https://github.com/{REPO}/issues/{bm.group(1)}" target="_blank">#{bm.group(1)}</a>'
            else:
                issue_link = f'<a href="https://github.com/{REPO}/issues/{m.group(1)}" target="_blank">#{m.group(1)}</a>'

            state_map = {
                "merged": ("&#x2705;", "pill-green", "Merged"),
                "closed": ("&#x274c;", "pill-red", "Closed"),
                "open": ("&#x1f7e2;", "pill-green", "Open"),
            }
            se, sc, sl = state_map.get(state, ("?", "pill-gray", state))

            rows += f'''
            <tr>
                <td><a href="{url}" target="_blank" style="font-weight:600">#{n}</a></td>
                <td style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{title}</td>
                <td>{issue_link}</td>
                <td><code>{branch}</code></td>
                <td><span class="pill {sc}">{se} {sl}</span></td>
            </tr>'''

        return f'''
        <div class="section">
            <div class="section-header">
                <h2>&#x1f500; Pull Requests</h2>
                <span class="badge">last {len(recent)}</span>
            </div>
            <div class="card" style="overflow-x:auto">
                <table>
                    <tr><th>PR</th><th>Title</th><th>Issue</th><th>Branch</th><th>Status</th></tr>
                    {rows}
                </table>
            </div>
        </div>'''

    # ── Section 6: Failure Diagnostics ───────────────────────────────────

    def _section_failures(self, m: Dict) -> str:
        patterns = m["patterns"]
        if not patterns:
            return ""

        total_f = sum(len(v) for v in patterns.values())
        rows = ""
        for pattern, nums in sorted(patterns.items(), key=lambda x: -len(x[1])):
            count = len(nums)
            pct = (count / total_f * 100) if total_f > 0 else 0
            bar_w = max(4, min(pct * 2.5, 100))
            links = ", ".join(f'<a href="https://github.com/{REPO}/issues/{n}" target="_blank">#{n}</a>' for n in nums[:8])
            if len(nums) > 8:
                links += f' <span class="text-muted">+{len(nums) - 8}</span>'

            rows += f'''
            <tr>
                <td style="font-weight:600;white-space:nowrap">&#x1f6a8; {self._esc(pattern)}</td>
                <td style="font-weight:700;color:#f85149">{count}</td>
                <td>
                    <div style="display:flex;align-items:center;gap:8px">
                        <div style="background:#f85149;height:8px;width:{bar_w}%;border-radius:4px;min-width:4px"></div>
                        <span class="text-muted" style="font-size:11px">{pct:.0f}%</span>
                    </div>
                </td>
                <td style="font-size:12px">{links}</td>
            </tr>'''

        return f'''
        <div class="section">
            <div class="section-header">
                <h2>&#x1f6a8; Failure Diagnostics</h2>
                <span class="badge">{total_f} failures</span>
            </div>
            <div class="card" style="overflow-x:auto">
                <table>
                    <tr><th>Pattern</th><th>Count</th><th>Distribution</th><th>Issues</th></tr>
                    {rows}
                </table>
            </div>
        </div>'''

    # ── Section 7: Workflow Runs ─────────────────────────────────────────

    def _section_runs(self, runs: List[Dict]) -> str:
        recent = sorted(runs, key=lambda x: x.get("created_at", ""), reverse=True)[:30]
        if not recent:
            return ""

        rows = ""
        for run in recent:
            rid = run["id"]
            url = run.get("html_url", f"https://github.com/{REPO}/actions/runs/{rid}")
            title = self._esc(run.get("display_title", "")[:40])
            event = run.get("event", "")
            conclusion = run.get("conclusion") or "running"
            created = run.get("created_at", "")[:16].replace("T", " ")
            dur = run.get("duration_s", 0)

            c_map = {
                "success": ("&#x2705;", "pill-green", "Success"),
                "failure": ("&#x274c;", "pill-red", "Failure"),
                "skipped": ("&#x23ed;&#xfe0f;", "pill-gray", "Skipped"),
                "running": ("&#x1f535;", "pill-blue", "Running"),
            }
            ce, cc, cl = c_map.get(conclusion, ("?", "pill-gray", conclusion))

            e_map = {
                "issues": ("&#x1f41b;", "pill-blue"),
                "issue_comment": ("&#x1f4ac;", "pill-purple"),
                "push": ("&#x1f4e4;", "pill-gray"),
                "pull_request": ("&#x1f500;", "pill-amber"),
            }
            ee, ec = e_map.get(event, ("&#x26a1;", "pill-gray"))

            dur_str = f"{dur}s" if dur > 0 else "-"
            dc = "#3fb950" if 0 < dur <= 35 else "#d29922" if dur <= 50 else "#f85149" if dur > 50 else "#8b949e"

            rows += f'''
            <tr>
                <td><a href="{url}" target="_blank" style="font-size:12px">{rid}</a></td>
                <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{title}</td>
                <td><span class="pill {ec}">{ee} {event}</span></td>
                <td><span class="pill {cc}">{ce} {cl}</span></td>
                <td style="color:{dc};font-weight:600;font-family:monospace;font-size:12px">{dur_str}</td>
                <td class="text-muted" style="font-size:12px">{created}</td>
            </tr>'''

        return f'''
        <div class="section">
            <div class="section-header">
                <h2>&#x26a1; Workflow Runs</h2>
                <span class="badge">last {len(recent)}</span>
            </div>
            <div class="card" style="overflow-x:auto">
                <table>
                    <tr><th>Run ID</th><th>Title</th><th>Event</th><th>Result</th><th>Duration</th><th>Time</th></tr>
                    {rows}
                </table>
            </div>
        </div>'''

    # ── Main Render ──────────────────────────────────────────────────────

    def render(self) -> str:
        m = self._metrics()
        agent_issues = self._data["agent_issues"]
        prs = self._data["prs"]
        runs = self._data["runs"]
        run_timings = self._data.get("run_timings", [])

        tat_durations = [t.get("duration_s", 0) for t in run_timings if t.get("duration_s", 0) > 0]
        avg_tat = int(sum(tat_durations) / len(tat_durations)) if tat_durations else 0

        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GlassBox Agent v1.0 - Performance Tracker</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>💎</text></svg>">
    <style>{self._css()}</style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>&#x1f48e; GlassBox Agent <span class="version">v1.0</span></h1>
            <div class="subtitle">Real-time performance tracking - <a href="https://github.com/{REPO}" target="_blank">github.com/{REPO}</a></div>
        </div>

        {self._section_success(agent_issues, m)}
        {self._section_metrics(m, avg_tat)}
        {self._section_tat(run_timings)}
        {self._section_issues(agent_issues)}
        {self._section_prs(prs)}
        {self._section_failures(m)}
        {self._section_runs(runs)}

        <div class="updated">&#x1f48e; Last updated: {self._now} | Generated by scripts/dashboard/generate.py</div>
    </div>
</body>
</html>'''
