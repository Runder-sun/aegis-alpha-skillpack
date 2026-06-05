from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
import urllib.request
import urllib.error


def _load_pipelines(workspace: Path) -> dict:
    pipeline_path = workspace / "skills" / "pipeline-runner" / "data" / "pipelines.json"
    if not pipeline_path.exists():
        raise FileNotFoundError(f"pipelines.json not found: {pipeline_path}")
    return json.loads(pipeline_path.read_text(encoding="utf-8"))


def _run_cmd(cmd: list[str]) -> dict:
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    raw = (proc.stdout or "").strip()
    try:
        parsed = json.loads(raw) if raw else None
    except Exception:
        parsed = None
        if raw:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                snippet = raw[start:end + 1]
                try:
                    parsed = json.loads(snippet)
                except Exception:
                    parsed = None
    return {
        "ok": proc.returncode == 0,
        "code": proc.returncode,
        "raw": raw,
        "json": parsed,
        "cmd": cmd,
    }


def _http_get(url: str, timeout: int = 15):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return None, str(e)


def _resolve_hhxg_command(package_dir: Path, command: str, payload: dict | None = None) -> list[str] | None:
    payload = payload or {}
    command_map: dict[str, tuple[str, list[str]]] = {
        "snapshot-full": ("fetch_snapshot.py", []),
        "snapshot-market": ("fetch_snapshot.py", ["market"]),
        "snapshot-themes": ("fetch_snapshot.py", ["themes"]),
        "snapshot-ladder": ("fetch_snapshot.py", ["ladder"]),
        "snapshot-hotmoney": ("fetch_snapshot.py", ["hotmoney"]),
        "snapshot-sectors": ("fetch_snapshot.py", ["sectors"]),
        "snapshot-news": ("fetch_snapshot.py", ["news"]),
        "snapshot-summary": ("fetch_snapshot.py", ["summary"]),
        "calendar-week": ("calendar_hhxg.py", ["week"]),
        "calendar-trading": ("calendar_hhxg.py", ["trading"]),
        "calendar-unlock": ("calendar_hhxg.py", ["unlock"]),
        "calendar-earnings": ("calendar_hhxg.py", ["earnings"]),
        "calendar-delivery": ("calendar_hhxg.py", ["delivery"]),
        "margin-full": ("margin.py", []),
        "margin-overview": ("margin.py", ["overview"]),
        "margin-top": ("margin.py", ["top"]),
    }
    resolved = command_map.get(command)
    if not resolved:
        return None
    script, args = resolved
    if command == "calendar-trading":
        date = str(payload.get("date", "")).strip()
        if date:
            args = [*args, date]
    elif command in {"calendar-unlock", "calendar-earnings"}:
        month = str(payload.get("month", "")).strip()
        if month:
            args = [*args, month]
    script_path = package_dir / "scripts" / script
    if not script_path.exists():
        return None
    return ["python3", str(script_path), *args, "--json"]


def _resolve_dispatch_command(package_dir: Path, command: str, payload: dict | None) -> list[str] | None:
    dispatch = package_dir / "scripts" / "dispatch.py"
    if not dispatch.exists():
        return None
    return [
        "python3",
        str(dispatch),
        "--command",
        command,
        "--payload",
        json.dumps(payload or {}, ensure_ascii=False),
    ]


def _should_skip_step(step: dict, allow_push: bool, skip_packages: set[str], skip_commands: set[str]) -> bool:
    cmd = str(step.get("command", ""))
    if ("push" in cmd or cmd.endswith("-push")) and not allow_push:
        return True
    if str(step.get("package", "")) in skip_packages:
        return True
    if cmd in skip_commands:
        return True
    return False


def _pick_latest(records):
    if not records:
        return None
    return records[-1]


def _nightly_prewarm_unavailable(results: list[dict]) -> bool:
    for result in results:
        if result.get("command") != "nightly-prewarm":
            continue
        return bool(result.get("skipped")) or result.get("ok") is False
    return False


def _extract_step_output(results: list[dict], package: str, command: str):
    for r in results:
        if r.get("package") == package and r.get("command") == command:
            return r.get("output")
    return None


def _extract_strategy_report(results: list[dict]) -> tuple[str | None, str | None]:
    strategy = _extract_step_output(results, "advice-lifecycle", "nightly-strategy")
    if not isinstance(strategy, dict):
        return None, None
    title = None
    content = None
    result = strategy.get("result")
    if isinstance(result, dict):
        title = result.get("title")
        content = result.get("report")
    if content is None and isinstance(result, str):
        content = result
    if content is None and isinstance(strategy.get("output"), str):
        content = strategy.get("output")
    if content is None and isinstance(strategy.get("text"), str):
        content = strategy.get("text")
    return content, title


