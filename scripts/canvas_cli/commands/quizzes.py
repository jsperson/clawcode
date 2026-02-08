"""Quiz commands."""

import sys
import json
from canvasapi.exceptions import ResourceDoesNotExist

from canvas_cli.client import get_canvas, get_courses_list
from canvas_cli.output import output
from canvas_cli.converters import quiz_to_dict
from canvas_cli.input_helpers import (
    add_body_args, resolve_body, confirm_destructive, write_result,
)


def register(subparsers):
    p = subparsers.add_parser('quizzes', help='List quizzes')
    p.add_argument('--course', type=int, help='Filter by course ID')
    p.set_defaults(func=cmd_quizzes)

    p = subparsers.add_parser('quiz', help='Get quiz details')
    p.add_argument('id', type=int, help='Quiz ID')
    p.set_defaults(func=cmd_quiz)

    p = subparsers.add_parser('create-quiz', help='Create a quiz')
    p.add_argument('--course', type=int, required=True, help='Course ID')
    p.add_argument('--title', type=str, required=True)
    p.add_argument('--quiz-type', type=str,
                   choices=['practice_quiz', 'assignment', 'graded_survey', 'survey'],
                   default='assignment')
    p.add_argument('--time-limit', type=int, help='Time limit in minutes')
    p.add_argument('--allowed-attempts', type=int, default=1)
    p.add_argument('--due-at', type=str)
    p.add_argument('--points-possible', type=float)
    p.add_argument('--published', action='store_true', default=False)
    add_body_args(p, 'description')
    p.set_defaults(func=cmd_create_quiz)

    p = subparsers.add_parser('edit-quiz', help='Edit a quiz')
    p.add_argument('course_id', type=int)
    p.add_argument('quiz_id', type=int)
    p.add_argument('--title', type=str)
    p.add_argument('--time-limit', type=int)
    p.add_argument('--due-at', type=str)
    p.add_argument('--published', type=str, choices=['true', 'false'])
    add_body_args(p, 'description')
    p.set_defaults(func=cmd_edit_quiz)

    p = subparsers.add_parser('delete-quiz', help='Delete a quiz')
    p.add_argument('course_id', type=int)
    p.add_argument('quiz_id', type=int)
    p.add_argument('--yes', '-y', action='store_true')
    p.set_defaults(func=cmd_delete_quiz)

    p = subparsers.add_parser('create-quiz-question', help='Create a quiz question')
    p.add_argument('course_id', type=int)
    p.add_argument('quiz_id', type=int)
    p.add_argument('--question-name', type=str, required=True)
    p.add_argument('--question-type', type=str, required=True,
                   choices=['multiple_choice_question', 'true_false_question',
                            'short_answer_question', 'essay_question',
                            'fill_in_multiple_blanks_question',
                            'matching_question', 'numerical_question',
                            'multiple_answers_question'])
    p.add_argument('--question-text', type=str, required=True)
    p.add_argument('--points-possible', type=float, default=1.0)
    p.add_argument('--answers', type=str, help='JSON array of answer objects')
    p.set_defaults(func=cmd_create_quiz_question)

    p = subparsers.add_parser('start-quiz', help='Start a quiz attempt')
    p.add_argument('course_id', type=int)
    p.add_argument('quiz_id', type=int)
    p.set_defaults(func=cmd_start_quiz)

    p = subparsers.add_parser('update-quiz-scores',
                              help='Update quiz submission scores')
    p.add_argument('course_id', type=int)
    p.add_argument('quiz_id', type=int)
    p.add_argument('submission_id', type=int)
    p.add_argument('--questions', type=str, required=True,
                   help='JSON object: {"question_id": {"score": N, "comment": "..."}}')
    p.set_defaults(func=cmd_update_quiz_scores)


