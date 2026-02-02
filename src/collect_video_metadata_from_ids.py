#!/usr/bin/env python3
"""
Given a JSON file produced by your seed-user run (containing results[].videos[].video_id/url),
fetch per-video metadata using yt-dlp.

- Always collects video metadata (no download).
- Attempts comment extraction via --write-comments, but TikTok often blocks/doesn't expose comments.

Outputs:
- One combined JSON: <out_dir>/videos_enriched_<timestamp>.json
- Optionally per-video JSON files: <out_dir>/per_video/<video_id>.json

Usage:
  python collect_video_metadata_from_ids.py \
    --input outputs/raw/2026-02-01/tiktok_seed_users_20260201_214501.json \
    --out outputs/enriched/2026-02-01 \
    --sleep 2.0 --jitter 1.5 \
    --write-per-video
"""

import argparse
import json
import os
import random
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_ytdlp_dump_json(
    url: str,
    timeout_sec: int = 180,
    user_agent: Optional[str] = None,
    proxy: Optional[str] = None,
    attempt_comments: bool = True,
) -> Tuple[Optional[Dict[str, Any]], Optional[str], int]:
    """
    Returns: (json_dict or None, error_string or None, returncode)
    """
    cmd = [
        "yt-dlp",
        "--no-download",
        "-J",
        "--skip-download",
        # Add more extractor detail when available
        "--dump-single-json",
    ]

    # Try to fetch comments. For TikTok, this may do nothing / error / be blocked.
    if attempt_comments:
        cmd.append("--write-comments")

    if user_agent:
        cmd += ["--user-agent", user_agent]

    if proxy:
        cmd += ["--proxy", proxy]

    cmd.append(url)

    try:
        p = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired:
        return None, "timeout", 124
    except FileNotFoundError:
        return None, "yt-dlp not found (is your venv active?)", 127
    except Exception as e:
        return None, f"exception: {e}", 1

    if p.returncode != 0:
        err = (p.stderr or "").strip()
        if len(err) > 2000:
            err = err[-2000:]
        return None, err or "yt-dlp failed", p.returncode

    try:
        return json.loads(p.stdout), None, 0
    except json.JSONDecodeError:
        return None, "failed to parse yt-dlp JSON output", 2


def extract_video_urls_from_seed_run(seed_run_json: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Returns list of {"video_id": "...", "url": "...", "username": "..."} items.
    """
    out: List[Dict[str, str]] = []
    results = seed_run_json.get("results", [])
    for r in results:
        profile = r.get("profile", {}) or {}
        username = profile.get("username") or "unknown"
        for v in (r.get("videos") or []):
            vid = v.get("video_id")
            url = v.get("url")
            if not url and vid and username and username != "unknown":
                url = f"https://www.tiktok.com/@{username}/video/{vid}"
            if vid and url:
                out.append({"video_id": str(vid), "url": str(url), "username": str(username)})
    # de-dup by video_id preserving order
    seen = set()
    deduped = []
    for item in out:
        if item["video_id"] not in seen:
            seen.add(item["video_id"])
            deduped.append(item)
    return deduped


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Enrich TikTok video IDs/URLs into per-video metadata JSON using yt-dlp")
    ap.add_argument("--input", required=True, help="Path to seed-user run JSON (the file with results[].videos[]).")
    ap.add_argument("--out", default="outputs/enriched", help="Output directory.")
    ap.add_argument("--sleep", type=float, default=2.0, help="Base sleep seconds between videos.")
    ap.add_argument("--jitter", type=float, default=1.5, help="Random extra sleep (0..jitter) seconds.")
    ap.add_argument("--timeout", type=int, default=180, help="yt-dlp timeout per video (seconds).")
    ap.add_argument("--user-agent", default=None, help="Optional custom User-Agent.")
    ap.add_argument("--proxy", default=None, help="Optional proxy URL (e.g. http://host:port).")
    ap.add_argument("--no-comments", action="store_true", help="Do not attempt comment extraction.")
    ap.add_argument("--write-per-video", action="store_true", help="Write one JSON per video in out/per_video/.")
    ap.add_argument("--max-videos", type=int, default=0, help="Optional cap for testing (0 = no cap).")
    ap.add_argument("--max-consecutive-errors",type=int,default=0,help="Stop early after this many consecutive errors (0 = disabled).")

    return ap.parse_args()


def main() -> int:
    args = parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"ERROR: input file not found: {in_path}")
        return 2

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    seed_run = json.loads(in_path.read_text(encoding="utf-8"))
    videos = extract_video_urls_from_seed_run(seed_run)
    if args.max_videos and args.max_videos > 0:
        videos = videos[: args.max_videos]

    per_video_dir = out_dir / "per_video"
    if args.write_per_video:
        per_video_dir.mkdir(parents=True, exist_ok=True)

    enriched: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    print(f"Found {len(videos)} unique videos to enrich")

    consecutive_errors = 0

    for i, item in enumerate(videos, 1):
        vid = item["video_id"]
        url = item["url"]
        print(f"[{i}/{len(videos)}] {vid} … ", end="", flush=True)

        info, err, rc = run_ytdlp_dump_json(
            url=url,
            timeout_sec=args.timeout,
            user_agent=args.user_agent,
            proxy=args.proxy,
            attempt_comments=not args.no_comments,
        )

        if err or not info:
        print("ERROR")
        consecutive_errors += 1

        errors.append({
            "video_id": vid,
            "url": url,
            "username": item.get("username"),
            "scraped_at": now_iso(),
            "returncode": rc,
            "error": err or "unknown error",
        })

        if args.max_consecutive_errors > 0 and consecutive_errors >= args.max_consecutive_errors:
            print(
                f"\nStopping early after {consecutive_errors} consecutive errors "
                f"(likely rate-limited or blocked)."
            )
            break

        else:
            print("OK")
            record = {
                "video_id": vid,
                "url": url,
                "username": item.get("username"),
                "scraped_at": now_iso(),
                "yt_dlp": info,  # raw yt-dlp infojson (includes as much as extractor can provide)
            }
            consecutive_errors = 0

            enriched.append(record)

            if args.write_per_video:
                (per_video_dir / f"{vid}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")

        # polite delay
        time.sleep(max(0.0, args.sleep + random.random() * args.jitter))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / f"videos_enriched_{ts}.json"
    payload = {
        "run_started_at": now_iso(),
        "source_input": str(in_path),
        "video_count_requested": len(videos),
        "video_count_succeeded": len(enriched),
        "video_count_failed": len(errors),
        "attempted_comments": not args.no_comments,
        "results": enriched,
        "errors": errors,
    }
    out_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"\nDone. Wrote: {out_file}")
    if errors:
        print(f"Failures: {len(errors)} (TikTok often blocks comment/extra metadata access.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
