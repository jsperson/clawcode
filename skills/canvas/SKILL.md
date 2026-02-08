---
name: canvas
description: Query and manage Newman University Canvas LMS data via CLI
triggers:
  - canvas
  - assignments
  - grades
  - submissions
  - course
  - quiz
metadata:
  clawcode:
    requires:
      bins:
        - python3
---

# Canvas LMS CLI Skill

Query and manage Newman University Canvas LMS data via CLI. Supports 112 commands covering full CRUD operations.

## Setup

1. Get API token from Canvas: Settings → Approved Integrations → New Access Token
2. Store token: `echo "YOUR_TOKEN" > ~/.config/canvas/token && chmod 600 ~/.config/canvas/token`
3. Or set environment variable: `export CANVAS_TOKEN="YOUR_TOKEN"`

## CLI Location

```bash
/Users/jsperson/clawcode/scripts/canvas-cli.py
# Or as a Python module:
cd /Users/jsperson/clawcode/scripts && python3 -m canvas_cli
```

## Output

All commands output JSON to stdout. Parse with `jq`:

```bash
canvas-cli.py upcoming | jq -r '.[] | "\(.due_at) - \(.name)"'
```

Write operations output JSON with an `"action"` key:
```json
{"action": "created", "id": 12345, "name": "..."}
```

Status messages go to stderr.

## Content Input (Write Commands)

Commands that accept rich content (descriptions, messages, page bodies) support three mutually exclusive input methods:

```bash
# Inline text
--body "Short content here"
--message "Discussion reply"
--description "Assignment description"

# Read from file
--body-file /path/to/content.html

# Read from stdin (piping)
echo "Content" | canvas-cli.py create-page --course 123 --title "Test" --body-stdin
```

## Destructive Operation Safety

All `delete-*` and `bulk-grade` commands prompt for confirmation:
- Interactive by default
- `--yes` / `-y` flag to skip confirmation
- Requires `--yes` when stdin is not a TTY

---

## Commands Reference

### Courses (6 commands)

```bash
canvas-cli.py courses                     # List enrolled courses
canvas-cli.py course ID                   # Course details (syllabus, term)
canvas-cli.py course-update ID [opts]     # Update course (--name, --default-view, etc.)
canvas-cli.py course-update-settings ID   # Update flags (--hide-final-grades, etc.)
canvas-cli.py create-rubric COURSE_ID --title T --criteria JSON
canvas-cli.py create-assignment-group COURSE_ID --name N [--position P --group-weight W]
```

### Assignments (6 commands)

```bash
canvas-cli.py assignments [--course ID] [--upcoming N]
canvas-cli.py assignment ID
canvas-cli.py create-assignment --course ID --name N [--points-possible P --due-at DT --submission-types T --published --description "..."]
canvas-cli.py edit-assignment COURSE_ID ASSIGN_ID [--name --points-possible --due-at --published true/false --description "..."]
canvas-cli.py delete-assignment COURSE_ID ASSIGN_ID [-y]
canvas-cli.py submit-assignment COURSE_ID ASSIGN_ID --type online_text_entry|online_url|online_upload [--body "..." --url URL --file PATH]
```

### Submissions (7 commands)

```bash
canvas-cli.py submissions [--course ID]
canvas-cli.py submission ASSIGNMENT_ID
canvas-cli.py grade-submission COURSE ASSIGN USER [--score S --comment C --excused]
canvas-cli.py bulk-grade COURSE ASSIGN --grades-file FILE [-y]
canvas-cli.py submission-mark-read COURSE ASSIGN USER
canvas-cli.py submission-mark-unread COURSE ASSIGN USER
canvas-cli.py upload-submission-comment COURSE ASSIGN USER --file PATH
```

### Discussions (14 commands)

