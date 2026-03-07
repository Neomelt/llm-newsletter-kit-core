#!/usr/bin/env python3
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

DEFAULT_FEEDS: List[Tuple[str, str]] = [
    # AI / LLM / Agent
    ("https://openai.com/news/rss.xml", "ai"),
    ("https://blog.google/technology/ai/rss/", "ai"),
    ("https://venturebeat.com/category/ai/feed/", "ai"),
    ("https://huggingface.co/blog/feed.xml", "ai"),

    # Robotics industry / ecosystem
    ("https://robohub.org/feed/", "robotics"),
    ("https://www.therobotreport.com/feed/", "robotics"),
    ("https://discourse.ros.org/latest.rss", "robotics"),
    ("https://spectrum.ieee.org/rss/robotics/fulltext", "robotics"),

    # Robotics/autonomy OSS release streams
    ("https://github.com/ros-navigation/navigation2/releases.atom", "robotics"),
    ("https://github.com/moveit/moveit2/releases.atom", "robotics"),
    ("https://github.com/gazebosim/gz-sim/releases.atom", "robotics"),
    ("https://github.com/NVIDIA-ISAAC-ROS/isaac_ros_common/releases.atom", "robotics"),
    ("https://github.com/PX4/PX4-Autopilot/releases.atom", "robotics"),

    # Academic frontier
    ("https://rss.arxiv.org/rss/cs.RO", "academic"),
    ("https://rss.arxiv.org/rss/cs.AI", "academic"),
    ("https://rss.arxiv.org/rss/cs.CV", "academic"),
]

ROBOTICS_KEYWORDS = [
    "robot", "robotics", "ros", "nav2", "moveit", "gazebo", "isaac", "manipulation", "autonomous",
    "drone", "uav", "ugv", "humanoid", "quadruped", "embodied", "vla", "vln",
]

AI_KEYWORDS = [
    "llm", "agent", "reasoning", "multimodal", "benchmark", "foundation model", "transformer", "inference",
]

COMPANY_KEYWORDS = [
    "unitree", "宇树", "deep robotics", "云深处", "figure", "boston dynamics", "agility", "tesla optimus",
]

STRIP_QUERY_KEYS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
    "gclid", "fbclid", "igshid", "mc_cid", "mc_eid", "spm", "mkt_tok",
}


def clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_url(url: str) -> str:
    if not url:
        return ""
    try:
        parts = urlsplit(url.strip())
        q = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k not in STRIP_QUERY_KEYS]
        new_query = urlencode(q)
        path = parts.path.rstrip("/") or "/"
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, new_query, ""))
    except Exception:
        return url.strip()


def parse_datetime(value: str) -> datetime | None:
    if not value:
        return None

    txt = value.strip()
    try:
        dt = parsedate_to_datetime(txt)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    try:
        txt2 = txt.replace("Z", "+00:00")
        dt = datetime.fromisoformat(txt2)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def now_local_date() -> datetime.date:
    if ZoneInfo is not None:
        return datetime.now(ZoneInfo("Asia/Shanghai")).date()
    return datetime.now().date()


def is_today_utc(dt_utc: datetime | None) -> bool:
    if dt_utc is None:
        return False
    if ZoneInfo is not None:
        local_dt = dt_utc.astimezone(ZoneInfo("Asia/Shanghai"))
    else:
        local_dt = dt_utc.astimezone()
    return local_dt.date() == now_local_date()


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


def parse_rss(root: ET.Element, source: str, category: str) -> List[Dict]:
    items = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = clean_html(item.findtext("description") or "")
        pub_raw = (
            (item.findtext("pubDate") or "").strip()
            or (item.findtext("{http://purl.org/dc/elements/1.1/date") or "").strip()
        )
        pub_dt = parse_datetime(pub_raw)

        if not title or not link:
            continue

        items.append(
            {
                "title": title,
                "url": link,
                "normalized_url": normalize_url(link),
                "content": desc,
                "source": source,
                "category": category,
                "published_at": pub_dt.isoformat() if pub_dt else None,
                "published_at_dt": pub_dt,
            }
        )
    return items


