"""Object-to-dict converter functions for Canvas API objects."""

from canvas_cli.config import CANVAS_URL
from canvas_cli.output import format_datetime, html_to_text


def course_to_dict(course, detailed=False):
    """Convert course object to dictionary."""
    result = {
        "id": course.id,
        "name": course.name,
        "code": getattr(course, 'course_code', None),
        "term": getattr(course, 'term', {}).get('name') if hasattr(course, 'term') else None,
        "start_at": format_datetime(getattr(course, 'start_at', None)),
        "end_at": format_datetime(getattr(course, 'end_at', None)),
    }
    if detailed:
        result.update({
            "workflow_state": getattr(course, 'workflow_state', None),
            "default_view": getattr(course, 'default_view', None),
            "syllabus_body": html_to_text(getattr(course, 'syllabus_body', None)),
            "needs_grading_count": getattr(course, 'needs_grading_count', None),
            "enrollment_term_id": getattr(course, 'enrollment_term_id', None),
            "html_url": f"{CANVAS_URL}/courses/{course.id}",
        })
    return result


def assignment_to_dict(assignment, include_description=False):
    """Convert assignment object to dictionary."""
    # Derive submission status from the included submission object if available,
    # rather than trusting has_submitted_submissions (which returns stale/cached data).
    submission = getattr(assignment, 'submission', None)
    if isinstance(submission, dict):
        workflow = submission.get('workflow_state', 'unsubmitted')
        submitted = workflow not in ('unsubmitted', None)
        graded = workflow == 'graded'
        score = submission.get('score')
        grade = submission.get('grade')
    else:
        submitted = getattr(assignment, 'has_submitted_submissions', False)
        graded = getattr(assignment, 'graded_submissions_exist', False)
        score = None
        grade = None

    result = {
        "id": assignment.id,
        "name": assignment.name,
        "course_id": assignment.course_id,
        "due_at": format_datetime(getattr(assignment, 'due_at', None)),
        "unlock_at": format_datetime(getattr(assignment, 'unlock_at', None)),
        "lock_at": format_datetime(getattr(assignment, 'lock_at', None)),
        "points_possible": getattr(assignment, 'points_possible', None),
        "submission_types": getattr(assignment, 'submission_types', []),
        "submitted": submitted,
        "graded": graded,
        "score": score,
        "grade": grade,
        "workflow_state": workflow if isinstance(submission, dict) else None,
        "html_url": getattr(assignment, 'html_url', None),
    }
    if include_description:
        result["description"] = html_to_text(getattr(assignment, 'description', None))
        result["description_html"] = getattr(assignment, 'description', None)
    return result


def submission_to_dict(submission, include_comments=False):
    """Convert submission object to dictionary."""
    result = {
        "id": getattr(submission, 'id', None),
        "assignment_id": submission.assignment_id,
        "user_id": getattr(submission, 'user_id', None),
        "score": getattr(submission, 'score', None),
        "grade": getattr(submission, 'grade', None),
        "submitted_at": format_datetime(getattr(submission, 'submitted_at', None)),
        "graded_at": format_datetime(getattr(submission, 'graded_at', None)),
        "late": getattr(submission, 'late', False),
        "missing": getattr(submission, 'missing', False),
        "excused": getattr(submission, 'excused', False),
        "workflow_state": getattr(submission, 'workflow_state', None),
        "attempt": getattr(submission, 'attempt', None),
        "body": html_to_text(getattr(submission, 'body', None)),
        "preview_url": getattr(submission, 'preview_url', None),
    }
    if include_comments:
        comments = getattr(submission, 'submission_comments', [])
        result['comments'] = [{
            'author': c.get('author_name'),
            'comment': c.get('comment'),
            'created_at': format_datetime(c.get('created_at')),
        } for c in comments]
    return result


