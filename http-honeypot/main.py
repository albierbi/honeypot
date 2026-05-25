import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx
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

# --- geo lookup ---

_geo_cache: dict = {}
_PRIVATE_PREFIXES = ("10.", "172.", "192.168.", "127.", "::1", "fd", "fc")


async def geo_lookup(ip: str) -> dict:
    if any(ip.startswith(p) for p in _PRIVATE_PREFIXES):
        return {"country": "", "city": "", "latitude": None, "longitude": None}
    if ip in _geo_cache:
        return _geo_cache[ip]
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            r = await client.get(f"http://ip-api.com/json/{ip}?fields=country,city,lat,lon")
            d = r.json()
            result = {
                "country": d.get("country", ""),
                "city": d.get("city", ""),
                "latitude": d.get("lat"),
                "longitude": d.get("lon"),
            }
    except Exception:
        result = {"country": "", "city": "", "latitude": None, "longitude": None}
    _geo_cache[ip] = result
    return result


# --- request logger ---

async def log_request(request: Request, body: str, response_code: int):
    ip = request.headers.get("x-forwarded-for", request.client.host)
    geo = await geo_lookup(ip)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "src_ip": ip,
        "method": request.method,
        "path": request.url.path,
        "query": str(request.url.query),
        "user_agent": request.headers.get("user-agent", ""),
        "body": body[:500],
        "response_code": response_code,
        "country": geo["country"],
        "city": geo["city"],
        "latitude": geo["latitude"],
        "longitude": geo["longitude"],
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
        await log_request(request, body, 200)
        return PlainTextResponse(FAKE_ENV, status_code=200)

    if p in ("/wp-login.php", "/wp-admin/", "/wp-admin"):
        await log_request(request, body, 200)
        return HTMLResponse(FAKE_WP_LOGIN, status_code=200)

    if p in ("/admin", "/admin/", "/administrator", "/login", "/phpmyadmin", "/phpmyadmin/"):
        await log_request(request, body, 200)
        return HTMLResponse(FAKE_LOGIN_PAGE, status_code=200)

    if p in ("/.git/config", "/config.php", "/config.json", "/backup.sql"):
        await log_request(request, body, 403)
        return PlainTextResponse("Forbidden", status_code=403)

    await log_request(request, body, 404)
    return HTMLResponse(FAKE_404, status_code=404)
