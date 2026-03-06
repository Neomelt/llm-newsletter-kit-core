#!/usr/bin/env python3
import json
import os
import re
import urllib.request
from pathlib import Path


def _extract_headlines() -> list[str]:
    md_path = Path("playground/output/newsletter.md")
    if not md_path.exists():
        return []
    text = md_path.read_text(encoding="utf-8", errors="ignore")
    lines = [ln.strip() for ln in text.splitlines()]

    headlines = []
    for line in lines:
        if line.startswith("### "):
            headlines.append(line[4:].strip())
            if len(headlines) >= 5:
                break

    if not headlines:
        # fallback: pick first non-title informative lines
        for line in lines:
            if line and not line.startswith("---") and not line.startswith("title:") and not line.startswith("##"):
                line = re.sub(r"^[-*]\s*", "", line)
                headlines.append(line[:80])
                if len(headlines) >= 5:
                    break
    return headlines


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

    headlines = _extract_headlines()
    if headlines:
        news_block = "\n".join([f"• {h}" for h in headlines])
    else:
        news_block = "（本次未解析到头条，点日志查看详情）"

    payload = {
      "msg_type": "interactive",
      "card": {
        "config": {"wide_screen_mode": True},
        "header": {
          "template": color,
          "title": {"tag": "plain_text", "content": "AI + Robotics 每日快报"},
        },
        "elements": [
          {
            "tag": "div",
            "text": {
              "tag": "lark_md",
              "content": f"**状态**：{status}  |  **模式**：{mode_text}\n**Provider/Model**：{provider} / {model}",
            },
          },
          {
            "tag": "div",
            "text": {
              "tag": "lark_md",
              "content": f"**今日要闻**\n{news_block}",
            },
          },
          {
            "tag": "action",
            "actions": [
              {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "查看完整运行与产物"},
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