def discussion_to_dict(topic, include_entries=False):
    """Convert discussion topic to dictionary."""
    return {
        "id": topic.id,
        "title": topic.title,
        "posted_at": format_datetime(getattr(topic, 'posted_at', None)),
        "last_reply_at": format_datetime(getattr(topic, 'last_reply_at', None)),
        "discussion_type": getattr(topic, 'discussion_type', None),
        "message": html_to_text(getattr(topic, 'message', None)),
        "author": getattr(topic, 'author', {}).get('display_name') if hasattr(topic, 'author') else None,
        "published": getattr(topic, 'published', None),
        "locked": getattr(topic, 'locked', False),
        "pinned": getattr(topic, 'pinned', False),
        "html_url": getattr(topic, 'html_url', None),
        "unread_count": getattr(topic, 'unread_count', 0),
        "discussion_subentry_count": getattr(topic, 'discussion_subentry_count', 0),
    }


def entry_to_dict(entry, depth=0):
    """Convert discussion entry to dictionary."""
    result = {
        "id": entry.id,
        "user_name": getattr(entry, 'user_name', None),
        "message": html_to_text(getattr(entry, 'message', None)),
        "created_at": format_datetime(getattr(entry, 'created_at', None)),
        "depth": depth,
    }
    replies = getattr(entry, 'recent_replies', []) or getattr(entry, 'replies', [])
    if replies:
        result['replies'] = [entry_to_dict(type('Entry', (), r)(), depth+1) for r in replies]
    return result


def page_to_dict(page, include_body=False):
    """Convert wiki page to dictionary."""
    result = {
        "url": page.url,
        "title": page.title,
        "created_at": format_datetime(getattr(page, 'created_at', None)),
        "updated_at": format_datetime(getattr(page, 'updated_at', None)),
        "published": getattr(page, 'published', None),
        "front_page": getattr(page, 'front_page', False),
        "html_url": getattr(page, 'html_url', None),
    }
    if include_body:
        result["body"] = html_to_text(getattr(page, 'body', None))
        result["body_html"] = getattr(page, 'body', None)
    return result


def quiz_to_dict(quiz, include_details=False):
    """Convert quiz to dictionary."""
    result = {
        "id": quiz.id,
        "title": quiz.title,
        "quiz_type": getattr(quiz, 'quiz_type', None),
        "points_possible": getattr(quiz, 'points_possible', None),
        "time_limit": getattr(quiz, 'time_limit', None),
        "due_at": format_datetime(getattr(quiz, 'due_at', None)),
        "unlock_at": format_datetime(getattr(quiz, 'unlock_at', None)),
        "lock_at": format_datetime(getattr(quiz, 'lock_at', None)),
        "published": getattr(quiz, 'published', None),
        "question_count": getattr(quiz, 'question_count', None),
        "html_url": getattr(quiz, 'html_url', None),
    }
    if include_details:
        result["description"] = html_to_text(getattr(quiz, 'description', None))
        result["allowed_attempts"] = getattr(quiz, 'allowed_attempts', None)
        result["scoring_policy"] = getattr(quiz, 'scoring_policy', None)
        result["show_correct_answers"] = getattr(quiz, 'show_correct_answers', None)
    return result


def module_to_dict(module):
    """Convert module to dictionary."""
    return {
        "id": module.id,
        "name": module.name,
        "position": getattr(module, 'position', None),
        "state": getattr(module, 'state', None),
        "items_count": getattr(module, 'items_count', 0),
        "unlock_at": format_datetime(getattr(module, 'unlock_at', None)),
        "completed_at": format_datetime(getattr(module, 'completed_at', None)),
    }


def module_item_to_dict(item):
    """Convert module item to dictionary."""
    return {
        "id": item.id,
        "title": item.title,
        "type": getattr(item, 'type', None),
        "position": getattr(item, 'position', None),
        "content_id": getattr(item, 'content_id', None),
        "html_url": getattr(item, 'html_url', None),
        "url": getattr(item, 'url', None),
        "external_url": getattr(item, 'external_url', None),
        "completion_requirement": getattr(item, 'completion_requirement', None),
        "published": getattr(item, 'published', None),
    }


