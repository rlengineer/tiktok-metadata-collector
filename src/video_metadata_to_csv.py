#!/usr/bin/env python3
"""
video_metadata_to_csv.py

Purpose:
- Converts video metadata from JSON to CSV format (to reduce storage space)
- Specifically designed to process the ouput from src/collect_video_metadata_from_ids.py

Supports:
1) Batch enriched JSON:
   { run_started_at, ..., results: [ {...}, ... ] }

2) Single-video JSON files:
   { video_id, url, username, scraped_at, yt_dlp:{...} }

Input:
batch-style files - ../outputs/enriched/2026-02-02/videos_enriched_20260202_185751.json 
a folder of per-video JSONs - ../outputs/enriched/2026-02-01/per_video

Output:
  - ../outputs/csv_out/video_data/videos_enriched_<timestamp>.csv

Timestamp priority:
1) run_started_at (batch)
2) earliest scraped_at (folder mode)
3) current time

"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def iter_inputs(path: Path) -> List[Path]:
    if path.is_dir():
        return sorted([p for p in path.rglob("*.json") if p.is_file()])
    return [path]


def parse_iso_dt(s: Optional[str]) -> Optional[datetime]:
    if not s or not isinstance(s, str):
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

def pick_best_format(formats: Any) -> Dict[str, Any]:
    if not isinstance(formats, list) or not formats:
        return {}

    def score(fmt: Dict[str, Any]) -> Tuple[int, float, int]:
        return (
            int(fmt.get("height") or 0),
            float(fmt.get("tbr") or 0.0),
            int(fmt.get("filesize") or fmt.get("filesize_approx") or 0),
        )

    best, best_s = None, (-1, -1.0, -1)
    for f in formats:
        if not isinstance(f, dict):
            continue
        s = score(f)
        if s > best_s:
            best_s, best = s, f

    if not isinstance(best, dict):
        return {}

    return {
        "best_format_id": best.get("format_id"),
        "best_ext": best.get("ext"),
        "best_vcodec": best.get("vcodec"),
        "best_acodec": best.get("acodec"),
        "best_width": best.get("width"),
        "best_height": best.get("height"),
        "best_tbr": best.get("tbr"),
        "best_filesize": best.get("filesize") or best.get("filesize_approx"),
    }


def first_thumbnail(thumbnails: Any) -> Dict[str, Any]:
    if not isinstance(thumbnails, list) or not thumbnails:
        return {}
    preferred = {t.get("id"): t for t in thumbnails if isinstance(t, dict)}
    cover = preferred.get("cover") or preferred.get("originCover") or preferred.get("dynamicCover")
    if isinstance(cover, dict):
        return {"thumb_id": cover.get("id"), "thumb_url": cover.get("url")}
    t0 = thumbnails[0] if isinstance(thumbnails[0], dict) else None
    return {"thumb_id": t0.get("id"), "thumb_url": t0.get("url")} if isinstance(t0, dict) else {}


def normalize_record(item: Dict[str, Any], run_meta: Dict[str, Any]) -> Dict[str, Any]:
    yt = item.get("yt_dlp") if isinstance(item.get("yt_dlp"), dict) else {}

    artists = yt.get("artists")
    artists_str = ",".join(artists) if isinstance(artists, list) else None

    return {
        **run_meta,
        "video_id": item.get("video_id") or yt.get("id"),
        "url": item.get("url") or yt.get("webpage_url") or yt.get("original_url"),
        "username": item.get("username") or yt.get("uploader"),
        "scraped_at": item.get("scraped_at"),

        # Core yt-dlp fields
        "yt_id": yt.get("id"),
        "title": yt.get("title"),
        "description": yt.get("description"),
        "timestamp": yt.get("timestamp"),
        "duration": yt.get("duration"),
        "view_count": yt.get("view_count"),
        "like_count": yt.get("like_count"),
        "comment_count": yt.get("comment_count"),
        "repost_count": yt.get("repost_count"),
        "save_count": yt.get("save_count"),

        # Channel/uploader identifiers
        "channel": yt.get("channel"),
        "channel_id": yt.get("channel_id"),
        "uploader": yt.get("uploader"),
        "uploader_id": yt.get("uploader_id"),

        # Audio/music
        "track": yt.get("track"),
        "album": yt.get("album"),
        "artists": artists_str,

        # Summaries from large lists
        **pick_best_format(yt.get("formats")),
        **first_thumbnail(yt.get("thumbnails")),

        # URLs
        "webpage_url": yt.get("webpage_url"),
        "original_url": yt.get("original_url"),
        "extractor": yt.get("extractor"),
        "extractor_key": yt.get("extractor_key"),
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True, help="Input JSON file OR folder")
    ap.add_argument("--out", dest="out_dir", required=True, help="Output directory")
    ap.add_argument("--prefix", default="videos_enriched", help="Filename prefix")
    args = ap.parse_args()

    in_path = Path(args.in_path).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []
    candidate_times: List[datetime] = []

    for fp in iter_inputs(in_path):
        data = read_json(fp)

        # Batch file
        if isinstance(data, dict) and isinstance(data.get("results"), list):
            dt = parse_iso_dt(data.get("run_started_at"))
            if dt:
                candidate_times.append(dt)

            run_meta = {
                "run_started_at": data.get("run_started_at"),
                "source_input": data.get("source_input"),
                "video_count_requested": data.get("video_count_requested"),
                "video_count_succeeded": data.get("video_count_succeeded"),
                "video_count_failed": data.get("video_count_failed"),
                "attempted_comments": data.get("attempted_comments"),
                "skipped_existing": data.get("skipped_existing"),
            }

            for item in data["results"]:
                if isinstance(item, dict):
                    rows.append(normalize_record(item, run_meta))

        # Single-video file
        elif isinstance(data, dict):
            dt = parse_iso_dt(data.get("scraped_at"))
            if dt:
                candidate_times.append(dt)

            rows.append(
                normalize_record(
                    data,
                    {"source_file": fp.name},
                )
            )

    df = pd.DataFrame(rows)

    if not candidate_times:
        ts = datetime.now()
    else:
        ts = min(candidate_times)

    out_csv = out_dir / f"{args.prefix}_{ts.strftime('%Y%m%d_%H%M%S')}.csv"
    df.to_csv(out_csv, index=False)

    print(f"Wrote {out_csv} (rows={len(df):,}, cols={df.shape[1]:,})")


if __name__ == "__main__":
    main()
