"""Canvas API client initialization."""

import sys
from datetime import datetime

try:
    from canvasapi import Canvas
    from canvasapi.exceptions import Unauthorized, ResourceDoesNotExist
except ImportError:
    print("Error: canvasapi not installed. Run: pip3 install canvasapi", file=sys.stderr)
    sys.exit(1)

from canvas_cli.config import CANVAS_URL, get_token


def get_canvas():
    """Initialize Canvas API client."""
    token = get_token()
    return Canvas(CANVAS_URL, token)


def get_courses_list(canvas, course_id=None):
    """Get courses list, or single course if ID provided."""
    user = canvas.get_current_user()
    if course_id:
        return [canvas.get_course(course_id)]
    now = datetime.now().astimezone()
    courses = []
    for course in user.get_courses(enrollment_state='active'):
        end_at = getattr(course, 'end_at', None)
        if end_at:
            try:
                end = datetime.fromisoformat(end_at.replace('Z', '+00:00'))
                if end < now:
                    continue
            except Exception:
                pass
        courses.append(course)
    return courses
