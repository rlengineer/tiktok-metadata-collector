# tiktok-metadata-collector/
A sandbox for collecting tiktok metadata

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
│   │
│   └── README.md
│
├── notebooks/
│   └── explore_seed_outputs.ipynb
│
└── logs/
    └── runs.log
```

## How to Run the TikTok User Metadata Collector

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

## Core principles
- Seeds are immutable snapshots
- One JSON output per run
- Outputs always reference the seed file used
- Errors are logged, not fatal
- Slow > blocked