def _render_nightly_report(results: list[dict]) -> str:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# 🌙 晚间策略预汇总 ({now_str})", ""]

    # hhxg snapshot
    snapshot = _extract_step_output(results, "market-data", "snapshot-full")
    if isinstance(snapshot, dict):
        summary = snapshot.get("ai_summary") or snapshot.get("summary") or ""
        if isinstance(summary, dict):
            summary = (
                f"{summary.get('market_state', '')}；"
                f"{summary.get('focus_direction', '')}；"
                f"{summary.get('theme_focus', '')}；"
                f"{summary.get('hotmoney_state', '')}；"
                f"{summary.get('news_highlight', '')}"
            ).strip("；")
        date = snapshot.get("date") or snapshot.get("trading_date") or ""
        lines.append("## 1. 盘后快照")
        if date:
            lines.append(f"- 数据日期: {date}")
        if summary:
            lines.append(f"- 一句话总结: {summary}")
        else:
            lines.append("- 一句话总结: (缺失)")
        lines.append("")

    # themesurfer signal
    ts = _extract_step_output(results, "themesurfer-signal", "signal")
    if isinstance(ts, dict):
        data = ts.get("data") if isinstance(ts.get("data"), dict) else ts.get("data", ts)
        status = data.get("status")
        close = data.get("close")
        ma20 = data.get("ma20")
        symbol = data.get("symbol")
        lines.append("## 2. 市场过滤器 (MA20)")
        lines.append(f"- 标的: {symbol}")
        lines.append(f"- 状态: {status}")
        lines.append(f"- 收盘: {close} | MA20: {ma20}")
        lines.append("")

    # akshare macro
    pmi = _extract_step_output(results, "market-data", "macro-pmi")
    cpi = _extract_step_output(results, "market-data", "macro-cpi")
    ppi = _extract_step_output(results, "market-data", "macro-ppi")
    if isinstance(pmi, dict) or isinstance(cpi, dict) or isinstance(ppi, dict):
        lines.append("## 3. 宏观指标")
        if isinstance(pmi, dict):
            data = pmi.get("data") if isinstance(pmi.get("data"), dict) else pmi
            latest = data.get("latest") if isinstance(data, dict) else None
            if latest is None:
                records = data.get("records", []) if isinstance(data, dict) else []
                latest = _pick_latest(records)
            lines.append(f"- PMI: {latest}" if latest else "- PMI: 无数据")
        if isinstance(cpi, dict):
            data = cpi.get("data") if isinstance(cpi.get("data"), dict) else cpi
            latest = data.get("latest") if isinstance(data, dict) else None
            if latest is None:
                records = data.get("records", []) if isinstance(data, dict) else []
                latest = _pick_latest(records)
            lines.append(f"- CPI: {latest}" if latest else "- CPI: 无数据")
        if isinstance(ppi, dict):
            data = ppi.get("data") if isinstance(ppi.get("data"), dict) else ppi
            latest = data.get("latest") if isinstance(data, dict) else None
            if latest is None:
                records = data.get("records", []) if isinstance(data, dict) else []
                latest = _pick_latest(records)
            lines.append(f"- PPI: {latest}" if latest else "- PPI: 无数据")
        lines.append("")

    # baostock index daily
    idx = _extract_step_output(results, "market-data", "index-daily")
    idx_items = None
    if isinstance(idx, dict):
        data = idx.get("data") if isinstance(idx.get("data"), dict) else idx
        idx_items = data.get("items") if isinstance(data, dict) else None
    if isinstance(idx, list):
        idx_items = idx
    if isinstance(idx_items, list):
        latest = _pick_latest(idx_items)
        lines.append("## 4. 指数快照")
        lines.append(f"- 上证指数: {latest}" if latest else "- 上证指数: 无数据")
        lines.append("")

    # nightly strategy output (from advice-lifecycle)
    strategy = _extract_step_output(results, "advice-lifecycle", "nightly-strategy")
    if isinstance(strategy, dict):
        content = strategy.get("result") or strategy.get("output") or strategy.get("text")
        if content:
            lines.append("## 5. 晚间策略核心输出")
            lines.append(str(content))
            lines.append("")

    # step status summary
    lines.append("## 6. 管线执行情况")
    for r in results:
        status = "OK" if r.get("ok", False) else ("SKIP" if r.get("skipped") else "FAIL")
        lines.append(f"- {r.get('package')}::{r.get('command')}: {status}")

    lines.append("")
    lines.append("> 说明: 该报告为自动预汇总，核心策略请以最终策略模板为准。")
    return "\n".join(lines)


def _write_report(workspace: Path, pipeline_id: str, content: str) -> str:
    out_dir = workspace / "memory" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = out_dir / f"{pipeline_id}-report-{stamp}.md"
    out_path.write_text(content, encoding="utf-8")
    return str(out_path)


def _write_context(workspace: Path, pipeline_id: str, results: list[dict]) -> str:
    out_dir = workspace / "memory" / "pipeline_context"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = out_dir / f"{pipeline_id}-context-{stamp}.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(out_path)


