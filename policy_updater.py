"""
Mapae — Policy Change Tracker
==============================

Fetches public policy pages for Google Play, App Store, and Toss,
saves dated snapshots, and diffs against previous versions.

Crawl policy:
- PUBLIC pages only (robots.txt checked before each fetch).
- Login-required or paywalled pages are never accessed.
- SPA pages that return <200 chars of text are flagged as partial.

⚠️ All data collected here is used for policy-based compliance estimation only.
   Not real review data. Not legal advice.
"""

import datetime
import difflib
import urllib.robotparser
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SNAPSHOT_DIR = Path(__file__).parent / "policy_snapshots"

POLICY_SOURCES: Dict[str, Dict] = {
    "google_play": {
        "name": "Google Play 개발자 정책",
        "url": "https://play.google.com/about/developer-content-policy/",
        "robots_url": "https://play.google.com/robots.txt",
    },
    "app_store": {
        "name": "App Store 심사 지침",
        "url": "https://developer.apple.com/app-store/review/guidelines/",
        "robots_url": "https://developer.apple.com/robots.txt",
    },
    "toss": {
        "name": "Toss 판매자 약관",
        "url": "https://www.toss.im/terms",
        "robots_url": "https://www.toss.im/robots.txt",
    },
}

# Descriptive UA so site owners can contact if needed
_UA = "Mapae-Policy-Monitor/1.1 (Game compliance research; public pages only)"
_HEADERS = {"User-Agent": _UA, "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8"}
_TIMEOUT = 15  # seconds


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _check_robots(source_key: str) -> Tuple[bool, str]:
    """Return (allowed, reason). Conservative: allow on fetch failure."""
    source = POLICY_SOURCES[source_key]
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(source["robots_url"])
    try:
        rp.read()
        allowed = rp.can_fetch(_UA, source["url"])
        if not allowed:
            return False, f"robots.txt disallows: {source['url']}"
        return True, "allowed"
    except Exception as e:
        # Cannot read robots.txt — proceed conservatively (no explicit disallow)
        return True, f"robots.txt unavailable ({e}); proceeding"


def _fetch_page(url: str) -> Tuple[str, bool]:
    """
    Fetch a public page and extract plain text via BeautifulSoup.
    Returns (text, is_substantial).
    is_substantial=False means likely SPA / login-wall / empty.
    """
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")

        # Strip noise
        for tag in soup(["script", "style", "nav", "header", "footer",
                         "iframe", "noscript", "svg"]):
            tag.decompose()

        # Try to isolate main content
        main = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", id="content")
            or soup.find("div", class_=lambda c: c and "content" in c.lower())
        )
        text = (main or soup.body or soup).get_text(separator="\n", strip=True)

        # Heuristic: very short text → SPA not rendered server-side
        is_substantial = len(text) >= 300
        return text, is_substantial

    except requests.HTTPError as e:
        return f"[HTTP_ERROR: {e}]", False
    except Exception as e:
        return f"[FETCH_ERROR: {e}]", False


def _snapshot_dir(source_key: str) -> Path:
    return SNAPSHOT_DIR / source_key


def _get_latest_snapshot(source_key: str) -> Optional[Tuple[str, str]]:
    """Return (date_str, content) of the most recent snapshot, or None."""
    d = _snapshot_dir(source_key)
    if not d.exists():
        return None
    snaps = sorted(d.glob("*.txt"), reverse=True)
    if not snaps:
        return None
    return snaps[0].stem, snaps[0].read_text(encoding="utf-8")


def _get_prev_snapshot(source_key: str, skip_date: str) -> Optional[Tuple[str, str]]:
    """Return the snapshot before skip_date (for same-day re-fetch comparison)."""
    d = _snapshot_dir(source_key)
    if not d.exists():
        return None
    snaps = sorted(d.glob("*.txt"), reverse=True)
    for snap in snaps:
        if snap.stem != skip_date:
            return snap.stem, snap.read_text(encoding="utf-8")
    return None


