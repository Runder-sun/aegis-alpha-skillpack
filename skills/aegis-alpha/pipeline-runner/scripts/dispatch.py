from __future__ import annotations

import argparse
import json
from pathlib import Path


def load_manifest(base: Path) -> dict:
    path = base / "data" / "command-manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_pipelines(base: Path) -> dict:
    path = base / "data" / "pipelines.json"
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_pipeline_id(command: str, payload: dict) -> str | None:
    if command == "pipeline-run":
        value = payload.get("pipeline_id")
        return value if isinstance(value, str) and value else None
    if command == "pipeline-run-nightly":
        return "nightly"
    if command == "pipeline-run-morning":
        return "morning"
    if command == "pipeline-run-market-review":
        return "market-review"
    if command == "pipeline-run-weekly":
        return "weekly"
    return None


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

    payload = json.loads(args.payload)
    pipelines = load_pipelines(package_root).get("pipelines", [])
    pipeline_index = {p.get("id"): p for p in pipelines if isinstance(p, dict)}

    if args.command == "pipeline-list":
        output_payload = {"pipelines": pipelines}
    else:
        pipeline_id = resolve_pipeline_id(args.command, payload)
        if not pipeline_id or pipeline_id not in pipeline_index:
            raise SystemExit(f"unknown pipeline_id: {pipeline_id}")
        output_payload = {
            "pipeline_id": pipeline_id,
            "pipeline": pipeline_index[pipeline_id],
        }

    print(
        json.dumps(
            {
                "package": "pipeline-runner",
                "command": args.command,
                "payload": output_payload,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
