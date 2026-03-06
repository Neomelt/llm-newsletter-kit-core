#!/usr/bin/env python3
import json
import os
import sys
import urllib.request


def main() -> int:
    webhook = os.getenv("FEISHU_WEBHOOK", "").strip()
    if not webhook:
      print("FEISHU_WEBHOOK missing, skip")
      return 0

    status = os.getenv("JOB_STATUS", "unknown")
    run_url = os.getenv("RUN_URL", "")
    repo = os.getenv("REPO", "")
    provider = os.getenv("PROVIDER", "unknown")
    model = os.getenv("MODEL", "unknown")
    mode_text = os.getenv("MODE_TEXT", "unknown")

    color = "green"
    if provider == "fallback":
      color = "orange"
    if status != "success":
      color = "red"

    payload = {
      "msg_type": "interactive",
      "card": {
        "config": {"wide_screen_mode": True},
        "header": {
          "template": color,
          "title": {"tag": "plain_text", "content": "AI+Robotics Newsletter 任务通知"},
        },
        "elements": [
          {
            "tag": "div",
            "text": {
              "tag": "lark_md",
              "content": f"**状态**：{status}\n**模式**：{mode_text}",
            },
          },
          {
            "tag": "div",
            "text": {
              "tag": "lark_md",
              "content": f"**Provider**：{provider}\n**Model**：{model}",
            },
          },
          {
            "tag": "action",
            "actions": [
              {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "查看运行日志"},
                "type": "primary",
                "url": run_url,
              }
            ],
          },
          {"tag": "note", "elements": [{"tag": "plain_text", "content": f"Repo: {repo}"}]},
        ],
      },
    }

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
      webhook,
      data=data,
      headers={"Content-Type": "application/json"},
      method="POST",
    )
    try:
      with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode("utf-8", errors="replace")
        print(body)
    except Exception as exc:
      print(f"notify error: {exc}")
      return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
