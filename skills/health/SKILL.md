---
name: health
description: Query Apple Health data — steps, heart rate, sleep, exercise, and more.
  Use when user asks about "health", "steps", "heart rate", "sleep", "exercise",
  "how's my health", "health summary", "fitness", "calories", "HRV", "blood oxygen",
  "stand hours", or "health anomalies".
metadata:
  clawcode:
    emoji: "❤️"
    os: ["darwin"]
    requires:
      bins: [python3]
      files:
        - ~/clawcode/scripts/health-summary.py
---

# Health — Apple Health Data

Query health and fitness data synced from Apple Watch via Health Auto Export (iOS app).

## Data Source

- **App:** Health Auto Export (iOS, Premium tier) — background syncs to iCloud
- **Path:** `~/Library/Mobile Documents/iCloud~com~ifunography~HealthExport/Documents/NormalExport/HealthAutoExport-YYYY-MM-DD.json`
- **Metrics:** steps, active calories, exercise time, heart rate (min/avg/max), resting HR, HRV, blood O2, stand hours, walking/cycling distance, flights climbed, daylight, sleep

## Usage

```bash
# Today's summary (JSON)
python3 ~/clawcode/scripts/health-summary.py

# Today's summary (human-readable)
python3 ~/clawcode/scripts/health-summary.py --format text

# Specific date
python3 ~/clawcode/scripts/health-summary.py 2026-02-23 --format text

# Last 7 days
python3 ~/clawcode/scripts/health-summary.py --days 7 --format text

# With anomaly detection (compares against 7-day baseline)
python3 ~/clawcode/scripts/health-summary.py --format text --anomalies
```

## Anomaly Detection

`--anomalies` checks today against a 7-day rolling baseline:
- **Resting HR:** flags if >10% above 7-day average
- **Sleep:** flags if <6 hours total
- **Exercise:** flags if 0 minutes for 3+ consecutive days

## Interpreting Results

- `—` means no data for that metric (common for sleep if Watch wasn't worn, or cycling if Scott didn't ride)
- Heart rate shows min/avg/max across all samples for the day
- Active calories = movement only (excludes basal metabolic rate)
- Exercise minutes = Apple's auto-detected exercise (green ring)
- Stand hours = hours with 1+ minute of standing (max 24)

## Multi-Day Trends

For trend questions ("am I exercising enough this week?", "how's my sleep been?"), use `--days 7` or `--days 14`. Compare values across days rather than relying on a single day.

## Limitations

- Data depends on Health Auto Export app syncing reliably — if a day is missing, the app may need to be opened on the phone
- Sleep data can be sparse if Scott doesn't wear the Watch to bed
- No real-time data — export happens periodically, not instantly
- No write access — read-only health data
