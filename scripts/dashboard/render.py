"""Renders the HTML dashboard from fetched data."""

import html
import math
import re
from datetime import datetime, timezone
from typing import Dict, List

from .config import REPO


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _fmt_date(iso: str) -> str:
    """Format ISO date to Indian style: 12 May 26, 18:30"""
    if not iso:
        return "-"
    try:
        dt = datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        # Convert to IST (UTC+5:30)
        from datetime import timedelta
        dt = dt + timedelta(hours=5, minutes=30)
        d = dt.day
        m = MONTHS[dt.month - 1]
        y = str(dt.year)[2:]
        t = dt.strftime("%H:%M")
        return f'{d} {m} {y}, <span style="color:#8b949e">{t}</span>'
    except (ValueError, TypeError):
        return iso[:16]


class DashboardRenderer:
    """Generates a complete HTML dashboard from agent data."""

    def __init__(self, data: Dict):
        self._data = data
        now = datetime.now(timezone.utc)
        from datetime import timedelta
        ist = now + timedelta(hours=5, minutes=30)
        d = ist.day
        m = MONTHS[ist.month - 1]
        y = str(ist.year)[2:]
        t = ist.strftime("%H:%M")
        self._now = f"{d} {m} {y}, {t} IST"

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

        # Only agent-relevant runs (triggered by issues or issue_comment)
        agent_runs = [r for r in runs if r.get("event") in ("issues", "issue_comment")]
        total_runs = len(agent_runs)
        run_success = sum(1 for r in agent_runs if r.get("conclusion") == "success")
        run_fail = sum(1 for r in agent_runs if r.get("conclusion") == "failure")

        # Failure pattern analysis
        patterns = {}
        for i in agent:
            msg = i.get("failure_msg", "")
            if not msg:
                continue
            if "IndentationError" in msg:
                patterns.setdefault("IndentationError", []).append(i)
            elif "OperationalError" in msg or "SQL" in msg.lower() or "DEFAULT_TRUST" in msg:
                patterns.setdefault("SQL / Variable Error", []).append(i)
            elif "AttributeError" in msg:
                patterns.setdefault("AttributeError", []).append(i)
            elif "SyntaxError" in msg or "Syntax error" in msg:
                patterns.setdefault("SyntaxError", []).append(i)
            elif "Tests failed" in msg:
                patterns.setdefault("Test Failure", []).append(i)
            elif "Debate could not approve" in msg:
                patterns.setdefault("Debate Rejection", []).append(i)
            else:
                patterns.setdefault("_other_", []).append(i)

        return {
            "total_agent": total_agent, "merged": merged, "failed": failed,
            "open_pr": open_pr, "analyzed": analyzed, "pr_created": pr_created,
            "by_label": by_label, "by_mention": by_mention,
            "success_rate": success_rate, "total_runs": total_runs,
            "run_success": run_success, "run_fail": run_fail,
            "agent_runs": agent_runs, "patterns": patterns,
        }

    # ── CSS ───────────────────────────────────────────────────────────────

    def _css(self) -> str:
        return """
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; background: #0d1117; color: #c9d1d9; line-height: 1.6; }
        .container { max-width: 1200px; margin: 0 auto; padding: 32px 24px; }

        .header { text-align: center; margin-bottom: 40px; }
        .header h1 { font-size: 24px; font-weight: 700; color: #e6edf3; }
        .header .subtitle { color: #8b949e; font-size: 13px; margin-top: 4px; }
        .header .ver { color: #8b949e; font-size: 11px; border: 1px solid #30363d; padding: 1px 8px; border-radius: 10px; margin-left: 6px; }

        .section { margin-bottom: 40px; }
        .section-title { font-size: 15px; font-weight: 600; color: #e6edf3; margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }
        .section-title .count { color: #8b949e; font-weight: 400; font-size: 12px; }

        .card { background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 16px; }
        .row { display: flex; gap: 16px; }
        .col { flex: 1; }

        .stat-row { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }
        .stat { background: #161b22; border: 1px solid #21262d; border-radius: 8px; padding: 14px 16px; flex: 1; min-width: 120px; }
        .stat .val { font-size: 24px; font-weight: 700; color: #e6edf3; }
        .stat .lbl { font-size: 11px; color: #8b949e; margin-top: 2px; }

        table { width: 100%; border-collapse: collapse; font-size: 13px; }
        th { text-align: left; padding: 8px 12px; border-bottom: 1px solid #21262d; font-size: 11px; color: #8b949e; font-weight: 500; }
        td { padding: 7px 12px; border-bottom: 1px solid #161b22; }
        tr:hover td { background: #1c2128; }

        .tag { display: inline-block; padding: 1px 8px; border-radius: 10px; font-size: 11px; font-weight: 500; }
        .tag-green { color: #3fb950; background: #12261e; }
        .tag-red { color: #f85149; background: #2d1215; }
        .tag-amber { color: #d29922; background: #2d2200; }
        .tag-blue { color: #58a6ff; background: #0d2039; }
        .tag-gray { color: #8b949e; background: #21262d; }

        a { color: #58a6ff; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .muted { color: #484f58; }
        .mono { font-family: ui-monospace, 'SF Mono', monospace; font-size: 12px; }
        code { background: #21262d; padding: 1px 6px; border-radius: 3px; font-size: 11px; color: #8b949e; }
        .center { text-align: center; }
        .footer { color: #484f58; font-size: 11px; text-align: center; margin-top: 32px; padding-top: 16px; border-top: 1px solid #161b22; }

        @media (max-width: 800px) {
            .row { flex-direction: column; }
            .stat-row { flex-direction: column; }
        }
        """

    # ── Section 1: Funnel + Success Rate ─────────────────────────────────

    def _section_funnel(self, agent_issues: List[Dict], m: Dict) -> str:
        total = m["total_agent"]
        if total == 0:
            return ""

        stages = [
            ("Assigned", total, "#58a6ff"),
            ("Analyzed", m["analyzed"], "#79c0ff"),
            ("PR Created", m["pr_created"], "#d29922"),
            ("Merged", m["merged"], "#3fb950"),
        ]

        # SVG funnel - actual narrowing trapezoid shape
        fw, fh = 320, 220
        funnel_svg = self._svg_funnel(stages, total, fw, fh)

        rate = m["success_rate"]
        chart = self._svg_success_chart(agent_issues)

        return f'''
        <div class="section">
            <div class="section-title">Success Pipeline <span class="count">{m["merged"]}/{total} merged - {rate:.0f}%</span></div>
            <div class="row">
                <div class="card col" style="display:flex;align-items:center;justify-content:center">
                    {funnel_svg}
                </div>
                <div class="card col">
                    <div style="font-size:12px;color:#8b949e;margin-bottom:8px">Success rate over time</div>
                    {chart}
                </div>
            </div>
        </div>'''

    def _svg_funnel(self, stages: list, total: int, w: int, h: int) -> str:
        """Render actual funnel shape - trapezoids narrowing downward."""
        n = len(stages)
        row_h = h / n
        min_w = w * 0.25
        svg = f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">'

        for i, (label, count, color) in enumerate(stages):
            pct = (count / total * 100) if total > 0 else 0
            # Top width and bottom width - narrowing
            top_pct = count / total if total > 0 else 0
            if i == 0:
                top_w = w * 0.92
            else:
                prev_count = stages[i - 1][1]
                top_w = max(min_w, w * 0.92 * (prev_count / total))
            bot_w = max(min_w, w * 0.92 * top_pct)
            if i == 0:
                top_w = w * 0.92

            y = i * row_h
            cx = w / 2
            # Trapezoid points
            x1 = cx - top_w / 2
            x2 = cx + top_w / 2
            x3 = cx + bot_w / 2
            x4 = cx - bot_w / 2
            gap = 2

            svg += f'<polygon points="{x1},{y + gap} {x2},{y + gap} {x3},{y + row_h - gap} {x4},{y + row_h - gap}" fill="{color}" opacity="0.18" stroke="{color}" stroke-width="1" stroke-opacity="0.4"/>'

            # Label
            mid_y = y + row_h / 2
            svg += f'<text x="{cx}" y="{mid_y - 5}" fill="#c9d1d9" font-size="12" font-weight="600" text-anchor="middle">{count}</text>'
            svg += f'<text x="{cx}" y="{mid_y + 10}" fill="#8b949e" font-size="10" text-anchor="middle">{label} ({pct:.0f}%)</text>'

        svg += '</svg>'
        return svg

    def _svg_success_chart(self, agent_issues: List[Dict]) -> str:
        sorted_issues = sorted(agent_issues, key=lambda x: x.get("created_at", ""))
        if not sorted_issues:
            return '<div class="muted center" style="padding:40px">No data yet</div>'

        points = []
        total = merged = 0
        for i in sorted_issues:
            total += 1
            if i["outcome"] == "merged":
                merged += 1
            points.append((total, (merged / total) * 100))

        w, h = 480, 200
        pl, pr_, pt, pb = 36, 8, 8, 24
        cw, ch = w - pl - pr_, h - pt - pb
        mx = max(total, 1)

        def sx(v): return pl + (v / mx) * cw
        def sy(v): return pt + ch - (v / 100) * ch

        grid = ""
        for pct in [0, 25, 50, 75, 100]:
            y = sy(pct)
            grid += f'<line x1="{pl}" y1="{y}" x2="{w - pr_}" y2="{y}" stroke="#21262d" stroke-width="1"/>'
            grid += f'<text x="{pl - 4}" y="{y + 3}" fill="#484f58" font-size="9" text-anchor="end">{pct}%</text>'

        path_d = " ".join(f"{'M' if i == 0 else 'L'}{sx(x):.1f},{sy(y):.1f}" for i, (x, y) in enumerate(points))
        area_d = path_d + f" L{sx(points[-1][0]):.1f},{sy(0):.1f} L{sx(points[0][0]):.1f},{sy(0):.1f} Z"

        cur = points[-1][1]
        color = "#3fb950" if cur >= 50 else "#d29922" if cur >= 30 else "#f85149"

        dots = ""
        show = points[-12:] if len(points) > 12 else points
        for x, y in show:
            dots += f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="2.5" fill="{color}" stroke="#161b22" stroke-width="1"/>'

        return f'''
        <svg width="100%" viewBox="0 0 {w} {h}" style="max-width:{w}px">
            <defs><linearGradient id="sg" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="{color}" stop-opacity="0.15"/>
                <stop offset="100%" stop-color="{color}" stop-opacity="0.0"/>
            </linearGradient></defs>
            {grid}
            <path d="{area_d}" fill="url(#sg)"/>
            <path d="{path_d}" fill="none" stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            {dots}
            <text x="{w // 2}" y="{h - 4}" fill="#484f58" font-size="9" text-anchor="middle">Issue # - current {cur:.0f}%</text>
        </svg>'''

    # ── Section 2: Metrics ───────────────────────────────────────────────

    def _section_metrics(self, m: Dict, avg_tat: int) -> str:
        rate = m["success_rate"]
        rc = "#3fb950" if rate >= 50 else "#d29922" if rate >= 30 else "#f85149"
        tc = "#3fb950" if avg_tat <= 35 else "#d29922" if avg_tat <= 50 else "#f85149" if avg_tat > 0 else "#8b949e"

        def stat(val, label, color="#e6edf3"):
            return f'<div class="stat"><div class="val" style="color:{color}">{val}</div><div class="lbl">{label}</div></div>'

        return f'''
        <div class="section">
            <div class="section-title">Overview</div>
            <div class="stat-row">
                {stat(str(m["total_agent"]), "Total Issues")}
                {stat(str(m["merged"]), "Merged", "#3fb950")}
                {stat(str(m["failed"]), "Failed", "#f85149")}
                {stat(str(m["open_pr"]), "Open PRs", "#d29922")}
                {stat(f'{rate:.0f}%', "Success Rate", rc)}
            </div>
            <div class="stat-row">
                {stat(f'{avg_tat}s' if avg_tat else '-', "Avg TAT", tc)}
                {stat(str(m["total_runs"]), "Agent Runs")}
                {stat(str(m["run_success"]), "Run Success", "#3fb950")}
                {stat(str(m["run_fail"]), "Run Failures", "#f85149")}
            </div>
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
        colors_map = {"Setup": "#58a6ff", "Agent": "#d29922", "Ack": "#bc8cff", "Overhead": "#484f58"}
        for cat in ["Setup", "Agent", "Ack", "Overhead"]:
            if cat in step_totals:
                avg_s = round(step_totals[cat] / n_runs, 1)
                segments.append((cat, avg_s, colors_map.get(cat, "#484f58")))

        pie = self._svg_pie_chart(segments, 140)
        total_seg = sum(s[1] for s in segments)

        legend = ""
        for label, val, color in segments:
            pct = (val / total_seg * 100) if total_seg > 0 else 0
            legend += f'<div style="display:flex;align-items:center;gap:6px;margin:4px 0;font-size:12px"><span style="width:8px;height:8px;border-radius:2px;background:{color};display:inline-block"></span><span style="color:#8b949e">{label}</span><span style="margin-left:auto;color:#c9d1d9">{val:.0f}s ({pct:.0f}%)</span></div>'

        trend = self._svg_tat_chart(run_timings)

        lc = "#3fb950" if latest <= 35 else "#d29922" if latest <= 50 else "#f85149"
        ac = "#3fb950" if avg <= 35 else "#d29922" if avg <= 50 else "#f85149"

        return f'''
        <div class="section">
            <div class="section-title">Turnaround Time <span class="count">last {len(run_timings)} runs</span></div>
            <div class="row">
                <div class="card col">
                    <div style="display:flex;align-items:center;gap:20px">
                        <div style="flex-shrink:0">{pie}</div>
                        <div style="flex:1">
                            <div style="font-size:12px;color:#8b949e;margin-bottom:8px">Avg breakdown per run</div>
                            {legend}
                            <div style="margin-top:10px;padding-top:10px;border-top:1px solid #21262d;font-size:12px">
                                <div style="display:flex;justify-content:space-between;margin:2px 0"><span style="color:#8b949e">Latest</span><span style="color:{lc}">{latest}s</span></div>
                                <div style="display:flex;justify-content:space-between;margin:2px 0"><span style="color:#8b949e">Average</span><span style="color:{ac}">{avg}s</span></div>
                                <div style="display:flex;justify-content:space-between;margin:2px 0"><span style="color:#8b949e">Best / Worst</span><span style="color:#8b949e">{best}s / {worst}s</span></div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="card col">
                    <div style="font-size:12px;color:#8b949e;margin-bottom:8px">TAT trend</div>
                    {trend}
                </div>
            </div>
        </div>'''

    def _svg_pie_chart(self, segments: list, size: int = 140) -> str:
        total = sum(v for _, v, _ in segments)
        if total == 0:
            return ""
        cx, cy = size / 2, size / 2
        ro = size / 2 - 4
        ri = ro * 0.58

        paths = ""
        start = -90
        for _, value, color in segments:
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
            paths += f'<path d="{d}" fill="{color}" opacity="0.8" stroke="#161b22" stroke-width="2"/>'
            start = end

        avg_t = int(total)
        center = f'''
            <text x="{cx}" y="{cy - 4}" fill="#e6edf3" font-size="16" font-weight="700" text-anchor="middle">{avg_t}s</text>
            <text x="{cx}" y="{cy + 10}" fill="#484f58" font-size="9" text-anchor="middle">avg</text>'''

        return f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">{paths}{center}</svg>'

    def _svg_tat_chart(self, run_timings: List[Dict]) -> str:
        timings = list(reversed(run_timings))
        points = [(i + 1, t.get("duration_s", 0)) for i, t in enumerate(timings) if t.get("duration_s", 0) > 0]
        if not points:
            return '<div class="muted center" style="padding:40px">No data</div>'

        w, h = 480, 190
        pl, pr_, pt, pb = 40, 8, 8, 24
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
            grid += f'<text x="{pl - 4}" y="{y + 3}" fill="#484f58" font-size="9" text-anchor="end">{s}s</text>'

        if my >= 55:
            y60 = sy(60)
            grid += f'<line x1="{pl}" y1="{y60}" x2="{w - pr_}" y2="{y60}" stroke="#f85149" stroke-width="1" stroke-dasharray="4,4" opacity="0.4"/>'
            grid += f'<text x="{w - pr_}" y="{y60 - 4}" fill="#f85149" font-size="8" text-anchor="end" opacity="0.6">60s</text>'

        if my >= 28:
            y32 = sy(32)
            grid += f'<line x1="{pl}" y1="{y32}" x2="{w - pr_}" y2="{y32}" stroke="#3fb950" stroke-width="1" stroke-dasharray="4,4" opacity="0.3"/>'
            grid += f'<text x="{w - pr_}" y="{y32 - 4}" fill="#3fb950" font-size="8" text-anchor="end" opacity="0.5">32s</text>'

        path_d = " ".join(f"{'M' if i == 0 else 'L'}{sx(x):.1f},{sy(y):.1f}" for i, (x, y) in enumerate(points))
        area_d = path_d + f" L{sx(points[-1][0]):.1f},{sy(0):.1f} L{sx(points[0][0]):.1f},{sy(0):.1f} Z"

        latest = points[-1][1]
        color = "#3fb950" if latest <= 35 else "#d29922" if latest <= 50 else "#f85149"

        dots = ""
        for x, y in points:
            dc = "#3fb950" if y <= 35 else "#d29922" if y <= 50 else "#f85149"
            dots += f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="3" fill="{dc}" stroke="#161b22" stroke-width="1"/>'

        return f'''
        <svg width="100%" viewBox="0 0 {w} {h}" style="max-width:{w}px">
            <defs><linearGradient id="tg" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="{color}" stop-opacity="0.12"/>
                <stop offset="100%" stop-color="{color}" stop-opacity="0.0"/>
            </linearGradient></defs>
            {grid}
            <path d="{area_d}" fill="url(#tg)"/>
            <path d="{path_d}" fill="none" stroke="{color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            {dots}
            <text x="{w // 2}" y="{h - 4}" fill="#484f58" font-size="9" text-anchor="middle">Runs (chronological) - latest {latest}s</text>
        </svg>'''

    # ── Section 4: Recent Issues ─────────────────────────────────────────

    def _section_issues(self, agent_issues: List[Dict]) -> str:
        recent = sorted(agent_issues, key=lambda x: x["number"], reverse=True)[:30]
        if not recent:
            return ""

        rows = ""
        for issue in recent:
            n = issue["number"]
            title = self._esc(issue["title"][:60])
            url = issue.get("html_url", f"https://github.com/{REPO}/issues/{n}")

            # Type
            t = issue.get("title", "").lower()
            if t.startswith("[fix]") or "fix:" in t[:15]:
                tp = '<span class="tag tag-blue">Fix</span>'
            elif t.startswith("[bug]") or "bug" in t[:15]:
                tp = '<span class="tag tag-red">Bug</span>'
            elif t.startswith("[feature]") or "feature" in t[:15]:
                tp = '<span class="tag tag-amber">Feature</span>'
            else:
                tp = '<span class="tag tag-gray">Other</span>'

            # Template
            template = '<span class="muted">-</span>'
            pr = issue.get("linked_pr")
            if pr:
                body = (pr.get("body") or "").lower()
                for tpl in ["typo_fix", "wrong_value", "wrong_name", "swapped_args"]:
                    if tpl in body:
                        template = f'<code>{tpl}</code>'
                        break

            # Pipeline checkmarks
            outcome = issue.get("outcome", "not_triggered")
            cc = issue.get("comment_count", 0)
            classify_ok = cc >= 1
            fix_ok = pr is not None
            test_ok = pr is not None

            def check(ok, pending=False):
                if ok:
                    return '<span style="color:#3fb950">Y</span>'
                if pending:
                    return '<span class="muted">-</span>'
                return '<span style="color:#f85149">N</span>'

            pr_cell = '<span class="muted">-</span>'
            if pr:
                pn = pr["number"]
                pu = pr.get("html_url", f"https://github.com/{REPO}/pull/{pn}")
                pr_cell = f'<a href="{pu}" target="_blank">#{pn}</a>'

            # Result with reason for closed
            if outcome == "merged":
                result = '<span class="tag tag-green">Merged</span>'
            elif outcome == "closed":
                reason = self._close_reason(issue)
                result = f'<span class="tag tag-red">Closed</span>'
                if reason:
                    result += f' <span class="muted" style="font-size:11px">{self._esc(reason)}</span>'
            elif outcome == "failed":
                reason = self._fail_reason(issue)
                result = f'<span class="tag tag-red">Failed</span>'
                if reason:
                    result += f' <span class="muted" style="font-size:11px">{self._esc(reason)}</span>'
            elif outcome == "open_pr":
                result = '<span class="tag tag-amber">Open</span>'
            else:
                result = '<span class="muted">-</span>'

            created = _fmt_date(issue.get("created_at", ""))

            rows += f'''
            <tr>
                <td><a href="{url}" target="_blank">#{n}</a></td>
                <td style="max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{title}</td>
                <td>{tp}</td>
                <td>{template}</td>
                <td class="center">{check(classify_ok, not classify_ok and outcome == "not_triggered")}</td>
                <td class="center">{check(fix_ok, not classify_ok)}</td>
                <td class="center">{check(test_ok, not classify_ok)}</td>
                <td>{pr_cell}</td>
                <td>{result}</td>
                <td style="font-size:11px">{created}</td>
            </tr>'''

        return f'''
        <div class="section">
            <div class="section-title">Recent Issues <span class="count">{len(recent)}</span></div>
            <div class="card" style="overflow-x:auto">
                <table>
                    <tr>
                        <th>#</th><th>Title</th><th>Type</th><th>Template</th>
                        <th class="center">Classify</th><th class="center">Fix</th><th class="center">Test</th>
                        <th>PR</th><th>Result</th><th>Date</th>
                    </tr>
                    {rows}
                </table>
            </div>
        </div>'''

    def _close_reason(self, issue: Dict) -> str:
        """Extract a short reason for why a PR was closed."""
        msg = issue.get("failure_msg", "")
        if not msg:
            return ""
        if "IndentationError" in msg:
            return "indentation"
        if "Debate could not approve" in msg:
            return "debate rejected"
        if "Tests failed" in msg:
            return "tests failed"
        if "SyntaxError" in msg:
            return "syntax error"
        return ""

    def _fail_reason(self, issue: Dict) -> str:
        """Extract a short reason for pipeline failure."""
        msg = issue.get("failure_msg", "")
        if not msg:
            return ""
        if "IndentationError" in msg:
            return "indentation"
        if "AttributeError" in msg:
            return "attribute error"
        if "OperationalError" in msg or "SQL" in msg.lower():
            return "sql error"
        if "SyntaxError" in msg:
            return "syntax error"
        if "Tests failed" in msg:
            return "tests failed"
        if "Debate" in msg:
            return "debate rejected"
        # Trim to short snippet
        clean = msg.replace("\n", " ").strip()[:40]
        return clean if clean else ""

    # ── Section 5: Pull Requests ─────────────────────────────────────────

    def _section_prs(self, prs: List[Dict]) -> str:
        recent = sorted(prs, key=lambda x: x["number"], reverse=True)[:30]
        if not recent:
            return ""

        rows = ""
        for pr in recent:
            n = pr["number"]
            title = self._esc(pr["title"][:55])
            url = pr.get("html_url", f"https://github.com/{REPO}/pull/{n}")
            branch = self._esc(pr.get("head", ""))
            merged = pr.get("merged_at")
            state = "merged" if merged else pr["state"]

            # Linked issue
            body = pr.get("body") or ""
            issue_link = '<span class="muted">-</span>'
            match = re.search(r'#(\d+)', body)
            if not match:
                bm = re.search(r'issue-(\d+)', branch)
                if bm:
                    issue_link = f'<a href="https://github.com/{REPO}/issues/{bm.group(1)}" target="_blank">#{bm.group(1)}</a>'
            else:
                issue_link = f'<a href="https://github.com/{REPO}/issues/{match.group(1)}" target="_blank">#{match.group(1)}</a>'

            state_map = {
                "merged": ("tag-green", "Merged"),
                "closed": ("tag-red", "Closed"),
                "open": ("tag-green", "Open"),
            }
            sc, sl = state_map.get(state, ("tag-gray", state))

            created = _fmt_date(pr.get("merged_at") or pr.get("created_at", ""))

            rows += f'''
            <tr>
                <td><a href="{url}" target="_blank">#{n}</a></td>
                <td style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{title}</td>
                <td>{issue_link}</td>
                <td><code>{branch}</code></td>
                <td><span class="tag {sc}">{sl}</span></td>
                <td style="font-size:11px">{created}</td>
            </tr>'''

        return f'''
        <div class="section">
            <div class="section-title">Pull Requests <span class="count">{len(recent)}</span></div>
            <div class="card" style="overflow-x:auto">
                <table>
                    <tr><th>PR</th><th>Title</th><th>Issue</th><th>Branch</th><th>Status</th><th>Date</th></tr>
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

        # Expand "Other" if <10 items: list each individually
        expanded = {}
        for pattern, items in patterns.items():
            if pattern == "_other_" and len(items) < 10:
                for item in items:
                    msg = item.get("failure_msg", "")
                    short = msg.replace("\n", " ").strip()[:60] or "Unknown"
                    key = f"#{item['number']}: {short}"
                    expanded[key] = [item]
            else:
                label = pattern if pattern != "_other_" else "Other"
                expanded[label] = items

        # Description map
        desc_map = {
            "IndentationError": "LLM generated code with wrong indentation level",
            "SQL / Variable Error": "Referenced undefined variable or SQL schema mismatch",
            "AttributeError": "Accessed attribute that does not exist on object",
            "SyntaxError": "Generated code with invalid Python syntax",
            "Test Failure": "Fix broke existing tests or new tests failed",
            "Debate Rejection": "Multi-agent debate could not reach consensus to approve",
            "Other": "Miscellaneous failures not matching known patterns",
        }

        # Pie chart segments
        pie_segments = []
        pie_colors = ["#f85149", "#d29922", "#58a6ff", "#bc8cff", "#8b949e", "#484f58", "#3fb950"]
        ci = 0
        for pattern, items in sorted(expanded.items(), key=lambda x: -len(x[1])):
            if pattern.startswith("#"):
                continue
            color = pie_colors[ci % len(pie_colors)]
            pie_segments.append((pattern, len(items), color))
            ci += 1

        pie = self._svg_pie_chart_simple(pie_segments, 120) if pie_segments else ""

        rows = ""
        for pattern, items in sorted(expanded.items(), key=lambda x: -len(x[1])):
            count = len(items)
            pct = (count / total_f * 100) if total_f > 0 else 0
            nums = [i["number"] for i in items]
            links = ", ".join(f'<a href="https://github.com/{REPO}/issues/{n}" target="_blank">#{n}</a>' for n in nums[:10])
            if len(nums) > 10:
                links += f' <span class="muted">+{len(nums) - 10}</span>'

            desc = desc_map.get(pattern, "")
            if pattern.startswith("#"):
                desc = ""

            rows += f'''
            <tr>
                <td style="white-space:nowrap">{self._esc(pattern)}</td>
                <td style="font-size:12px;color:#8b949e">{desc}</td>
                <td style="color:#f85149">{count}</td>
                <td class="muted">{pct:.0f}%</td>
                <td style="font-size:11px">{links}</td>
            </tr>'''

        return f'''
        <div class="section">
            <div class="section-title">Failure Diagnostics <span class="count">{total_f}</span></div>
            <div class="row">
                {"<div class='card' style='flex:0 0 140px;display:flex;align-items:center;justify-content:center'>" + pie + "</div>" if pie else ""}
                <div class="card col" style="overflow-x:auto">
                    <table>
                        <tr><th>Pattern</th><th>Description</th><th>Count</th><th>%</th><th>Issues</th></tr>
                        {rows}
                    </table>
                </div>
            </div>
        </div>'''

    def _svg_pie_chart_simple(self, segments: list, size: int = 120) -> str:
        """Simple pie chart (not donut) for failure distribution."""
        total = sum(v for _, v, _ in segments)
        if total == 0:
            return ""
        cx, cy = size / 2, size / 2
        r = size / 2 - 4

        paths = ""
        start = -90
        for _, value, color in segments:
            if value == 0:
                continue
            sweep = (value / total) * 360
            end = start + sweep
            sa, ea = math.radians(start), math.radians(end)

            x1, y1 = cx + r * math.cos(sa), cy + r * math.sin(sa)
            x2, y2 = cx + r * math.cos(ea), cy + r * math.sin(ea)

            large = 1 if sweep > 180 else 0
            d = f"M{cx},{cy} L{x1:.1f},{y1:.1f} A{r:.1f},{r:.1f} 0 {large} 1 {x2:.1f},{y2:.1f} Z"
            paths += f'<path d="{d}" fill="{color}" opacity="0.7" stroke="#161b22" stroke-width="1.5"/>'
            start = end

        return f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">{paths}</svg>'

    # ── Section 7: Agent Runs ────────────────────────────────────────────

    def _section_runs(self, agent_runs: List[Dict]) -> str:
        recent = sorted(agent_runs, key=lambda x: x.get("created_at", ""), reverse=True)[:30]
        if not recent:
            return ""

        rows = ""
        for run in recent:
            rid = run["id"]
            url = run.get("html_url", f"https://github.com/{REPO}/actions/runs/{rid}")
            title = self._esc(run.get("display_title", "")[:45])
            event = run.get("event", "")
            conclusion = run.get("conclusion") or "running"
            dur = run.get("duration_s", 0)

            c_map = {
                "success": ("tag-green", "Success"),
                "failure": ("tag-red", "Failure"),
                "skipped": ("tag-gray", "Skipped"),
                "running": ("tag-blue", "Running"),
            }
            cc, cl = c_map.get(conclusion, ("tag-gray", conclusion))

            dur_str = f"{dur}s" if dur > 0 else "-"
            dc = "#3fb950" if 0 < dur <= 35 else "#d29922" if dur <= 50 else "#f85149" if dur > 50 else "#484f58"

            created = _fmt_date(run.get("created_at", ""))

            rows += f'''
            <tr>
                <td><a href="{url}" target="_blank" class="mono">{rid}</a></td>
                <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{title}</td>
                <td><span class="tag tag-gray">{event}</span></td>
                <td><span class="tag {cc}">{cl}</span></td>
                <td class="mono" style="color:{dc}">{dur_str}</td>
                <td style="font-size:11px">{created}</td>
            </tr>'''

        return f'''
        <div class="section">
            <div class="section-title">Agent Runs <span class="count">{len(recent)}</span></div>
            <div class="card" style="overflow-x:auto">
                <table>
                    <tr><th>Run</th><th>Title</th><th>Trigger</th><th>Result</th><th>Duration</th><th>Date</th></tr>
                    {rows}
                </table>
            </div>
        </div>'''

    # ── Main Render ──────────────────────────────────────────────────────

    def render(self) -> str:
        m = self._metrics()
        agent_issues = self._data["agent_issues"]
        prs = self._data["prs"]
        run_timings = self._data.get("run_timings", [])

        tat_durations = [t.get("duration_s", 0) for t in run_timings if t.get("duration_s", 0) > 0]
        avg_tat = int(sum(tat_durations) / len(tat_durations)) if tat_durations else 0

        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GlassBox Agent - Performance Tracker</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>💎</text></svg>">
    <style>{self._css()}</style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>GlassBox Agent <span class="ver">v1.0</span></h1>
            <div class="subtitle">Performance Tracker - <a href="https://github.com/{REPO}" target="_blank">{REPO}</a></div>
        </div>

        {self._section_funnel(agent_issues, m)}
        {self._section_metrics(m, avg_tat)}
        {self._section_tat(run_timings)}
        {self._section_issues(agent_issues)}
        {self._section_prs(prs)}
        {self._section_failures(m)}
        {self._section_runs(m["agent_runs"])}

        <div class="footer">Last updated {self._now}</div>
    </div>
</body>
</html>'''