```bash
canvas-cli.py discussions [--course ID]
canvas-cli.py discussion ID
canvas-cli.py create-discussion --course ID --title T [--discussion-type threaded --published --pinned --message "..."]
canvas-cli.py edit-discussion COURSE TOPIC [--title --published --pinned --locked --message "..."]
canvas-cli.py delete-discussion COURSE TOPIC [-y]
canvas-cli.py post-discussion-entry COURSE TOPIC --message "..."
canvas-cli.py reply-to-entry COURSE TOPIC ENTRY --message "..."
canvas-cli.py edit-entry COURSE TOPIC ENTRY --message "..."
canvas-cli.py delete-entry COURSE TOPIC ENTRY [-y]
canvas-cli.py rate-entry COURSE TOPIC ENTRY --rating 0|1
canvas-cli.py subscribe-discussion COURSE TOPIC
canvas-cli.py unsubscribe-discussion COURSE TOPIC
canvas-cli.py mark-discussion-read COURSE TOPIC [--all]
canvas-cli.py mark-discussion-unread COURSE TOPIC [--all]
```

### Announcements (2 commands)

```bash
canvas-cli.py announcements [--course ID] [--limit N]
canvas-cli.py create-announcement --course ID --title T [--message "..."]
```

### Pages (5 commands)

```bash
canvas-cli.py pages [--course ID]
canvas-cli.py page COURSE_ID TITLE
canvas-cli.py create-page --course ID --title T [--published --front-page --body "..."]
canvas-cli.py edit-page COURSE URL_OR_TITLE [--title --published --body "..."]
canvas-cli.py delete-page COURSE URL_OR_TITLE [-y]
```

### Quizzes (8 commands)

```bash
canvas-cli.py quizzes [--course ID]
canvas-cli.py quiz ID
canvas-cli.py create-quiz --course ID --title T [--quiz-type assignment --time-limit M --allowed-attempts N --due-at DT --published --description "..."]
canvas-cli.py edit-quiz COURSE QUIZ [--title --time-limit --due-at --published --description "..."]
canvas-cli.py delete-quiz COURSE QUIZ [-y]
canvas-cli.py create-quiz-question COURSE QUIZ --question-name N --question-type T --question-text Q [--points-possible P --answers JSON]
canvas-cli.py start-quiz COURSE QUIZ
canvas-cli.py update-quiz-scores COURSE QUIZ SUB --questions JSON
```

### Modules (8 commands)

```bash
canvas-cli.py modules [--course ID]
canvas-cli.py module-items MODULE_ID --course ID
canvas-cli.py create-module --course ID --name N [--position P --unlock-at DT --require-sequential-progress]
canvas-cli.py edit-module COURSE MODULE [--name --position --published]
canvas-cli.py delete-module COURSE MODULE [-y]
canvas-cli.py create-module-item COURSE MODULE --title T --type TYPE [--content-id ID --external-url URL --position P]
canvas-cli.py edit-module-item COURSE MODULE ITEM [--title --position --published]
canvas-cli.py delete-module-item COURSE MODULE ITEM [-y]
```

### Files & Folders (10 commands)

```bash
canvas-cli.py files [--course ID] [--folder ID]
canvas-cli.py file ID
canvas-cli.py download FILE_ID [--output PATH]
canvas-cli.py folders [--course ID]
canvas-cli.py upload-file --folder ID --file PATH
canvas-cli.py create-folder --name N (--course ID | --parent-folder ID)
canvas-cli.py update-file FILE_ID [--name --locked --hidden]
canvas-cli.py delete-file FILE_ID [-y]
canvas-cli.py update-folder FOLDER_ID [--name --locked --hidden]
canvas-cli.py delete-folder FOLDER_ID [-y] [--force]
```

### Groups (10 commands)

```bash
canvas-cli.py groups
canvas-cli.py group ID
canvas-cli.py create-group --name N [--description D --is-public --join-level invitation_only]
canvas-cli.py edit-group ID [--name --description --join-level]
canvas-cli.py delete-group ID [-y]
canvas-cli.py add-group-member GROUP USER
canvas-cli.py remove-group-member GROUP USER [-y]
canvas-cli.py group-create-discussion GROUP --title T [--message "..."]
canvas-cli.py group-create-page GROUP --title T [--body "..."]
canvas-cli.py group-create-folder GROUP --name N
```

### Conversations (8 commands)