def parse_atom(root: ET.Element, source: str, category: str) -> List[Dict]:
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

        pub_raw = (
            (entry.findtext("atom:updated", namespaces=ns) or "").strip()
            or (entry.findtext("atom:published", namespaces=ns) or "").strip()
        )
        pub_dt = parse_datetime(pub_raw)

        if not title or not link:
            continue

        items.append(
            {
                "title": title,
                "url": link,
                "normalized_url": normalize_url(link),
                "content": summary,
                "source": source,
                "category": category,
                "published_at": pub_dt.isoformat() if pub_dt else None,
                "published_at_dt": pub_dt,
            }
        )
    return items


def classify(title: str, source: str, category: str) -> Tuple[str, str, str]:
    t = f"{title} {source}".lower()
    if category in ("robotics", "academic") or any(k in t for k in ROBOTICS_KEYWORDS):
        if "vla" in t or "vln" in t or "embodied" in t:
            return "Robotics", "Embodied AI", "Research"
        if category == "academic":
            return "Robotics", "Research", "Academic"
        return "Robotics", "Autonomy", "Industry"

    if any(k in t for k in AI_KEYWORDS):
        return "AI", "Agent/LLM", "Industry"
    return "AI", "LLM", "Industry"


def score_item(item: Dict) -> int:
    t = f"{item.get('title','')} {item.get('content','')} {item.get('source','')}".lower()
    score = 50

    category = item.get("category")
    if category == "robotics":
        score += 20
    elif category == "academic":
        score += 15
    elif category == "ai":
        score += 10

    score += sum(4 for k in ROBOTICS_KEYWORDS if k in t)
    score += sum(2 for k in AI_KEYWORDS if k in t)
    score += sum(8 for k in COMPANY_KEYWORDS if k in t)

    return score


def build_article(idx: int, item: Dict) -> Dict:
    tag1, tag2, tag3 = classify(item["title"], item["source"], item.get("category", "ai"))
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
        "importanceScore": min(10, max(1, int(item.get("score", 50) / 10))),
        "contentType": "News",
        "url": item["normalized_url"] or item["url"],
        "publishedAt": item.get("published_at"),
    }


def select_balanced(items: List[Dict], max_items: int) -> List[Dict]:
    robotics_target = int(max_items * 0.6)
    ai_target = max_items - robotics_target

    robotics = [i for i in items if i.get("category") in ("robotics", "academic")]
    ai = [i for i in items if i.get("category") == "ai"]

    robotics.sort(key=lambda x: x["score"], reverse=True)
    ai.sort(key=lambda x: x["score"], reverse=True)

    picked = robotics[:robotics_target] + ai[:ai_target]

    if len(picked) < max_items:
        remaining = [i for i in items if i not in picked]
        remaining.sort(key=lambda x: x["score"], reverse=True)
        picked.extend(remaining[: max_items - len(picked)])

    return picked[:max_items]


def main() -> int:
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("playground/data/articles.json")
    max_items = int(sys.argv[2]) if len(sys.argv) > 2 else 40

    raw_items: List[Dict] = []
    for feed, category in DEFAULT_FEEDS:
        try:
            content = fetch(feed)
            root = ET.fromstring(content)
            tag = root.tag.lower()
            if tag.endswith("rss"):
                raw_items.extend(parse_rss(root, feed, category))
            elif tag.endswith("feed"):
                raw_items.extend(parse_atom(root, feed, category))
        except Exception as exc:
            print(f"[WARN] feed failed: {feed} ({exc})")

    # Keep only today's items (Asia/Shanghai)
    today_items = [i for i in raw_items if is_today_utc(i.get("published_at_dt"))]

    # Strong dedupe by normalized URL first, then title+source fallback
    dedup: Dict[str, Dict] = {}
    for item in today_items:
        key = item.get("normalized_url") or f"{item.get('title','').strip().lower()}|{item.get('source','')}"
        prev = dedup.get(key)
        if prev is None:
            dedup[key] = item
        else:
            # prefer richer content
            if len(item.get("content", "")) > len(prev.get("content", "")):
                dedup[key] = item

    items = list(dedup.values())
    for item in items:
        item["score"] = score_item(item)

    selected = select_balanced(items, max_items)
    selected.sort(key=lambda x: x["score"], reverse=True)

    articles = [build_article(i + 1, item) for i, item in enumerate(selected)]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8")

    robot_cnt = sum(1 for a in articles if a["tag1"] == "Robotics")
    ai_cnt = len(articles) - robot_cnt
    print(
        f"Fetched={len(raw_items)}, Today={len(today_items)}, Dedup={len(items)}, "
        f"Generated={len(articles)} -> {output_path} (Robotics={robot_cnt}, AI={ai_cnt})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
