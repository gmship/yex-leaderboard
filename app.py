from __future__ import annotations

import hashlib
import hmac
import http.client
import ipaddress
import json
import math
import os
import re
import secrets
import socket
import sqlite3
import ssl
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from flask import Flask, Response, abort, g, has_request_context, jsonify, redirect, render_template, request, session, url_for
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

try:
    import stripe
except ImportError:  # Lets health checks explain a missing optional dependency.
    stripe = None


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", BASE_DIR / "data" / "leaderboard.db"))
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:5000").rstrip("/")
SITE_NAME = os.getenv("SITE_NAME", "Whatever Board").strip() or "Whatever Board"
SECRET_KEY_FILE = os.getenv("FLASK_SECRET_KEY_FILE", "").strip()
if os.getenv("FLASK_SECRET_KEY"):
    SECRET_KEY = os.environ["FLASK_SECRET_KEY"]
    SECRET_KEY_IS_PERSISTENT = True
elif SECRET_KEY_FILE and Path(SECRET_KEY_FILE).is_file():
    SECRET_KEY = Path(SECRET_KEY_FILE).read_text(encoding="utf-8").strip()
    SECRET_KEY_IS_PERSISTENT = True
else:
    SECRET_KEY = secrets.token_hex(32)
    SECRET_KEY_IS_PERSISTENT = False
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "").strip()
MIN_SUBMISSION_CENTS = max(100, int(os.getenv("SUBMISSION_MIN_CENTS", "100")))
ALLOW_INSECURE_DEV_CONFIG = os.getenv("ALLOW_INSECURE_DEV_CONFIG", "0") == "1"
TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "0") == "1"
configured_hosts = {
    host.strip()
    for host in os.getenv("TRUSTED_HOSTS", "").split(",")
    if host.strip()
}
configured_hosts.update({"localhost", "127.0.0.1", urlsplit(BASE_URL).hostname or ""})
TRUSTED_HOSTS = sorted(host for host in configured_hosts if host)

if not ALLOW_INSECURE_DEV_CONFIG:
    if not SECRET_KEY_IS_PERSISTENT or len(SECRET_KEY) < 32:
        raise RuntimeError(
            "Configure a persistent FLASK_SECRET_KEY or FLASK_SECRET_KEY_FILE "
            "containing at least 32 characters."
        )
    if len(ADMIN_PASSWORD) < 12 or ADMIN_PASSWORD.casefold() in {
        "admin",
        "password",
        "changeme",
        "replace-this-password",
        "replace-with-a-long-random-password",
    }:
        raise RuntimeError("Configure ADMIN_PASSWORD with at least 12 non-default characters.")

TOOL_DEFINITIONS = (
    {"name": "ChatGPT", "slug": "chatgpt", "description": "Explore products whose builders used ChatGPT to move from idea to launch."},
    {"name": "Claude", "slug": "claude", "description": "Discover products built with Claude and Claude Code by independent AI builders."},
    {"name": "GitHub Copilot", "slug": "github-copilot", "description": "Explore products created with GitHub Copilot and see how builders use it to ship."},
    {"name": "Gemini", "slug": "gemini", "description": "See products built with Gemini, Gemini CLI, and Google's AI development tools."},
    {"name": "Codex", "slug": "codex", "description": "Browse products built with OpenAI Codex, ranked by real bids from their builders."},
    {"name": "Cursor", "slug": "cursor", "description": "Find apps and developer tools built with the Cursor AI code editor."},
    {"name": "DeepSeek", "slug": "deepseek", "description": "Discover products built with DeepSeek models and open-weight AI workflows."},
    {"name": "Replit", "slug": "replit", "description": "Discover apps created and shipped with Replit and Replit Agent."},
    {"name": "Lovable", "slug": "lovable", "description": "Browse apps built with Lovable, from early prototypes to launched products."},
    {"name": "v0", "slug": "v0", "description": "Explore websites and applications designed and built with Vercel v0."},
    {"name": "Bolt", "slug": "bolt", "description": "Discover full-stack products created with Bolt.new."},
    {"name": "Windsurf", "slug": "windsurf", "description": "Browse projects built with the Windsurf AI coding environment."},
    {"name": "Base44", "slug": "base44", "description": "Explore applications created with the Base44 AI app builder."},
    {"name": "Qwen", "slug": "qwen", "description": "Explore products built with Alibaba's Qwen model family and coding models."},
    {"name": "Kimi", "slug": "kimi", "description": "Discover projects built with Kimi models and agentic development workflows."},
    {"name": "Grok", "slug": "grok", "description": "Browse products whose builders used Grok models for coding and creation."},
    {"name": "Llama", "slug": "llama", "description": "Explore products built with Meta's open Llama model ecosystem."},
    {"name": "OpenCode", "slug": "opencode", "description": "Discover products shipped with the open-source OpenCode coding agent."},
    {"name": "Antigravity", "slug": "antigravity", "description": "See projects built with Google's Antigravity development environment."},
    {"name": "Cline", "slug": "cline", "description": "Browse projects built with the Cline autonomous coding agent."},
    {"name": "Roo Code", "slug": "roo-code", "description": "Explore apps created with the Roo Code AI development agent."},
    {"name": "Aider", "slug": "aider", "description": "Find software built with Aider's terminal-based AI pair programming workflow."},
    {"name": "Amazon Q", "slug": "amazon-q", "description": "Discover software created with Amazon Q Developer."},
    {"name": "Devin", "slug": "devin", "description": "Discover software projects created with the Devin AI engineering agent."},
    {"name": "Junie", "slug": "junie", "description": "Browse products built with JetBrains Junie."},
    {"name": "Firebase Studio", "slug": "firebase-studio", "description": "Explore applications built with Firebase Studio's AI workspace."},
    {"name": "Other", "slug": "other", "description": "Explore products built with emerging and independent AI development tools."},
)
TOOLS = tuple(tool["name"] for tool in TOOL_DEFINITIONS)
TOOL_BY_SLUG = {tool["slug"]: tool for tool in TOOL_DEFINITIONS}
FEATURED_TOOL_SLUGS = (
    "chatgpt",
    "claude",
    "gemini",
    "codex",
    "cursor",
    "deepseek",
    "grok",
    "github-copilot",
)
FEATURED_TOOLS = tuple(TOOL_BY_SLUG[slug] for slug in FEATURED_TOOL_SLUGS)
MORE_TOOLS = tuple(
    tool for tool in TOOL_DEFINITIONS if tool["slug"] not in FEATURED_TOOL_SLUGS
)
CATEGORIES = ("Apps", "Agents", "Developer tools", "Creative", "Games", "Other")
TIME_UNITS = {"minutes", "hours", "days", "weeks"}
SITE_PREVIEW_MAX_BYTES = 512 * 1024
SITE_PREVIEW_MAX_REDIRECTS = 3
SITE_PREVIEW_REQUESTS_PER_MINUTE = 3
PREVIEW_SSL_CONTEXT = ssl.create_default_context()

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = BASE_URL.startswith("https://")
app.config["TRUSTED_HOSTS"] = TRUSTED_HOSTS
if TRUST_PROXY_HEADERS:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)


@app.context_processor
def inject_branding():
    return {"site_name": SITE_NAME}

if stripe and STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def db_session():
    connection = get_db()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db_session() as db:
        db.executescript(
            """
            PRAGMA journal_mode = WAL;

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                tagline TEXT NOT NULL,
                category TEXT NOT NULL,
                built_with TEXT NOT NULL,
                build_time_value REAL NOT NULL,
                build_time_unit TEXT NOT NULL,
                submitted_by TEXT NOT NULL DEFAULT 'Anonymous',
                x_user_id TEXT,
                x_handle TEXT,
                favicon_url TEXT,
                total_bid_cents INTEGER NOT NULL DEFAULT 0,
                clicks INTEGER NOT NULL DEFAULT 0,
                is_demo INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'live',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pending_submissions (
                id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                amount_cents INTEGER NOT NULL,
                stripe_session_id TEXT UNIQUE,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                pending_id TEXT NOT NULL,
                stripe_session_id TEXT NOT NULL UNIQUE,
                payment_intent_id TEXT,
                amount_cents INTEGER NOT NULL,
                currency TEXT NOT NULL DEFAULT 'usd',
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id),
                FOREIGN KEY(pending_id) REFERENCES pending_submissions(id)
            );

            CREATE TABLE IF NOT EXISTS checkout_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS preview_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS admin_login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_hash TEXT NOT NULL,
                account_hash TEXT NOT NULL,
                succeeded INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS click_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                ip_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS site_stats (
                name TEXT PRIMARY KEY,
                value INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS active_visitors (
                visitor_id TEXT PRIMARY KEY,
                last_seen TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS site_settings (
                name TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_projects_rank
                ON projects(status, is_demo, total_bid_cents DESC);
            CREATE INDEX IF NOT EXISTS idx_projects_leaderboard
                ON projects(status, total_bid_cents DESC, created_at ASC);
            CREATE INDEX IF NOT EXISTS idx_attempts_ip
                ON checkout_attempts(ip_hash, created_at);
            CREATE INDEX IF NOT EXISTS idx_preview_attempts_ip
                ON preview_attempts(ip_hash, created_at);
            CREATE INDEX IF NOT EXISTS idx_admin_login_attempts_pair
                ON admin_login_attempts(ip_hash, account_hash, created_at);
            CREATE INDEX IF NOT EXISTS idx_click_events_ip
                ON click_events(ip_hash, created_at);
            CREATE INDEX IF NOT EXISTS idx_active_visitors_last_seen
                ON active_visitors(last_seen);

            INSERT OR IGNORE INTO site_stats (name, value)
                VALUES ('total_visits', 0);
            """
        )
        project_columns = {
            row["name"] for row in db.execute("PRAGMA table_info(projects)").fetchall()
        }
        if "favicon_url" not in project_columns:
            db.execute("ALTER TABLE projects ADD COLUMN favicon_url TEXT")
        db.execute("PRAGMA optimize")
        if os.getenv("SEED_DEMO_DATA", "1") == "1":
            seed_demo_data(db)


