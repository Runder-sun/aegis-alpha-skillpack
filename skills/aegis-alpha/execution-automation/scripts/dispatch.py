from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


PREWARM_COMMANDS = {
    "nightly-prewarm": "nightly",
    "morning-prewarm": "morning",
    "midday-prewarm": "midday",
    "evening-prewarm": "evening",
    "weekly-prewarm": "weekly",
}

PUSH_COMMANDS = {"nightly-push", "morning-push", "intraday-push", "weekly-push"}


def _now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _workspace_dir() -> Path:
    raw = os.environ.get("AEGIS_ALPHA_WORKSPACE")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".aegis-alpha" / "workspace"


def _load_env() -> None:
    for env_path in (_workspace_dir() / ".env", Path(__file__).resolve().parents[1] / ".env"):
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or "=" not in raw:
                continue
            key, value = raw.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def _http_request(url: str, headers: dict | None = None, body: dict | None = None, timeout: int = 15):
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url=url, data=data, method="POST" if data is not None else "GET")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    if data is not None and "Content-Type" not in req.headers:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return None, str(exc)


def _feishu_tenant_token(app_id: str, app_secret: str):
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
    status, content = _http_request(url, body={"app_id": app_id, "app_secret": app_secret})
    if status != 200 or '"code":0' not in content:
        return None
    try:
        payload = json.loads(content)
    except Exception:
        return None
    return payload.get("tenant_access_token")


def _send_feishu_cards(report_text: str, title: str, push_type: str, date_str: str = "") -> dict:
    from feishu_cards import build_push_card, build_report_cards

    app_id = os.environ.get("FEISHU_APP_ID") or ""
    app_secret = os.environ.get("FEISHU_APP_SECRET") or ""
    receive_id = os.environ.get("FEISHU_RECEIVE_ID") or ""
    chat_id = os.environ.get("FEISHU_CHAT_ID") or ""
    if not (app_id and app_secret and (receive_id or chat_id)):
        return {"mode": "app", "status": "missing_config"}

    token = _feishu_tenant_token(app_id, app_secret)
    if not token:
        return {"mode": "app", "status": "auth_failed"}

    targets = []
    if chat_id:
        targets.append(("chat_id", chat_id))
    elif receive_id:
        targets.append(("open_id", receive_id))

    if "### Section" in report_text:
        cards = build_report_cards(report_text, date_str=date_str, include_dashboard=True)
    else:
        cards = [build_push_card(report_text, push_type=push_type, title=title, date_str=date_str)]

    sent = 0
    for receive_id_type, target in targets:
        for card in cards:
            status, content = _http_request(
                f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}",
                headers={"Authorization": f"Bearer {token}"},
                body={
                    "receive_id": target,
                    "msg_type": "interactive",
                    "content": json.dumps(card, ensure_ascii=False),
                },
            )
            if status == 200 and '"code":0' in content:
                sent += 1
            time.sleep(0.3)
    return {"mode": "app", "status": 200, "sent": sent, "cards": len(cards)}


def _send_feishu(text: str, title: str = "报告推送") -> dict:
    app_id = os.environ.get("FEISHU_APP_ID") or ""
    app_secret = os.environ.get("FEISHU_APP_SECRET") or ""
    receive_id = os.environ.get("FEISHU_RECEIVE_ID") or ""
    chat_id = os.environ.get("FEISHU_CHAT_ID") or ""

    if len(text) > 3500:
        text = text[:3500] + "\n...(truncated)"

    if app_id and app_secret and (receive_id or chat_id):
        token = _feishu_tenant_token(app_id, app_secret)
        if not token:
            return {"mode": "app", "status": "auth_failed"}
        target = chat_id or receive_id
        receive_id_type = "chat_id" if chat_id else "open_id"
        status, content = _http_request(
            f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}",
            headers={"Authorization": f"Bearer {token}"},
            body={
                "receive_id": target,
                "msg_type": "text",
                "content": json.dumps({"text": f"{title}\n\n{text}"}),
            },
        )
        return {"mode": "app", "status": status, "response": content[:200]}

    return {"mode": "none", "status": "missing_config"}


