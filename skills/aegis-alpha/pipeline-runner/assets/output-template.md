# pipeline-runner Output Template

```json
{
  "package": "pipeline-runner",
  "command": "pipeline-run",
  "payload": {
    "pipeline_id": "nightly",
    "pipeline": {
      "id": "nightly",
      "label": "晚间策略",
      "steps": [
        {"package": "execution-automation", "command": "nightly-prewarm"},
        {"package": "advice-lifecycle", "command": "nightly-strategy"},
        {"package": "execution-automation", "command": "nightly-push", "optional": true}
      ]
    }
  }
}
```
