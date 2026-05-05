#!/usr/bin/env python3
"""
Aggregate Health Auto Export data into a daily summary.

Reads: ~/Library/Mobile Documents/iCloud~com~ifunography~HealthExport/Documents/NormalExport/
Outputs: JSON summary to stdout, or formatted text with --format text.

Usage:
    python3 health-summary.py                  # today's summary as JSON
    python3 health-summary.py 2026-02-22       # specific date
    python3 health-summary.py --days 7         # last 7 days
    python3 health-summary.py --format text    # human-readable output
    python3 health-summary.py --anomalies      # check for anomalies against 7-day baseline
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

EXPORT_DIR = Path.home() / "Library/Mobile Documents/iCloud~com~ifunography~HealthExport/Documents/NormalExport"
ICLOUD_READ = Path(__file__).parent / "icloud-read.swift"


def load_day(date_str):
    """Load a single day's export file. Returns None if not found.

    Uses NSFileCoordinator (via icloud-read.swift) to properly coordinate
    with iCloud and avoid deadlocks (OSError: [Errno 11]).
    Falls back to direct read if the helper isn't available.
    """
    path = EXPORT_DIR / f"HealthAutoExport-{date_str}.json"
    if not path.exists():
        return None
    # Primary: use NSFileCoordinator via Swift helper
    if ICLOUD_READ.exists():
        try:
            result = subprocess.run(
                ["swift", str(ICLOUD_READ), str(path)],
                capture_output=True, timeout=30
            )
            if result.returncode == 0 and result.stdout:
                return json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            pass
    # Fallback: direct read (may deadlock on iCloud files)
    try:
        with open(path) as f:
            return json.load(f)
    except OSError:
        return None


def get_metric(data, name):
    """Extract a metric by name from the export data."""
    for m in data["data"]["metrics"]:
        if m["name"] == name:
            return m
    return None


def sum_qty(metric):
    """Sum the qty field across all samples."""
    if not metric:
        return None
    samples = metric.get("data", [])
    if not samples:
        return None
    return round(sum(s.get("qty", 0) for s in samples), 1)


def avg_qty(metric):
    """Average the qty field across all samples."""
    if not metric:
        return None
    samples = metric.get("data", [])
    if not samples:
        return None
    return round(sum(s.get("qty", 0) for s in samples) / len(samples), 1)


def hr_stats(metric):
    """Get heart rate min/avg/max from samples with Min/Avg/Max fields."""
    if not metric:
        return None
    samples = metric.get("data", [])
    if not samples:
        return None

    all_min = [s["Min"] for s in samples if "Min" in s]
    all_avg = [s["Avg"] for s in samples if "Avg" in s]
    all_max = [s["Max"] for s in samples if "Max" in s]

    if not all_avg:
        return None

    return {
        "min": round(min(all_min), 0) if all_min else None,
        "avg": round(sum(all_avg) / len(all_avg), 0) if all_avg else None,
        "max": round(max(all_max), 0) if all_max else None,
        "samples": len(samples),
    }


def sleep_summary(metric):
    """Extract sleep data from sleep_analysis metric."""
    if not metric:
        return None
    samples = metric.get("data", [])
    if not samples:
        return None

    total_sleep = sum(s.get("totalSleep", 0) for s in samples)
    rem = sum(s.get("rem", 0) for s in samples)
    core = sum(s.get("core", 0) for s in samples)
    awake = sum(s.get("awake", 0) for s in samples)

    return {
        "total_hours": round(total_sleep, 1),
        "rem_hours": round(rem, 1),
        "core_hours": round(core, 1),
        "awake_hours": round(awake, 1),
    }


def summarize_day(date_str):
    """Produce a summary dict for a single day."""
    data = load_day(date_str)
    if not data:
        return None

    hr = hr_stats(get_metric(data, "heart_rate"))
    sleep = sleep_summary(get_metric(data, "sleep_analysis"))

    return {
        "date": date_str,
        "steps": sum_qty(get_metric(data, "step_count")),
        "active_calories": sum_qty(get_metric(data, "active_energy")),
        "exercise_minutes": sum_qty(get_metric(data, "apple_exercise_time")),
        "heart_rate": hr,
        "resting_heart_rate": avg_qty(get_metric(data, "resting_heart_rate")),
        "stand_hours": sum_qty(get_metric(data, "apple_stand_hour")),
        "walking_distance_mi": sum_qty(get_metric(data, "walking_running_distance")),
        "cycling_distance_mi": sum_qty(get_metric(data, "cycling_distance")),
        "flights_climbed": sum_qty(get_metric(data, "flights_climbed")),
        "blood_oxygen_pct": avg_qty(get_metric(data, "blood_oxygen_saturation")),
        "hrv_ms": avg_qty(get_metric(data, "heart_rate_variability")),
        "sleep": sleep,
        "daylight_minutes": sum_qty(get_metric(data, "time_in_daylight")),
    }


def check_anomalies(today_summary, baseline_days=7):
    """Check today's data against a 7-day baseline. Returns list of anomaly strings."""
    anomalies = []
    today_date = datetime.strptime(today_summary["date"], "%Y-%m-%d")

    # Gather baseline
    resting_hrs = []
    exercise_days_with_data = []
    sleep_hours = []

    for i in range(1, baseline_days + 1):
        d = (today_date - timedelta(days=i)).strftime("%Y-%m-%d")
        s = summarize_day(d)
        if not s:
            continue
        if s["resting_heart_rate"] is not None:
            resting_hrs.append(s["resting_heart_rate"])
        exercise_days_with_data.append(s.get("exercise_minutes"))
        if s["sleep"] and s["sleep"]["total_hours"] > 0:
            sleep_hours.append(s["sleep"]["total_hours"])

    # Resting HR anomaly: >10% above 7-day average
    if today_summary["resting_heart_rate"] and resting_hrs:
        avg_rhr = sum(resting_hrs) / len(resting_hrs)
        if today_summary["resting_heart_rate"] > avg_rhr * 1.1:
            anomalies.append(
                f"Resting HR elevated: {today_summary['resting_heart_rate']} bpm "
                f"(7-day avg: {avg_rhr:.0f} bpm, +{((today_summary['resting_heart_rate'] / avg_rhr) - 1) * 100:.0f}%)"
            )

    # Sleep anomaly: <6h
    if today_summary["sleep"] and today_summary["sleep"]["total_hours"] < 6:
        anomalies.append(
            f"Low sleep: {today_summary['sleep']['total_hours']} hours"
        )

    # Exercise drought: 3+ consecutive days with 0 or no exercise
    recent_exercise = []
    for i in range(3):
        d = (today_date - timedelta(days=i)).strftime("%Y-%m-%d")
        s = summarize_day(d) if i > 0 else today_summary
        ex = s.get("exercise_minutes") if s else None
        recent_exercise.append(ex)

    if all(e is None or e == 0 for e in recent_exercise):
        anomalies.append("No exercise logged for 3+ consecutive days")

    return anomalies


