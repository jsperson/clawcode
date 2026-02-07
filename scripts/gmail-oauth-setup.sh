#!/usr/bin/env bash
# One-time OAuth setup for gmail-mcp
# Gets a Google refresh token and stores it in .env
set -euo pipefail

CLAWCODE_DIR="${CLAWCODE_DIR:-$HOME/clawcode}"
ENV_FILE="$CLAWCODE_DIR/.env"

# Read credentials from .env
GOOGLE_CLIENT_ID=""
GOOGLE_CLIENT_SECRET=""
while IFS= read -r line; do
    case "$line" in
        GOOGLE_CLIENT_ID=*) GOOGLE_CLIENT_ID="${line#*=}" ;;
        GOOGLE_CLIENT_SECRET=*) GOOGLE_CLIENT_SECRET="${line#*=}" ;;
    esac
done < "$ENV_FILE"

if [ -z "$GOOGLE_CLIENT_ID" ] || [ -z "$GOOGLE_CLIENT_SECRET" ]; then
    echo "Error: GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in $ENV_FILE" >&2
    exit 1
fi

LISTEN_PORT=9025
REDIRECT_URI="http://localhost:${LISTEN_PORT}/callback"
SCOPES="https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send https://www.googleapis.com/auth/gmail.modify"
ENCODED_SCOPES=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$SCOPES'))")

AUTH_URL="https://accounts.google.com/o/oauth2/v2/auth?client_id=${GOOGLE_CLIENT_ID}&redirect_uri=${REDIRECT_URI}&response_type=code&scope=${ENCODED_SCOPES}&access_type=offline&prompt=consent"

echo ""
echo "Gmail OAuth Setup"
echo "================="
echo ""
echo "Opening Google authorization in your browser..."

open "$AUTH_URL"

echo "Waiting for callback on port $LISTEN_PORT..."
echo ""

# One-shot HTTP server to capture the auth code
AUTH_CODE=$(python3 << 'PYEOF'
import http.server, urllib.parse, sys, threading

code_result = None

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global code_result
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        code = params.get('code', [''])[0]
        error = params.get('error', [''])[0]
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        if error:
            self.wfile.write(f'<h2>Error: {error}</h2><p>Close this tab.</p>'.encode())
            code_result = ''
        elif code:
            self.wfile.write(b'<h2>Authorization successful!</h2><p>You can close this tab.</p>')
            code_result = code
        else:
            self.wfile.write(b'<h2>No code received</h2>')
            code_result = ''
        threading.Thread(target=self.server.shutdown).start()
    def log_message(self, *args):
        pass

server = http.server.HTTPServer(('127.0.0.1', 9025), Handler)
server.serve_forever()
print(code_result or '')
PYEOF
)

if [ -z "$AUTH_CODE" ]; then
    echo "Error: Failed to get authorization code" >&2
    exit 1
fi

echo "Got auth code. Exchanging for tokens..."

TOKEN_RESPONSE=$(curl -s -X POST https://oauth2.googleapis.com/token \
    -d "code=${AUTH_CODE}" \
    -d "client_id=${GOOGLE_CLIENT_ID}" \
    -d "client_secret=${GOOGLE_CLIENT_SECRET}" \
    -d "redirect_uri=${REDIRECT_URI}" \
    -d "grant_type=authorization_code")

REFRESH_TOKEN=$(echo "$TOKEN_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('refresh_token',''))")

if [ -z "$REFRESH_TOKEN" ]; then
    echo "Error: No refresh token received" >&2
    echo "$TOKEN_RESPONSE" >&2
    exit 1
fi

# Save refresh token to .env
if grep -q "^GOOGLE_REFRESH_TOKEN=" "$ENV_FILE" 2>/dev/null; then
    sed -i '' "s|^GOOGLE_REFRESH_TOKEN=.*|GOOGLE_REFRESH_TOKEN=$REFRESH_TOKEN|" "$ENV_FILE"
else
    echo "GOOGLE_REFRESH_TOKEN=$REFRESH_TOKEN" >> "$ENV_FILE"
fi

echo ""
echo "✓ Refresh token saved to $ENV_FILE"
echo "✓ Gmail OAuth setup complete"
echo ""
