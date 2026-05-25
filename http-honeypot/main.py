import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse

# --- logging setup ---

LOG_FILE = Path("/app/logs/http.json")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

file_handler = logging.FileHandler(LOG_FILE)
file_handler.setFormatter(logging.Formatter("%(message)s"))

logger = logging.getLogger("honeypot")
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)


def log_request(request: Request, body: str, response_code: int):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "src_ip": request.headers.get("x-forwarded-for", request.client.host),
        "method": request.method,
        "path": request.url.path,
        "query": str(request.url.query),
        "user_agent": request.headers.get("user-agent", ""),
        "body": body[:500],  # cap at 500 chars to avoid huge log entries
        "response_code": response_code,
    }
    logger.info(json.dumps(entry))


# --- fake responses ---

FAKE_ENV = """\
APP_ENV=production
APP_KEY=base64:kDz3gX2mN8pQvR1sT4uW7yB0cF5hJ6lE
DB_HOST=127.0.0.1
DB_DATABASE=app_production
DB_USERNAME=root
DB_PASSWORD=Sup3rS3cr3tP@ss!
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
MAIL_PASSWORD=smtp_secret_123
"""

FAKE_LOGIN_PAGE = """\
<!DOCTYPE html>
<html>
<head><title>Admin Login</title></head>
<body>
<h2>Administrator Login</h2>
<form method="POST">
  <input name="username" placeholder="Username" /><br/>
  <input name="password" type="password" placeholder="Password" /><br/>
  <button type="submit">Login</button>
</form>
</body>
</html>
"""

FAKE_WP_LOGIN = """\
<!DOCTYPE html>
<html>
<head><title>WordPress &rsaquo; Log In</title></head>
<body id="login">
<h1>WordPress</h1>
<form method="POST">
  <label>Username<input name="log" type="text" /></label>
  <label>Password<input name="pwd" type="password" /></label>
  <input type="submit" value="Log In" />
</form>
</body>
</html>
"""

FAKE_404 = """\
<!DOCTYPE html>
<html>
<head><title>404 Not Found</title></head>
<body>
<h1>Not Found</h1>
<p>The requested URL was not found on this server.</p>
<hr/><address>Apache/2.4.41 (Ubuntu) Server at localhost Port 80</address>
</body>
</html>
"""


# --- app ---

app = FastAPI(docs_url=None, redoc_url=None)


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"])
async def catch_all(request: Request, path: str):
    body = ""
    if request.method in ("POST", "PUT"):
        raw = await request.body()
        body = raw.decode(errors="replace")

    p = "/" + path.lstrip("/")

    if p == "/.env":
        log_request(request, body, 200)
        return PlainTextResponse(FAKE_ENV, status_code=200)

    if p in ("/wp-login.php", "/wp-admin/", "/wp-admin"):
        log_request(request, body, 200)
        return HTMLResponse(FAKE_WP_LOGIN, status_code=200)

    if p in ("/admin", "/admin/", "/administrator", "/login", "/phpmyadmin", "/phpmyadmin/"):
        log_request(request, body, 200)
        return HTMLResponse(FAKE_LOGIN_PAGE, status_code=200)

    if p in ("/.git/config", "/config.php", "/config.json", "/backup.sql"):
        log_request(request, body, 403)
        return PlainTextResponse("Forbidden", status_code=403)

    log_request(request, body, 404)
    return HTMLResponse(FAKE_404, status_code=404)
