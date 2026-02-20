#!/usr/bin/env bash
# Send an email with a file attachment via Gmail API
# Reuses the same OAuth credentials as gmail-mcp
#
# Usage: gmail-send-attachment.sh <to> <subject> <body> <file>
# Example: gmail-send-attachment.sh jsperson_PuR3Fa@kindle.com "Article Title" "See attached." /tmp/article.html
set -euo pipefail

if [ $# -lt 4 ]; then
    echo "Usage: $0 <to> <subject> <body> <file>" >&2
    echo "Example: $0 user@kindle.com \"Article\" \"See attached.\" /tmp/doc.html" >&2
    exit 1
fi

TO="$1"
SUBJECT="$2"
BODY="$3"
FILE="$4"

if [ ! -f "$FILE" ]; then
    echo "Error: File not found: $FILE" >&2
    exit 1
fi

CLAWCODE_DIR="${CLAWCODE_DIR:-$HOME/clawcode}"
ENV_FILE="$CLAWCODE_DIR/.env"

# Read credentials from .env
GOOGLE_CLIENT_ID=""
GOOGLE_CLIENT_SECRET=""
GOOGLE_REFRESH_TOKEN=""
while IFS= read -r line; do
    case "$line" in
        GOOGLE_CLIENT_ID=*) GOOGLE_CLIENT_ID="${line#*=}" ;;
        GOOGLE_CLIENT_SECRET=*) GOOGLE_CLIENT_SECRET="${line#*=}" ;;
        GOOGLE_REFRESH_TOKEN=*) GOOGLE_REFRESH_TOKEN="${line#*=}" ;;
    esac
done < "$ENV_FILE"

if [ -z "$GOOGLE_REFRESH_TOKEN" ]; then
    echo "Error: GOOGLE_REFRESH_TOKEN not set." >&2
    exit 1
fi

# Exchange refresh token for access token
ACCESS_TOKEN=$(curl -s -X POST https://oauth2.googleapis.com/token \
    -d "client_id=${GOOGLE_CLIENT_ID}" \
    -d "client_secret=${GOOGLE_CLIENT_SECRET}" \
    -d "refresh_token=${GOOGLE_REFRESH_TOKEN}" \
    -d "grant_type=refresh_token" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))")

if [ -z "$ACCESS_TOKEN" ]; then
    echo "Error: Failed to refresh access token." >&2
    exit 1
fi

# Detect MIME type
FILENAME=$(basename "$FILE")
case "${FILENAME##*.}" in
    html|htm) MIME_TYPE="text/html" ;;
    pdf)      MIME_TYPE="application/pdf" ;;
    doc)      MIME_TYPE="application/msword" ;;
    docx)     MIME_TYPE="application/vnd.openxmlformats-officedocument.wordprocessingml.document" ;;
    txt)      MIME_TYPE="text/plain" ;;
    epub)     MIME_TYPE="application/epub+zip" ;;
    mobi)     MIME_TYPE="application/x-mobipocket-ebook" ;;
    *)        MIME_TYPE="application/octet-stream" ;;
esac

# Build MIME message with attachment
BOUNDARY="boundary_$(date +%s)_$$"
FILE_BASE64=$(base64 < "$FILE")

MIME_MESSAGE=$(cat <<MIME_EOF
From: me
To: ${TO}
Subject: ${SUBJECT}
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="${BOUNDARY}"

--${BOUNDARY}
Content-Type: text/plain; charset="UTF-8"

${BODY}

--${BOUNDARY}
Content-Type: ${MIME_TYPE}; name="${FILENAME}"
Content-Disposition: attachment; filename="${FILENAME}"
Content-Transfer-Encoding: base64

${FILE_BASE64}

--${BOUNDARY}--
MIME_EOF
)

# URL-safe base64 encode the entire message
RAW_MESSAGE=$(printf '%s' "$MIME_MESSAGE" | base64 | tr '+/' '-_' | tr -d '=\n')

# Send via Gmail API
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
    "https://gmail.googleapis.com/gmail/v1/users/me/messages/send" \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"raw\": \"${RAW_MESSAGE}\"}")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY_RESPONSE=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    MSG_ID=$(echo "$BODY_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "unknown")
    echo "Sent successfully. Message ID: ${MSG_ID}"
else
    echo "Error (HTTP ${HTTP_CODE}): ${BODY_RESPONSE}" >&2
    exit 1
fi
