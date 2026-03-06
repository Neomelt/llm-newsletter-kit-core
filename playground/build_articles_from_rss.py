#!/usr/bin/env python3
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

DEFAULT_FEEDS = [
    # AI
    "https://openai.com/news/rss.xml",
    "https://blog.google/technology/ai/rss/",
    "https://venturebeat.com/category/ai/feed/",
    "https://huggingface.co/blog/feed.xml",
    # Robotics
    "https://robohub.org/feed/",
    "https://www.therobotreport.com/feed/",
    "https://discourse.ros.org/latest.rss",
    "https://spectrum.ieee.org/rss/robotics/fulltext",
]


def clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (NewsletterBot/1.0)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def parse_rss(root: ET.Element, source: str) -> List[Dict]:
    items = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = clean_html(item.findtext("description") or "")
        if not title or not link:
            continue
        items.append(
            {
                "title": title,
                "url": link,
                "content": desc,
                "source": source,
            }
        )
    return items


def parse_atom(root: ET.Element, source: str) -> List[Dict]:
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = []
    for entry in root.findall("atom:entry", ns):
        title = (entry.findtext("atom:title", namespaces=ns) or "").strip()
        link = ""
        for l in entry.findall("atom:link", ns):
            rel = l.attrib.get("rel", "alternate")
            if rel == "alternate" and l.attrib.get("href"):
                link = l.attrib["href"].strip()
                break
        if not link:
            first = entry.find("atom:link", ns)
            if first is not None and first.attrib.get("href"):
                link = first.attrib["href"].strip()
        summary = (
            entry.findtext("atom:summary", namespaces=ns)
            or entry.findtext("atom:content", namespaces=ns)
            or ""
        )
        summary = clean_html(summary)
        if not title or not link:
            continue
        items.append(
            {
                "title": title,
                "url": link,
                "content": summary,
                "source": source,
            }
        )
    return items


def classify(title: str, source: str) -> Tuple[str, str, str]:
    t = f"{title} {source}".lower()
    if any(k in t for k in ["robot", "ros", "autonomous", "drone", "humanoid", "gazebo"]):
        return "Robotics", "Autonomy", "Industry"
    return "AI", "LLM", "Industry"


def build_article(idx: int, item: Dict) -> Dict:
    tag1, tag2, tag3 = classify(item["title"], item["source"])
    detail = item["content"][:900] if item["content"] else f"Source update from {item['source']}"
    return {
        "id": idx,
        "title": item["title"],
        "detailContent": detail,
        "hasAttachedImage": False,
        "imageContextByLlm": None,
        "tag1": tag1,
        "tag2": tag2,
        "tag3": tag3,
        "targetUrl": item["source"],
        "importanceScore": 7,
        "contentType": "News",
        "url": item["url"],
    }


def main() -> int:
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("playground/data/articles.json")
    max_items = int(sys.argv[2]) if len(sys.argv) > 2 else 40

    raw_items: List[Dict] = []
    for feed in DEFAULT_FEEDS:
        try:
            content = fetch(feed)
            root = ET.fromstring(content)
            tag = root.tag.lower()
            if tag.endswith("rss"):
                raw_items.extend(parse_rss(root, feed))
            elif tag.endswith("feed"):
                raw_items.extend(parse_atom(root, feed))
        except Exception as exc:
            print(f"[WARN] feed failed: {feed} ({exc})")

    dedup = {}
    for item in raw_items:
        dedup[item["url"]] = item

    items = list(dedup.values())[:max_items]
    articles = [build_article(i + 1, item) for i, item in enumerate(items)]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Generated {len(articles)} articles -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
