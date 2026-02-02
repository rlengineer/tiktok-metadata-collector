#!/usr/bin/env python3
"""
seed_users_to_user_videos_csv.py

Input:  seed-user run JSON shaped like:
  { run_started_at, ..., results: [ { scraped_at, source, profile:{...}, videos:[...]} , ... ] }

Output:
  - user_videos_<timestamp>.csv   (one row per video, with user columns attached)

Timestamp strategy:
- If run_started_at exists, we parse it and use it for filename.
- Otherwise we use current local time.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_get(d: Optional[Dict[str, Any]], key: str, default=None):
    return d.get(key, default) if isinstance(d, dict) else default


def parse_iso_dt(s: Optional[str]) -> Optional[datetime]:
    """
    Parse ISO timestamps like:
      2026-02-02T03:11:32.146851+00:00
    Returns datetime or None.
    """
    if not s or not isinstance(s, str):
        return None
    try:
        s2 = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s2)
    except Exception:
        return None


def filename_timestamp(run_started_at: Optional[str]) -> str:
    dt = parse_iso_dt(run_started_at)
    if dt is None:
        dt = datetime.now()
    if dt.tzinfo is not None:
        dt = dt.astimezone()
    return dt.strftime("%Y%m%d_%H%M%S")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, help="Input seed users JSON file")
    ap.add_argument("--out", dest="out_dir", required=True, help="Output directory for CSV")
    ap.add_argument(
        "--prefix",
        default="user_videos",
        help="Output filename prefix (default: user_videos)",
    )
    args = ap.parse_args()

    in_path = Path(args.in_path).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    data = read_json(in_path)

    run_meta = {
        "run_started_at": data.get("run_started_at"),
        "run_finished_at": data.get("run_finished_at"),
        "seed_file": data.get("seed_file"),
        "requested_max_videos": data.get("requested_max_videos"),
        "user_count_requested": data.get("user_count_requested"),
        "user_count_succeeded": data.get("user_count_succeeded"),
        "user_count_failed": data.get("user_count_failed"),
    }

    videos_rows: List[Dict[str, Any]] = []

    for r in data.get("results", []):
        if not isinstance(r, dict):
            continue

        profile = r.get("profile") if isinstance(r.get("profile"), dict) else None
        scraped_at = r.get("scraped_at")
        source = r.get("source")

        username = safe_get(profile, "username", None) or r.get("username")
        profile_url = safe_get(profile, "profile_url")

        # Videos nested under each successful user result
        for v in r.get("videos", []):
            if not isinstance(v, dict):
                continue

            hashtags = v.get("hashtags")
            videos_rows.append({
                **run_meta,
                "user_scraped_at": scraped_at,
                "user_source": source,
                "username": username,
                "profile_url": profile_url,

                "video_id": v.get("video_id"),
                "url": v.get("url"),
                "title": v.get("title"),
                "caption": v.get("caption"),
                "timestamp": v.get("timestamp"),
                "upload_date": v.get("upload_date"),
                "duration_sec": v.get("duration_sec"),
                "uploader": v.get("uploader"),
                "uploader_id": v.get("uploader_id"),
                "view_count": v.get("view_count"),
                "like_count": v.get("like_count"),
                "comment_count": v.get("comment_count"),
                "repost_count": v.get("repost_count"),
                "hashtags": ",".join(hashtags) if isinstance(hashtags, list) else None,
            })

    videos_df = pd.DataFrame(videos_rows)

    ts = filename_timestamp(data.get("run_started_at"))
    out_csv = out_dir / f"{args.prefix}_{ts}.csv"

    videos_df.to_csv(out_csv, index=False)
    print(f"Wrote {out_csv} (rows={len(videos_df):,}, cols={videos_df.shape[1]:,})")


if __name__ == "__main__":
    main()