def load_manifest(base: Path) -> dict:
    path = base / "data" / "command-manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _base_output(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    as_of = _now()
    return {
        "package": "execution-automation",
        "command": command,
        "payload": payload,
        "as_of": as_of,
        "freshness": {
            "status": "current",
            "as_of": as_of,
            "policy": "automation status is current at command runtime; market data freshness is inherited from prewarm artifacts",
        },
        "ok": True,
        "decision_allowed": False,
        "requires_human_confirmation": True,
        "max_action_level": "automation_only",
        "source": [],
        "sources": [],
        "artifacts": [],
        "warnings": [],
        "errors": [],
        "missing_critical_inputs": [],
        "result": {},
    }


def _fail(command: str, payload: dict[str, Any], errors: list[str], warnings: list[str] | None = None) -> dict[str, Any]:
    output = _base_output(command, payload)
    output["ok"] = False
    output["freshness"]["status"] = "unavailable"
    output["errors"] = errors
    output["warnings"] = warnings or []
    output["missing_critical_inputs"] = errors
    output["result"] = {
        "note": "Execution automation could not prove required evidence or explicit send authorization.",
        "missing_critical_inputs": errors,
    }
    return output


def _wrap(command: str, payload: dict[str, Any], result: dict[str, Any], artifacts: list[str] | None = None, warnings: list[str] | None = None, sources: list[str] | None = None, freshness_status: str = "current") -> dict[str, Any]:
    output = _base_output(command, payload)
    output["result"] = result
    output["artifacts"] = artifacts or []
    output["warnings"] = warnings or []
    output["source"] = sources or []
    output["sources"] = sources or []
    output["freshness"]["status"] = freshness_status
    gaps = result.get("critical_gaps")
    if isinstance(gaps, list) and gaps:
        output["missing_critical_inputs"] = gaps
        output["warnings"] = sorted(set(output["warnings"] + ["critical_data_gaps_present"]))
        output["freshness"]["status"] = "partial"
    return output


def _parse_json_output(raw: str) -> object:
    try:
        return json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except Exception:
                pass
    return raw