def format_text(summary, anomalies=None):
    """Format summary as human-readable text."""
    lines = [f"Health Summary — {summary['date']}", ""]

    def val(v, unit=""):
        if v is None:
            return "—"
        return f"{v}{unit}"

    lines.append(f"Steps:            {val(summary['steps'])}")
    lines.append(f"Active Calories:  {val(summary['active_calories'], ' kcal')}")
    lines.append(f"Exercise:         {val(summary['exercise_minutes'], ' min')}")

    hr = summary.get("heart_rate")
    if hr:
        lines.append(f"Heart Rate:       {hr['min']:.0f}/{hr['avg']:.0f}/{hr['max']:.0f} bpm (min/avg/max, {hr['samples']} samples)")
    else:
        lines.append(f"Heart Rate:       —")

    lines.append(f"Resting HR:       {val(summary['resting_heart_rate'], ' bpm')}")
    lines.append(f"HRV:              {val(summary['hrv_ms'], ' ms')}")
    lines.append(f"Blood O2:         {val(summary['blood_oxygen_pct'], '%')}")
    lines.append(f"Stand Hours:      {val(summary['stand_hours'])}")
    lines.append(f"Walking:          {val(summary['walking_distance_mi'], ' mi')}")
    lines.append(f"Cycling:          {val(summary['cycling_distance_mi'], ' mi')}")
    lines.append(f"Flights Climbed:  {val(summary['flights_climbed'])}")
    lines.append(f"Daylight:         {val(summary['daylight_minutes'], ' min')}")

    sleep = summary.get("sleep")
    if sleep and sleep["total_hours"] > 0:
        lines.append(f"Sleep:            {sleep['total_hours']} hrs (core: {sleep['core_hours']}, REM: {sleep['rem_hours']}, awake: {sleep['awake_hours']})")
    else:
        lines.append(f"Sleep:            —")

    if anomalies:
        lines.append("")
        lines.append("ANOMALIES:")
        for a in anomalies:
            lines.append(f"  ⚠ {a}")

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Health Auto Export daily summary")
    parser.add_argument("date", nargs="?", default=datetime.now().strftime("%Y-%m-%d"),
                        help="Date to summarize (YYYY-MM-DD, default: today)")
    parser.add_argument("--days", type=int, default=1, help="Number of days to summarize")
    parser.add_argument("--format", choices=["json", "text"], default="json", help="Output format")
    parser.add_argument("--anomalies", action="store_true", help="Check for anomalies")

    args = parser.parse_args()

    target = datetime.strptime(args.date, "%Y-%m-%d")
    summaries = []

    for i in range(args.days):
        d = (target - timedelta(days=i)).strftime("%Y-%m-%d")
        s = summarize_day(d)
        if s:
            summaries.append(s)

    if not summaries:
        print(f"No health data found.", file=sys.stderr)
        sys.exit(1)

    if args.days == 1:
        summary = summaries[0]
        anomalies = check_anomalies(summary) if args.anomalies else None

        if args.format == "json":
            output = summary
            if anomalies:
                output["anomalies"] = anomalies
            print(json.dumps(output, indent=2))
        else:
            print(format_text(summary, anomalies))
    else:
        if args.format == "json":
            print(json.dumps(summaries, indent=2))
        else:
            for s in summaries:
                anomalies = check_anomalies(s) if args.anomalies else None
                print(format_text(s, anomalies))
                print()


if __name__ == "__main__":
    main()