def save_snapshot(source_key: str, content: str,
                  date_str: Optional[str] = None) -> Path:
    """Persist a snapshot. Returns the path written."""
    if date_str is None:
        date_str = datetime.date.today().isoformat()
    path = _snapshot_dir(source_key) / f"{date_str}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def diff_snapshots(old_content: str, new_content: str) -> Dict:
    """
    Unified diff between two snapshot strings.
    Returns a dict with changed flag, line counts, and sample lines.
    """
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    raw_diff = list(difflib.unified_diff(old_lines, new_lines,
                                         fromfile="prev", tofile="new",
                                         lineterm=""))

    added: List[str] = []
    removed: List[str] = []
    for line in raw_diff:
        if line.startswith("+") and not line.startswith("+++"):
            stripped = line[1:].strip()
            if stripped:
                added.append(stripped)
        elif line.startswith("-") and not line.startswith("---"):
            stripped = line[1:].strip()
            if stripped:
                removed.append(stripped)

    return {
        "changed": bool(added or removed),
        "added_lines": len(added),
        "removed_lines": len(removed),
        "added_sample": added[:10],
        "removed_sample": removed[:10],
        "diff_text": "".join(raw_diff[:300]),  # cap for display
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_and_update(source_key: str) -> Dict:
    """
    Fetch the latest policy page for one source, save a snapshot,
    and return a result dict including diff vs. the previous snapshot.
    """
    source = POLICY_SOURCES[source_key]
    today = datetime.date.today().isoformat()

    # ① robots.txt gate
    allowed, robots_reason = _check_robots(source_key)
    if not allowed:
        return {
            "source": source_key,
            "name": source["name"],
            "status": "blocked_by_robots",
            "reason": robots_reason,
            "snapshot_path": None,
            "diff": None,
        }

    # ② Fetch
    content, is_substantial = _fetch_page(source["url"])

    # ③ Save snapshot
    snap_path = save_snapshot(source_key, content, today)

    # ④ Diff vs. previous snapshot
    latest = _get_latest_snapshot(source_key)
    diff_result: Optional[Dict] = None
    prev_date: Optional[str] = None

    if latest:
        prev_date_candidate, prev_content = latest
        if prev_date_candidate != today:
            # Compare today vs. yesterday's snapshot
            prev_date = prev_date_candidate
            diff_result = diff_snapshots(prev_content, content)
        else:
            # Same-day re-fetch: compare against the snapshot before today
            older = _get_prev_snapshot(source_key, today)
            if older:
                prev_date, prev_content2 = older
                diff_result = diff_snapshots(prev_content2, content)
            else:
                # First snapshot ever
                diff_result = {
                    "changed": False, "added_lines": 0, "removed_lines": 0,
                    "added_sample": [], "removed_sample": [], "diff_text": "",
                }

    return {
        "source": source_key,
        "name": source["name"],
        "url": source["url"],
        "status": "ok" if is_substantial else "spa_partial",
        "snapshot_path": str(snap_path),
        "snapshot_date": today,
        "prev_snapshot_date": prev_date,
        "content_length": len(content),
        "is_substantial": is_substantial,
        "diff": diff_result,
    }


def update_all_policies() -> Dict[str, Dict]:
    """Fetch + snapshot + diff for all three platforms. Returns results dict."""
    return {key: fetch_and_update(key) for key in POLICY_SOURCES}


def get_changes_summary(results: Dict[str, Dict]) -> str:
    """Human-readable Markdown summary of policy change results."""
    lines = ["## 📋 정책 변경 현황\n"]

    for source_key, result in results.items():
        name = result.get("name", source_key)
        status = result.get("status", "unknown")

        if status == "blocked_by_robots":
            lines.append(f"### {name}\n")
            lines.append(f"- ⛔ robots.txt 차단: {result.get('reason', '')}\n\n")
            continue

        diff = result.get("diff")
        snap_date = result.get("snapshot_date", "")
        prev_date = result.get("prev_snapshot_date", "N/A")

        lines.append(f"### {name}\n")

        if diff is None:
            lines.append(f"- 📥 첫 스냅샷 저장 ({snap_date})\n\n")
        elif diff.get("changed"):
            added = diff.get("added_lines", 0)
            removed = diff.get("removed_lines", 0)
            lines.append(f"- ⚠️ **변경 감지** ({prev_date} → {snap_date}): "
                         f"+{added}줄 추가 / -{removed}줄 삭제\n")
            for sample in diff.get("added_sample", [])[:3]:
                if len(sample) > 15:
                    lines.append(f"  > +{sample[:200]}\n")
            lines.append("\n")
        else:
            lines.append(f"- ✅ 변경 없음 (기준: {prev_date})\n\n")

        if status == "spa_partial":
            lines.append("  *(SPA 감지: 서버사이드 렌더 콘텐츠만 수집됨)*\n\n")

    return "".join(lines)


def get_latest_policy_text(source_key: str) -> Optional[str]:
    """Return the latest snapshot text for a given source, or None."""
    result = _get_latest_snapshot(source_key)
    return result[1] if result else None