def _latest_prewarm() -> tuple[Path | None, dict[str, Any] | None, str | None]:
    prewarm_dir = _workspace_dir() / "memory" / "prewarm"
    if not prewarm_dir.exists():
        return None, None, "prewarm_directory_missing"
    files = sorted(prewarm_dir.glob("nightly-prewarm-*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not files:
        return None, None, "prewarm_artifact_missing"
    latest = files[0]
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except Exception:
        return latest, None, "prewarm_artifact_invalid_json"
    if not isinstance(payload, dict):
        return latest, None, "prewarm_artifact_invalid_schema"
    return latest, payload, None


def _artifact_age_seconds(path: Path | None) -> float | None:
    if path is None:
        return None
    try:
        return max(0.0, time.time() - path.stat().st_mtime)
    except Exception:
        return None


def _prewarm_gaps(payload: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    market_data = payload.get("market_data") if isinstance(payload.get("market_data"), dict) else dict()
    news = payload.get("news_sentiment") if isinstance(payload.get("news_sentiment"), dict) else dict()
    if not (isinstance(market_data.get("hhxg_snapshot"), dict) or isinstance(payload.get("hhxg_snapshot"), dict)):
        gaps.append("hhxg_snapshot_missing")
    if not (market_data.get("baostock_index_daily") or payload.get("baostock_index_daily")):
        gaps.append("index_daily_missing")
    if not (news.get("hhxg_news") or payload.get("hhxg_news")):
        gaps.append("market_news_missing")
    if not (market_data.get("akshare_macro_pmi") or market_data.get("akshare_macro_pmi_yearly") or payload.get("akshare_macro_pmi") or payload.get("akshare_macro_pmi_yearly")):
        gaps.append("macro_pmi_missing")
    return gaps


def _write_marker(command: str, artifact: str | None, result: dict[str, Any]) -> Path:
    marker_dir = _workspace_dir() / "memory" / "automation"
    marker_dir.mkdir(parents=True, exist_ok=True)
    marker = marker_dir / f"{command}-last.json"
    marker.write_text(json.dumps({
        "command": command,
        "updated_at": _now(),
        "artifact": artifact,
        "result": result,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return marker


def _run_prewarm(command: str, payload: dict[str, Any], package_root: Path) -> dict[str, Any]:
    phase = PREWARM_COMMANDS[command]
    if payload.get("dry_run"):
        result = {
            "phase": phase,
            "dry_run": True,
            "planned_script": str(package_root / "scripts" / "nightly_prewarm.py"),
            "artifact_written": False,
        }
        return _wrap(command, payload, result, freshness_status="not_run")

    script = package_root / "scripts" / "nightly_prewarm.py"
    if not script.exists():
        return _fail(command, payload, ["prewarm_script_missing"])

    env = dict(os.environ)
    env["AEGIS_ALPHA_WORKSPACE"] = str(_workspace_dir())
    proc = subprocess.run(
        ["python3", str(script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        check=False,
        timeout=int(payload.get("timeout_sec") or 180),
    )
    raw = (proc.stdout or "").strip()
    parsed = _parse_json_output(raw) if raw else dict()
    if proc.returncode != 0:
        return _fail(command, payload, ["prewarm_script_failed"], [str(parsed)[:500]])
    if not isinstance(parsed, dict):
        return _fail(command, payload, ["prewarm_script_output_invalid"], [str(parsed)[:500]])
    saved_to = parsed.get("saved_to")
    if not saved_to:
        return _fail(command, payload, ["prewarm_artifact_path_missing"])

    artifact_path = Path(str(saved_to)).expanduser().resolve()
    workspace = _workspace_dir().resolve()
    try:
        artifact_path.relative_to(workspace)
    except ValueError:
        return _fail(command, payload, ["prewarm_artifact_outside_workspace"])
    if not artifact_path.exists():
        return _fail(command, payload, ["prewarm_artifact_missing_after_run"])
    try:
        artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except Exception:
        return _fail(command, payload, ["prewarm_artifact_invalid_json_after_run"])
    if not isinstance(artifact_payload, dict):
        return _fail(command, payload, ["prewarm_artifact_invalid_schema_after_run"])

    gaps = _prewarm_gaps(artifact_payload)
    result = {
        "phase": phase,
        "dry_run": False,
        "saved_to": str(artifact_path),
        "artifact_valid": True,
        "keys": sorted(artifact_payload.keys()),
        "critical_gaps": gaps,
        "raw_summary": parsed,
    }
    marker = _write_marker(command, str(artifact_path), result)
    warnings = ["prewarm_partial"] if gaps else []
    return _wrap(command, payload, result, artifacts=[str(artifact_path), str(marker)], warnings=warnings, sources=["nightly_prewarm.py"])


def _prewarm_status(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    path, prewarm, error = _latest_prewarm()
    if error:
        return _fail(command, payload, [error])
    assert prewarm is not None
    age = _artifact_age_seconds(path)
    max_age = float(payload.get("max_age_minutes") or 720) * 60.0
    gaps = _prewarm_gaps(prewarm)
    result = {
        "artifact": str(path),
        "age_seconds": age,
        "stale": age is not None and age > max_age,
        "critical_gaps": gaps,
        "keys": sorted(prewarm.keys()),
    }
    if result["stale"]:
        return _fail(command, payload, ["prewarm_stale"], [f"age_seconds={age}"])
    return _wrap(command, payload, result, artifacts=[str(path)] if path else [], warnings=["prewarm_partial"] if gaps else [], sources=["memory/prewarm"])


def _snapshot_from_prewarm(prewarm: dict[str, Any]) -> dict[str, Any]:
    market_data = prewarm.get("market_data") if isinstance(prewarm.get("market_data"), dict) else dict()
    snapshot = market_data.get("hhxg_snapshot") if isinstance(market_data.get("hhxg_snapshot"), dict) else dict()
    if not snapshot and isinstance(prewarm.get("hhxg_snapshot"), dict):
        snapshot = prewarm["hhxg_snapshot"]
    return snapshot


def _market_scan(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    path, prewarm, error = _latest_prewarm()
    if error:
        return _fail(command, payload, [error])
    assert prewarm is not None
    age = _artifact_age_seconds(path)
    max_age = float(payload.get("max_age_minutes") or 360) * 60.0
    if age is not None and age > max_age:
        return _fail(command, payload, ["prewarm_stale"], [f"age_seconds={age}"])

    snapshot = _snapshot_from_prewarm(prewarm)
    if not snapshot:
        return _fail(command, payload, ["hhxg_snapshot_missing"])
    market = snapshot.get("market") if isinstance(snapshot.get("market"), dict) else dict()
    hot_themes = snapshot.get("hot_themes") if isinstance(snapshot.get("hot_themes"), list) else list()
    alerts = []
    sentiment = market.get("sentiment_index")
    limit_down = market.get("limit_down")
    fried = market.get("fried")
    promotion_rate = market.get("promotion_rate")
    try:
        if sentiment is not None and float(sentiment) < 35:
            alerts.append({"type": "sentiment_low", "value": sentiment})
        if limit_down is not None and float(limit_down) >= 10:
            alerts.append({"type": "limit_down_high", "value": limit_down})
        if fried is not None and float(fried) >= 30:
            alerts.append({"type": "fried_board_high", "value": fried})
        if promotion_rate is not None and float(promotion_rate) < 0.3:
            alerts.append({"type": "promotion_rate_low", "value": promotion_rate})
    except Exception:
        alerts.append({"type": "market_metric_parse_error"})

    top_themes = []
    for item in hot_themes[:5]:
        if isinstance(item, dict):
            top_themes.append({
                "name": item.get("name"),
                "net_yi": item.get("net_yi"),
                "limitup_count": item.get("limitup_count"),
            })

    result = {
        "artifact": str(path),
        "age_seconds": age,
        "alerts": alerts,
        "alert_count": len(alerts),
        "heartbeat_status": "ALERT" if alerts else "HEARTBEAT_OK",
        "market": {
            "sentiment_index": sentiment,
            "limit_down": limit_down,
            "fried": fried,
            "promotion_rate": promotion_rate,
        },
        "top_themes": top_themes,
    }
    return _wrap(command, payload, result, artifacts=[str(path)] if path else [], sources=["memory/prewarm"])


def _alerts_summary(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    scan = _market_scan(command, payload)
    if not scan.get("ok"):
        return scan
    result = scan.get("result") if isinstance(scan.get("result"), dict) else dict()
    summary = {
        "artifact": result.get("artifact"),
        "alert_count": result.get("alert_count", 0),
        "alerts": result.get("alerts", []),
        "heartbeat_status": result.get("heartbeat_status"),
    }
    return _wrap(command, payload, summary, artifacts=scan.get("artifacts", []), sources=scan.get("sources", []))


def _monitor_state_path() -> Path:
    return _workspace_dir() / "memory" / "automation" / "realtime-monitor-state.json"


def _monitor_control(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    action = str(payload.get("action") or "status").strip().lower()
    if action not in {"start", "stop", "status"}:
        return _fail(command, payload, ["invalid_monitor_action"])
    path = _monitor_state_path()
    state = {"running": False, "updated_at": None, "mode": "state_marker_only"}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state.update(loaded)
        except Exception:
            return _fail(command, payload, ["monitor_state_invalid_json"])
    if action in {"start", "stop"}:
        path.parent.mkdir(parents=True, exist_ok=True)
        state.update({
            "running": action == "start",
            "updated_at": _now(),
            "max_age_minutes": payload.get("max_age_minutes") or 360,
            "note": "This command records monitor desired state only; no autonomous trading or order execution is started.",
        })
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    result = {"action": action, "state": state, "state_path": str(path)}
    artifacts = [str(path)] if path.exists() else []
    return _wrap(command, payload, result, artifacts=artifacts, sources=["memory/automation"])


def _resolve_report_text(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    report_path = payload.get("report_path")
    if report_path:
        try:
            candidate = Path(str(report_path)).expanduser().resolve()
            allowed_root = (_workspace_dir() / "memory" / "reports").resolve()
            candidate.relative_to(allowed_root)
        except Exception:
            return None, "report_path_outside_workspace"
        if not candidate.exists():
            return None, "report_path_missing"
        try:
            return candidate.read_text(encoding="utf-8"), None
        except Exception:
            return None, "report_path_unreadable"
    text = payload.get("text")
    if isinstance(text, str) and text.strip():
        return text, None
    return None, "report_text_required"


def _push(command: str, payload: dict[str, Any]) -> dict[str, Any]:
    report_text, error = _resolve_report_text(payload)
    if error:
        return _fail(command, payload, [error])
    assert report_text is not None
    report_title = payload.get("report_title") or "报告推送"
    push_type = command.replace("-push", "")

    if payload.get("dry_run"):
        result = {
            "dry_run": True,
            "push_type": push_type,
            "report_title": report_title,
            "text_chars": len(report_text),
            "sent": False,
        }
        return _wrap(command, payload, result, freshness_status="not_sent")

    if payload.get("confirm_send") is not True:
        return _fail(command, payload, ["external_send_requires_confirm"])

    _load_env()
    if os.environ.get("FEISHU_APP_ID") and os.environ.get("FEISHU_APP_SECRET"):
        push_result = _send_feishu_cards(report_text, report_title, push_type)
    else:
        push_result = _send_feishu(report_text, title=report_title)
    if push_result.get("status") in {"missing_config", "auth_failed"}:
        return _fail(command, payload, [f"push_{push_result.get('status')}"])
    return _wrap(command, payload, {"dry_run": False, "push": push_result, "sent": True}, sources=["feishu"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--command", required=True)
    parser.add_argument("--payload", default="{}")
    args = parser.parse_args()

    package_root = Path(__file__).resolve().parents[1]
    manifest = load_manifest(package_root)
    available = {c["name"] for c in manifest.get("commands", [])}
    if args.command not in available:
        raise SystemExit(f"unknown command: {args.command}")

    payload: dict[str, Any] = {}
    try:
        payload = json.loads(args.payload or "{}")
        if not isinstance(payload, dict):
            raise ValueError("payload_must_be_object")

        if args.command == "nightly-prewarm":
            output = _run_prewarm(args.command, payload, package_root)
        elif args.command == "morning-prewarm":
            output = _run_prewarm(args.command, payload, package_root)
        elif args.command == "midday-prewarm":
            output = _run_prewarm(args.command, payload, package_root)
        elif args.command == "evening-prewarm":
            output = _run_prewarm(args.command, payload, package_root)
        elif args.command == "weekly-prewarm":
            output = _run_prewarm(args.command, payload, package_root)
        elif args.command == "prewarm-status":
            output = _prewarm_status(args.command, payload)
        elif args.command == "market-heartbeat":
            output = _market_scan(args.command, payload)
        elif args.command == "realtime-market-scan":
            output = _market_scan(args.command, payload)
        elif args.command == "realtime-alerts-summary":
            output = _alerts_summary(args.command, payload)
        elif args.command == "realtime-monitor-control":
            output = _monitor_control(args.command, payload)
        elif args.command == "nightly-push":
            output = _push(args.command, payload)
        elif args.command == "morning-push":
            output = _push(args.command, payload)
        elif args.command == "intraday-push":
            output = _push(args.command, payload)
        elif args.command == "weekly-push":
            output = _push(args.command, payload)
        else:
            output = _fail(args.command, payload, ["unknown_command"])
    except ValueError as exc:
        output = _fail(args.command, payload, [str(exc)])
    except subprocess.TimeoutExpired:
        output = _fail(args.command, payload, ["prewarm_script_timeout"])

    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