EXAMPLE_LISTINGS = (
    ("atlas-notes", "Atlas Notes", "https://example.com/atlas-notes", "Turn scattered research into a clean visual map.", "Apps", ["ChatGPT"], 3, "hours", "Example maker", 1000, 84),
    ("prompt-library", "Prompt Library", "https://example.com/prompt-library", "Save, organize, and share the prompts your team reuses.", "Developer tools", ["Claude"], 90, "minutes", "Example maker", 900, 73),
    ("ship-log", "Ship Log", "https://example.com/ship-log", "A tiny public changelog for fast-moving products.", "Developer tools", ["Codex"], 2, "days", "Example maker", 800, 61),
    ("pixel-kit", "Pixel Kit", "https://example.com/pixel-kit", "Generate a consistent set of launch graphics in minutes.", "Creative", ["Gemini"], 6, "hours", "Example maker", 700, 55),
    ("agent-desk", "Agent Desk", "https://example.com/agent-desk", "Keep lightweight AI workflows together in one workspace.", "Agents", ["OpenCode"], 4, "days", "Example maker", 600, 48),
    ("model-watch", "Model Watch", "https://example.com/model-watch", "Track model releases, context windows, and pricing changes.", "Apps", ["DeepSeek"], 8, "hours", "Example maker", 500, 39),
    ("copy-studio", "Copy Studio", "https://example.com/copy-studio", "Draft concise product copy from a single brief.", "Creative", ["ChatGPT"], 45, "minutes", "Example maker", 400, 31),
    ("repo-radar", "Repo Radar", "https://example.com/repo-radar", "Surface the pull requests and issues that need attention.", "Developer tools", ["GitHub Copilot"], 5, "hours", "Example maker", 300, 24),
    ("meeting-mint", "Meeting Mint", "https://example.com/meeting-mint", "Turn a rough meeting transcript into clear next steps.", "Apps", ["Claude"], 2, "hours", "Example maker", 200, 17),
    ("data-sketch", "Data Sketch", "https://example.com/data-sketch", "Make quick exploratory charts without a complicated setup.", "Apps", ["Cursor"], 1, "days", "Example maker", 100, 9),
)


def seed_demo_data(db: sqlite3.Connection) -> None:
    if db.execute("SELECT COUNT(*) FROM projects").fetchone()[0]:
        return
    now = utc_now()
    db.executemany(
        """
        INSERT INTO projects (
            slug, name, url, tagline, category, built_with,
            build_time_value, build_time_unit, submitted_by,
            total_bid_cents, clicks, is_demo, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'live', ?, ?)
        """,
        [
            (*row[:4], json.dumps([row[4]]), json.dumps(row[5]), *row[6:], now, now)
            for row in EXAMPLE_LISTINGS
        ],
    )