def run_pipeline(pipeline_id: str, allow_push: bool, dry_run: bool, max_fail: int, skip_packages: set[str], skip_commands: set[str]) -> dict:
    workspace = Path(os.environ.get("AEGIS_ALPHA_WORKSPACE") or os.path.expanduser("~/.aegis-alpha/workspace"))
    pipelines = _load_pipelines(workspace).get("pipelines", [])
    index = {p.get("id"): p for p in pipelines if isinstance(p, dict)}
    if pipeline_id not in index:
        raise ValueError(f"unknown pipeline_id: {pipeline_id}")

    pipeline = index[pipeline_id]
    steps = pipeline.get("steps", [])
    results = []
    fail_count = 0

    report_path: str | None = None

    for step in steps:
        package = step.get("package")
        command = step.get("command")
        optional = bool(step.get("optional"))
        payload = step.get("payload")

        if _should_skip_step(step, allow_push, skip_packages, skip_commands):
            reason = "push_disabled" if ("push" in str(command) or str(command).endswith("-push")) and not allow_push else "requested_skip"
            results.append({"package": package, "command": command, "skipped": True, "reason": reason})
            continue

        if (
            pipeline_id == "nightly"
            and str(package) == "quant-validation"
            and str(command) == "nightly-eval-12m"
            and _nightly_prewarm_unavailable(results)
        ):
            results.append({"package": package, "command": command, "skipped": True, "reason": "prewarm_unavailable"})
            continue

        if dry_run:
            results.append({"package": package, "command": command, "skipped": True, "reason": "dry_run"})
            continue

        package_dir = workspace / "skills" / str(package)
        if not package_dir.exists():
            results.append({"package": package, "command": command, "ok": False, "error": "package_not_found", "optional": optional})
            if not optional:
                fail_count += 1
            if fail_count > max_fail:
                break
            continue

        # generate nightly report before push (based on current results)
        if allow_push and not report_path and pipeline_id == "nightly" and str(command).endswith("push"):
            strategy_report, strategy_title = _extract_strategy_report(results)
            if strategy_report:
                report_content = strategy_report
                report_title = strategy_title or "🌙 晚间策略报告"
            else:
                report_content = _render_nightly_report(results)
                report_title = "🌙 晚间策略预汇总"
            report_path = _write_report(workspace, pipeline_id, report_content)
            payload = dict(payload or {})
            payload["report_path"] = report_path
            payload["report_title"] = report_title

        if str(package) == "advice-lifecycle" and str(command) == "nightly-strategy":
            payload = dict(payload or {})
            payload["context_path"] = _write_context(workspace, pipeline_id, results)

        cmd = _resolve_hhxg_command(package_dir, str(command), payload)
        if cmd is None:
            cmd = _resolve_dispatch_command(package_dir, str(command), payload)

        if cmd is None:
            results.append({"package": package, "command": command, "ok": False, "error": "no_dispatch", "optional": optional})
            if not optional:
                fail_count += 1
            if fail_count > max_fail:
                break
            continue

        res = _run_cmd(cmd)
        results.append({
            "package": package,
            "command": command,
            "ok": res["ok"],
            "optional": optional,
            "output": res["json"] if res["json"] is not None else res["raw"],
            "code": res["code"],
        })
        if not res["ok"] and not optional:
            fail_count += 1
            if fail_count > max_fail:
                break

    return {
        "pipeline_id": pipeline_id,
        "allow_push": allow_push,
        "dry_run": dry_run,
        "failed": fail_count,
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--payload", default="{}")
    args = parser.parse_args()

    payload = json.loads(args.payload or "{}")
    command = args.command

    if command not in {"pipeline-run", "pipeline-dry-run"}:
        raise SystemExit(f"unknown command: {command}")

    pipeline_id = payload.get("pipeline_id")
    if not pipeline_id:
        raise SystemExit("missing pipeline_id")

    allow_push = bool(payload.get("allow_push", False))
    dry_run = bool(payload.get("dry_run", False) or command == "pipeline-dry-run")
    max_fail = int(payload.get("max_fail", 0) or 0)
    skip_packages = set(payload.get("skip_packages") or [])
    skip_commands = set(payload.get("skip_commands") or [])

    start = time.time()
    result = run_pipeline(pipeline_id, allow_push, dry_run, max_fail, skip_packages, skip_commands)
    duration = time.time() - start

    workspace = Path(os.environ.get("AEGIS_ALPHA_WORKSPACE") or os.path.expanduser("~/.aegis-alpha/workspace"))
    out_dir = workspace / "memory" / "pipeline_runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = out_dir / f"{pipeline_id}-{stamp}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "package": "pipeline-orchestrator",
        "command": command,
        "payload": payload,
        "duration_sec": round(duration, 2),
        "saved_to": str(out_path),
        "result": result,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
