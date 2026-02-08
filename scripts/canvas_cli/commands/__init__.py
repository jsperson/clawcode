"""Command registration for Canvas CLI."""

from canvas_cli.commands import (
    courses,
    assignments,
    submissions,
    discussions,
    announcements,
    pages,
    quizzes,
    modules,
    files,
    groups,
    conversations,
    calendar,
    enrollments,
    user,
    utility,
)


def register_all(subparsers):
    """Register all command modules with the argument parser."""
    courses.register(subparsers)
    assignments.register(subparsers)
    submissions.register(subparsers)
    discussions.register(subparsers)
    announcements.register(subparsers)
    pages.register(subparsers)
    quizzes.register(subparsers)
    modules.register(subparsers)
    files.register(subparsers)
    groups.register(subparsers)
    conversations.register(subparsers)
    calendar.register(subparsers)
    enrollments.register(subparsers)
    user.register(subparsers)
    utility.register(subparsers)