def canonical_url(raw_url: str) -> str:
    raw_url = raw_url.strip()
    if not raw_url:
        raise ValueError("Add a product URL.")
    if "://" not in raw_url:
        raw_url = f"https://{raw_url}"
    parsed = urlsplit(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
        raise ValueError("Use a public http or https URL.")
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname == "localhost" or hostname.endswith(".local"):
        raise ValueError("Use a public product URL.")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address and (address.is_private or address.is_loopback or address.is_reserved):
        raise ValueError("Use a public product URL.")
    port = parsed.port
    display_hostname = f"[{hostname}]" if ":" in hostname else hostname
    netloc = display_hostname if port is None else f"{display_hostname}:{port}"
    path = parsed.path.rstrip("/") or ""
    return urlunsplit((parsed.scheme.lower(), netloc, path, parsed.query, ""))


def resolve_preview_target(raw_url: str) -> tuple[str, tuple[str, ...]]:
    """Resolve a preview URL once and return only vetted public target addresses."""
    url = canonical_url(raw_url)
    parsed = urlsplit(url)
    if parsed.port not in {None, 80, 443}:
        raise ValueError("Use a public website on the standard http or https port.")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise ValueError("That website could not be found.") from error
    if not addresses:
        raise ValueError("That website could not be found.")
    vetted_addresses = []
    for address_info in addresses:
        address = ipaddress.ip_address(address_info[4][0])
        if not address.is_global:
            raise ValueError("Use a public product URL.")
        normalized = str(address)
        if normalized not in vetted_addresses:
            vetted_addresses.append(normalized)
    return url, tuple(vetted_addresses)


def preview_target_url(raw_url: str) -> str:
    return resolve_preview_target(raw_url)[0]


def open_pinned_preview_url(
    url: str, addresses: tuple[str, ...]
) -> tuple[int, str, http.client.HTTPMessage, bytes]:
    """Fetch one URL while connecting only to a previously vetted numeric address."""
    parsed = urlsplit(url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    target = parsed.path or "/"
    if parsed.query:
        target = f"{target}?{parsed.query}"
    display_hostname = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    default_port = 443 if parsed.scheme == "https" else 80
    host_header = display_hostname if port == default_port else f"{display_hostname}:{port}"
    headers = {
        "Host": host_header,
        "User-Agent": f"{SITE_NAME} link preview/1.0 (+https://yex.lol)",
        "Accept": "text/html,application/xhtml+xml",
        "Connection": "close",
    }
    last_error: OSError | None = None
    for address in addresses:
        if parsed.scheme == "https":
            connection = http.client.HTTPSConnection(
                parsed.hostname, port, timeout=6, context=PREVIEW_SSL_CONTEXT
            )
        else:
            connection = http.client.HTTPConnection(parsed.hostname, port, timeout=6)

        def create_connection(_target, timeout=6, source_address=None, *, _address=address):
            return socket.create_connection((_address, port), timeout, source_address)

        connection._create_connection = create_connection
        try:
            connection.request("GET", target, headers=headers)
            if connection.sock is not None:
                peer_address = ipaddress.ip_address(connection.sock.getpeername()[0])
                if not peer_address.is_global:
                    raise ValueError("Use a public product URL.")
            response = connection.getresponse()
            body = (
                b""
                if response.status in {301, 302, 303, 307, 308} or not 200 <= response.status < 300
                else response.read(SITE_PREVIEW_MAX_BYTES + 1)
            )
            return response.status, response.reason, response.headers, body
        except OSError as error:
            last_error = error
        finally:
            connection.close()
    if last_error:
        raise last_error
    raise OSError("The website could not be reached.")


class SiteMetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.metadata: dict[str, str] = {}
        self.title_parts: list[str] = []
        self.icon_hrefs: list[str] = []
        self.in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = {str(key).lower(): value for key, value in attrs if value is not None}
        if tag.lower() == "title":
            self.in_title = True
        if tag.lower() == "link":
            rel_tokens = str(attributes.get("rel") or "").lower().split()
            href = str(attributes.get("href") or "").strip()
            if href and ("icon" in rel_tokens or "apple-touch-icon" in rel_tokens):
                self.icon_hrefs.append(href)
        if tag.lower() != "meta":
            return
        key = str(
            attributes.get("property")
            or attributes.get("name")
            or attributes.get("itemprop")
            or ""
        ).lower()
        content = str(attributes.get("content") or "").strip()
        if key and content and key not in self.metadata:
            self.metadata[key] = content

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)


def clean_preview_text(value: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def parse_site_metadata(html: str, source_url: str) -> dict[str, str]:
    parser = SiteMetadataParser()
    parser.feed(html)
    title = (
        parser.metadata.get("og:title")
        or parser.metadata.get("twitter:title")
        or " ".join(parser.title_parts)
        or urlsplit(source_url).hostname
        or ""
    )
    description = (
        parser.metadata.get("og:description")
        or parser.metadata.get("twitter:description")
        or parser.metadata.get("description")
        or ""
    )
    favicon_url = urljoin(source_url, parser.icon_hrefs[0]) if parser.icon_hrefs else urljoin(source_url, "/favicon.ico")
    if urlsplit(favicon_url).scheme not in {"http", "https"}:
        favicon_url = urljoin(source_url, "/favicon.ico")
    return {
        "name": clean_preview_text(title, 64),
        "description": clean_preview_text(description, 180),
        "favicon_url": favicon_url,
    }


def fetch_site_metadata(raw_url: str) -> dict[str, str]:
    current_url = raw_url
    for redirect_count in range(SITE_PREVIEW_MAX_REDIRECTS + 1):
        current_url, addresses = resolve_preview_target(current_url)
        status, reason, headers, body = open_pinned_preview_url(current_url, addresses)
        if status in {301, 302, 303, 307, 308}:
            location = headers.get("Location")
            if not location or redirect_count >= SITE_PREVIEW_MAX_REDIRECTS:
                raise ValueError("That website redirected too many times.")
            current_url = urljoin(current_url, location)
            continue
        if not 200 <= status < 300:
            raise HTTPError(current_url, status, reason, headers, None)
        content_type = headers.get_content_type()
        if content_type not in {"text/html", "application/xhtml+xml"}:
            raise ValueError("That URL does not appear to be a web page.")
        content_length = headers.get("Content-Length")
        if content_length:
            try:
                declared_size = int(content_length)
            except ValueError as error:
                raise ValueError("That website returned an invalid response size.") from error
            if declared_size < 0:
                raise ValueError("That website returned an invalid response size.")
            if declared_size > SITE_PREVIEW_MAX_BYTES:
                raise ValueError("That page is too large to preview.")
        if len(body) > SITE_PREVIEW_MAX_BYTES:
            raise ValueError("That page is too large to preview.")
        encoding = headers.get_content_charset() or "utf-8"
        return parse_site_metadata(body.decode(encoding, errors="replace"), current_url)
    raise ValueError("That website redirected too many times.")


def make_slug(db: sqlite3.Connection, name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48]
    base = base or "build"
    slug = base
    counter = 2
    while db.execute("SELECT 1 FROM projects WHERE slug = ?", (slug,)).fetchone():
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def submission_favicon_url(raw_url: str, product_url: str) -> str:
    candidate = urljoin(product_url, raw_url.strip()) if raw_url.strip() else urljoin(product_url, "/favicon.ico")
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
        return urljoin(product_url, "/favicon.ico")
    if len(candidate) > 500:
        return urljoin(product_url, "/favicon.ico")
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def validate_submission(data: dict) -> dict:
    if data.get("company_website"):
        raise ValueError("Unable to accept this submission.")

    name = str(data.get("name", "")).strip()
    build_time_unit = str(data.get("build_time_unit", "")).strip()
    terms_accepted = data.get("terms_accepted")

    if not 2 <= len(name) <= 64:
        raise ValueError("Product name must be 2–64 characters.")
    if build_time_unit not in TIME_UNITS:
        raise ValueError("Choose a valid build-time unit.")
    if terms_accepted not in {True, "true", "1", "on", 1}:
        raise ValueError("Accept the Rules, Terms, and Privacy Policy to continue.")

    categories = data.get("categories", data.get("category", []))
    if isinstance(categories, str):
        categories = [categories]
    categories = list(
        dict.fromkeys(str(item).strip() for item in categories if str(item).strip())
    )
    if not categories or len(categories) > 2 or any(item not in managed_categories() for item in categories):
        raise ValueError("Choose one or two valid categories.")

    built_with = data.get("built_with", [])
    if isinstance(built_with, str):
        built_with = [built_with]
    built_with = list(dict.fromkeys(str(item).strip() for item in built_with if str(item).strip()))
    if len(built_with) != 1 or any(item not in managed_tools() for item in built_with):
        raise ValueError("Choose one main build tool.")

    try:
        build_time_value = float(data.get("build_time_value", 0))
        bid_dollars = int(data.get("bid_dollars", 1))
    except (TypeError, ValueError):
        raise ValueError("Use valid numbers for build time and bid.") from None
    if not 0 < build_time_value <= 10000:
        raise ValueError("Build time must be greater than zero.")
    amount_cents = bid_dollars * 100
    if amount_cents < MIN_SUBMISSION_CENTS or amount_cents > 1_000_000:
        raise ValueError("Bid must be between $1 and $10,000.")

    product_url = canonical_url(str(data.get("url", "")))
    return {
        "name": name,
        "url": product_url,
        "favicon_url": submission_favicon_url(str(data.get("favicon_url", "")), product_url),
        "tagline": name,
        "categories": categories,
        "built_with": built_with,
        "build_time_value": build_time_value,
        "build_time_unit": build_time_unit,
        "submitted_by": "Anonymous",
        "x_user_id": None,
        "x_handle": None,
        "amount_cents": amount_cents,
    }


def validate_outbid(data: dict) -> int:
    if data.get("company_website"):
        raise ValueError("Unable to accept this bid.")
    if data.get("terms_accepted") not in {True, "true", "1", "on", 1}:
        raise ValueError("Accept the Rules, Terms, and Privacy Policy to continue.")
    try:
        bid_dollars = int(data.get("bid_dollars", 0))
    except (TypeError, ValueError):
        raise ValueError("Enter a whole-dollar bid.") from None
    amount_cents = bid_dollars * 100
    if amount_cents < MIN_SUBMISSION_CENTS or amount_cents > 1_000_000:
        raise ValueError("Bid must be between $1 and $10,000.")
    return amount_cents


def payments_enabled() -> bool:
    return bool(
        stripe
        and STRIPE_SECRET_KEY.startswith(("sk_test_", "sk_live_", "rk_test_", "rk_live_"))
    )


def client_ip_hash() -> str:
    ip = request.remote_addr or "unknown"
    return hashlib.sha256(f"{SECRET_KEY}:{ip}".encode()).hexdigest()


class RateLimitError(ValueError):
    def __init__(self, message: str, retry_after: int):
        super().__init__(message)
        self.retry_after = retry_after


def enforce_preview_rate_limit(db: sqlite3.Connection) -> None:
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(minutes=1)).isoformat(timespec="seconds")
    retention_cutoff = (now - timedelta(days=1)).isoformat(timespec="seconds")
    ip_hash = client_ip_hash()
    db.execute("DELETE FROM preview_attempts WHERE created_at < ?", (retention_cutoff,))
    recent = db.execute(
        "SELECT COUNT(*) FROM preview_attempts WHERE ip_hash = ? AND created_at >= ?",
        (ip_hash, cutoff),
    ).fetchone()[0]
    if recent >= SITE_PREVIEW_REQUESTS_PER_MINUTE:
        raise RateLimitError("Too many preview requests. Try again in a minute.", 60)
    db.execute(
        "INSERT INTO preview_attempts (ip_hash, created_at) VALUES (?, ?)",
        (ip_hash, now.isoformat(timespec="seconds")),
    )


def admin_account_hash(account: str) -> str:
    normalized = account.strip().casefold() or "admin"
    return hmac.new(SECRET_KEY.encode(), normalized.encode(), hashlib.sha256).hexdigest()


def admin_login_backoff(
    db: sqlite3.Connection, account: str
) -> tuple[int, int, str, str]:
    now = datetime.now(timezone.utc)
    ip_hash = client_ip_hash()
    account_hash = admin_account_hash(account)
    retention_cutoff = (now - timedelta(days=30)).isoformat(timespec="seconds")
    window_cutoff = (now - timedelta(hours=1)).isoformat(timespec="seconds")
    db.execute("DELETE FROM admin_login_attempts WHERE created_at < ?", (retention_cutoff,))
    latest_success = db.execute(
        """
        SELECT MAX(created_at) FROM admin_login_attempts
        WHERE ip_hash = ? AND account_hash = ? AND succeeded = 1
        """,
        (ip_hash, account_hash),
    ).fetchone()[0]
    failure_cutoff = max(window_cutoff, latest_success or window_cutoff)
    rows = db.execute(
        """
        SELECT created_at FROM admin_login_attempts
        WHERE ip_hash = ? AND account_hash = ? AND succeeded = 0
          AND created_at > ?
        ORDER BY created_at DESC
        """,
        (ip_hash, account_hash, failure_cutoff),
    ).fetchall()
    failure_count = len(rows)
    if failure_count < 5:
        return 0, failure_count, ip_hash, account_hash
    delay_seconds = min(900, 2 ** min(failure_count - 5, 10))
    latest_failure = datetime.fromisoformat(rows[0]["created_at"])
    retry_after = max(0, math.ceil((latest_failure + timedelta(seconds=delay_seconds) - now).total_seconds()))
    return retry_after, failure_count, ip_hash, account_hash


def record_admin_login_attempt(
    db: sqlite3.Connection,
    *,
    ip_hash: str,
    account_hash: str,
    succeeded: bool,
) -> None:
    db.execute(
        """
        INSERT INTO admin_login_attempts (ip_hash, account_hash, succeeded, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            ip_hash,
            account_hash,
            int(succeeded),
            datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        ),
    )


@app.template_filter("tracked_url")
def tracked_outbound_url(url: str) -> str:
    parts = urlsplit(url)
    preferences = outbound_preferences()
    tracking_parameter = preferences["tracking_parameter"]
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key != tracking_parameter
    ]
    query.append((tracking_parameter, preferences["tracking_value"]))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def admin_login_token() -> str:
    return hmac.new(
        SECRET_KEY.encode(), b"admin-login", hashlib.sha256
    ).hexdigest()


def admin_authenticated() -> bool:
    return session.get("admin_authenticated") is True


def verify_admin_password(password: str) -> bool:
    with db_session() as db:
        row = db.execute(
            "SELECT value FROM site_settings WHERE name = 'admin_password_hash'"
        ).fetchone()
    if row:
        return check_password_hash(row["value"], password)
    return hmac.compare_digest(password, ADMIN_PASSWORD)


def admin_form_token(project_id: int) -> str:
    message = f"admin-project:{project_id}".encode()
    return hmac.new(SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def admin_action_token(action: str) -> str:
    message = f"admin-action:{action}".encode()
    return hmac.new(SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def managed_list(setting_name: str, defaults: tuple[str, ...]) -> tuple[str, ...]:
    with db_session() as db:
        row = db.execute(
            "SELECT value FROM site_settings WHERE name = ?", (setting_name,)
        ).fetchone()
    if not row:
        return defaults
    try:
        values = json.loads(row["value"])
    except (json.JSONDecodeError, TypeError):
        return defaults
    if not isinstance(values, list):
        return defaults
    cleaned = tuple(
        value.strip()
        for value in values
        if isinstance(value, str) and value.strip()
    )
    return cleaned or defaults


def managed_categories() -> tuple[str, ...]:
    return managed_list("categories_json", CATEGORIES)


def managed_tools() -> tuple[str, ...]:
    return managed_list("tools_json", TOOLS)


def save_managed_list(setting_name: str, values: tuple[str, ...]) -> None:
    with db_session() as db:
        db.execute(
            """
            INSERT INTO site_settings (name, value) VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET value = excluded.value
            """,
            (setting_name, json.dumps(values)),
        )


def outbound_preferences() -> dict[str, str]:
    cache_name = "_outbound_preferences"
    if has_request_context() and hasattr(g, cache_name):
        return getattr(g, cache_name)
    with db_session() as db:
        rows = db.execute(
            """
            SELECT name, value FROM site_settings
            WHERE name IN ('outbound_mode', 'tracking_parameter', 'tracking_value')
            """
        ).fetchall()
    saved = {row["name"]: row["value"] for row in rows}
    preferences = {
        "mode": saved.get("outbound_mode", "direct"),
        "tracking_parameter": saved.get("tracking_parameter", "utm_source"),
        "tracking_value": saved.get("tracking_value", "yex"),
    }
    if preferences["mode"] not in {"direct", "go"}:
        preferences["mode"] = "direct"
    if has_request_context():
        setattr(g, cache_name, preferences)
    return preferences


def seo_preferences() -> dict[str, str]:
    cache_name = "_seo_preferences"
    if has_request_context() and hasattr(g, cache_name):
        return getattr(g, cache_name)
    with db_session() as db:
        rows = db.execute(
            """
            SELECT name, value FROM site_settings
            WHERE name IN ('seo_title', 'seo_description')
            """
        ).fetchall()
    saved = {row["name"]: row["value"] for row in rows}
    preferences = {
        "title": saved.get(
            "seo_title", f"{SITE_NAME} — The leaderboard for whatever you want"
        ),
        "description": saved.get(
            "seo_description",
            "A public leaderboard for launches, products, tools, and whatever you want to rank.",
        ),
    }
    if has_request_context():
        setattr(g, cache_name, preferences)
    return preferences


@app.template_filter("listing_url")
def public_listing_url(project) -> str:
    if outbound_preferences()["mode"] == "go":
        return url_for("open_project", slug=project["slug"])
    return tracked_outbound_url(project["url"])


def tool_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48] or "tool"


def managed_tool_definitions() -> tuple[dict[str, str], ...]:
    built_ins = {tool["name"].casefold(): tool for tool in TOOL_DEFINITIONS}
    definitions = []
    used_slugs = set()
    for name in managed_tools():
        built_in = built_ins.get(name.casefold())
        definition = dict(built_in) if built_in else {
            "name": name,
            "slug": tool_slug(name),
            "description": f"Explore products built with {name}.",
        }
        base_slug = definition["slug"]
        suffix = 2
        while definition["slug"] in used_slugs:
            definition["slug"] = f"{base_slug}-{suffix}"
            suffix += 1
        used_slugs.add(definition["slug"])
        definitions.append(definition)
    return tuple(definitions)


def admin_response(template_name: str, *, status_code: int = 200, **context):
    response = app.make_response(
        (
            render_template(
                template_name,
                logout_token=admin_login_token(),
                **context,
            ),
            status_code,
        )
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


def render_admin(*, error: str = "", status_code: int = 200):
    search = str(request.args.get("q", "")).strip()[:100]
    listing_status = str(request.args.get("status", "all"))
    if listing_status not in {"all", "live", "hidden"}:
        listing_status = "all"
    try:
        current_page = max(1, int(request.args.get("page", "1")))
    except ValueError:
        current_page = 1
    conditions = []
    parameters: list[object] = []
    if listing_status != "all":
        conditions.append("status = ?")
        parameters.append(listing_status)
    if search:
        conditions.append("(name LIKE ? OR url LIKE ? OR slug LIKE ?)")
        search_term = f"%{search}%"
        parameters.extend([search_term] * 3)
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    per_page = 20
    with db_session() as db:
        total_projects = db.execute(
            f"SELECT COUNT(*) FROM projects {where_clause}", parameters
        ).fetchone()[0]
        total_pages = max(1, (total_projects + per_page - 1) // per_page)
        current_page = min(current_page, total_pages)
        rows = db.execute(
            f"""
            SELECT id, slug, name, url, tagline, category, built_with,
                   build_time_value, build_time_unit, status, is_demo,
                   total_bid_cents, clicks, created_at, updated_at
            FROM projects
            {where_clause}
            ORDER BY status = 'live' DESC, is_demo ASC,
                     total_bid_cents DESC, created_at ASC
            LIMIT ? OFFSET ?
            """,
            [*parameters, per_page, (current_page - 1) * per_page],
        ).fetchall()
    projects = []
    for row in rows:
        project = dict(row)
        try:
            categories = json.loads(project["category"])
        except (json.JSONDecodeError, TypeError):
            categories = [project["category"]]
        if isinstance(categories, str):
            categories = [categories]
        try:
            built_with = json.loads(project["built_with"])
        except (json.JSONDecodeError, TypeError):
            built_with = [project["built_with"]]
        if isinstance(built_with, str):
            built_with = [built_with]
        project["categories"] = categories[:2]
        project["main_built_with"] = built_with[0] if built_with else ""
        project["admin_token"] = admin_form_token(project["id"])
        projects.append(project)
    return admin_response(
        "admin.html",
        status_code=status_code,
        admin_section="links",
        projects=projects,
        error=error,
        add_token=admin_action_token("add-project"),
        categories=managed_categories(),
        tools=managed_tools(),
        search=search,
        listing_status=listing_status,
        current_page=current_page,
        total_pages=total_pages,
        total_projects=total_projects,
    )


def render_admin_stats():
    return admin_response(
        "admin_stats.html",
        admin_section="stats",
        stats=admin_stats_snapshot(),
    )


def render_admin_settings(*, error: str = "", status_code: int = 200):
    return admin_response(
        "admin_settings.html",
        status_code=status_code,
        admin_section="settings",
        error=error,
        password_token=admin_action_token("change-password"),
        taxonomy_token=admin_action_token("manage-taxonomy"),
        outbound_token=admin_action_token("outbound-settings"),
        seo_token=admin_action_token("seo-settings"),
        categories=managed_categories(),
        tools=managed_tools(),
        outbound=outbound_preferences(),
        seo=seo_preferences(),
    )


def enforce_rate_limit(db: sqlite3.Connection) -> None:
    cutoff = datetime.now(timezone.utc).timestamp() - 3600
    ip_hash = client_ip_hash()
    rows = db.execute(
        "SELECT created_at FROM checkout_attempts WHERE ip_hash = ?", (ip_hash,)
    ).fetchall()
    recent = 0
    for row in rows:
        try:
            if datetime.fromisoformat(row["created_at"]).timestamp() >= cutoff:
                recent += 1
        except ValueError:
            continue
    if recent >= 8:
        raise ValueError("Too many checkout attempts. Try again in an hour.")
    db.execute(
        "INSERT INTO checkout_attempts (ip_hash, created_at) VALUES (?, ?)",
        (ip_hash, utc_now()),
    )


def traffic_snapshot(*, record_visit: bool) -> dict[str, int]:
    visitor_id = session.get("visitor_id")
    if not visitor_id:
        visitor_id = secrets.token_urlsafe(18)
        session["visitor_id"] = visitor_id

    count_visit = record_visit and not session.get("visit_counted")
    now = datetime.now(timezone.utc)
    now_text = now.isoformat(timespec="seconds")
    cutoff = (now - timedelta(minutes=5)).isoformat(timespec="seconds")

    with db_session() as db:
        db.execute("DELETE FROM active_visitors WHERE last_seen < ?", (cutoff,))
        db.execute(
            """
            INSERT INTO active_visitors (visitor_id, last_seen)
            VALUES (?, ?)
            ON CONFLICT(visitor_id) DO UPDATE SET last_seen = excluded.last_seen
            """,
            (visitor_id, now_text),
        )
        if count_visit:
            db.execute(
                "UPDATE site_stats SET value = value + 1 WHERE name = 'total_visits'"
            )
        total_visits = db.execute(
            "SELECT value FROM site_stats WHERE name = 'total_visits'"
        ).fetchone()[0]
        online_count = db.execute("SELECT COUNT(*) FROM active_visitors").fetchone()[0]

    if count_visit:
        session["visit_counted"] = True
    return {"online": int(online_count), "total_visits": int(total_visits)}


def fulfill_checkout(session) -> int | None:
    metadata = session.get("metadata") or {}
    pending_id = metadata.get("pending_id")
    session_id = session.get("id")
    if not pending_id or not session_id or session.get("payment_status") != "paid":
        return None

    with db_session() as db:
        db.execute("BEGIN IMMEDIATE")
        prior = db.execute(
            "SELECT project_id FROM payments WHERE stripe_session_id = ?", (session_id,)
        ).fetchone()
        if prior:
            return int(prior["project_id"])

        pending = db.execute(
            "SELECT * FROM pending_submissions WHERE id = ?", (pending_id,)
        ).fetchone()
        if not pending:
            return None
        payload = json.loads(pending["payload_json"])
        amount_cents = int(session.get("amount_total") or pending["amount_cents"])
        project = None
        if payload.get("kind") == "outbid" and payload.get("project_id"):
            project = db.execute(
                "SELECT id FROM projects WHERE id = ?", (int(payload["project_id"]),)
            ).fetchone()
        elif payload.get("url"):
            project = db.execute(
                "SELECT id FROM projects WHERE url = ? AND status = 'live'",
                (payload["url"],),
            ).fetchone()
        now = utc_now()
        if project:
            project_id = int(project["id"])
            db.execute(
                """
                UPDATE projects
                SET total_bid_cents = total_bid_cents + ?,
                    favicon_url = COALESCE(favicon_url, ?),
                    updated_at = ?
                WHERE id = ?
                """,
                (amount_cents, payload.get("favicon_url"), now, project_id),
            )
        else:
            if payload.get("kind") == "outbid":
                return None
            cursor = db.execute(
                """
                INSERT INTO projects (
                    slug, name, url, tagline, category, built_with,
                    build_time_value, build_time_unit, submitted_by,
                    favicon_url, total_bid_cents, is_demo, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'live', ?, ?)
                """,
                (
                    make_slug(db, payload["name"]),
                    payload["name"],
                    payload["url"],
                    payload["tagline"],
                    json.dumps(
                        payload.get("categories")
                        or [payload.get("category", "Other")]
                    ),
                    json.dumps(payload["built_with"]),
                    payload["build_time_value"],
                    payload["build_time_unit"],
                    "Anonymous",
                    payload.get("favicon_url"),
                    amount_cents,
                    now,
                    now,
                ),
            )
            project_id = int(cursor.lastrowid)

        db.execute(
            """
            INSERT INTO payments (
                project_id, pending_id, stripe_session_id, payment_intent_id,
                amount_cents, currency, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'paid', ?)
            """,
            (
                project_id,
                pending_id,
                session_id,
                session.get("payment_intent"),
                amount_cents,
                session.get("currency") or "usd",
                now,
            ),
        )
        db.execute(
            "UPDATE pending_submissions SET status = 'completed', completed_at = ? WHERE id = ?",
            (now, pending_id),
        )
        return project_id


def project_rows(tool_name: str | None = None) -> list[dict]:
    with db_session() as db:
        rows = db.execute(
            """
            SELECT * FROM projects
            WHERE status = 'live'
            ORDER BY total_bid_cents DESC, created_at ASC
            """
        ).fetchall()
    projects = []
    for row in rows:
        project = dict(row)
        project["built_with"] = json.loads(project["built_with"])
        if tool_name and tool_name not in project["built_with"]:
            continue
        project["rank"] = len(projects) + 1
        try:
            categories = json.loads(project["category"])
        except (json.JSONDecodeError, TypeError):
            categories = [project["category"]]
        if isinstance(categories, str):
            categories = [categories]
        project["categories"] = categories[:2]
        project["favicon_url"] = project.get("favicon_url") or submission_favicon_url("", project["url"])
        projects.append(project)
    return projects


def listing_highlights() -> tuple[list[dict], list[dict]]:
    with db_session() as db:
        newest = db.execute(
            """
            SELECT slug, name, url FROM projects
            WHERE status = 'live' AND is_demo = 0
            ORDER BY created_at DESC, id DESC
            LIMIT 10
            """
        ).fetchall()
        top_clicks = db.execute(
            """
            SELECT slug, name, url, clicks FROM projects
            WHERE status = 'live' AND is_demo = 0
            ORDER BY clicks DESC, created_at DESC, id DESC
            LIMIT 10
            """
        ).fetchall()
    return [dict(row) for row in newest], [dict(row) for row in top_clicks]


def project_detail_snapshot(project_slug: str) -> tuple[dict, int] | None:
    projects = project_rows()
    project = next((item for item in projects if item["slug"] == project_slug), None)
    if not project:
        return None
    return project, len(projects)


def admin_stats_snapshot() -> dict:
    now = datetime.now(timezone.utc)
    active_cutoff = (now - timedelta(minutes=5)).isoformat(timespec="seconds")
    month_cutoff = (now - timedelta(days=30)).isoformat(timespec="seconds")
    with db_session() as db:
        totals = db.execute(
            """
            SELECT
                COUNT(*) AS total_listings,
                SUM(status = 'live') AS live_listings,
                SUM(status = 'hidden') AS hidden_listings,
                COALESCE(SUM(clicks), 0) AS total_clicks,
                COALESCE(SUM(total_bid_cents), 0) AS total_bid_cents,
                SUM(created_at >= ?) AS new_last_30_days
            FROM projects
            WHERE is_demo = 0
            """,
            (month_cutoff,),
        ).fetchone()
        visits = db.execute(
            "SELECT value FROM site_stats WHERE name = 'total_visits'"
        ).fetchone()
        online = db.execute(
            "SELECT COUNT(*) FROM active_visitors WHERE last_seen >= ?",
            (active_cutoff,),
        ).fetchone()[0]
        payments = db.execute(
            """
            SELECT COUNT(*) AS payment_count,
                   COALESCE(SUM(amount_cents), 0) AS revenue_cents
            FROM payments WHERE status = 'paid'
            """
        ).fetchone()
        top_projects = db.execute(
            """
            SELECT slug, name, url, clicks, total_bid_cents
            FROM projects
            WHERE status = 'live' AND is_demo = 0
            ORDER BY clicks DESC, total_bid_cents DESC
            LIMIT 8
            """
        ).fetchall()
        classification_rows = db.execute(
            """
            SELECT category, built_with FROM projects
            WHERE status = 'live' AND is_demo = 0
            """
        ).fetchall()

    category_counts: dict[str, int] = {}
    tool_counts: dict[str, int] = {}
    for row in classification_rows:
        for field, target in (("category", category_counts), ("built_with", tool_counts)):
            try:
                values = json.loads(row[field])
            except (json.JSONDecodeError, TypeError):
                values = [row[field]]
            if isinstance(values, str):
                values = [values]
            for value in values:
                if isinstance(value, str) and value:
                    target[value] = target.get(value, 0) + 1

    total_listings = int(totals["total_listings"] or 0)
    total_clicks = int(totals["total_clicks"] or 0)
    total_visits = int(visits["value"] if visits else 0)
    return {
        "total_listings": total_listings,
        "live_listings": int(totals["live_listings"] or 0),
        "hidden_listings": int(totals["hidden_listings"] or 0),
        "total_clicks": total_clicks,
        "total_bid_cents": int(totals["total_bid_cents"] or 0),
        "new_last_30_days": int(totals["new_last_30_days"] or 0),
        "total_visits": total_visits,
        "online": int(online),
        "payment_count": int(payments["payment_count"] or 0),
        "revenue_cents": int(payments["revenue_cents"] or 0),
        "clicks_per_listing": round(total_clicks / total_listings, 1) if total_listings else 0,
        "listing_rate": round(total_listings / total_visits * 100, 1) if total_visits else 0,
        "top_projects": [dict(row) for row in top_projects],
        "category_counts": sorted(category_counts.items(), key=lambda item: (-item[1], item[0]))[:8],
        "tool_counts": sorted(tool_counts.items(), key=lambda item: (-item[1], item[0]))[:8],
        "category_max": max(category_counts.values(), default=1),
        "tool_max": max(tool_counts.values(), default=1),
    }


@app.after_request
def set_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data: https:; "
        "connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'",
    )
    return response


@app.get("/")
def home():
    return render_leaderboard()


def render_leaderboard(active_tool: dict[str, str] | None = None):
    try:
        current_page = int(request.args.get("page", "1"))
    except ValueError:
        abort(404)
    if current_page < 1:
        abort(404)

    all_projects = project_rows(active_tool["name"] if active_tool else None)
    total_projects = len(all_projects)
    per_page = 20
    total_pages = max(1, (total_projects + per_page - 1) // per_page)
    if current_page > total_pages:
        abort(404)
    page_offset = (current_page - 1) * per_page
    projects = all_projects[page_offset : page_offset + per_page]
    total_builds = sum(1 for project in all_projects if not project["is_demo"])
    traffic = traffic_snapshot(record_visit=True)
    newest_listings, top_clicked_listings = listing_highlights() if not active_tool else ([], [])
    tool_definitions = managed_tool_definitions()
    featured_tools = tuple(
        tool for tool in tool_definitions if tool["slug"] in FEATURED_TOOL_SLUGS
    )
    more_tools = tuple(
        tool for tool in tool_definitions if tool["slug"] not in FEATURED_TOOL_SLUGS
    )
    return render_template(
        "index.html",
        projects=projects,
        tools=managed_tools(),
        featured_tools=featured_tools,
        more_tools=more_tools,
        active_tool=active_tool,
        current_page=current_page,
        page_offset=page_offset,
        total_pages=total_pages,
        total_projects=total_projects,
        categories=managed_categories(),
        min_bid=MIN_SUBMISSION_CENTS // 100,
        payments_ready=payments_enabled(),
        total_builds=total_builds,
        online_count=traffic["online"],
        total_visits=traffic["total_visits"],
        newest_listings=newest_listings,
        top_clicked_listings=top_clicked_listings,
        outbound_mode=outbound_preferences()["mode"],
        seo=seo_preferences(),
    )


@app.get("/built-with/<tool_slug>")
def built_with(tool_slug: str):
    tool = next(
        (tool for tool in managed_tool_definitions() if tool["slug"] == tool_slug),
        None,
    )
    if not tool:
        abort(404)
    return render_leaderboard(tool)


@app.get("/product/<project_slug>")
def product_detail(project_slug: str):
    snapshot = project_detail_snapshot(project_slug)
    if not snapshot:
        abort(404)
    project, total_projects = snapshot
    traffic = traffic_snapshot(record_visit=True)
    tool_links = {tool["name"]: tool["slug"] for tool in managed_tool_definitions()}
    detail_url = f"{BASE_URL}{url_for('product_detail', project_slug=project['slug'])}"
    share_text = f"{project['name']} is #{project['rank']} on the {SITE_NAME} leaderboard."
    return render_template(
        "product.html",
        project=project,
        total_projects=total_projects,
        min_bid=MIN_SUBMISSION_CENTS // 100,
        payments_ready=payments_enabled(),
        online_count=traffic["online"],
        total_visits=traffic["total_visits"],
        outbound_mode=outbound_preferences()["mode"],
        detail_url=detail_url,
        share_text=share_text,
        tool_links=tool_links,
        x_share_url="https://x.com/intent/post?" + urlencode(
            {"text": share_text, "url": detail_url}
        ),
        linkedin_share_url="https://www.linkedin.com/sharing/share-offsite/?" + urlencode(
            {"url": detail_url}
        ),
    )


@app.get("/rules")
def rules():
    return render_template("legal.html", document="rules")


@app.get("/terms")
def terms():
    return render_template("legal.html", document="terms")


@app.get("/privacy")
def privacy():
    return render_template("legal.html", document="privacy")


@app.get("/admin")
def admin_dashboard():
    if not admin_authenticated():
        return redirect(url_for("admin_login"))
    return render_admin()


@app.get("/admin/stats")
def admin_stats():
    if not admin_authenticated():
        return redirect(url_for("admin_login"))
    return render_admin_stats()


@app.get("/admin/settings")
def admin_settings():
    if not admin_authenticated():
        return redirect(url_for("admin_login"))
    return render_admin_settings()


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        supplied_token = str(request.form.get("admin_token", ""))
        if not hmac.compare_digest(supplied_token, admin_login_token()):
            abort(403)
        supplied_username = str(request.form.get("username", ""))
        supplied_password = str(request.form.get("password", ""))
        with db_session() as db:
            retry_after, failure_count, ip_hash, account_hash = admin_login_backoff(
                db, supplied_username
            )
        if retry_after:
            app.logger.warning(
                "admin_login_blocked ip_hash=%s account_hash=%s failures=%d retry_after=%d",
                ip_hash[:12],
                account_hash[:12],
                failure_count,
                retry_after,
            )
            response = app.make_response(
                (
                    render_template(
                        "admin_login.html",
                        admin_token=admin_login_token(),
                        error=f"Too many failed attempts. Try again in {retry_after} seconds.",
                    ),
                    429,
                )
            )
            response.headers["Retry-After"] = str(retry_after)
        else:
            username_valid = hmac.compare_digest(supplied_username, ADMIN_USERNAME)
            password_valid = verify_admin_password(supplied_password)
            if username_valid and password_valid:
                with db_session() as db:
                    record_admin_login_attempt(
                        db,
                        ip_hash=ip_hash,
                        account_hash=account_hash,
                        succeeded=True,
                    )
                session.clear()
                session["admin_authenticated"] = True
                return redirect(url_for("admin_dashboard"))
            with db_session() as db:
                record_admin_login_attempt(
                    db,
                    ip_hash=ip_hash,
                    account_hash=account_hash,
                    succeeded=False,
                )
            new_failure_count = failure_count + 1
            log_method = app.logger.warning if new_failure_count >= 5 else app.logger.info
            log_method(
                "admin_login_failed ip_hash=%s account_hash=%s failures=%d",
                ip_hash[:12],
                account_hash[:12],
                new_failure_count,
            )
            response = app.make_response(
                (
                    render_template(
                        "admin_login.html",
                        admin_token=admin_login_token(),
                        error="Incorrect username or password.",
                    ),
                    401,
                )
            )
    elif admin_authenticated():
        return redirect(url_for("admin_dashboard"))
    else:
        response = app.make_response(
            render_template(
                "admin_login.html", admin_token=admin_login_token(), error=""
            )
        )
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@app.post("/admin/logout")
def admin_logout():
    supplied_token = str(request.form.get("admin_token", ""))
    if not hmac.compare_digest(supplied_token, admin_login_token()):
        abort(403)
    session.pop("admin_authenticated", None)
    return redirect(url_for("admin_login"))


@app.post("/admin/projects")
def admin_add_project():
    if not admin_authenticated():
        abort(403)
    supplied_token = str(request.form.get("admin_token", ""))
    if not hmac.compare_digest(
        supplied_token, admin_action_token("add-project")
    ):
        abort(403)

    try:
        name = str(request.form.get("name", "")).strip()
        if not name or len(name) > 64:
            raise ValueError("Use a project name up to 64 characters.")
        project_url = canonical_url(str(request.form.get("url", "")))
        tagline = name
        primary_category = str(
            request.form.get("category_primary", request.form.get("category", ""))
        ).strip()
        secondary_category = str(request.form.get("category_secondary", "")).strip()
        categories = [primary_category]
        if secondary_category and secondary_category != primary_category:
            categories.append(secondary_category)
        if not primary_category or any(item not in managed_categories() for item in categories):
            raise ValueError("Choose one or two valid categories.")
        built_with = str(request.form.get("built_with", ""))
        if built_with not in managed_tools():
            raise ValueError("Choose one valid main build tool.")
        try:
            bid_dollars = int(str(request.form.get("bid_dollars", "")))
            build_time_value = float(str(request.form.get("build_time_value", "1")))
        except ValueError:
            raise ValueError("Enter valid bid and build-time numbers.") from None
        if not 1 <= bid_dollars <= 10000:
            raise ValueError("Bid must be between $1 and $10,000.")
        build_time_unit = str(request.form.get("build_time_unit", "hours"))
        if not 0 < build_time_value <= 10000 or build_time_unit not in TIME_UNITS:
            raise ValueError("Choose a valid build time.")

        now = utc_now()
        with db_session() as db:
            slug = make_slug(db, name)
            db.execute(
                """
                INSERT INTO projects (
                    slug, name, url, tagline, category, built_with,
                    build_time_value, build_time_unit, submitted_by, favicon_url,
                    total_bid_cents, is_demo, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Anonymous', ?, ?, 0, 'live', ?, ?)
                """,
                (
                    slug,
                    name,
                    project_url,
                    tagline,
                    json.dumps(categories),
                    json.dumps([built_with]),
                    build_time_value,
                    build_time_unit,
                    submission_favicon_url("", project_url),
                    bid_dollars * 100,
                    now,
                    now,
                ),
            )
    except ValueError as error:
        return render_admin(error=str(error), status_code=400)
    except sqlite3.IntegrityError:
        return render_admin(
            error="That URL is already assigned to another listing.", status_code=409
        )

    return redirect(url_for("admin_dashboard", added="1"))


@app.post("/admin/password")
def admin_change_password():
    if not admin_authenticated():
        abort(403)
    supplied_token = str(request.form.get("admin_token", ""))
    if not hmac.compare_digest(
        supplied_token, admin_action_token("change-password")
    ):
        abort(403)

    current_password = str(request.form.get("current_password", ""))
    new_password = str(request.form.get("new_password", ""))
    confirm_password = str(request.form.get("confirm_password", ""))
    if not verify_admin_password(current_password):
        return render_admin_settings(error="Current password is incorrect.", status_code=400)
    if len(new_password) < 12:
        return render_admin_settings(
            error="New password must be at least 12 characters.", status_code=400
        )
    if new_password != confirm_password:
        return render_admin_settings(error="New passwords do not match.", status_code=400)

    password_hash = generate_password_hash(new_password)
    with db_session() as db:
        db.execute(
            """
            INSERT INTO site_settings (name, value)
            VALUES ('admin_password_hash', ?)
            ON CONFLICT(name) DO UPDATE SET value = excluded.value
            """,
            (password_hash,),
        )
    return redirect(url_for("admin_settings", password_updated="1"))


@app.post("/admin/settings/taxonomy")
def admin_manage_taxonomy():
    if not admin_authenticated():
        abort(403)
    supplied_token = str(request.form.get("admin_token", ""))
    if not hmac.compare_digest(
        supplied_token, admin_action_token("manage-taxonomy")
    ):
        abort(403)

    kind = str(request.form.get("kind", ""))
    operation = str(request.form.get("operation", ""))
    if kind == "category":
        setting_name = "categories_json"
        values = managed_categories()
    elif kind == "tool":
        setting_name = "tools_json"
        values = managed_tools()
    else:
        abort(400)

    if operation == "add":
        name = " ".join(str(request.form.get("name", "")).split())
        if not name or len(name) > 40:
            return render_admin_settings(
                error="Use a name between 1 and 40 characters.", status_code=400
            )
        if any(item.casefold() == name.casefold() for item in values):
            return render_admin_settings(
                error=f"{name} already exists.", status_code=409
            )
        values = (*values, name)
    elif operation == "remove":
        name = str(request.form.get("name", ""))
        if len(values) <= 1:
            return render_admin_settings(
                error="Keep at least one option.", status_code=400
            )
        values = tuple(item for item in values if item != name)
        if len(values) == len(managed_categories() if kind == "category" else managed_tools()):
            abort(404)
    else:
        abort(400)

    save_managed_list(setting_name, values)
    return redirect(url_for("admin_settings", updated=kind))


@app.post("/admin/settings/outbound")
def admin_update_outbound_settings():
    if not admin_authenticated():
        abort(403)
    supplied_token = str(request.form.get("admin_token", ""))
    if not hmac.compare_digest(
        supplied_token, admin_action_token("outbound-settings")
    ):
        abort(403)

    mode = str(request.form.get("mode", ""))
    tracking_parameter = str(request.form.get("tracking_parameter", "")).strip()
    tracking_value = str(request.form.get("tracking_value", "")).strip()
    if mode not in {"direct", "go"}:
        return render_admin_settings(error="Choose a valid URL mode.", status_code=400)
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,50}", tracking_parameter):
        return render_admin_settings(
            error="Tracking parameter may use letters, numbers, dot, dash, or underscore.",
            status_code=400,
        )
    if not tracking_value or len(tracking_value) > 100:
        return render_admin_settings(
            error="Tracking value must be between 1 and 100 characters.",
            status_code=400,
        )

    with db_session() as db:
        db.executemany(
            """
            INSERT INTO site_settings (name, value) VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET value = excluded.value
            """,
            (
                ("outbound_mode", mode),
                ("tracking_parameter", tracking_parameter),
                ("tracking_value", tracking_value),
            ),
        )
    return redirect(url_for("admin_settings", outbound_updated="1"))


@app.post("/admin/settings/seo")
def admin_update_seo_settings():
    if not admin_authenticated():
        abort(403)
    supplied_token = str(request.form.get("admin_token", ""))
    if not hmac.compare_digest(supplied_token, admin_action_token("seo-settings")):
        abort(403)

    title = " ".join(str(request.form.get("title", "")).split())
    description = " ".join(str(request.form.get("description", "")).split())
    if not 5 <= len(title) <= 70:
        return render_admin_settings(
            error="SEO title must be between 5 and 70 characters.", status_code=400
        )
    if not 20 <= len(description) <= 180:
        return render_admin_settings(
            error="Meta description must be between 20 and 180 characters.",
            status_code=400,
        )

    with db_session() as db:
        db.executemany(
            """
            INSERT INTO site_settings (name, value) VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET value = excluded.value
            """,
            (("seo_title", title), ("seo_description", description)),
        )
    return redirect(url_for("admin_settings", seo_updated="1"))


@app.post("/admin/projects/<int:project_id>")
def admin_update_project(project_id: int):
    if not admin_authenticated():
        abort(403)
    supplied_token = str(request.form.get("admin_token", ""))
    if not hmac.compare_digest(supplied_token, admin_form_token(project_id)):
        abort(403)

    action = str(request.form.get("action", ""))
    try:
        with db_session() as db:
            project = db.execute(
                "SELECT id, url FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            if not project:
                abort(404)
            if action == "save":
                name = str(request.form.get("name", "")).strip()
                if not name or len(name) > 64:
                    raise ValueError("Use a project name up to 64 characters.")
                tagline = name
                new_url = canonical_url(str(request.form.get("url", "")))
                primary_category = str(request.form.get("category_primary", "")).strip()
                secondary_category = str(request.form.get("category_secondary", "")).strip()
                categories = [primary_category]
                if secondary_category and secondary_category != primary_category:
                    categories.append(secondary_category)
                if not primary_category or any(item not in managed_categories() for item in categories):
                    raise ValueError("Choose one or two valid categories.")
                built_with = str(request.form.get("built_with", "")).strip()
                if built_with not in managed_tools():
                    raise ValueError("Choose one valid main build tool.")
                try:
                    build_time_value = float(str(request.form.get("build_time_value", "")))
                except ValueError:
                    raise ValueError("Enter a valid build time.") from None
                build_time_unit = str(request.form.get("build_time_unit", ""))
                if not 0 < build_time_value <= 10000 or build_time_unit not in TIME_UNITS:
                    raise ValueError("Choose a valid build time.")
                favicon_url = (
                    submission_favicon_url("", new_url)
                    if new_url != project["url"]
                    else None
                )
                db.execute(
                    """
                    UPDATE projects
                    SET name = ?, url = ?, tagline = ?, category = ?, built_with = ?,
                        build_time_value = ?, build_time_unit = ?,
                        favicon_url = COALESCE(?, favicon_url), updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        name,
                        new_url,
                        tagline,
                        json.dumps(categories),
                        json.dumps([built_with]),
                        build_time_value,
                        build_time_unit,
                        favicon_url,
                        utc_now(),
                        project_id,
                    ),
                )
            elif action in {"hide", "show"}:
                status = "hidden" if action == "hide" else "live"
                db.execute(
                    "UPDATE projects SET status = ?, updated_at = ? WHERE id = ?",
                    (status, utc_now(), project_id),
                )
            else:
                abort(400)
    except ValueError as error:
        return render_admin(error=str(error), status_code=400)
    except sqlite3.IntegrityError:
        return render_admin(
            error="That URL is already assigned to another listing.", status_code=409
        )

    return redirect(url_for("admin_dashboard", updated="1"))


@app.get("/sitemap.xml")
def sitemap():
    with db_session() as db:
        product_slugs = [
            row["slug"]
            for row in db.execute(
                "SELECT slug FROM projects WHERE status = 'live' ORDER BY id"
            ).fetchall()
        ]
    urls = [
        f"{BASE_URL}/",
        f"{BASE_URL}/rules",
        f"{BASE_URL}/terms",
        f"{BASE_URL}/privacy",
    ] + [
        f"{BASE_URL}/built-with/{tool['slug']}" for tool in managed_tool_definitions()
    ] + [
        f"{BASE_URL}/product/{slug}" for slug in product_slugs
    ]
    body = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
    body += "\n".join(f"  <url><loc>{url}</loc></url>" for url in urls)
    body += "\n</urlset>\n"
    return Response(body, content_type="application/xml")


@app.get("/robots.txt")
def robots():
    return Response(
        f"User-agent: *\nAllow: /\nDisallow: /admin\nSitemap: {BASE_URL}/sitemap.xml\n",
        content_type="text/plain",
    )


@app.post("/api/presence")
def presence():
    return jsonify(traffic_snapshot(record_visit=False))


@app.post("/api/site-preview")
def site_preview():
    payload = request.get_json(silent=True) or {}
    try:
        product_url = canonical_url(str(payload.get("url", "")))
    except ValueError as error:
        return jsonify(error=str(error)), 400
    with db_session() as db:
        try:
            enforce_preview_rate_limit(db)
        except RateLimitError as error:
            return (
                jsonify(error=str(error)),
                429,
                {"Retry-After": str(error.retry_after)},
            )
    try:
        details = fetch_site_metadata(product_url)
    except ValueError as error:
        return jsonify(error=str(error)), 422
    except (HTTPError, URLError, TimeoutError, OSError):
        return jsonify(error="We couldn't read that site. You can still enter the details manually."), 422
    with db_session() as db:
        existing = db.execute(
            "SELECT slug, name, total_bid_cents FROM projects WHERE url = ? AND status = 'live'",
            (product_url,),
        ).fetchone()
    details["existing_bid_cents"] = int(existing["total_bid_cents"]) if existing else 0
    details["existing_slug"] = existing["slug"] if existing else ""
    details["existing_name"] = existing["name"] if existing else ""
    return jsonify(details)


@app.post("/api/checkout")
def create_checkout():
    try:
        submission = validate_submission(request.get_json(silent=True) or {})
    except ValueError as error:
        return jsonify(error=str(error)), 400
    with db_session() as db:
        existing = db.execute(
            "SELECT slug FROM projects WHERE url = ? AND status = 'live'",
            (submission["url"],),
        ).fetchone()
    if existing:
        return jsonify(
            error="This website is already listed. Use Help bid on its listing instead.",
            code="existing_listing",
            slug=existing["slug"],
        ), 409
    if not payments_enabled():
        return jsonify(
            error="Stripe Checkout is not connected yet. The submission form is ready for keys.",
            code="payments_unavailable",
        ), 503

    pending_id = uuid.uuid4().hex
    payload = {key: value for key, value in submission.items() if key != "amount_cents"}
    try:
        with db_session() as db:
            enforce_rate_limit(db)
            db.execute(
                """
                INSERT INTO pending_submissions
                    (id, payload_json, amount_cents, status, created_at)
                VALUES (?, ?, ?, 'pending', ?)
                """,
                (pending_id, json.dumps(payload), submission["amount_cents"], utc_now()),
            )
        checkout = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": submission["amount_cents"],
                        "product_data": {
                            "name": f"List {submission['name']} on {SITE_NAME}",
                            "description": "One-time anti-spam submission and full leaderboard bid.",
                        },
                    },
                    "quantity": 1,
                }
            ],
            client_reference_id=pending_id,
            metadata={"pending_id": pending_id, "kind": "new_listing"},
            payment_intent_data={"metadata": {"pending_id": pending_id}},
            success_url=f"{BASE_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{BASE_URL}/?checkout=cancelled#leaderboard",
        )
        with db_session() as db:
            db.execute(
                "UPDATE pending_submissions SET stripe_session_id = ? WHERE id = ?",
                (checkout.id, pending_id),
            )
        return jsonify(url=checkout.url)
    except ValueError as error:
        return jsonify(error=str(error)), 429
    except Exception:
        app.logger.exception("Unable to create Stripe Checkout Session")
        return jsonify(error="Checkout could not be started. Please try again."), 502