def cmd_quizzes(args):
    """List quizzes."""
    canvas = get_canvas()
    courses = get_courses_list(canvas, args.course)

    result = []
    for course in courses:
        try:
            quizzes = course.get_quizzes()
            for q in quizzes:
                qdict = quiz_to_dict(q)
                qdict['course_id'] = course.id
                qdict['course_name'] = course.name
                result.append(qdict)
        except Exception:
            pass

    result.sort(key=lambda x: x.get('due_at') or '9999')
    output(result)


def cmd_quiz(args):
    """Get quiz details."""
    canvas = get_canvas()
    user = canvas.get_current_user()

    for course in user.get_courses(enrollment_state='active'):
        try:
            quiz = course.get_quiz(args.id)
            result = quiz_to_dict(quiz, include_details=True)
            result['course_name'] = course.name
            output(result)
            return
        except ResourceDoesNotExist:
            continue
        except Exception:
            continue

    print(f"Error: Quiz {args.id} not found", file=sys.stderr)
    sys.exit(1)


def cmd_create_quiz(args):
    """Create a quiz in a course."""
    canvas = get_canvas()
    course = canvas.get_course(args.course)
    kwargs = {
        'title': args.title,
        'quiz_type': args.quiz_type,
        'published': args.published,
        'allowed_attempts': args.allowed_attempts,
    }
    if args.time_limit is not None:
        kwargs['time_limit'] = args.time_limit
    if args.due_at:
        kwargs['due_at'] = args.due_at
    if args.points_possible is not None:
        kwargs['points_possible'] = args.points_possible
    desc = resolve_body(args, 'description')
    if desc:
        kwargs['description'] = desc
    quiz = course.create_quiz(quiz=kwargs)
    write_result("created", quiz.id, quiz.title)


def cmd_edit_quiz(args):
    """Edit a quiz."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    quiz = course.get_quiz(args.quiz_id)
    kwargs = {}
    if args.title:
        kwargs['title'] = args.title
    if args.time_limit is not None:
        kwargs['time_limit'] = args.time_limit
    if args.due_at:
        kwargs['due_at'] = args.due_at
    if args.published is not None:
        kwargs['published'] = args.published == 'true'
    desc = resolve_body(args, 'description')
    if desc:
        kwargs['description'] = desc
    if not kwargs:
        print("Error: No update fields provided.", file=sys.stderr)
        sys.exit(1)
    quiz.edit(quiz=kwargs)
    write_result("updated", quiz.id, quiz.title)


def cmd_delete_quiz(args):
    """Delete a quiz."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    quiz = course.get_quiz(args.quiz_id)
    if not confirm_destructive(f"delete quiz '{quiz.title}' (ID {quiz.id})", args):
        print("Cancelled.", file=sys.stderr)
        sys.exit(0)
    quiz.delete()
    write_result("deleted", quiz.id, quiz.title)


def cmd_create_quiz_question(args):
    """Create a question in a quiz."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    quiz = course.get_quiz(args.quiz_id)
    question = {
        'question_name': args.question_name,
        'question_type': args.question_type,
        'question_text': args.question_text,
        'points_possible': args.points_possible,
    }
    if args.answers:
        question['answers'] = json.loads(args.answers)
    result = quiz.create_question(question=question)
    write_result("created", getattr(result, 'id', None), args.question_name)


def cmd_start_quiz(args):
    """Start a quiz attempt (create submission)."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    quiz = course.get_quiz(args.quiz_id)
    submission = quiz.create_submission()
    write_result("started", getattr(submission, 'id', None), quiz.title,
                 attempt=getattr(submission, 'attempt', None),
                 validation_token=getattr(submission, 'validation_token', None))


def cmd_update_quiz_scores(args):
    """Update scores and comments for a quiz submission."""
    canvas = get_canvas()
    course = canvas.get_course(args.course_id)
    quiz = course.get_quiz(args.quiz_id)
    questions_data = json.loads(args.questions)
    quiz_submissions = [{'id': args.submission_id, 'questions': questions_data}]
    result = quiz.set_extensions(quiz_submissions)
    write_result("updated_scores", args.submission_id, quiz.title)