```bash
canvas-cli.py inbox [--filter all|unread|starred|sent|archived]
canvas-cli.py conversation ID
canvas-cli.py create-conversation --recipients UID... --subject S --body "..." [--group-conversation]
canvas-cli.py reply-conversation ID --body "..."
canvas-cli.py add-recipients ID --recipients UID...
canvas-cli.py edit-conversation ID [--workflow-state read|unread|archived --starred true/false --subject S]
canvas-cli.py delete-conversation ID [-y]
canvas-cli.py mark-all-conversations-read
```

### Calendar (4 commands)

```bash
canvas-cli.py calendar [--days N]
canvas-cli.py create-calendar-event --context CONTEXT --title T --start-at DT [--end-at DT --location-name L --description "..."]
canvas-cli.py edit-calendar-event EVENT_ID [--title --start-at --end-at --location-name --description "..."]
canvas-cli.py delete-calendar-event EVENT_ID [-y]
```

### Enrollments & Sections (9 commands)

```bash
canvas-cli.py people --course ID
canvas-cli.py create-section COURSE --name N [--start-at --end-at]
canvas-cli.py edit-section SECTION_ID [--name --start-at --end-at]
canvas-cli.py delete-section SECTION_ID [-y]
canvas-cli.py cross-list-section SECTION NEW_COURSE
canvas-cli.py enroll-user SECTION USER --type StudentEnrollment|TeacherEnrollment|...
canvas-cli.py accept-enrollment COURSE ENROLLMENT_ID
canvas-cli.py deactivate-enrollment COURSE ENROLLMENT_ID [--task conclude|delete|deactivate]
canvas-cli.py reactivate-enrollment COURSE ENROLLMENT_ID
```

### User & Preferences (10 commands)

```bash
canvas-cli.py profile
canvas-cli.py edit-profile [--name --short-name --bio --title --time-zone --locale]
canvas-cli.py update-user-settings [--manual-mark-as-read --collapse-global-nav --hide-dashcard-color-overlays]
canvas-cli.py update-color ASSET HEXCODE
canvas-cli.py add-favorite-course COURSE_ID
canvas-cli.py add-favorite-group GROUP_ID
canvas-cli.py create-planner-note --title T [--details D --todo-date DT --course-id ID]
canvas-cli.py create-planner-override TYPE ID [--marked-complete --dismissed]
canvas-cli.py create-communication-channel --address ADDR --type email|sms|push
canvas-cli.py update-notification-preference CHANNEL_ID NOTIFICATION --frequency immediately|daily|weekly|never
```

### Utility (5 commands)

```bash
canvas-cli.py grades [--course ID]
canvas-cli.py todo
canvas-cli.py upcoming [--days N]
canvas-cli.py notifications
canvas-cli.py search QUERY
```

## Common Patterns

### Daily Digest Integration
```bash
canvas-cli.py upcoming --days=7 | jq -r '.[] | "- **\(.due_at[:10])** \(.course_name): \(.name)"'
```

### Check for New Announcements
```bash
canvas-cli.py announcements --limit=5 | jq -r '.[] | "[\(.course_name)] \(.title)"'
```

### Grade Check
```bash
canvas-cli.py grades | jq -r '.[] | "\(.course_name): \(.current_grade // .current_score // "N/A")"'
```

### Submit Text Entry
```bash
canvas-cli.py submit-assignment 12345 67890 --type online_text_entry --body "My submission text"
```

### Post Discussion Reply
```bash
canvas-cli.py reply-to-entry 12345 100 200 --message "Great point! I agree because..."
```

### Create and Delete Calendar Event
```bash
canvas-cli.py create-calendar-event --context user_12345 --title "Study Session" --start-at "2025-01-15T14:00:00"
canvas-cli.py delete-calendar-event 99999 -y
```

## Error Handling

- Missing token: "Error: No Canvas token found"
- Invalid token: "Error: Invalid or expired Canvas token"
- Course not found: Returns empty array or error message
- Destructive ops without confirmation: "Error: Destructive operation requires --yes flag"

## Notes

- All datetimes formatted as "YYYY-MM-DD HH:MM" in local time
- Courses filtered to active enrollments only
- JSON output suitable for parsing with jq or Python
- Package lives in `scripts/canvas_cli/` (importable as `canvas_cli`)