@app.post("/api/outbid/<project_slug>")
def create_outbid_checkout(project_slug: str):
    data = request.get_json(silent=True) or {}
    try:
        amount_cents = validate_outbid(data)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    if not payments_enabled():
        return jsonify(
            error="Stripe Checkout is not connected yet.", code="payments_unavailable"
        ), 503

    with db_session() as db:
        project = db.execute(
            "SELECT id, slug, name, url, total_bid_cents FROM projects WHERE slug = ? AND status = 'live'",
            (project_slug,),
        ).fetchone()
    if not project:
        return jsonify(error="This listing is no longer available."), 404

    pending_id = uuid.uuid4().hex
    payload = {
        "kind": "outbid",
        "project_id": int(project["id"]),
        "url": project["url"],
        "name": project["name"],
    }
    try:
        with db_session() as db:
            enforce_rate_limit(db)
            db.execute(
                """
                INSERT INTO pending_submissions
                    (id, payload_json, amount_cents, status, created_at)
                VALUES (?, ?, ?, 'pending', ?)
                """,
                (pending_id, json.dumps(payload), amount_cents, utc_now()),
            )
        checkout = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": amount_cents,
                        "product_data": {
                            "name": f"Help bid for {project['name']} on {SITE_NAME}",
                            "description": (
                                f"Adds ${amount_cents // 100} to its leaderboard bid, "
                                f"for a ${int(project['total_bid_cents']) // 100 + amount_cents // 100} total."
                            ),
                        },
                    },
                    "quantity": 1,
                }
            ],
            client_reference_id=pending_id,
            metadata={"pending_id": pending_id, "kind": "outbid"},
            payment_intent_data={"metadata": {"pending_id": pending_id}},
            success_url=f"{BASE_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{BASE_URL}/product/{project['slug']}?checkout=cancelled",
        )
        with db_session() as db:
            db.execute(
                "UPDATE pending_submissions SET stripe_session_id = ? WHERE id = ?",
                (checkout.id, pending_id),
            )
        return jsonify(url=checkout.url)
    except ValueError as error:
        return jsonify(error=str(error)), 429
    except Exception:
        app.logger.exception("Unable to create Help bid Checkout Session")
        return jsonify(error="Checkout could not be started. Please try again."), 502


