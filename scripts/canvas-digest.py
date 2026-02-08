#!/usr/bin/env python3
"""
Canvas Digest Generator
Outputs a markdown section for the daily digest with:
- Assignments due in next 7 days (flagged if unsubmitted)
- Discussion status (unread count, reply requirements)
- Recent announcements (last 3 days)
- Current grade

Designed to be compact for token efficiency.
"""

import os
import sys
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

try:
    from canvasapi import Canvas
    from canvasapi.exceptions import Unauthorized, ResourceDoesNotExist
except ImportError:
    print("Error: canvasapi not installed", file=sys.stderr)
    sys.exit(1)

# Configuration
CANVAS_URL = "https://newmanu.instructure.com"
TOKEN_FILE = Path.home() / ".config" / "canvas" / "token"
DAYS_AHEAD = 10
ANNOUNCEMENT_DAYS = 3

# Active course - Data Engineering
ACTIVE_COURSE_ID = 13684


def get_token():
    token = os.environ.get("CANVAS_TOKEN")
    if token:
        return token.strip()
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()
    return None


def format_date(dt_str):
    """Format ISO datetime to readable format (in local timezone)."""
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        local_dt = dt.astimezone()  # Convert to local timezone
        return local_dt.strftime("%b %d")
    except Exception:
        return dt_str


def days_until(dt_str):
    """Calculate days until a due date."""
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        now = datetime.now().astimezone()
        delta = dt - now
        return delta.days
    except Exception:
        return None


def html_to_text(html):
    """Strip HTML tags for plain text."""
    if not html:
        return ""
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def truncate(text, max_len=150):
    """Truncate text with ellipsis."""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len-3] + "..."


def main():
    token = get_token()
    if not token:
        print("## Canvas")
        print("No Canvas token configured")
        return

    try:
        canvas = Canvas(CANVAS_URL, token)
        user = canvas.get_current_user()
        course = canvas.get_course(ACTIVE_COURSE_ID)
    except Exception as e:
        print("## Canvas")
        print(f"Canvas connection error: {e}")
        return

    course_name = course.name

    # === GRADE ===
    current_grade = None
    try:
        enrollments = list(user.get_enrollments(type=['StudentEnrollment']))
        for enrollment in enrollments:
            if enrollment.course_id == ACTIVE_COURSE_ID:
                grades = getattr(enrollment, 'grades', {})
                current_grade = grades.get('current_score')
                break
    except Exception:
        pass

    # === ASSIGNMENTS DUE SOON ===
    assignments_section = []
    now = datetime.now().astimezone()
    cutoff = now + timedelta(days=DAYS_AHEAD)

    try:
        assignments = course.get_assignments(order_by='due_at', include=['submission'])
        for a in assignments:
            due_at = getattr(a, 'due_at', None)
            if not due_at:
                continue

            try:
                due = datetime.fromisoformat(due_at.replace('Z', '+00:00'))
                if due < now or due > cutoff:
                    continue
            except Exception:
                continue

            submission = getattr(a, 'submission', {})
            workflow = submission.get('workflow_state', 'unsubmitted') if submission else 'unsubmitted'
            submitted = workflow not in ['unsubmitted', None]

            days = days_until(due_at)
            days_str = f"{days}d" if days is not None else ""

            status = "done" if submitted else "TODO"
            url = getattr(a, 'html_url', '')

            assignments_section.append({
                'name': a.name,
                'due': format_date(due_at),
                'days': days_str,
                'status': status,
                'submitted': submitted,
                'url': url,
            })
    except Exception as e:
        assignments_section = [{'error': str(e)}]

    # === DISCUSSIONS ===
    discussions_section = []
    total_unread = 0

    try:
        topics = course.get_discussion_topics()
        for t in topics:
            unread = getattr(t, 'unread_count', 0) or 0
            total_unread += unread

            if unread > 0:
                url = getattr(t, 'html_url', '')
                discussions_section.append({
                    'title': t.title,
                    'unread': unread,
                    'url': url,
                })
    except Exception:
        pass

    # === ANNOUNCEMENTS (last N days) ===
    announcements_section = []
    announcement_cutoff = now - timedelta(days=ANNOUNCEMENT_DAYS)

    try:
        ann_topics = course.get_discussion_topics(only_announcements=True)
        for a in ann_topics:
            posted_at = getattr(a, 'posted_at', None)
            if posted_at:
                try:
                    posted = datetime.fromisoformat(posted_at.replace('Z', '+00:00'))
                    if posted < announcement_cutoff:
                        continue
                except Exception:
                    continue

            message = html_to_text(getattr(a, 'message', ''))
            url = getattr(a, 'html_url', '')

            announcements_section.append({
                'title': a.title,
                'date': format_date(posted_at),
                'summary': truncate(message, 120),
                'url': url,
            })

            if len(announcements_section) >= 3:
                break
    except Exception:
        pass

    # === OUTPUT ===
    print(f"## {course_name}")
    if current_grade is not None:
        print(f"**Grade:** {current_grade}%")
    print()

    # Assignments
    unsubmitted = [a for a in assignments_section if not a.get('submitted', True) and 'error' not in a]
    if assignments_section and 'error' not in assignments_section[0]:
        print(f"### Due Soon ({len(assignments_section)} items)")
        for a in assignments_section:
            if 'error' in a:
                print(f"- Error: {a['error']}")
            else:
                line = f"- {a['status']} **{a['name']}** — {a['due']} ({a['days']})"
                if a['url']:
                    line += f" [link]({a['url']})"
                print(line)
        if unsubmitted:
            print(f"\n**{len(unsubmitted)} unsubmitted**")
    else:
        print("### Due Soon")
        print("- None in next 7 days")
    print()

    # Discussions
    if discussions_section or total_unread > 0:
        print("### Discussions")
        if total_unread > 0:
            print(f"**{total_unread} unread** replies")
            for d in discussions_section:
                line = f"- {d['title']} ({d['unread']} new)"
                if d['url']:
                    line += f" [link]({d['url']})"
                print(line)
        else:
            print("- All caught up")
    print()

    # Announcements
    if announcements_section:
        print("### Recent Announcements")
        for a in announcements_section:
            line = f"- **{a['title']}** ({a['date']})"
            if a['url']:
                line += f" [link]({a['url']})"
            print(line)
            if a['summary']:
                print(f"  _{a['summary']}_")

    print()


if __name__ == '__main__':
    main()
