# tiktok-metadata-collector/
A slow-and-strady approach to collecting tiktok metadata

## Core principles
- One JSON output per run
- Errors are logged, not fatal
- Slow > blocked

## General flow
- Create a seed file
- - Stored as .txt
- - One username per row
- - Save in seeds/yyyy-mm-dd
- Run collect_user_metadata.py
- - Saves the output from the run (metadata for each user) as json in outputs/raw/YYYY-MM-DD
- Run collect_video_metadata_from_ids.py
- - Saves the output from the run (metadata for each video) as json in outputs/enriched/YYYY-MM-DD

## Folder structure
```
tiktok-metadata-collector/
│
├── README.md
├── requirements.txt
│
├── src/
│   └── collect_user_metadata.py
│
├── seeds/
│   ├── 2026-02-01/
│   │   ├── travel_brands.txt
│   │   ├── tourism_boards.txt
│   │   └── content_creators.txt
│   │
│   ├── 2026-02-15/
│   │   ├── travel_creators_high_engagement.txt
│   │   └── airlines.txt
│   │
│   └── README.md
│
├── outputs/
│   ├── raw/
│   │   ├── 2026-02-01/
│   │   │   ├── tiktok_seed_users_20260201_214501.json
│   │   │   └── tiktok_seed_users_20260201_221833.json
│   │   │
│   │   └── 2026-02-15/
│   │       └── tiktok_seed_users_20260215_090212.json
├   ├── enriched/
│   │   ├── 2026-02-01/
│   │       ├── tiktok_seed_users_20260201_214501.json
│   │       └── tiktok_seed_users_20260201_221833.json
│   │
│   └── README.md
│
├── notebooks/
│   └── explore_seed_outputs.ipynb
```

# TikTok User Metadata Collector

## How to run the collector

This guide documents the **repeatable workflow** for:
- updating seed files
- running the user metadata collector
- locating and verifying JSON outputs

Follow these steps **in order** each time you run a new snapshot.

---

### 0) Navigate to the repo root

```bash
cd ~/Documents/repos/tiktok-metadata-collector
```

### 1) Activate the virtual environment
```bash
source venv/bin/activate
```

Confirm dependencies are available:
```bash
yt-dlp --version
which yt-dlp
```

Expected:
- yt-dlp prints a version
- which yt-dlp points to .../venv/bin/yt-dlp

### 2) Create a new dated seed folder
Seeds are immutable snapshots. Use one folder per date.

```bash
mkdir -p "seeds/$(date +%F)"
```

### 3) Update or create seed files
Each file contains one TikTok username per line.

Example files
- travel_brands.txt
- tourism_boards.txt
- creators_general.txt

File format rules
- one username per line
- no @ required
- comments allowed with #

### 4) Create an output folder for this run
Mirror the seed date for traceability.

```bash
mkdir -p "outputs/raw/$(date +%F)"
```

### 5) Run the collector for one seed file
From the repo root:

```bash
python scripts/collect_user_metadata.py \
  --seed seeds/2026-02-01/travel_brands.txt \
  --out outputs/raw/2026-02-01 \
  --max-videos 25 \
  --sleep 3 \
  --jitter 2
```

What this does:
-r eads the seed file
- collects profile + last N videos
- waits for set time between users
- writes one timestamped JSON file

###  6) Locate the JSON output
Get the most recent file:

```bash
ls -t outputs/raw/2026-02-01/*.json | head -n 1
```

### Note: If TikTok starts blocking requests
Slow the crawl:

```bash
--sleep 6 --jitter 4
```

###  7) Deactivate when finished
```bash
deactivate
```

# TikTok Video Metadata Collector

## How to run the collector
The script does the following:
- reads JSON file output by the user metadata collector script
- extracts all video URLs from the JSON
- calls yt-dlp per video to get richer metadata (-J --no-download)
- attempts comments with --write-comments
- outputs the results in JSON

### 1) Activate venv
```bash
source venv/bin/activate
```

### 2) Optional but recommended 
```bash
pip install -U "yt-dlp[default,curl-cffi]"
```

### 3) Run the script
Fill in the correct file names and run:

```bash
python collect_video_metadata_from_ids.py \
  --input ../outputs/raw/2026-02-01/tiktok_seed_users_20260201_223844.json \
  --out ../outputs/enriched/2026-02-01 \
  --write-per-video \
  --no-comments \
  --sleep 6.0 --jitter 3.0 \
  --max-total-errors 20
```
Note - sleep 6.0 and jitter 3.0 runs about 215/hour, no ERRORs

# JSON to CSV conversion scripts
First:
```bash
pip install pandas
```

To run user_metadata_to_csv.py
```bash
python user_metadata_to_csv.py \
  --in ../outputs/raw/2026-02-01/tiktok_seed_users_20260201_223844.json \
  --out ../outputs/csv_out
```

To run video_metadata_to_csv.py on batch-style files:
```bash
python enriched_videos_to_csv.py \
  --in /mnt/data/videos_enriched_20260202_133449.json \
  --out ./csv_out/videos_enriched.csv
```

To run video_metadata_to_csv.py on a folder of per-video JSONs::
```bash
python enriched_videos_to_csv.py \
  --in ./outputs/enriched/per_video_jsons \
  --out ./csv_out/videos_enriched.csv
```