@app.post("/stripe/webhook")
def stripe_webhook():
    if not stripe or not STRIPE_WEBHOOK_SECRET:
        return jsonify(error="Webhook is not configured."), 503
    try:
        event = stripe.Webhook.construct_event(
            request.get_data(),
            request.headers.get("Stripe-Signature", ""),
            STRIPE_WEBHOOK_SECRET,
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        return jsonify(error="Invalid webhook signature."), 400

    if event["type"] in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
        fulfill_checkout(event["data"]["object"])
    return jsonify(received=True)


@app.get("/success")
def checkout_success():
    session_id = request.args.get("session_id", "")
    project = None
    if payments_enabled() and session_id.startswith("cs_"):
        try:
            checkout = stripe.checkout.Session.retrieve(session_id)
            project_id = fulfill_checkout(checkout)
            if project_id:
                with db_session() as db:
                    row = db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
                    if row:
                        project = dict(row)
        except Exception:
            app.logger.exception("Unable to confirm Checkout Session")
    return render_template("success.html", project=project)


def record_project_click(slug: str):
    with db_session() as db:
        row = db.execute(
            "SELECT id, url FROM projects WHERE slug = ? AND status = 'live'", (slug,)
        ).fetchone()
        if not row:
            return None
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(hours=1)).isoformat(timespec="seconds")
        ip_hash = client_ip_hash()
        db.execute("DELETE FROM click_events WHERE created_at < ?", (cutoff,))
        counted = db.execute(
            """
            INSERT INTO click_events (project_id, ip_hash, created_at)
            SELECT ?, ?, ?
            WHERE (
                SELECT COUNT(*) FROM click_events
                WHERE ip_hash = ? AND created_at >= ?
            ) < 5
            """,
            (row["id"], ip_hash, now.isoformat(timespec="seconds"), ip_hash, cutoff),
        )
        if counted.rowcount:
            db.execute("UPDATE projects SET clicks = clicks + 1 WHERE id = ?", (row["id"],))
    return row


@app.post("/api/click/<slug>")
def record_direct_click(slug: str):
    if not record_project_click(slug):
        abort(404)
    return "", 204


@app.get("/go/<slug>")
def open_project(slug: str):
    row = record_project_click(slug)
    if not row:
        return redirect("/")
    return redirect(tracked_outbound_url(row["url"]), code=302)


@app.get("/health")
def health():
    try:
        with db_session() as db:
            db.execute("SELECT 1").fetchone()
        return jsonify(status="ok", database="ok", payments=payments_enabled())
    except sqlite3.Error:
        return jsonify(status="error", database="unavailable"), 503


init_db()


if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=False,
    )
