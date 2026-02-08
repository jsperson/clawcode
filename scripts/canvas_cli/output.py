"""Output formatting utilities."""

import json
import re
from datetime import datetime
from html.parser import HTMLParser


class HTMLTextExtractor(HTMLParser):
    """Extract plain text from HTML."""
    def __init__(self):
        super().__init__()
        self.text = []

    def handle_data(self, data):
        self.text.append(data)

    def get_text(self):
        return ' '.join(self.text).strip()


def html_to_text(html):
    """Convert HTML to plain text."""
    if not html:
        return None
    try:
        parser = HTMLTextExtractor()
        parser.feed(html)
        text = parser.get_text()
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    except Exception:
        return html


def format_datetime(dt_str):
    """Format ISO datetime string to readable format (converted to local timezone)."""
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        dt_local = dt.astimezone()
        return dt_local.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return dt_str


def output(data):
    """Output data as JSON."""
    print(json.dumps(data, indent=2, default=str))
