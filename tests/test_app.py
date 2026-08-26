import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TEST_DIR = tempfile.TemporaryDirectory()
os.environ["DATABASE_PATH"] = str(Path(TEST_DIR.name) / "test.db")
os.environ["SEED_DEMO_DATA"] = "0"
os.environ["STRIPE_SECRET_KEY"] = ""
os.environ["FLASK_SECRET_KEY"] = "test-secret"
os.environ["ADMIN_PASSWORD"] = "admin"
os.environ["ALLOW_INSECURE_DEV_CONFIG"] = "1"
os.environ["TRUST_PROXY_HEADERS"] = "0"
os.environ["TRUSTED_HOSTS"] = "localhost,127.0.0.1"

import app as application  # noqa: E402


class AppTests(unittest.TestCase):
    def setUp(self):
        self.client = application.app.test_client()
        with application.db_session() as db:
            db.execute("DELETE FROM click_events")
            db.execute("DELETE FROM preview_attempts")
            db.execute("DELETE FROM admin_login_attempts")
            db.execute(
                "DELETE FROM site_settings WHERE name IN ('admin_password_hash', 'categories_json', 'tools_json', 'outbound_mode', 'tracking_parameter', 'tracking_value', 'seo_title', 'seo_description')"
            )

    def test_home_contains_product_positioning(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"The leaderboard for things", response.data)
        self.assertIn(b"whatever you want", response.data)
        self.assertNotIn(b'class="ai-word"', response.data)
        self.assertIn(b"Ship it. List it. Outbid it.", response.data)
        self.assertIn(b"You built it. Now get people to see it.", response.data)
        self.assertIn(b'A public launch board with <span class="dofollow-link">dofollow links</span>.', response.data)
        self.assertIn(b'class="hero-subline"', response.data)
        self.assertIn(b'class="hero-subline-icon"', response.data)
        self.assertNotIn(b'class="closing-statement', response.data)
        self.assertNotIn(b"pay-to-rank launch board", response.data)
        self.assertNotIn(b"A tiny attention market", response.data)
        self.assertNotIn(b"Built by", response.data)
        self.assertNotIn(b"Open Source on GitHub", response.data)
        self.assertIn(b"Made with", response.data)
        self.assertIn(b'href="https://yex.lol"', response.data)
        self.assertNotIn(b"Submitted by", response.data)
        self.assertIn(b"List for $1", response.data)
        self.assertNotIn(b"Explore the board", response.data)
        self.assertIn(b'class="click-count"', response.data)
        self.assertIn(b'class="project-favicon"', response.data)
        self.assertNotIn(b'href="/go/', response.data)
        self.assertIn(b"utm_source=yex", response.data)
        self.assertIn(b"data-project-slug=", response.data)
        self.assertNotIn(b"data-project-url=", response.data)
        self.assertIn(b'name="terms_accepted"', response.data)
        self.assertIn(b"We'll pull in the name.", response.data)
        self.assertNotIn(b'name="tagline"', response.data)
        self.assertIn(b"All payments are final.", response.data)
        self.assertIn(b"One purchase keeps the listing live for the lifetime of Whatever Board", response.data)
        self.assertIn(b'href="/rules"', response.data)
        self.assertIn(b'href="/terms"', response.data)
        self.assertIn(b'href="/privacy"', response.data)
        self.assertIn(b'class="theme-toggle js-theme-toggle"', response.data)
        self.assertIn(b'/static/theme.js', response.data)
        self.assertIn(b'hero-motif--orbit', response.data)
        self.assertIn(b'hero-motif--pixels', response.data)
        self.assertIn(b'class="section-signal"', response.data)
        self.assertIn(b"New listings", response.data)
        self.assertIn(b"Top clicks", response.data)
        self.assertIn(b"Live leaderboard", response.data)
        self.assertNotIn(b"What people are shipping", response.data)
        self.assertIn(b'class="board-highlights"', response.data)
        self.assertIn(b"All apps", response.data)
        self.assertIn(b'/built-with/deepseek#leaderboard', response.data)
        self.assertIn(b'/built-with/grok#leaderboard', response.data)
        self.assertIn(b"visitors since launch", response.data)
        self.assertNotIn(b'name="submitted_by"', response.data)
        self.assertIn(b"Mainly built with", response.data)
        self.assertIn(b'type="radio" name="built_with"', response.data)
        self.assertIn(b"Help bid", response.data)
        self.assertIn(b"See detail", response.data)
        self.assertIn(b'id="outbid-dialog"', response.data)
        self.assertIn(b"Choose your bid", response.data)
        self.assertNotIn(b"What did you ship?", response.data)

    def test_share_defaults_have_ten_safe_example_links(self):
        self.assertEqual(len(application.EXAMPLE_LISTINGS), 10)
        self.assertTrue(
            all(row[2].startswith("https://example.com/") for row in application.EXAMPLE_LISTINGS)
        )

    def test_tool_pages_are_indexable(self):
        response = self.client.get("/built-with/codex")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Projects built with Codex", response.data)
        self.assertIn(b'rel="canonical"', response.data)
        self.assertEqual(self.client.get("/built-with/not-a-tool").status_code, 404)

    def test_sitemap_lists_tool_pages(self):
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"/built-with/claude", response.data)
        self.assertIn(b"/built-with/github-copilot", response.data)
        self.assertIn(b"/built-with/codex", response.data)
        self.assertIn(b"/built-with/deepseek", response.data)
        self.assertIn(b"/rules", response.data)
        self.assertIn(b"/terms", response.data)
        self.assertIn(b"/privacy", response.data)

    def test_legal_pages_explain_payment_and_data_policies(self):
        rules = self.client.get("/rules")
        terms = self.client.get("/terms")
        privacy = self.client.get("/privacy")

        self.assertEqual(rules.status_code, 200)
        self.assertEqual(terms.status_code, 200)
        self.assertEqual(privacy.status_code, 200)
        self.assertIn(b"All payments are final.", rules.data)
        self.assertIn(b"lifetime of Whatever Board", rules.data)
        self.assertIn(b"spam, malicious, deceptive, unsafe, harmful to Whatever Board", rules.data)
        self.assertIn(b"final and non-refundable", terms.data)
        self.assertIn(b"permanently delete a listing or URL", terms.data)
        self.assertIn(b"Payments are processed by Stripe", privacy.data)
        self.assertIn(b"one-way hash derived from the visitor IP address", privacy.data)
        self.assertIn(b'class="theme-toggle js-theme-toggle"', privacy.data)

    def test_visit_is_counted_once_per_browser_session(self):
        with application.db_session() as db:
            before = db.execute(
                "SELECT value FROM site_stats WHERE name = 'total_visits'"
            ).fetchone()[0]
        self.client.get("/")
        self.client.get("/")
        with application.db_session() as db:
            after = db.execute(
                "SELECT value FROM site_stats WHERE name = 'total_visits'"
            ).fetchone()[0]
        self.assertEqual(after, before + 1)

        presence = self.client.post("/api/presence")
        self.assertEqual(presence.status_code, 200)
        self.assertGreaterEqual(presence.get_json()["online"], 1)

    def test_invalid_submission_is_rejected(self):
        response = self.client.post("/api/checkout", json={"url": "http://localhost"})
        self.assertEqual(response.status_code, 400)

    def test_site_preview_rejects_private_urls(self):
        response = self.client.post("/api/site-preview", json={"url": "http://127.0.0.1"})
        self.assertEqual(response.status_code, 400)

    def test_preview_connection_is_pinned_to_the_vetted_numeric_address(self):
        connected_targets = []

        class FakeSocket:
            def getpeername(self):
                return ("93.184.216.34", 443)

        class FakeResponse:
            status = 200
            reason = "OK"
            headers = application.http.client.HTTPMessage()

            def read(self, _limit):
                return b"<html><title>Safe</title></html>"

        class FakeConnection:
            def __init__(self, *_args, **_kwargs):
                self.sock = None

            def request(self, *_args, **_kwargs):
                self.sock = self._create_connection(("attacker.example", 443), 6, None)

            def getresponse(self):
                return FakeResponse()

            def close(self):
                return None

        def fake_create_connection(target, *_args, **_kwargs):
            connected_targets.append(target)
            return FakeSocket()

        with patch.object(application.http.client, "HTTPSConnection", FakeConnection), patch.object(
            application.socket, "create_connection", fake_create_connection
        ):
            application.open_pinned_preview_url(
                "https://attacker.example/product", ("93.184.216.34",)
            )
        self.assertEqual(connected_targets, [("93.184.216.34", 443)])

    def test_site_preview_returns_editable_details(self):
        with patch.object(
            application,
            "fetch_site_metadata",
            return_value={"name": "Fetched build", "description": "Fetched description."},
        ):
            response = self.client.post(
                "/api/site-preview", json={"url": "https://example.org/product"}
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["name"], "Fetched build")
        self.assertEqual(response.get_json()["description"], "Fetched description.")

    def test_site_preview_is_limited_to_three_requests_per_ip_per_minute(self):
        with patch.object(
            application,
            "fetch_site_metadata",
            return_value={"name": "Fetched build", "description": "Fetched description."},
        ):
            responses = [
                self.client.post(
                    "/api/site-preview",
                    json={"url": f"https://preview-{number}.example/product"},
                )
                for number in range(4)
            ]
        self.assertEqual([response.status_code for response in responses], [200, 200, 200, 429])
        self.assertEqual(responses[-1].headers["Retry-After"], "60")

    def test_untrusted_host_and_forwarded_host_are_not_accepted(self):
        rejected = self.client.get("/", headers={"Host": "attacker.example"})
        self.assertEqual(rejected.status_code, 400)
        ignored = self.client.get("/", headers={"X-Forwarded-Host": "attacker.example"})
        self.assertEqual(ignored.status_code, 200)
        self.assertNotIn(b"attacker.example", ignored.data)

    def test_metadata_parser_prefers_open_graph(self):
        details = application.parse_site_metadata(
            """
            <html><head><title>Fallback title</title>
            <meta property="og:title" content="Open Graph name">
            <meta name="description" content="A useful imported description.">
            <link rel="icon" href="/assets/icon.svg">
            </head></html>
            """,
            "https://example.org",
        )
        self.assertEqual(details["name"], "Open Graph name")
        self.assertEqual(details["description"], "A useful imported description.")
        self.assertEqual(details["favicon_url"], "https://example.org/assets/icon.svg")

    def test_fulfillment_uses_full_bid_then_adds_later_payments(self):
        now = application.utc_now()
        payload = {
            "name": "Bid Rules Build",
            "url": "https://bid-rules.example/product",
            "favicon_url": "https://bid-rules.example/icon.png",
            "tagline": "A project for testing full bids and later additions.",
            "categories": ["Apps"],
            "built_with": ["Codex"],
            "build_time_value": 2,
            "build_time_unit": "hours",
            "submitted_by": "Anonymous",
        }
        with application.db_session() as db:
            db.execute(
                """
                INSERT INTO pending_submissions
                    (id, payload_json, amount_cents, status, created_at)
                VALUES ('full-bid-pending', ?, 400, 'pending', ?)
                """,
                (json.dumps(payload), now),
            )

        project_id = application.fulfill_checkout(
            {
                "id": "cs_full_bid",
                "payment_status": "paid",
                "amount_total": 400,
                "currency": "usd",
                "payment_intent": "pi_full_bid",
                "metadata": {"pending_id": "full-bid-pending"},
            }
        )
        with application.db_session() as db:
            project = db.execute(
                "SELECT total_bid_cents, favicon_url FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            outbid_payload = {
                "kind": "outbid",
                "project_id": project_id,
                "url": payload["url"],
                "name": payload["name"],
            }
            db.execute(
                """
                INSERT INTO pending_submissions
                    (id, payload_json, amount_cents, status, created_at)
                VALUES ('add-bid-pending', ?, 100, 'pending', ?)
                """,
                (json.dumps(outbid_payload), now),
            )
        self.assertEqual(project["total_bid_cents"], 400)
        self.assertEqual(project["favicon_url"], "https://bid-rules.example/icon.png")

        application.fulfill_checkout(
            {
                "id": "cs_add_bid",
                "payment_status": "paid",
                "amount_total": 100,
                "currency": "usd",
                "payment_intent": "pi_add_bid",
                "metadata": {"pending_id": "add-bid-pending"},
            }
        )
        with application.db_session() as db:
            total = db.execute(
                "SELECT total_bid_cents FROM projects WHERE id = ?", (project_id,)
            ).fetchone()[0]
        self.assertEqual(total, 500)

    def test_valid_submission_reports_missing_payment_config(self):
        payload = {
            "name": "Test Build",
            "url": "https://example.org/product",
            "tagline": "A useful product made for testing.",
            "categories": ["Apps", "Developer tools"],
            "built_with": ["Codex"],
            "build_time_value": 3,
            "build_time_unit": "hours",
            "submitted_by": "",
            "bid_dollars": 1,
            "terms_accepted": True,
        }
        response = self.client.post("/api/checkout", json=payload)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["code"], "payments_unavailable")

    def test_submission_rejects_more_than_two_categories(self):
        payload = {
            "name": "Too Many Cats",
            "url": "https://example.org/categories",
            "tagline": "A valid pitch with too many directory categories.",
            "categories": ["Apps", "Agents", "Creative"],
            "built_with": ["Codex"],
            "build_time_value": 1,
            "build_time_unit": "hours",
            "submitted_by": "",
            "bid_dollars": 1,
            "terms_accepted": True,
        }
        response = self.client.post("/api/checkout", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("one or two", response.get_json()["error"])

    def test_submission_is_anonymous_and_requires_one_main_tool(self):
        anonymous = application.validate_submission(
            {
                "name": "Anonymous Build",
                "url": "https://example.org/anonymous",
                "tagline": "A valid anonymously submitted leaderboard project.",
                "categories": ["Apps"],
                "built_with": ["Codex"],
                "build_time_value": 2,
                "build_time_unit": "hours",
                "submitted_by": "@someone",
                "bid_dollars": 1,
                "terms_accepted": True,
            }
        )
        self.assertEqual(anonymous["submitted_by"], "Anonymous")
        self.assertEqual(anonymous["tagline"], anonymous["name"])
        self.assertIsNone(anonymous["x_user_id"])
        self.assertIsNone(anonymous["x_handle"])

        response = self.client.post(
            "/api/checkout",
            json={
                "name": "Too Many Tools",
                "url": "https://example.org/tools",
                "tagline": "A valid product that selected more than one main tool.",
                "categories": ["Apps"],
                "built_with": ["Codex", "Claude"],
                "build_time_value": 1,
                "build_time_unit": "hours",
                "bid_dollars": 1,
                "terms_accepted": True,
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("one main build tool", response.get_json()["error"])

    def test_existing_listing_uses_bid_only_help_flow(self):
        now = application.utc_now()
        with application.db_session() as db:
            db.execute(
                """
                INSERT INTO projects (
                    slug, name, url, tagline, category, built_with,
                    build_time_value, build_time_unit, submitted_by,
                    total_bid_cents, is_demo, status, created_at, updated_at
                ) VALUES ('share-help-bid-only', 'Share Help Bid', 'https://share-help-bid.example',
                    'An existing listing whose details stay locked.', '["Apps"]', '["Codex"]',
                    2, 'hours', 'Anonymous', 400, 0, 'live', ?, ?)
                """,
                (now, now),
            )
        response = self.client.post(
            "/api/checkout",
            json={
                "name": "Attempted replacement",
                "url": "https://share-help-bid.example",
                "tagline": "This must not replace the existing listing details.",
                "categories": ["Other"],
                "built_with": ["Claude"],
                "build_time_value": 99,
                "build_time_unit": "days",
                "bid_dollars": 5,
                "terms_accepted": True,
            },
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["code"], "existing_listing")
        self.assertEqual(response.get_json()["slug"], "share-help-bid-only")

    def test_help_bid_checkout_cannot_store_listing_edits(self):
        now = application.utc_now()
        with application.db_session() as db:
            cursor = db.execute(
                """
                INSERT INTO projects (
                    slug, name, url, tagline, category, built_with,
                    build_time_value, build_time_unit, submitted_by,
                    total_bid_cents, is_demo, status, created_at, updated_at
                ) VALUES ('share-help-checkout', 'Locked Share Listing', 'https://share-locked.example',
                    'The original description stays unchanged.', '["Apps"]', '["Codex"]',
                    3, 'hours', 'Anonymous', 200, 0, 'live', ?, ?)
                """,
                (now, now),
            )
            project_id = cursor.lastrowid
        checkout = type("Checkout", (), {"id": "cs_share_help", "url": "https://checkout.example/help"})()
        with patch.object(application, "payments_enabled", return_value=True), patch.object(
            application.stripe.checkout.Session, "create", return_value=checkout
        ):
            response = self.client.post(
                "/api/outbid/share-help-checkout",
                json={
                    "bid_dollars": 3,
                    "terms_accepted": True,
                    "name": "Attempted rewrite",
                    "categories": ["Other"],
                },
            )
        self.assertEqual(response.status_code, 200)
        with application.db_session() as db:
            pending = db.execute(
                "SELECT payload_json, amount_cents FROM pending_submissions WHERE stripe_session_id = 'cs_share_help'"
            ).fetchone()
        stored = json.loads(pending["payload_json"])
        self.assertEqual(pending["amount_cents"], 300)
        self.assertEqual(stored["project_id"], project_id)
        self.assertEqual(stored["kind"], "outbid")
        self.assertNotIn("categories", stored)

    def test_product_detail_page_has_rank_spend_and_sharing(self):
        now = application.utc_now()
        with application.db_session() as db:
            db.execute(
                """
                INSERT INTO projects (
                    slug, name, url, tagline, category, built_with,
                    build_time_value, build_time_unit, submitted_by,
                    total_bid_cents, is_demo, status, created_at, updated_at
                ) VALUES ('share-detail-build', 'Share Detail Build', 'https://share-detail.example',
                    'A safe fictional project for testing the detail page.', '["Apps"]', '["Codex"]',
                    4, 'days', 'Anonymous', 900, 0, 'live', ?, ?)
                """,
                (now, now),
            )
        response = self.client.get("/product/share-detail-build")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Spent", response.data)
        self.assertIn(b"Overall rank", response.data)
        self.assertIn(b"Share this listing", response.data)
        self.assertIn(b"Help bid +$1", response.data)
        self.assertIn(b"Made with", response.data)
        self.assertNotIn(b'name="submitted_by"', response.data)

    def test_submission_requires_terms_acceptance(self):
        payload = {
            "name": "Terms Test",
            "url": "https://example.org/terms-test",
            "tagline": "A valid pitch that has not accepted the terms.",
            "categories": ["Apps"],
            "built_with": ["Codex"],
            "build_time_value": 1,
            "build_time_unit": "hours",
            "submitted_by": "",
            "bid_dollars": 1,
        }
        response = self.client.post("/api/checkout", json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Accept the Rules", response.get_json()["error"])

    def test_home_paginates_twenty_projects(self):
        projects = []
        for rank in range(1, 22):
            projects.append(
                {
                    "id": rank,
                    "slug": f"build-{rank}",
                    "name": f"Build {rank}",
                    "url": f"https://example.org/build-{rank}",
                    "tagline": f"A useful AI build number {rank}.",
                    "categories": ["Apps"],
                    "built_with": ["Codex"],
                    "build_time_value": 1,
                    "build_time_unit": "hours",
                    "submitted_by": "Anonymous",
                    "total_bid_cents": 2300 - rank,
                    "is_demo": 0,
                    "status": "live",
                    "created_at": f"2026-08-{rank:02d}T00:00:00+00:00",
                    "updated_at": f"2026-08-{rank:02d}T00:00:00+00:00",
                    "clicks": rank,
                    "rank": rank,
                }
            )

        with patch.object(application, "project_rows", return_value=projects):
            first = self.client.get("/")
            second = self.client.get("/?page=2")

        self.assertEqual(first.status_code, 200)
        self.assertIn(b"Page 1 of 2", first.data)
        self.assertIn(b"Top 10", first.data)
        self.assertIn(b"1 hour", first.data)
        self.assertIn(b"Build 20", first.data)
        self.assertNotIn(b"Build 21", first.data)
        self.assertEqual(second.status_code, 200)
        self.assertIn(b"Page 2 of 2", second.data)
        self.assertIn(b"#21", second.data)
        self.assertIn(b"Build 21", second.data)

    def test_leaderboard_orders_by_bid_then_oldest_first(self):
        with application.db_session() as db:
            db.executemany(
                """
                INSERT INTO projects (
                    slug, name, url, tagline, category, built_with,
                    build_time_value, build_time_unit, submitted_by,
                    total_bid_cents, is_demo, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'Apps', ?, 1, 'days', 'Anonymous', ?, ?, 'live', ?, ?)
                """,
                [
                    (
                        "ordering-demo",
                        "Ordering Demo",
                        "https://ordering-demo.example",
                        "A higher demo bid for ordering tests.",
                        json.dumps(["Codex"]),
                        900,
                        1,
                        "2026-01-01T00:00:00+00:00",
                        "2026-01-01T00:00:00+00:00",
                    ),
                    (
                        "ordering-real",
                        "Ordering Real",
                        "https://ordering-real.example",
                        "A lower real bid for ordering tests.",
                        json.dumps(["Codex"]),
                        100,
                        0,
                        "2026-01-01T00:00:00+00:00",
                        "2026-01-01T00:00:00+00:00",
                    ),
                    (
                        "ordering-old-tie",
                        "Ordering Old Tie",
                        "https://ordering-old.example",
                        "The older project among equal bids.",
                        json.dumps(["Codex"]),
                        800,
                        0,
                        "2026-01-02T00:00:00+00:00",
                        "2026-01-02T00:00:00+00:00",
                    ),
                    (
                        "ordering-new-tie",
                        "Ordering New Tie",
                        "https://ordering-new.example",
                        "The newer project among equal bids.",
                        json.dumps(["Codex"]),
                        800,
                        0,
                        "2026-01-03T00:00:00+00:00",
                        "2026-01-03T00:00:00+00:00",
                    ),
                ],
            )

        slugs = [project["slug"] for project in application.project_rows()]
        self.assertLess(slugs.index("ordering-demo"), slugs.index("ordering-real"))
        self.assertLess(slugs.index("ordering-old-tie"), slugs.index("ordering-new-tie"))

    def test_click_route_redirects_and_counts(self):
        now = application.utc_now()
        with application.db_session() as db:
            db.execute(
                """
                INSERT INTO projects (
                    slug, name, url, tagline, category, built_with,
                    build_time_value, build_time_unit, submitted_by,
                    total_bid_cents, is_demo, status, created_at, updated_at
                ) VALUES ('ship', 'Ship', 'https://example.org/path?ref=abc#details', 'A shipped thing',
                          'Apps', ?, 2, 'hours', 'Anonymous', 100, 0, 'live', ?, ?)
                """,
                (json.dumps(["Codex"]), now, now),
            )
        response = self.client.get("/go/ship")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.location,
            "https://example.org/path?ref=abc&utm_source=yex#details",
        )
        with application.db_session() as db:
            clicks = db.execute("SELECT clicks FROM projects WHERE slug = 'ship'").fetchone()[0]
        self.assertEqual(clicks, 1)

        direct_response = self.client.post(
            "/api/click/ship", environ_base={"REMOTE_ADDR": "203.0.113.30"}
        )
        self.assertEqual(direct_response.status_code, 204)
        with application.db_session() as db:
            clicks = db.execute("SELECT clicks FROM projects WHERE slug = 'ship'").fetchone()[0]
        self.assertEqual(clicks, 2)

    def test_tracked_url_replaces_existing_source_and_keeps_fragment(self):
        self.assertEqual(
            application.tracked_outbound_url(
                "https://example.org/path?ref=abc&utm_source=old#section"
            ),
            "https://example.org/path?ref=abc&utm_source=yex#section",
        )

    def test_admin_login_uses_exponential_backoff_and_audits_failures(self):
        with self.assertLogs(application.app.logger, level="WARNING") as logs:
            failures = [
                self.client.post(
                    "/admin/login",
                    data={
                        "admin_token": application.admin_login_token(),
                        "username": "admin",
                        "password": "wrong",
                    },
                )
                for _ in range(5)
            ]
            blocked = self.client.post(
                "/admin/login",
                data={
                    "admin_token": application.admin_login_token(),
                    "username": "admin",
                    "password": "admin",
                },
            )
        self.assertTrue(all(response.status_code == 401 for response in failures))
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("Retry-After", blocked.headers)
        self.assertTrue(any("admin_login_blocked" in message for message in logs.output))
        with application.db_session() as db:
            audited_failures = db.execute(
                "SELECT COUNT(*) FROM admin_login_attempts WHERE succeeded = 0"
            ).fetchone()[0]
        self.assertEqual(audited_failures, 5)

    def test_admin_requires_password_and_can_edit_and_hide_a_listing(self):
        now = application.utc_now()
        with application.db_session() as db:
            cursor = db.execute(
                """
                INSERT INTO projects (
                    slug, name, url, tagline, category, built_with,
                    build_time_value, build_time_unit, submitted_by,
                    total_bid_cents, is_demo, status, created_at, updated_at
                ) VALUES ('admin-test', 'Admin Test', 'https://admin-test.example/path?ref=one',
                          'A listing managed in the private interface.', 'Apps', ?, 1, 'hours',
                          'Anonymous', 100, 0, 'live', ?, ?)
                """,
                (json.dumps(["Codex"]), now, now),
            )
            project_id = cursor.lastrowid

        protected_response = self.client.get("/admin")
        self.assertEqual(protected_response.status_code, 302)
        self.assertEqual(protected_response.location, "/admin/login")

        wrong_password = self.client.post(
            "/admin/login",
            data={
                "admin_token": application.admin_login_token(),
                "username": "admin",
                "password": "wrong",
            },
        )
        self.assertEqual(wrong_password.status_code, 401)
        self.assertIn(b"Incorrect username or password.", wrong_password.data)

        login_response = self.client.post(
            "/admin/login",
            data={
                "admin_token": application.admin_login_token(),
                "username": "admin",
                "password": "admin",
            },
        )
        self.assertEqual(login_response.status_code, 302)
        self.assertEqual(login_response.location, "/admin")

        admin_response = self.client.get(
            "/admin", environ_base={"REMOTE_ADDR": "203.0.113.20"}
        )
        self.assertEqual(admin_response.status_code, 200)
        self.assertIn(b"Link manager", admin_response.data)
        self.assertIn(b"Admin Test", admin_response.data)
        self.assertIn(b"utm_source=yex", admin_response.data)
        self.assertIn(b"Second category", admin_response.data)
        self.assertIn(b"Mainly built with", admin_response.data)
        self.assertIn(b"Build time", admin_response.data)
        self.assertNotIn(b'name="tagline"', admin_response.data)
        self.assertIn(b'class="admin-add-name"', admin_response.data)
        self.assertIn(b'admin-add-submit', admin_response.data)
        self.assertIn(b'<details class="admin-project-details">', admin_response.data)
        self.assertNotIn(b'<details class="admin-project-details" open', admin_response.data)
        self.assertEqual(admin_response.headers["X-Robots-Tag"], "noindex, nofollow")

        add_response = self.client.post(
            "/admin/projects",
            data={
                "admin_token": application.admin_action_token("add-project"),
                "name": "Admin Added",
                "url": "https://admin-added.example",
                "category": "Developer tools",
                "built_with": "Codex",
                "bid_dollars": "7",
            },
        )
        self.assertEqual(add_response.status_code, 302)
        with application.db_session() as db:
            added = db.execute(
                "SELECT name, tagline, category, built_with, total_bid_cents, status FROM projects WHERE slug = 'admin-added'"
            ).fetchone()
        self.assertEqual(added["tagline"], added["name"])
        self.assertEqual(json.loads(added["category"]), ["Developer tools"])
        self.assertEqual(json.loads(added["built_with"]), ["Codex"])
        self.assertEqual(added["total_bid_cents"], 700)
        self.assertEqual(added["status"], "live")

        token = application.admin_form_token(project_id)
        save_response = self.client.post(
            f"/admin/projects/{project_id}",
            data={
                "admin_token": token,
                "action": "save",
                "name": "Admin Test Updated",
                "url": "https://admin-test.example/new-path?ref=two",
                "category_primary": "Apps",
                "category_secondary": "Developer tools",
                "built_with": "Claude",
                "build_time_value": "2.5",
                "build_time_unit": "days",
            },
        )
        self.assertEqual(save_response.status_code, 302)

        hide_response = self.client.post(
            f"/admin/projects/{project_id}",
            data={"admin_token": token, "action": "hide"},
        )
        self.assertEqual(hide_response.status_code, 302)
        with application.db_session() as db:
            project = db.execute(
                """
                SELECT name, url, tagline, category, built_with,
                       build_time_value, build_time_unit, status
                FROM projects WHERE id = ?
                """,
                (project_id,),
            ).fetchone()
        self.assertEqual(project["name"], "Admin Test Updated")
        self.assertEqual(project["url"], "https://admin-test.example/new-path?ref=two")
        self.assertEqual(project["tagline"], "Admin Test Updated")
        self.assertEqual(json.loads(project["category"]), ["Apps", "Developer tools"])
        self.assertEqual(json.loads(project["built_with"]), ["Claude"])
        self.assertEqual(project["build_time_value"], 2.5)
        self.assertEqual(project["build_time_unit"], "days")
        self.assertEqual(project["status"], "hidden")

    def test_admin_rejects_invalid_form_token(self):
        self.client.post(
            "/admin/login",
            data={
                "admin_token": application.admin_login_token(),
                "username": "admin",
                "password": "admin",
            },
        )
        response = self.client.post(
            "/admin/projects/1",
            data={"admin_token": "wrong", "action": "hide"},
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_change_password(self):
        self.client.post(
            "/admin/login",
            data={
                "admin_token": application.admin_login_token(),
                "username": "admin",
                "password": "admin",
            },
        )
        response = self.client.post(
            "/admin/password",
            data={
                "admin_token": application.admin_action_token("change-password"),
                "current_password": "admin",
                "new_password": "new-admin-password",
                "confirm_password": "new-admin-password",
            },
        )
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as browser_session:
            browser_session.pop("admin_authenticated", None)
        old_login = self.client.post(
            "/admin/login",
            data={
                "admin_token": application.admin_login_token(),
                "username": "admin",
                "password": "admin",
            },
        )
        new_login = self.client.post(
            "/admin/login",
            data={
                "admin_token": application.admin_login_token(),
                "username": "admin",
                "password": "new-admin-password",
            },
        )
        self.assertEqual(old_login.status_code, 401)
        self.assertEqual(new_login.status_code, 302)

    def test_admin_navigation_stats_and_settings(self):
        self.client.post(
            "/admin/login",
            data={"admin_token": application.admin_login_token(), "username": "admin", "password": "admin"},
        )
        stats = self.client.get("/admin/stats")
        settings = self.client.get("/admin/settings")
        self.assertEqual(stats.status_code, 200)
        self.assertIn(b"Total visits", stats.data)
        self.assertIn(b"Top clicked listings", stats.data)
        self.assertIn(b"Categories", stats.data)
        self.assertIn(b"Built with", stats.data)
        self.assertEqual(settings.status_code, 200)
        self.assertIn(b"Administrator password", settings.data)
        self.assertIn(b"URL behavior", settings.data)
        self.assertIn(b"SEO", settings.data)
        self.assertIn(b'name="description"', settings.data)
        self.assertIn(b'name="tracking_parameter"', settings.data)
        self.assertIn(b'name="tracking_value"', settings.data)
        self.assertIn(b"New category", settings.data)
        self.assertIn(b"New AI tool", settings.data)
        self.assertIn(b'href="/admin/stats"', settings.data)

    def test_admin_can_update_homepage_seo(self):
        self.client.post(
            "/admin/login",
            data={"admin_token": application.admin_login_token(), "username": "admin", "password": "admin"},
        )
        response = self.client.post(
            "/admin/settings/seo",
            data={
                "admin_token": application.admin_action_token("seo-settings"),
                "title": "Custom leaderboard title",
                "description": "A custom search description for this public leaderboard homepage.",
            },
        )
        self.assertEqual(response.status_code, 302)
        home = self.client.get("/")
        self.assertIn(b"<title>Custom leaderboard title</title>", home.data)
        self.assertIn(
            b'content="A custom search description for this public leaderboard homepage."',
            home.data,
        )

    def test_admin_can_switch_outbound_url_mode_and_tracking_code(self):
        now = application.utc_now()
        with application.db_session() as db:
            db.execute(
                """
                INSERT INTO projects (
                    slug, name, url, tagline, category, built_with,
                    build_time_value, build_time_unit, submitted_by,
                    total_bid_cents, is_demo, status, created_at, updated_at
                ) VALUES ('url-mode-test', 'URL Mode Test',
                          'https://url-mode.example/path?utm_source=old#details', '',
                          'Apps', ?, 1, 'hours', 'Admin', 100, 0, 'live', ?, ?)
                """,
                (json.dumps(["Codex"]), now, now),
            )
        self.client.post(
            "/admin/login",
            data={"admin_token": application.admin_login_token(), "username": "admin", "password": "admin"},
        )
        token = application.admin_action_token("outbound-settings")
        go_update = self.client.post(
            "/admin/settings/outbound",
            data={
                "admin_token": token,
                "mode": "go",
                "tracking_parameter": "ref",
                "tracking_value": "custom-source",
            },
        )
        self.assertEqual(go_update.status_code, 302)
        go_home = self.client.get("/")
        self.assertIn(b'href="/go/url-mode-test"', go_home.data)
        self.assertNotIn(b'data-click-slug="url-mode-test"', go_home.data)
        go_redirect = self.client.get("/go/url-mode-test")
        self.assertEqual(
            go_redirect.location,
            "https://url-mode.example/path?utm_source=old&ref=custom-source#details",
        )

        direct_update = self.client.post(
            "/admin/settings/outbound",
            data={
                "admin_token": token,
                "mode": "direct",
                "tracking_parameter": "campaign",
                "tracking_value": "launch board",
            },
        )
        self.assertEqual(direct_update.status_code, 302)
        direct_home = self.client.get("/")
        self.assertIn(
            b'href="https://url-mode.example/path?utm_source=old&amp;campaign=launch+board#details"',
            direct_home.data,
        )
        self.assertIn(b'data-click-slug="url-mode-test"', direct_home.data)

    def test_admin_search_and_pagination_use_twenty_rows(self):
        now = application.utc_now()
        with application.db_session() as db:
            db.executemany(
                """
                INSERT INTO projects (
                    slug, name, url, tagline, category, built_with,
                    build_time_value, build_time_unit, submitted_by,
                    total_bid_cents, is_demo, status, created_at, updated_at
                ) VALUES (?, ?, ?, '', 'Apps', ?, 1, 'hours', 'Admin', 100, 0, 'live', ?, ?)
                """,
                [
                    (
                        f"admin-search-{number}",
                        f"Search Batch {number}",
                        f"https://admin-search-{number}.example",
                        json.dumps(["Codex"]),
                        now,
                        now,
                    )
                    for number in range(1, 22)
                ],
            )
        self.client.post(
            "/admin/login",
            data={"admin_token": application.admin_login_token(), "username": "admin", "password": "admin"},
        )
        first = self.client.get("/admin?q=Search+Batch&page=1")
        second = self.client.get("/admin?q=Search+Batch&page=2")
        self.assertEqual(first.data.count(b'<form class="admin-project"'), 20)
        self.assertIn(b"Page 1 of 2", first.data)
        self.assertEqual(second.data.count(b'<form class="admin-project"'), 1)
        self.assertIn(b"Page 2 of 2", second.data)

    def test_admin_can_manage_categories_and_tools(self):
        self.client.post(
            "/admin/login",
            data={"admin_token": application.admin_login_token(), "username": "admin", "password": "admin"},
        )
        token = application.admin_action_token("manage-taxonomy")
        add_category = self.client.post(
            "/admin/settings/taxonomy",
            data={"admin_token": token, "kind": "category", "operation": "add", "name": "Research"},
        )
        add_tool = self.client.post(
            "/admin/settings/taxonomy",
            data={"admin_token": token, "kind": "tool", "operation": "add", "name": "NewTool"},
        )
        self.assertEqual(add_category.status_code, 302)
        self.assertEqual(add_tool.status_code, 302)
        self.assertIn("Research", application.managed_categories())
        self.assertIn("NewTool", application.managed_tools())
        self.assertEqual(self.client.get("/built-with/newtool").status_code, 200)

        remove_category = self.client.post(
            "/admin/settings/taxonomy",
            data={"admin_token": token, "kind": "category", "operation": "remove", "name": "Research"},
        )
        remove_tool = self.client.post(
            "/admin/settings/taxonomy",
            data={"admin_token": token, "kind": "tool", "operation": "remove", "name": "NewTool"},
        )
        self.assertEqual(remove_category.status_code, 302)
        self.assertEqual(remove_tool.status_code, 302)
        self.assertNotIn("Research", application.managed_categories())
        self.assertNotIn("NewTool", application.managed_tools())

    def test_listing_highlights_order_new_and_clicked_projects(self):
        now = application.utc_now()
        with application.db_session() as db:
            db.executemany(
                """
                INSERT INTO projects (
                    slug, name, url, tagline, category, built_with,
                    build_time_value, build_time_unit, submitted_by,
                    total_bid_cents, clicks, is_demo, status, created_at, updated_at
                ) VALUES (?, ?, ?, '', 'Apps', ?, 1, 'hours', 'Admin', 100, ?, 0, 'live', ?, ?)
                """,
                [
                    ("highlight-old", "Highlight Old", "https://highlight-old.example", json.dumps(["Codex"]), 9, "2099-01-01T00:00:00+00:00", now),
                    ("highlight-new", "Highlight New", "https://highlight-new.example", json.dumps(["Codex"]), 2, "2099-02-01T00:00:00+00:00", now),
                ],
            )
        newest, top_clicked = application.listing_highlights()
        self.assertLess(
            [item["name"] for item in newest].index("Highlight New"),
            [item["name"] for item in newest].index("Highlight Old"),
        )
        self.assertLess(
            [item["name"] for item in top_clicked].index("Highlight Old"),
            [item["name"] for item in top_clicked].index("Highlight New"),
        )
        response = self.client.get("/")
        self.assertIn(b'class="highlight-clicks">9 clicks</span>', response.data)

    def test_click_count_is_limited_to_five_per_ip_per_hour(self):
        now = application.utc_now()
        with application.db_session() as db:
            db.execute(
                """
                INSERT INTO projects (
                    slug, name, url, tagline, category, built_with,
                    build_time_value, build_time_unit, submitted_by,
                    total_bid_cents, is_demo, status, created_at, updated_at
                ) VALUES ('limited-ship', 'Limited Ship', 'https://example.net',
                          'A click-limited shipped thing', 'Apps', ?, 2, 'hours',
                          'Anonymous', 100, 0, 'live', ?, ?)
                """,
                (json.dumps(["Codex"]), now, now),
            )

        for _ in range(6):
            response = self.client.get(
                "/go/limited-ship", environ_base={"REMOTE_ADDR": "203.0.113.10"}
            )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.location, "https://example.net?utm_source=yex")

        with application.db_session() as db:
            clicks = db.execute(
                "SELECT clicks FROM projects WHERE slug = 'limited-ship'"
            ).fetchone()[0]
        self.assertEqual(clicks, 5)

        self.client.get(
            "/go/limited-ship", environ_base={"REMOTE_ADDR": "203.0.113.11"}
        )
        with application.db_session() as db:
            clicks = db.execute(
                "SELECT clicks FROM projects WHERE slug = 'limited-ship'"
            ).fetchone()[0]
        self.assertEqual(clicks, 6)


if __name__ == "__main__":
    unittest.main()