def file_to_dict(f):
    """Convert file to dictionary."""
    return {
        "id": f.id,
        "name": getattr(f, 'display_name', getattr(f, 'filename', None)),
        "folder_id": getattr(f, 'folder_id', None),
        "size": getattr(f, 'size', None),
        "content_type": getattr(f, 'content_type', None) or getattr(f, 'mime_class', None),
        "url": getattr(f, 'url', None),
        "created_at": format_datetime(getattr(f, 'created_at', None)),
        "updated_at": format_datetime(getattr(f, 'updated_at', None)),
        "locked": getattr(f, 'locked', False),
        "hidden": getattr(f, 'hidden', False),
    }


def folder_to_dict(folder):
    """Convert folder to dictionary."""
    return {
        "id": folder.id,
        "name": folder.name,
        "full_name": getattr(folder, 'full_name', None),
        "parent_folder_id": getattr(folder, 'parent_folder_id', None),
        "files_count": getattr(folder, 'files_count', 0),
        "folders_count": getattr(folder, 'folders_count', 0),
        "created_at": format_datetime(getattr(folder, 'created_at', None)),
        "updated_at": format_datetime(getattr(folder, 'updated_at', None)),
        "locked": getattr(folder, 'locked', False),
        "hidden": getattr(folder, 'hidden', False),
    }


def user_to_dict(user):
    """Convert user to dictionary."""
    return {
        "id": user.id,
        "name": user.name,
        "sortable_name": getattr(user, 'sortable_name', None),
        "short_name": getattr(user, 'short_name', None),
        "email": getattr(user, 'email', None),
        "login_id": getattr(user, 'login_id', None),
        "avatar_url": getattr(user, 'avatar_url', None),
    }


def enrollment_to_dict(enrollment):
    """Convert enrollment to dictionary (for people list)."""
    user = getattr(enrollment, 'user', {})
    return {
        "user_id": enrollment.user_id,
        "name": user.get('name') if isinstance(user, dict) else getattr(user, 'name', None),
        "sortable_name": user.get('sortable_name') if isinstance(user, dict) else getattr(user, 'sortable_name', None),
        "role": getattr(enrollment, 'role', None),
        "enrollment_state": getattr(enrollment, 'enrollment_state', None),
        "type": getattr(enrollment, 'type', None),
    }


def group_to_dict(group):
    """Convert group to dictionary."""
    return {
        "id": group.id,
        "name": group.name,
        "description": getattr(group, 'description', None),
        "members_count": getattr(group, 'members_count', None),
        "context_type": getattr(group, 'context_type', None),
        "course_id": getattr(group, 'course_id', None),
        "html_url": getattr(group, 'html_url', None),
    }


def conversation_to_dict(conv, include_messages=False):
    """Convert conversation to dictionary."""
    result = {
        "id": conv.id,
        "subject": getattr(conv, 'subject', None),
        "workflow_state": getattr(conv, 'workflow_state', None),
        "last_message": getattr(conv, 'last_message', None),
        "last_message_at": format_datetime(getattr(conv, 'last_message_at', None)),
        "message_count": getattr(conv, 'message_count', None),
        "participants": [p.get('name') for p in getattr(conv, 'participants', [])],
        "context_name": getattr(conv, 'context_name', None),
    }
    if include_messages:
        messages = getattr(conv, 'messages', [])
        result['messages'] = [{
            'id': m.get('id'),
            'author_id': m.get('author_id'),
            'body': m.get('body'),
            'created_at': format_datetime(m.get('created_at')),
            'participating_user_ids': m.get('participating_user_ids', []),
        } for m in messages]
    return result


def announcement_to_dict(announcement):
    """Convert announcement object to dictionary."""
    return {
        "id": announcement.id,
        "title": announcement.title,
        "posted_at": format_datetime(getattr(announcement, 'posted_at', None)),
        "message": html_to_text(getattr(announcement, 'message', None)),
        "author": getattr(announcement, 'author', {}).get('display_name') if hasattr(announcement, 'author') else None,
        "html_url": getattr(announcement, 'html_url', None),
    }
