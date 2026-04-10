"""
job_radar.py  -  Daily Job Search Radar
───────────────────────────────────────────────────────────

WHAT IT DOES
  Runs every morning via Windows Task Scheduler. Searches 12 job sources,
  deduplicates, pre-filters hard disqualifiers, rates every new job using the
  Claude API, and emails a curated digest sorted by tier.

SOURCES (ordered richest data first so best version wins dedup)
  Tier 1 - Direct structured APIs (full description + salary + company):
    ATS direct (Greenhouse / Lever / Ashby) - 157 verified fintech/banking slugs
    Adzuna         - broad job board, plain-text descriptions, salary min/max
    Jobicy         - structured remote-only, salary USD, 5000-char descriptions
    Himalayas      - remote-only board, salary USD, paginated
    RemoteOK       - remote-only board, salary when listed
    Remotive       - remote-only board, 5000-char descriptions

  Tier 2 - Aggregators (good data, sourced from other boards):
    USAJobs        - federal government roles (GS-14/15 pay bands)

  Tier 3 - Discovery (find postings the structured boards miss):
    LinkedIn       - good for unique postings; no desc/salary/date stored
    Brave          - search engine queries targeting job board domains
    Tavily         - search engine backup to Brave
    WeWorkRemotely - RSS feed, tech-heavy, weakest data

PIPELINE
  Search -> Category filter -> Bad scrape filter -> Empty-company filter
  -> Location filter -> Salary filter -> Dedup against seen history
  -> Hard disqualifier pre-filter -> Claude rating -> Email digest

RATING TIERS
  ⭐ Perfect Fit  - 90-100% match, right domain, right seniority
  🟢 Good Fit    - 70-90% match, transferable skills, minor gaps
  🟡 Worth a Look - 60-70% match, stretch but worth a shot
  ⛔ Skip        - confirmed hard disqualifier or no realistic fit

COST
  Claude Haiku API: ~$1.50-2/month at typical daily volume (~50-100 jobs/day)
  All other sources: free (no key required or free tier)

VACATION MODE
  Set VACATION_START and VACATION_END below.
  Script buffers jobs daily with no email, then sends one digest on return day.

USAGE
  Scheduled daily:  python job_radar.py
  Manual test run:  python job_radar.py --run
  Sleep after run:  python job_radar.py --run --sleep-after

DEBUG
  After each run, output/job-radar/debug_job_log.txt contains every job with
  full description text as sent to Claude. Upload to Claude to verify data
  quality. File is overwritten on every run.

CHANGELOG (reverse chronological)
  2026-03-18 - Session 5: Bug fixes from live testing
    - salary_ok() bug fix: was using salary_min to check against MIN_SALARY floor.
      For a range like $140K-$180K this set sal=140K and dropped the job even though
      $150K falls within the range. Fixed to use salary_max when both fields are set,
      so a job only gets dropped if the ENTIRE range is confirmed below $150K.
    - Also clarified Claude prompt rule: skip only when the TOP of the range is below
      $150K, not when the bottom is.
    - FutureWarning fix: [---to] in _SALARY_CONTEXT_RE (em-dash cleanup artifact)
      turned [--to] into [---to] which Python 3.12 treats as ambiguous set difference.
      Fixed to [-to].
    - ATS COMPANIES list: restored 18 slugs lost during content-replacement sessions
      (chime, sofi, ramp, brex, adyen, lemonade, robinhood, altruist, whoop, alt,
      kikoff, checkr, lendingtree, pathward, securitize, alpaca, paxos, oneapp) plus
      melio and deel. Removed 5 duplicate entries. Final count: 152 unique slugs.

  2026-03-18 - Session 4: Post-run log analysis and pre-filter hardening
    - Title filter: added management consultant, customer service representative,
      business development representative - 3 types were slipping through
    - Claude salary validation: apply _is_plausible_salary() to Claude's returned
      salary string, not just our own regex extraction. Fixes Versapay "$257",
      Ramp "$100", Alpaca "$320", Deel "$11.2", etc. appearing as salary in email
    - salary_min display guard: raised from > 0 to > 30000 to block bogus ATS
      structured salary values (e.g. salary_min=2 from "$2B market" in description)
    - All major structural pre-filters were already in place from Session 3:
      _COMPANY_PREFILTER covers all 22 always-Skip companies (SoFi, Robinhood,
      Ramp, Brex, Adyen, Chime, Lemonade, Melio, Deel, Paxos, Alpaca, Securitize,
      Alt, OnePay, Kikoff, Altruist, WHOOP, Checkr, Lendingtree, Jerry, Pathward,
      Anchorage) - these were already blocking before Claude on the current zip
    - Most wrong-title patterns were also already in place from Session 3

  2026-03-17 - Session 3: Bug fixes and data quality improvements
    - ATS Ashby fix: API returns "jobs" key not "jobPostings" - was silently
      returning 0 results for ALL Ashby companies (Ramp, Sardine, Tilthq, etc.)
    - Greenhouse HTML fix: content field uses HTML entities (&lt;h2&gt;) not
      real tags; added html.unescape() BEFORE tag stripping so entities become
      real tags first, then get stripped cleanly
    - Lever description fix: was only using descriptionPlain (~1,470 chars of
      company boilerplate); now concatenates descriptionPlain + additionalPlain
      + lists[] bullet sections (~4,000-5,500 chars with actual requirements)
    - All non-ATS sources (Adzuna, Himalayas, Remotive, Jobicy,
      RemoteOK, WWR) now use consistent pipeline:
      html.unescape(raw) -> strip <tags> -> collapse whitespace -> truncate
    - Himalayas: was using "excerpt" field (~200 char summary); switched to
      "description" field with excerpt as fallback
    - Adzuna: removed full_description=1 param that caused HTTP 400 on free
      plan; description field returns clean plain text without it
    - Description truncation: prompt now uses 6000 chars (up from 5000) to
      match Lever's combined field length; GH/Ashby stay at 5000 since their
      content beyond that is benefits boilerplate
    - Claude rate limit fix: replaced fire-and-give-up with exponential backoff
      retry loop (4 attempts: 15s -> 30s -> 60s -> 120s wait between retries)
    - Claude batch pacing: replaced always-on ThreadPoolExecutor with batches
      of 3 + 5s sleep between batches; prevents token-burst rate limit spikes
      on large backlogs while maintaining parallelism on normal runs
    - Empty-company filter: added after bad_scrape filter to drop Brave/Tavily/
      LinkedIn results with no company field (news articles, aggregator pages,
      HiringCafe links, etc.)
    - Debug log: write_debug_log() writes full per-job log to
      output/job-radar/debug_job_log.txt after every run (overwritten each day)

  2026-03-15 - Session 2: ATS expansion and slug verification
    - Batch-tested all 412+ ATS slugs via browser; removed 298 dead slugs
      (credit unions, legacy banks on Workday/iCIMS, companies with no public
      ATS API); corrected 4 wrong slugs (mx->mxtechnologiesinc, bluevine->
      bluevineus, treasury-prime->treasuryprime, modern-treasury->moderntreasury)
    - Added 30+ new verified slugs: nubank, trustly, tilthq, adyen, truebill,
      creditkarma, prove, alt, engine, galileofinancialtechnologies,
      employerdirecthealthcare, anchorage, entersekt, versapay, aledade,
      redventures, atbayjobs, federato, sureify, ethoslife, kapitus, BestEgg,
      spreedly, truv, sparkadvisors, deepintent, modernhealth, oportun, etc.
    - ATS_NAME_OVERRIDES: added display name corrections for all new slugs
    - 133-slug clean sweep: all confirmed live before each deployment

  2026-03-15 - Session 1: Initial build and core bug fixes
    - 17 founding bugs fixed (see original session transcript for full list)
    - Key fixes: Ashby wrong key (jobPostings->jobs), Greenhouse entity order,
      Lever multi-field concatenation, dedup edge cases, rate limit retry,
      salary string parser false positives, WWR company extraction
    - Added: RemoteOK as 12th source, company signal layer (Wikipedia), parallel
      Claude rating (ThreadPoolExecutor), ATS description fetching improvements
    - rtp removed from Raleigh terms (was matching "Real-Time Payments" and
      surfacing Munich jobs in the Raleigh section)
"""

import os
import copy
import html
import re
import sys
import sqlite3
import subprocess
import json
import time
import random
import smtplib
import requests
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from datetime import date, datetime, timezone, timedelta
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()

# ── PERSONAL CONFIG ───────────────────────────────────────────────────────────
# All user-specific settings live in config.py (gitignored).
# sys already imported above — reuse it for path insertion
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from config import (
        MIN_SALARY, VACATION_START, VACATION_END, PROFILE, RALEIGH_TERMS, QUOTES,
        ADZUNA_QUERIES, BRAVE_QUERIES, TAVILY_QUERIES,
        LI_REMOTE_QUERIES, LI_RALEIGH_QUERIES,
        HIMALAYAS_QUERIES, REMOTIVE_QUERIES, USAJOBS_QUERIES, JOBICY_QUERIES,
    )
except ModuleNotFoundError:
    raise SystemExit(
        "\nERROR: config.py not found.\n"
        "Create scripts/config.py — copy from the repo README and fill in your details.\n"
    )


# ── CONFIG ──────────────────────────────────────────────────────────────────

def _require_env(key):
    """Raises a clear error if a required env var is missing, instead of a cryptic KeyError."""
    val = os.environ.get(key)
    if not val:
        raise SystemExit(
            f"\nERROR: Required environment variable '{key}' is not set.\n"
            f"Check your .env file in the same folder as job_radar.py.\n"
            f"Required keys: GMAIL_ADDRESS, GMAIL_APP_PW, ADZUNA_APP_ID, ADZUNA_APP_KEY,\n"
            f"               BRAVE_API_KEY, TAVILY_API_KEY, ANTHROPIC_API_KEY"
        )
    return val

EMAIL           = _require_env("GMAIL_ADDRESS")
GMAIL_APP_PW    = _require_env("GMAIL_APP_PW")
ADZUNA_APP_ID   = _require_env("ADZUNA_APP_ID")
ADZUNA_APP_KEY  = _require_env("ADZUNA_APP_KEY")
BRAVE_API_KEY   = _require_env("BRAVE_API_KEY")
TAVILY_API_KEY  = _require_env("TAVILY_API_KEY")
ANTHROPIC_KEY   = _require_env("ANTHROPIC_API_KEY")
USAJOBS_API_KEY  = os.environ.get("USAJOBS_API_KEY", "")   # optional - free at developer.usajobs.gov
USAJOBS_EMAIL    = os.environ.get("USAJOBS_EMAIL", "")     # required by USAJobs - your email address

# Resolve output paths relative to the project root (parent of scripts/)
# so the script works correctly regardless of which directory it is run from.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
_OUTPUT_DIR = os.path.join(_PROJECT_ROOT, "output", "job-radar")

SEEN_FILE           = os.path.join(_OUTPUT_DIR, ".seen.json")

# ── TUNING CONSTANTS ──────────────────────────────────────────────────────────
# Centralised here so they're easy to find and adjust without hunting through code.
CLAUDE_BATCH_SIZE   = 3    # parallel workers per rating batch; higher = faster but more rate-limit risk
CLAUDE_MAX_RETRIES  = 4    # retry attempts on rate-limit/overload (waits: 15s, 30s, 60s, 120s)
CLAUDE_TIMEOUT_SECS = 15   # per-request timeout for Claude API calls
CLAUDE_MAX_TOKENS   = 400  # max tokens in Claude response (250 was too tight for long reason+salary)

# ── TIER CONSTANTS ────────────────────────────────────────────────────────────
# Single source of truth for tier names. Use these everywhere instead of
# magic strings to prevent silent bugs from typos.
TIER_PERFECT = "Perfect Fit"
TIER_GOOD    = "Good Fit"
TIER_LOOK    = "Worth a Look"
TIER_SKIP    = "Skip"

# Default tier assigned when Claude cannot rate a job (API error, timeout, malformed response).
# FIX (code review): was a magic string "Worth a Look" repeated in 4+ places. Single constant now.
DEFAULT_TIER        = TIER_LOOK

# Companies exempt from description-extracted salary filtering.
# These are well-known fintech/tech employers whose posted PM/PO roles consistently
# pay above MIN_SALARY. Brave/Tavily search snippets sometimes surface salary figures
# from older Glassdoor estimates or truncated ranges that look below floor.
# ATS jobs from these companies (salary=None) already pass through — this only affects
# jobs where a search engine snippet incorrectly extracted a low salary number.
SALARY_FLOOR_EXEMPT = frozenset([
    "upstart", "stripe", "plaid", "mercury", "brex", "chime", "affirm",
    "robinhood", "coinbase", "square", "block", "marqeta", "adyen",
    "wells fargo", "capital one", "jpmorgan", "chase", "bank of america",
    "citigroup", "citi", "goldman sachs", "morgan stanley",
])

# ── OUTPUT FILE PATHS ──────────────────────────────────────────────────────────
# FIX (code review): these are file paths, not tuning constants. Moved to their
# own section to avoid confusion with the numeric tuning values above.
VACATION_BUFFER     = os.path.join(_OUTPUT_DIR, "vacation_buffer.json")
COMPANY_CACHE_FILE  = os.path.join(_OUTPUT_DIR, ".company_cache.json")
# Debug log: contains every job with full description text as sent to Claude.
# Upload to Claude to verify data quality. Overwritten each run.
DEBUG_LOG_FILE      = os.path.join(_OUTPUT_DIR, "debug_job_log.txt")
RADAR_DB_FILE       = os.path.join(_OUTPUT_DIR, "radar_runs.db")

# ── SQLITE HEALTH TRACKING ────────────────────────────────────────────────────
# Persists per-run stats (source counts, latencies, filter breakdown) to SQLite.
# Enables the Health tab in the dashboard to show run history over time.
# All DB operations are best-effort — errors are logged but never crash the radar.

_RADAR_DB_SCHEMA = """
    CREATE TABLE IF NOT EXISTS radar_runs (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at   TEXT NOT NULL,
        finished_at  TEXT,
        total_raw    INTEGER DEFAULT 0,
        total_new    INTEGER DEFAULT 0,
        total_rated  INTEGER DEFAULT 0,
        report_file  TEXT
    );

    CREATE TABLE IF NOT EXISTS source_stats (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id      INTEGER NOT NULL,
        source      TEXT NOT NULL,
        raw_count   INTEGER DEFAULT 0,
        new_count   INTEGER DEFAULT 0,
        latency_ms  INTEGER DEFAULT 0,
        FOREIGN KEY (run_id) REFERENCES radar_runs(id)
    );

    CREATE TABLE IF NOT EXISTS filter_stats (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id      INTEGER NOT NULL,
        reason      TEXT NOT NULL,
        count       INTEGER DEFAULT 0,
        FOREIGN KEY (run_id) REFERENCES radar_runs(id)
    );
"""


def _db_connect():
    """Open (or create) the radar runs SQLite database.

    WAL mode allows concurrent reads during writes — prevents dashboard from
    getting 'database is locked' when job_radar.py is writing run stats.
    """
    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    conn = sqlite3.connect(RADAR_DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_RADAR_DB_SCHEMA)
    conn.commit()
    return conn


def _db_insert_run(conn, started_at):
    cur = conn.execute(
        "INSERT INTO radar_runs (started_at) VALUES (?)", (started_at,)
    )
    conn.commit()
    return cur.lastrowid


def _db_finish_run(conn, run_id, finished_at, total_raw, total_new, total_rated, report_file):
    conn.execute(
        "UPDATE radar_runs SET finished_at=?, total_raw=?, total_new=?, "
        "total_rated=?, report_file=? WHERE id=?",
        (finished_at, total_raw, total_new, total_rated, report_file, run_id),
    )
    conn.commit()


def _db_insert_source_stats(conn, run_id, raw_counts, source_new_counts, source_latencies):
    for source, raw in raw_counts.items():
        conn.execute(
            "INSERT INTO source_stats (run_id, source, raw_count, new_count, latency_ms) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                run_id, source, raw,
                source_new_counts.get(source, 0),
                source_latencies.get(source, 0),
            ),
        )
    conn.commit()


def _db_insert_filter_stats(conn, run_id, filtered_jobs):
    by_reason: dict[str, int] = {}
    for j in filtered_jobs:
        by_reason[j["reason"]] = by_reason.get(j["reason"], 0) + 1
    for reason, count in by_reason.items():
        conn.execute(
            "INSERT INTO filter_stats (run_id, reason, count) VALUES (?, ?, ?)",
            (run_id, reason, count),
        )
    conn.commit()

# ── ATS SLUG -> DISPLAY NAME OVERRIDES ────────────────────────────────────────
# slug.replace("-", " ").title() gets most names right but fails for some.
# Add entries here when a company name from the email looks wrong.
ATS_NAME_OVERRIDES = {
    "ncino":           "nCino",
    "squareup":        "Square",
    "bill":            "Bill.com",
    "m1-finance":      "M1 Finance",
    "public-com":      "Public.com",
    "cross-river":     "Cross River Bank",
    "leadbank":        "Lead Bank",
    "q2":              "Q2",
    "mx":              "MX Technologies",
    "wex":             "WEX Inc.",
    "oneapp":          "OnePay",
    "Jerry.ai":        "Jerry",
    "varomoney":       "Varo Bank",
    "monzo":           "Monzo",
    "tilthq":          "Tilt",
    "galileofinancialtechnologies": "Galileo Financial Technologies",
    "employerdirecthealthcare": "Employer Direct Healthcare",
    "creditkarma":     "Credit Karma",
    "zipcolimited":    "Zip Co",
    "idme":            "ID.me",
    "incode":          "Incode",
    "stytch":          "Stytch",
    "orum":            "Orum",
    "finix":           "Finix",
    "amount":          "Amount",
    "oportun":         "Oportun",
    "inkind":          "inKind",
    "laporteusa":      "LaPorte USA",
    "boulevard":       "Boulevard",
    "whoop":           "WHOOP",
    "atbayjobs":       "At-Bay",
    "federato":        "Federato",
    "sureify":         "Sureify",
    "ethoslife":       "Ethos Life",
    "kapitus":         "Kapitus",
    "BestEgg":         "Best Egg",
    "spreedly":        "Spreedly",
    "truv":            "Truv",
    "anchorage":       "Anchorage Digital",
    "entersekt":       "Entersekt",
    "versapay":        "Versapay",
    "aledade":         "Aledade",
    "redventures":     "Red Ventures",
    "sparkadvisors":   "Spark Advisors",
    "deepintent":      "DeepIntent",
    "modernhealth":    "Modern Health",
    "peakcreditunion": "Peak Credit Union",
    "myfundedfutures": "My Funded Futures",
    "securitize":      "Securitize",
    "truebill":        "Rocket Money (Truebill)",
    "nubank":          "Nubank",
    "mxtechnologiesinc": "MX Technologies",
    "bluevineus":       "Bluevine",
    "treasuryprime":    "Treasury Prime",
    "moderntreasury":   "Modern Treasury",
}
# MIN_SALARY imported from config.py

# ── DOMAIN -> COMPANY NAME MAP ────────────────────────────────────────────────
# Maps URL domain substrings -> company display names for Brave/Tavily results
# where the API returns no company field. First match wins.
# Ported from devpyle/job-search-profile (2026-03-18).
DOMAIN_COMPANY_MAP: dict = {
    "fisglobal": "FIS", "fisv": "Fiserv", "fiserv": "Fiserv",
    "jpmorgan": "JPMorgan Chase", "jpmorganchase": "JPMorgan Chase",
    "goldmansachs": "Goldman Sachs", "morganstanley": "Morgan Stanley",
    "bankofamerica": "Bank of America", "wellsfargo": "Wells Fargo",
    "citigroup": "Citi", "citi.com": "Citi", "usbank": "U.S. Bank",
    "pnc.com": "PNC", "capitalone": "Capital One",
    "americanexpress": "American Express", "discover": "Discover",
    "synchrony": "Synchrony", "broadridge": "Broadridge",
    "dtcc.com": "DTCC", "intercontinentalexchange": "ICE", "ice.com": "ICE",
    "nasdaq.com": "Nasdaq", "bloomberg": "Bloomberg", "factset": "FactSet",
    "morningstar": "Morningstar", "blackrock": "BlackRock",
    "vanguard": "Vanguard", "fidelity": "Fidelity", "schwab": "Charles Schwab",
    "stripe.com": "Stripe", "plaid.com": "Plaid", "brex.com": "Brex",
    "marqeta": "Marqeta", "adyen": "Adyen", "paypal": "PayPal",
    "square": "Block (Square)", "intuit": "Intuit",
    "salesforce": "Salesforce", "servicenow": "ServiceNow",
    "workday": "Workday", "oracle": "Oracle", "sap.com": "SAP",
    "ibm.com": "IBM", "microsoft": "Microsoft", "amazon": "Amazon",
    "google": "Google",
}

# ── CANDIDATE PROFILE (sent to Claude for rating) ───────────────────────────

# PROFILE imported from config.py

# QUOTES imported from config.py
# Keep this list SHORT - only terms that are 100% unambiguous regardless of context.
# Everything else gets passed to Claude, which can read context and make a better call.

# FIX (code review): Changed from list to frozenset.
# Only used for `term in HARD_DISQUALIFIERS` membership tests — frozenset gives
# O(1) lookup vs O(n) list scan, and documents intent: these are unique, unordered terms.
HARD_DISQUALIFIERS = frozenset([
    # Crypto/blockchain - no legitimate fintech PM role needs these
    "blockchain", "web3", "cryptocurrency", "crypto currency",
    "digital assets", "programmable blockchain", "nft",
    "decentralized finance", "smart contract",
    # FIX (see changelog): Parafin/OnePay type cash advance origination
    "merchant cash advance",
    # Staffing agency description phrases — recruiter posting on behalf of a client
    "on behalf of our client",
    "on behalf of a client",
    "our client is looking",
    "our client is seeking",
])

# Separate regex-based disqualifiers that need word boundary matching
# "defi" must be whole-word only - "define", "defined", "definitely" are NOT DeFi
# "crypto" must be whole-word only - "cryptography", "cryptographic" are NOT crypto
_HARD_DISQ_RE = re.compile(r"\bdefi\b|\bcrypto\b", re.IGNORECASE)

def has_disqualifier(job):
    """
    Scans title + description for hard disqualifier keywords.
    Title is checked first (faster) - most disqualifiers appear in titles.
    Returns the matched term or None.
    """
    # Check title first - it is short and catches most cases immediately
    title_text = job.get("title", "").lower()
    # NOTE: HARD_DISQUALIFIERS is a frozenset — O(1) for `term in set` membership
    # but here we iterate the set and test `term in string` (substring search),
    # which is O(n) per term. The frozenset still prevents duplicates and signals
    # intent; it does NOT make substring search faster. Comment updated for clarity.
    for term in HARD_DISQUALIFIERS:
        if term in title_text:
            return term
    if _HARD_DISQ_RE.search(title_text):
        return "crypto/defi"
    # Only scan full description if title was clean
    desc_text = job.get("description", "").lower()
    for term in HARD_DISQUALIFIERS:
        if term in desc_text:
            return term
    if _HARD_DISQ_RE.search(desc_text):
        return "crypto/defi"
    return None


# ── COMPANY PRE-FILTER ────────────────────────────────────────────────────────
# Companies confirmed as structurally always-Skip over multiple runs.
# Pre-filtering these avoids burning Claude API credits on guaranteed-Skip jobs.
# Jobs still appear in the debug log tagged "Company pre-filter: <reason>" so we
# can monitor if a company's hiring pattern changes. To re-enable a company,
# just remove or comment its entry here.
#
# Company-level pre-filter: blocks specific companies before Claude is called.
# Currently used for staffing agencies that reliably post non-direct-hire roles.
# Root-cause filters handle most cases generically (location, salary, disqualifiers)
# but staffing agencies require a name-based block because their postings often
# pass all other filters — remote, correct title, no explicit salary.
#
# To re-enable a company: comment or remove its entry below.
# To add a new company: add "substring": ("category", "reason") — substring match,
# case-insensitive. Keep substrings specific enough to avoid false positives.
_COMPANY_PREFILTER = {
    # ── Staffing agencies — never pass to Claude ──────────────────────────────
    "jobgether":          ("staffing", "Jobgether posts on behalf of partner companies — staffing agency hard disqualifier"),
    "it excel":           ("staffing", "IT Excel is a staffing/recruiting firm — hard disqualifier"),
    "synersys":           ("staffing", "Synersys Technologies is a staffing firm — hard disqualifier"),
    "ec1 partners":       ("staffing", "EC1 Partners is a recruiting firm — hard disqualifier"),
    "pinnacle method":    ("staffing", "Pinnacle Method Consulting is a staffing firm — hard disqualifier"),
    "medasource":         ("staffing", "Medasource is a staffing/contract placement firm — hard disqualifier"),
    "akkodis":            ("staffing", "Akkodis is a contract staffing firm — hard disqualifier"),
    "ramp talent":        ("staffing", "Ramp Talent is a recruiting firm — hard disqualifier"),
    "davis talent":       ("staffing", "Davis Talent Search is a recruiting firm — hard disqualifier"),
    "swooped":            ("staffing", "Swooped is a job aggregator/staffing platform — hard disqualifier"),
    "themesoft":          ("staffing", "Themesoft is a staffing/contract placement firm — hard disqualifier"),
    "solve it strategies":("staffing", "Solve IT Strategies is a staffing agency — hard disqualifier"),
    "piper companies":    ("staffing", "Piper Companies is a staffing firm — hard disqualifier"),
    "seneca creek":       ("staffing", "Seneca Creek ES is a recruiting/placement firm — hard disqualifier"),
    "inizio partners":    ("staffing", "Inizio Partners is a staffing placement firm — hard disqualifier"),
    "crossing hurdles":   ("staffing", "Crossing Hurdles is a recruiting/placement firm — hard disqualifier"),
    "ladders":            ("aggregator", "Ladders is a job aggregator that reposts listings — not a direct employer"),
    # ── Added from v1.6.0 review — description-phrase based ──────────────────
    "insight global":     ("staffing", "Insight Global is a staffing/recruiting firm — hard disqualifier"),
    "apex systems":       ("staffing", "Apex Systems is a staffing/IT recruiting firm — hard disqualifier"),
}

def is_company_prefilter(job):
    """
    Check if the job's company is on the structural always-Skip pre-filter list.
    Returns a reason string if pre-filtered, None otherwise.

    Uses substring match on lowercase company name so "Anchorage Digital" matches
    the "anchorage digital" key, Greenhouse slug overrides included.

    To re-enable a company: remove or comment its entry in _COMPANY_PREFILTER.
    """
    company = (job.get("company") or "").lower().strip()
    for co_key, (category, reason) in _COMPANY_PREFILTER.items():
        if co_key in company:
            return f"Company pre-filter ({category}): {reason}"
    return None


# ── TITLE PRE-FILTER ─────────────────────────────────────────────────────────
# Catches clearly wrong roles and known staffing agencies before Claude sees them.

_WRONG_TITLE_RE = re.compile(
    r"^associate product (manager|owner)\b"      # junior level
    r"|^head of product\b"                       # usually people management
    r"|\bdata analyst\b"                         # wrong function
    r"|\b(sales|marketing) (manager|director|executive|rep|consultant|account)\b"
    r"|\bcustomer (service|success|care) (rep|representative|specialist|associate|coordinator|manager|operations)\b"  # FIX (see changelog): added "representative" - "Customer Service Representative" was slipping through
    r"|\bcustomer experience (associate|representative|specialist|rep|coordinator)\b"  # CX support roles
    r"|\bclient success\b"                       # wrong function
    r"|\b(backend|frontend|software|engineering) (manager|lead|director)\b"
    r"|^project manager\b"                       # project manager at start (not "product")
    r"|\belectrical products\b"                  # engineering products, not PM
    r"|supply chain\b"
    r"|entry.?level\b"
    r"|\bbusiness owner\b"                       # franchise/business ownership listings
    r"|\b(coordinator|negotiator|recruiter)\b"   # wrong level/function
    r"|\b(games?|gaming|esports) (product|title|portfolio|manager)\b"  # gaming PM
    r"|\breal estate\b"                          # wrong domain
    r"|\bsecurity (manager|guard|officer)\b"     # wrong function
    r"|\btalent acquisition\b"               # HR/recruiting roles
    r"|\bcommand center\b"                    # IT ops roles
    r"|\bsupport engineer\b"                  # engineering support roles
    r"|\bbilling success manager\b"           # customer success/billing ops
    r"|\bsenior independent\b"                # A.Team freelance listings
    r"|\baccount executive\b"                 # sales roles
    r"|\bsales (lead|executive|manager|rep|representative|development)\b"  # sales roles
    r"|\b(sdr|bdr|account executive|sales development)\b"  # sales roles
    # FIX (see changelog): Additional non-PM types confirmed in log analysis
    r"|\bproduct designer\b"                  # UX/design roles (not PM)
    r"|\bproduct design(er)?\b"               # design track
    r"|\bproduct marketing\b"                 # marketing, not PM
    r"|\bproduct security engineer\b"         # security engineering
    r"|\bcustomer success manager\b"          # CSM roles (not PM/PO/BA)
    r"|\blife underwriter\b"                  # insurance underwriting
    r"|\bimplementation specialist\b"         # implementation ops
    r"|\bcontact center rep\b"                # contact center staffing
    r"|\bvacation specialist\b"               # travel staffing
    r"|\bai trainer\b"                        # freelance AI training
    r"|\b(junior|associate) client partner\b" # junior sales at consulting firms
    r"|\bqa analyst\b"                        # quality assurance
    r"|\bindependent operator\b"              # AtWork Group franchise listings
    r"|\bsmb owner\b"                         # SMB ownership listings
    r"|\bregional sales lead\b"               # sales leadership
    r"|\bkey account manager\b"               # sales
    r"|\bpartnership sales manager\b"         # sales
    r"|\benterprise (billing|sales) (success|executive)\b"  # billing/sales ops
    r"|\bdirector.*talent acquisition\b"      # recruiting leadership
    r"|\bsenior account executive\b"          # sales
    r"|\bsenior client delivery\b"            # delivery/ops
    r"|\bclinical product lead\b.*temp\b"     # temp clinical roles requiring clinical degree
    r"|\bmanagement consultant\b"             # consulting placement roles (NAVIX, Deloitte, etc.)
    r"|\bcustomer service representative\b"   # explicitly spell out - CSR slips through the shorter pattern
    r"|\bbusiness development representative\b" # BDR/sales dev roles
    r"|^entrepreneur\b"                       # AtWork Group bizdev listings (title-start only)
    r"|\bengineering manager\b"               # eng people management (not PM)
    r"|\bdigital marketing\b"                 # marketing function (not PM)
    r"|\bfranchise\b"                         # franchise/bizdev (Empower Brands, AtWork, etc.)
    r"|program manager,?\s+sales\b"           # sales engineering program mgr (Samsara pattern)
    r"|\bbusiness consultant\b"               # consulting placement (broader than management consultant)
    r"|\bteam lead.*command\b"                # IT ops
    r"|\bpatient.specific instrument\b"       # medical device mfg
    # ── Added 2026-04-02 from flagged job review ──────────────────────────────
    r"|\bdata product manager\b"               # data PM (pre-filter to save Claude credits)
    r"|\bdata product owner\b"                 # data PO
    r"|\blead data product\b"                  # data PM variant
    r"|\bsr\.?\s+data product\b"               # senior data product variant
    r"|\bsenior data product\b"                # senior data product variant
    r"|\bstaff data product\b"                 # staff data product variant
    r"|\bquantitative analyst\b"               # quant roles — wrong function
    r"|\bsoftware (engineer|developer)\b"      # engineering roles — not PM
    r"|\bfrontend (engineer|developer)\b"      # frontend dev
    r"|\bfront.end (engineer|developer)\b"     # front-end dev
    r"|\bbackend (engineer|developer)\b"       # backend dev
    r"|\bfull.?stack (engineer|developer)\b"   # fullstack dev
    r"|\bdevice design engineer\b"             # hardware engineering
    r"|\blead product engineer\b"              # engineering function
    r"|\bproduct engineer\b"                   # engineering function (not PM)
    r"|\bsales engineer\b"                     # sales engineering
    r"|\bsolutions engineer\b"                 # solutions engineering
    r"|\b(food|meat|kitchen) (manager|production|lead)\b"  # ops/retail
    r"|\boperations director\b"                # ops leadership
    r"|\bservice manager\b"                    # service ops
    r"|\b(svp|senior vice president)\b"        # C-suite too senior
    r"|\bchief (executive|financial|operating|marketing|revenue)\b"  # C-suite
    r"|\bassociate director\b"                 # director-level people management
    r"|\bintern(ship)?\b"                      # internship roles
    r"|\bdesign researcher\b"                  # research function
    r"|\bowner operator\b"                     # owner-operator listings
    r"|\bcompliance safety\b"                  # safety/compliance operations
    r"|\bstatewide accountant\b"               # accounting operations
    r"|\bprior authorization\b"                # healthcare admin ops
    r"|\bcable backplane\b"                    # hardware engineering
    r"|\binitialization success\b"             # ops support role
    r"|\bintelligence engine\b"               # AI engineering
    r"|\bsecurity clearance\b"               # clearance-required roles — wrong domain
    # ── Added 2026-04-03 from flagged job review ──────────────────────────────
    r"|\bgraphic designer\b"                   # design function — not PM
    r"|\bhardware r.?d\b"                        # hardware engineering function
    r"|\bmaster data management\b"               # MDM/data governance — not PM
    r"|\barea business manager\b"              # field sales role
    r"|\bprofessional sales representative\b"  # pharma/field sales
    r"|\bsenior sales representative\b"        # sales
    r"|\bsales representative\b"               # sales (reinforced)
    r"|\bfield sales\b",                            # field sales
    re.IGNORECASE,
)

def is_wrong_title(job):
    title = job.get("title", "").lower()
    return bool(_WRONG_TITLE_RE.search(title))

# ── CATEGORY PAGE FILTER ─────────────────────────────────────────────────────
# Brave and Tavily return a lot of noise - blog posts, aggregator pages, wikis,
# "work from home" roundups, etc. Catch them all before Claude ever sees them.

_CATEGORY_URL_FRAGMENTS = [
    "glassdoor.com/Job/", "indeed.com/q-", "indeed.com/jobs",
    "linkedin.com/jobs/search", "linkedin.com/jobs/api-",
    "ziprecruiter.com/Jobs/", "jobgether.com/remote-jobs/",
    "remoterocketship.com/jobs/", "remotive.com/remote-jobs/",
    "wellfound.com/jobs", "builtin", "flexjobs.com/jobs",
    "workingnomads.com/jobs", "simplyhired.com/search",
    "dailyremote.com/remote-", "beamjobs.com", "resumeworded.com",
    "zety.com", "kickresume.com", "wikipedia.org", "workingnomads.com",
    "gearbrain.com", "monster.com/jobs", "dice.com/jobs",
    "sportstechjobs.com", "managementpedia.com", "jobberman.com",
    "arc.dev/remote-jobs", "fractional.jobs", "crossover.com",
    "workfromhomeboard.com", "remotejobsusa.com", "remotejob.biz",
    "career.zycto", "lensa.com", "tallo.com", "ladders.com/jobs",
    "visasponsorshipjobs", "jobbank.gc.ca",
    "drivecareer.us.com",      # spam aggregator impersonating Amazon careers
    "hiring.cafe/jobs/",      # HiringCafe listing pages (actual jobs use /viewjob/)
    "remoteok.com/remote-",   # RemoteOK category pages
    "roberthalf.com",         # Staffing agency search pages
    "weworkremotely.com/categories/",  # WWR category pages (RSS items are fine)
    "flexjobs.com/remote-jobs/",       # FlexJobs category pages
    "remoterocketship.com/us/jobs/",   # RemoteRocketship search pages
    "ratracerebellion.com",   # Work-from-home blog, not a job board
    "jaabz.com",              # Visa sponsorship aggregator
    "careerwave.lovestoblog.com",      # Spam job blog
    "remotefront.com/remote-jobs/",    # Job aggregator pages
    "careervault.io",         # Job aggregator
    "barchart.com/story",     # News/blog articles
    "searchengineland.com",   # Marketing news site
    "indeed.com/m/jobs",      # Indeed mobile search results pages
    "jooble.org",             # Jooble job aggregator search pages
    "careerbuilder.com/job-details",  # CareerBuilder aggregator
    "generalist.world",       # Not a real job board
    "ycombinator.com/jobs/role/",  # YC job search pages (not individual postings)
    "handbook.gitlab.com",    # GitLab internal handbook pages
    "sortlist.com",           # Agency/vendor directory, not a job board
    "virtualvocations.com",   # Low-quality job board with noise listings
    # ── Generic careers portal root/landing pages (no specific job ID) ──────
    "careers.pnc.com/global/en",          # PNC careers portal homepage
    "careers.bankofamerica.com/en-us",    # BofA careers search page
    "careers.bankofamerica.com/en-us/job-search",
    # ── Non-US job boards - remote or target metro only ──
    "totaljobs.com",          # UK job board
    "reed.co.uk",             # UK job board
    "cv-library.co.uk",       # UK job board
    "jobs.ac.uk",             # UK academic jobs
    "jobsite.co.uk",          # UK job board
    "theladders.com",         # US but surfaces lots of non-remote roles
    # ── Free website builders used as scraped job mirrors ──
    "wuaze.com",              # Free site builder - scraped/reposted jobs
    "wixsite.com",            # Wix free sites
    "weebly.com",             # Weebly free sites
    "wordpress.com",          # WordPress.com free sites (not .org)
    "blogspot.com",           # Blogger free sites
    "sites.google.com",       # Google Sites - rarely real job postings
]

_CATEGORY_TITLE_RE = re.compile(
    r"\d[\d,+]+\s+\w.*jobs?\s+(in|for|at)\b"          # "2,129 PM jobs in..."
    r"|^(browse|search(\s+the\s+best)?)\s+"             # "Browse 57..."
    r"|jobs?\s+in\s+(remote|united states|us)\b"
    r"|(top|best)\s+remote\s+\w.*jobs?\s+(in|from)\b"
    r"|^\d[\d,+]+\s+(remote|open)\s+\w+\s+jobs?\b"
    r"|today.s top \d"
    r"|resume (samples?|templates?|examples?|guide)"
    r"|how to (write|build|create|hire|find|get)"
    r"|(top|best)\s+\d+\s+(tools?|skills?|tips?|ways?|sites?)"
    r"|work.?from.?home\s+(jobs?|board|hub)"            # "Work From Home Jobs"
    r"|^remote\s+jobs?\s*[-–|]"                         # "Remote Jobs - ..."
    r"|^now hiring:"                                     # "Now Hiring: Huge List..."
    r"|^🧨|^🔥"                                         # emoji-led roundup posts
    r"|\bwikipedia\b"
    r"|\bsalary\b.*(guide|report|data|range)"
    r"|(list of|roundup|compilation).*(jobs?|roles?)"
    r"|jobs? you can do while"
    r"|work at home jobs for"
    r"|entry.?level.*(no experience|this week)"
    r"|flexible schedule.*remote"
    r"|online customer (service|relations)"
    # ── Added from v1.6.0 review ──────────────────────────────────────────────
    r"|\w[\w\s]+jobs?\s+in\s+(north america|united states|the us|latin america|europe|canada)\b"
    r"|\bsalary\b.*(guide|report|data|range|breakdown)"
    r"|(cost|price|pricing)\s+(breakdown|guide|in \d{4})"
    r"|^remote\s+jobs?\s*$"                             # bare "Remote Jobs" title
    r"|\bremote\s+\w[\w\s]+jobs?\s+in\s+\w",            # "remote product manager jobs in ..."
    re.IGNORECASE,
)

# Catches non-job titles that slip past CATEGORY_TITLE_RE because they don't
# mention "jobs" — e.g. "Top 10 Product Manager Skills" or "How to Price SaaS".
# NOTE: patterns overlapping with CATEGORY_TITLE_RE have been removed here to
# avoid redundancy. Only patterns unique to non-job content without "jobs" live here.
NON_JOB_TITLE_RE = re.compile(
    r"(cost|price|pricing)\s+(breakdown|guide|in \d{4})"
    r"|(top|best)\s+\d+\s+(tools?|skills?|tips?|ways?|sites?)\s*(for|to|in)?\s*\w",
    re.IGNORECASE,
)

_EXPIRED_RE = re.compile(
    r"no longer (accepting|available|active|taking)"
    r"|position (has been|is) (filled|closed)"
    r"|this (job|position|role) (has|is) (expired|closed|filled|no longer)"
    r"|job (has expired|is no longer|has been filled)"
    r"|applications? (are |is )?(now |currently )?(closed|no longer being accepted)"
    r"|posting (has|is) (expired|closed|been removed)"
    r"|we('re| are) (no longer|not) accepting"
    r"|thank you for your interest.*no longer"
    r"|this (listing|posting|requisition) (is|has been) (closed|removed|filled|expired)"
    r"|role has been filled"
    r"|search has been closed"
    r"|not currently hiring"
    r"|deadline (has passed|was|is past)",
    re.IGNORECASE,
)

_NON_US_RE = re.compile(
    # UK
    r"\b(london|manchester|birmingham|edinburgh|glasgow|leeds|bristol|liverpool|sheffield|cambridge|oxford)\b"
    r"|\bunited kingdom\b|\buk\b(?! based remote)|\bengland\b|\bscotland\b|\bwales\b|\bnorthern ireland\b"
    # Canada
    r"|\b(toronto|vancouver|montreal|ottawa|calgary|edmonton|winnipeg)\b|\bcanada\b"
    # Australia / NZ
    r"|\b(sydney|melbourne|brisbane|perth|adelaide|auckland|wellington)\b|\baustralia\b|\bnew zealand\b"
    # Western Europe
    r"|\b(berlin|munich|hamburg|frankfurt|cologne|amsterdam|rotterdam|paris|lyon|madrid|barcelona|rome|milan|zurich|vienna|brussels|stockholm|oslo|copenhagen|helsinki|dublin)\b"
    # Baltic / Eastern Europe
    r"|\b(tallinn|riga|vilnius|warsaw|prague|budapest|bucharest|sofia|zagreb|bratislava)\b"
    r"|\bestonia\b|\blatvia\b|\blithuania\b|\bpoland\b|\bczech\b|\bhungary\b|\bromania\b"
    # Nordic
    r"|\bsweden\b|\bnorway\b|\bdenmark\b|\bfinland\b|\biceland\b"
    # Asia
    r"|\b(singapore|hong kong|shanghai|beijing|tokyo|seoul|bangalore|mumbai|new delhi|hyderabad)\b"
    r"|\bindia\b|\bjapan\b|\bsouth korea\b|\bchina\b"
    # Middle East - FIX (see changelog): Tel Aviv/Israel were missing (Melio, Lemonade, Payoneer)
    r"|\b(tel aviv|tlv|herzliya|haifa|jerusalem)\b|\bisrael\b"
    # Latin America - FIX (see changelog): São Paulo/Brazil were missing (Adyen LATAM)
    r"|\b(são paulo|sao paulo|rio de janeiro|bogota|mexico city|ciudad de mexico|buenos aires|santiago|lima)\b"
    r"|\bbrazil\b|\bmexico\b(?! remote)|\bcolombia\b|\bargentina\b|\bchile\b|\bperu\b"
    # Southern Europe - FIX (see changelog): Portugal/Spain missing (Complyadvantage Lisbon, Securitize Spain)
    r"|\b(lisbon|porto|madrid|barcelona|seville)\b|\bportugal\b|\bspain\b"
    # Regions used as location labels - FIX (see changelog): EMEA/EU job boards (Deel, Lemonade EU)
    # Matched only when standing alone or at boundaries so we do not catch "eure" etc.
    r"|^emea$|\bemea\b|^eu$|^europe$|\beurope\b(?! remote)"
    # Added 2026-04-02: WeWorkRemotely international companies slipping through
    r"|\bphilippines\b|\bmanila\b|\bmetro manila\b"
    r"|\bukraine\b|\bkyiv\b|\bkharkiv\b"
    r"|\bswitzerland\b|\bzurich\b|\bgeneva\b|\bbern\b"
    r"|\bbelgium\b|\bbrussels\b|\bantwerp\b"
    r"|\bcagayan de oro\b",
    re.IGNORECASE,
)

# Regex to detect non-Raleigh / non-US cities embedded in job URLs
_URL_CITY_RE = re.compile(
    # ── US non-Raleigh cities ─────────────────────────────────────────────────
    r"new[-_]york|new%20york"
    r"|san[-_]francisco|san%20francisco"
    r"|los[-_]angeles|los%20angeles"
    r"|chicago"
    r"|boston"
    r"|seattle"
    r"|austin"
    r"|atlanta"
    r"|denver"
    r"|minneapolis"
    r"|philadelphia"
    r"|phoenix"
    r"|houston"
    r"|dallas"
    r"|miami"
    r"|washington[-_]dc|washington%20dc"
    r"|jersey[-_]city|jersey%20city"
    r"|hoboken"
    r"|stamford"
    r"|charlotte(?!sville)"  # Charlotte NC but not Charlottesville
    r"|new[-_]jersey|new%20jersey"
    r"|connecticut"
    # ── UK ────────────────────────────────────────────────────────────────────
    r"|london|manchester|birmingham|edinburgh|glasgow|leeds|bristol"
    r"|united[-_]kingdom|united%20kingdom"
    # ── Western Europe ────────────────────────────────────────────────────────
    r"|berlin|munich|hamburg|frankfurt|amsterdam|rotterdam"
    r"|paris|madrid|barcelona|rome|milan|zurich|vienna|brussels"
    r"|stockholm|oslo|copenhagen|helsinki|dublin[-_]ireland|dublin%20ireland"
    # ── Baltic / Eastern Europe ───────────────────────────────────────────────
    r"|tallinn|riga|vilnius|warsaw|prague|budapest|bucharest"
    # ── Canada / Australia ────────────────────────────────────────────────────
    r"|toronto|vancouver|montreal|sydney|melbourne",
    re.IGNORECASE,
)

# Regex to detect non-Raleigh US cities in the job's location FIELD (not URL).
# FIX (see changelog): ATS URLs (greenhouse.io/sofi/jobs/123) have no city slugs, so
# _URL_CITY_RE misses them entirely. The location field is the reliable source for
# ATS jobs - check it directly. Only triggers when remote is NOT in the location string.
_LOC_CITY_RE = re.compile(
    # Bay Area
    r"\b(san francisco|menlo park|palo alto|san jose|mountain view|sunnyvale|redwood city)\b"
    # NYC / NJ
    r"|\b(new york|new york city|manhattan|brooklyn|jersey city|hoboken|stamford)\b"
    # Seattle area
    r"|\b(seattle|bellevue|kirkland|redmond)\b"
    # Other major non-Raleigh US metros
    r"|\bchicago\b"
    r"|\bboston\b"
    r"|\b(los angeles|west hollywood|santa monica|culver city)\b"
    r"|\b(dallas|fort worth|frisco|westlake tx)\b"
    r"|\b(denver|boulder)\b"
    r"|\bmiami\b"
    r"|\batlanta\b"
    r"|\baustin\b"
    r"|\b(nashville|memphis)\b"
    r"|\bcharlotte\b(?! st)"  # Charlotte NC - not Raleigh metro (~3h away)
    r"|\b(salt lake city|cottonwood heights)\b"
    r"|\bphoenix\b"
    r"|\bhouston\b"
    r"|\bminneapolis\b"
    r"|\bphiladelphia\b"
    r"|\b(portland or|portland, or)\b"
    r"|\b(washington dc|washington, dc)\b"
    r"|\b(st louis|saint louis|kansas city)\b"
    # State-prefixed format used by SoFi/others: "CA - San Francisco", "WA - Seattle"
    # Match the state abbreviation when followed by a dash (location field convention)
    r"|\b(ca|wa|ny|il|ma|tx|co|ga|fl|az|ut|or|mn|pa|tn)\s*-"
    r"|\bcalifornia\b|\b(washington state|washington, wa)\b",
    re.IGNORECASE,
)


def is_bad_scrape(job):
    """Returns True if the description is clearly JavaScript/JSON/HTML noise instead
    of job content, OR if the job has neither a title nor a description (nothing for
    Claude to rate — wastes an API call and always falls back to DEFAULT_TIER).

    FIX (code review): previously an empty description returned False unconditionally.
    Jobs with no title AND no description still reached Claude, spent a credit, and
    got rated DEFAULT_TIER with no useful information. Now filtered pre-Claude.
    """
    title = job.get("title", "").strip()
    desc  = job.get("description", "").strip()
    if not desc and not title:
        return True   # nothing to rate — drop before Claude
    if not desc:
        return False  # title exists but no description — let Claude try
    if desc.startswith("{") or desc.startswith("["):
        return True   # raw JSON
    if desc.count("var(--") >= 2 or desc.count('"theme') >= 2:
        return True   # CSS variable soup
    if desc.count("<") > 10 and len(re.sub(r"<[^>]+>", "", desc)) < len(desc) * 0.3:
        return True   # mostly HTML tags
    return False

def is_non_us_location(job):
    """Returns True if the job location or description clearly indicates non-US.

    FIX: Description scanning is scoped to non-ATS sources only.
    ATS jobs (Greenhouse/Lever/Ashby) always return a structured location field —
    scanning their descriptions caused false positives on US companies like Plaid and
    Mercury whose JDs mention international offices or EMEA/APAC initiatives incidentally.
    Brave/Tavily/LinkedIn results often have empty location fields so description
    scanning remains necessary for them.
    """
    loc  = job.get("location", "").lower()
    if _NON_US_RE.search(loc):
        return True
    # Only scan description for non-ATS sources where location field is unreliable
    if job.get("source") not in ("Greenhouse", "Lever", "Ashby"):
        desc = job.get("description", "")[:1000].lower()
        if desc and _NON_US_RE.search(desc):
            return True
    return False

def is_onsite_non_raleigh(job):
    """
    Returns True if the job requires on-site attendance at a non-Raleigh location.

    Two detection paths:
      1. URL-based: URL contains a city slug (LinkedIn, Brave, Tavily job links)
      2. Location-field: location field contains a non-Raleigh city (ATS jobs;
         Greenhouse/Lever/Ashby URLs have no city slugs, so URL check alone misses them)

    See CHANGELOG for details on the location-field check added in Session 4.
    Remote signals in the location string override the filter so that postings
    like "San Francisco or Remote" still pass through.
    """
    url   = job.get("url", "").lower()
    loc   = job.get("location", "").lower()
    desc  = job.get("description", "").lower()
    title = job.get("title", "").lower()

    remote_signals = ("remote", "work from home", "wfh", "distributed", "virtual")
    # Explicit in-office requirement phrases found in job descriptions
    onsite_signals = (
        "come into our office",
        "expected to come into",
        "required to be in office",
        "required to be in the office",
        "in-office",
        "onsite required",
        "on-site required",
    )

    # ── Path 1: URL-based city detection (LinkedIn/Brave/Tavily) ─────────────
    if _URL_CITY_RE.search(url):
        if any(s in title for s in remote_signals):
            return False
        desc_intro = desc[:800]
        if any(s in loc for s in remote_signals):
            # Location says remote but also check if desc explicitly requires in-office
            # e.g. "San Francisco or Remote" with "required to be in office 2 days/week"
            if any(s in desc_intro for s in onsite_signals):
                return True
            return False
        if any(s in desc_intro for s in remote_signals):
            # Remote mentioned but also explicitly requires in-office — filter it
            if any(s in desc_intro for s in onsite_signals):
                return True
            return False
        return True

    # ── Path 2: Location-field city detection (ATS jobs) ─────────────────────
    if _LOC_CITY_RE.search(loc):
        # Keep if remote appears in the location field itself
        # e.g. "San Francisco or Remote", "Remote - San Francisco"
        if any(s in loc for s in remote_signals):
            return False
        desc_intro = desc[:800]
        # Keep if description says remote despite a city in the location field.
        if any(s in desc_intro for s in remote_signals):
            # But if they also explicitly say in-office, filter it
            if any(s in desc_intro for s in onsite_signals):
                return True
            return False
        return True

    return False

def is_category_page(job):
    """
    Returns True if the job appears to be a job board category/search page rather
    than an actual job listing - blog posts, roundup articles, aggregator pages,
    and expired listings are all caught here before reaching Claude.
    """
    url   = job.get("url", "")
    title = job.get("title", "")
    desc  = job.get("description", "")[:500]
    if any(frag in url for frag in _CATEGORY_URL_FRAGMENTS):
        return True
    if _CATEGORY_TITLE_RE.search(title) or NON_JOB_TITLE_RE.search(title):
        return True
    if _EXPIRED_RE.search(title) or _EXPIRED_RE.search(desc):
        return True
    return False

# ── SALARY FILTER ────────────────────────────────────────────────────────────

def _parse_salary_string(s):
    """
    Converts salary strings like '$120K', '$120,000', '$120k-$150k' to a number.
    Returns the UPPER bound of a range (or single value if no range), so salary_ok
    can correctly check whether the range reaches MIN_SALARY.

    BUG FIX: original returned the first (lower) number. For "$123,000 - $163,000"
    this gave 123,000, dropping the job even though the max $163K clears $150K.
    Now returns the max value found, matching the salary_max logic in salary_ok.

    Returns 0 (no salary info - let it through) for:
      - Hourly/weekly/monthly rates (cannot reliably annualize)
      - Bare 4-digit year-like numbers (e.g. "2026")
    """
    if not s:
        return 0
    s_orig = str(s).strip()
    s = s_orig.lower().replace(",", "")
    # Reject non-annual salary formats
    if re.search(r'/\s*(hour|hr|week|wk|month|mo)\b', s):
        return 0
    # Extract ALL dollar amounts (handles ranges like "$123K - $163K")
    nums = re.findall(r'\$?\s*(\d+(?:\.\d+)?)\s*(k?)', s)
    if not nums:
        return 0
    values = []
    for raw_num, k_suffix in nums:
        if re.fullmatch(r'(19|20)\d\d', raw_num.strip()):
            continue  # skip year-like numbers
        val = float(raw_num)
        if k_suffix == 'k':
            val *= 1000
        if val >= 1000:  # ignore sub-1000 bare numbers (noise)
            values.append(int(val))
    if not values:
        return 0
    return max(values)  # upper bound so salary_ok checks if range reaches the floor

def salary_ok(job):
    """
    Returns True if the job passes the salary floor check.
    Jobs with NO salary data always pass - we never drop a job just because
    salary is unlisted. Only drops when a salary IS listed AND the entire range
    is confirmed below MIN_SALARY.

    BUG FIX: original code used salary_min as the check value. For a range like
    $140K-$180K this gave sal=140K and incorrectly dropped the job even though
    $150K (MIN_SALARY) falls within the range. Correct logic:
      - If salary_max is set: check salary_max >= MIN_SALARY (range reaches the floor)
      - If only salary_min (no max): pass through - we cannot confirm the ceiling
        is below $150K, and a single low min may just be the base of an unlisted range
      - String salary (e.g. "$140K" with no range): this is likely a specific figure,
        so check it directly against MIN_SALARY
      - No salary data: always pass

    SALARY_FLOOR_EXEMPT: companies where salary data from Brave/Tavily search snippets
    is unreliable (truncated ranges, equity-only mentions, Glassdoor estimates surfaced
    by the search engine). These companies are well-known fintech employers whose posted
    roles consistently pay above MIN_SALARY — description-extracted salary should not
    filter them. ATS jobs from these companies have salary=None and already pass through;
    this exemption only matters when a search-engine snippet incorrectly lowers the number.
    """
    # Exempt known high-paying companies from description-extracted salary filtering.
    # Only applied to string/description-extracted salary paths — structured ATS salary
    # fields are trusted and still checked.
    company = (job.get("company") or "").lower()
    _salary_exempt = any(e in company for e in SALARY_FLOOR_EXEMPT)

    sal_min = job.get("salary_min") or 0
    sal_max = job.get("salary_max") or 0

    # Numeric range: both min and max present - use MAX to determine if range reaches floor
    if sal_min > 0 and sal_max > 0:
        return sal_max >= MIN_SALARY

    # Only max (no min) - check max directly
    if sal_max > 0:
        return sal_max >= MIN_SALARY

    # Only min (no max posted) - we cannot confirm the ceiling, pass through
    if sal_min > 0:
        return True

    # No structured salary — check string fields.
    for field in ("salary_extracted", "salary"):
        raw = job.get(field)
        if raw:
            sal = _parse_salary_string(str(raw))
            if sal > 0:
                return sal >= MIN_SALARY

    # Last resort: try to extract salary from description text.
    if _salary_exempt:
        return True   # don't filter exempt companies on description-extracted salary

    desc = (job.get("description") or "")[:1000]
    if desc:
        sal = _parse_salary_string(desc)
        if sal > 0:
            return sal >= MIN_SALARY

    return True   # no salary info at all - let it through

# ── DEDUPLICATION ────────────────────────────────────────────────────────────
# Seen file stores: { key: "YYYY-MM-DD" }
# Keys older than SEEN_EXPIRY_DAYS are removed on load so jobs can resurface.
# Migration: old flat-list format (no dates) is upgraded on first load -
#            existing entries get today is date and age out naturally.

SEEN_EXPIRY_DAYS = 60

def load_seen():
    """
    Loads the seen-jobs dictionary from disk. Handles two housekeeping tasks:
      - Migration: old flat-list format -> timestamped dict (runs once, first upgrade)
      - Expiry: removes entries older than SEEN_EXPIRY_DAYS so old jobs can resurface
    Returns a dict of { dedup_key: "YYYY-MM-DD" }.
    """
    today_str = date.today().isoformat()
    if not os.path.exists(SEEN_FILE):
        return {}
    try:
        with open(SEEN_FILE) as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        # Corrupt file (e.g. disk full during previous write) - start fresh rather than crash.
        # All jobs will re-appear once, then be seen again. A small price vs. no morning email.
        print(f"  WARNING: .seen.json is corrupt ({e}) - starting with empty seen list")
        # Back up the corrupt file so it can be inspected/recovered manually
        import shutil as _shutil
        try:
            _shutil.copy2(SEEN_FILE, SEEN_FILE + ".corrupt")
            print(f"  Corrupt file backed up to {SEEN_FILE}.corrupt")
        except OSError:
            pass
        return {}

    # ── Migrate old flat-list format -> dict with today is date ────────────────
    if isinstance(raw, list):
        print(f"  Migrating .seen.json to timestamped format ({len(raw)} entries -> dated today)")
        seen = {k: today_str for k in raw}
    else:
        seen = raw  # already a dict

    # ── Expire entries older than SEEN_EXPIRY_DAYS ────────────────────────────
    cutoff = (date.today() - timedelta(days=SEEN_EXPIRY_DAYS)).isoformat()
    before = len(seen)
    seen = {k: v for k, v in seen.items() if v >= cutoff}
    expired = before - len(seen)
    if expired:
        print(f"  Expired {expired} seen entries older than {SEEN_EXPIRY_DAYS} days")

    return seen

def save_seen(seen):
    """
    Writes the seen-jobs dict back to disk atomically (write to .tmp, then rename).
    This prevents a corrupt seen file if the process is killed mid-write.
    Called once at the end of each run.

    FIX (code review): wrapped in try/except so a disk-full or permissions error
    prints a warning rather than crashing the process after Claude API budget has
    already been spent on ratings.
    """
    try:
        os.makedirs(os.path.dirname(SEEN_FILE), exist_ok=True)
        tmp = SEEN_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(seen, f, indent=2)
        os.replace(tmp, SEEN_FILE)  # atomic on same filesystem - no half-written state
    except OSError as e:
        print(f"  WARNING: could not save seen history ({e}). Jobs may reappear tomorrow.")

# Strips trailing location/work-type suffixes before dedup key generation so that
# "Senior PM - Remote, US" and "Senior PM" at the same company dedup correctly.
_TITLE_CLEANUP_RE = re.compile(
    r"\s*[-–|]\s*(remote|remote,?\s*(us|usa)?|hybrid|onsite|on-site"
    r"|united states?|us|usa|\w{2,3},\s*\w{2})\s*$",
    re.IGNORECASE,
)

def normalize_title(title):
    """
    Strips trailing location/remote noise so that:
      'Senior PM (Remote)'  and  'Senior PM - Remote, US'  -> same key
    But preserves specialization so that:
      'Senior PM - Payments'  and  'Senior PM - Lending'  -> different keys
    """
    t = title.lower().strip()

    # Strip via _TITLE_CLEANUP_RE first (catches "- Remote, US", "- Hybrid", etc.)
    t = _TITLE_CLEANUP_RE.sub("", t).strip()

    # Strip parentheticals that are pure location/remote noise
    # Only strip if the content is a known location word - not role context
    location_words = {"remote", "us", "usa", "united states", "nationwide",
                      "anywhere", "hybrid", "onsite", "on-site", "contract",
                      "full-time", "full time", "part-time", "part time"}
    t = re.sub(r"\(([^)]*)\)", lambda m: "" if m.group(1).strip().lower() in location_words else m.group(0), t).strip()

    # Strip trailing location suffix only if the trailing segment is purely location words
    # e.g. "Senior PM - Remote, US" -> "Senior PM"
    # but "Senior PM - Payments" stays as-is
    for sep in [" - ", " | "]:
        if sep in t:
            parts = t.split(sep)
            suffix_words = set(re.split(r"[\s,]+", parts[-1]))
            if suffix_words.issubset(location_words):
                t = sep.join(parts[:-1]).strip()

    # Collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t

def url_key(url):
    """Strips query params so the same page with different tracking params matches."""
    return url.split("?")[0].rstrip("/").lower()

def dedup_keys(job):
    """
    Returns a list of dedup keys for this job - any one matching means it is a duplicate.
    company|title key is only added when company is known - empty-company jobs from
    Brave/Tavily/WWR would otherwise collide on title alone across different employers.
    Fallback key (title+source) used only when BOTH company and URL are missing -
    these jobs are unapplyable anyway (no link), so deduping them is safe.
    """
    keys = []
    company = job.get("company", "").lower().strip()
    title   = normalize_title(job.get("title", ""))
    if company:
        keys.append(f"{company}|{title}")
    if job.get("url"):
        keys.append(url_key(job["url"]))
    if not keys:
        # No company, no URL - build a weak fallback so this job is marked seen
        # and does not reappear every day. title+source is specific enough for this.
        keys.append(f"__nourl__|{title}|{job.get('source', '').lower()}")
    return keys

def is_seen(job, seen):
    """Returns True if any dedup key for this job already exists in the seen dict."""
    return any(k in seen for k in dedup_keys(job))

def mark_seen(job, seen):
    """Adds all dedup keys for this job to the seen dict with today's date."""
    today_str = date.today().isoformat()
    for k in dedup_keys(job):
        seen[k] = today_str

# ── SEARCH: ADZUNA ───────────────────────────────────────────────────────────

def search_adzuna():
    queries = ADZUNA_QUERIES  # defined in config.py
    jobs = []
    base = "https://api.adzuna.com/v1/api/jobs/us/search/1"
    adzuna_errors_seen = set()  # track unique error types so all distinct failures are logged
    for q in queries:
        try:
            r = requests.get(base, params={
                "app_id":           ADZUNA_APP_ID,
                "app_key":          ADZUNA_APP_KEY,
                "what":             q,
                "results_per_page": 10,
                "sort_by":          "date",
                "max_days_old":     1,
                # NOTE (see changelog): full_description=1 was added to get full JDs
                # but it caused HTTP 400 on the free Adzuna plan. Removed.
                # The default description field returns clean plain text (~300-500
                # chars) which is sufficient for title-domain scoring.
            }, timeout=10)
            if r.status_code != 200:
                err_key = f"HTTP_{r.status_code}"
                if err_key not in adzuna_errors_seen:
                    print(f"  Adzuna HTTP {r.status_code}: {r.text[:300]}")
                    print("  Check your ADZUNA_APP_ID and ADZUNA_APP_KEY in .env")
                    adzuna_errors_seen.add(err_key)
                continue
            for item in r.json().get("results", []):
                created = item.get("created", "")
                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    days_ago = (datetime.now(timezone.utc) - dt).days
                    posted = f"{days_ago}d ago" if days_ago > 0 else "today"
                except Exception:
                    posted = created[:10] if created else ""
                # Only use salary if it is explicitly stated by the employer, not Adzuna's estimate
                salary_predicted = item.get("salary_is_predicted", "0")
                if str(salary_predicted) == "1":
                    sal_min, sal_max = 0, 0
                else:
                    sal_min = item.get("salary_min", 0)
                    sal_max = item.get("salary_max", 0)
                jobs.append({
                    "title":       item.get("title", ""),
                    "company":     item.get("company", {}).get("display_name", ""),
                    "location":    item.get("location", {}).get("display_name", ""),
                    "description": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(item.get("description", "") or ""))).strip()[:5000],
                    "salary_min":  sal_min,
                    "salary_max":  sal_max,
                    "url":         item.get("redirect_url", ""),
                    "posted":      posted,
                    "source":      "Adzuna",
                })
        except Exception as e:
            err_key = type(e).__name__
            if err_key not in adzuna_errors_seen:
                print(f"  Adzuna error: {e}")
                adzuna_errors_seen.add(err_key)
    return jobs

# ── SEARCH: BRAVE ────────────────────────────────────────────────────────────

def search_brave():
    """Search Brave for job postings across all BRAVE_QUERIES.

    FIX (code review): was sequential — 47 queries × 1.2s = ~57s blocking.
    Now parallelised with 5 workers. Each worker sleeps 1.2s before its request
    to honour Brave's 1 req/sec free-tier rate limit across concurrent threads.
    5 workers × 1.2s = 5 req/5s = 1 req/sec average — within the rate limit.
    """
    queries = BRAVE_QUERIES  # defined in config.py
    headers = {"Accept": "application/json", "X-Subscription-Token": BRAVE_API_KEY}
    _brave_lock = threading.Lock()  # protects the shared results list

    def _fetch_one(q):
        time.sleep(1.2)  # honour Brave free-tier 1 req/sec rate limit
        try:
            r = requests.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers=headers,
                params={"q": q, "count": 5, "freshness": "pw"},  # pw = past week
                timeout=10,
            )
            results = []
            for item in r.json().get("web", {}).get("results", []):
                results.append({
                    "title":       item.get("title", ""),
                    "company":     "",
                    "location":    "",
                    "description": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(item.get("description", "") or ""))).strip()[:5000],
                    "salary_min":  0,
                    "salary_max":  0,
                    "url":         item.get("url", ""),
                    "posted":      "",
                    "source":      "Brave",
                })
            return results
        except Exception as e:
            print(f"Brave error ({q[:40]}): {e}")
            return []

    jobs = []
    # 5 workers: keeps average request rate at 1/sec while cutting wall time ~5x.
    with ThreadPoolExecutor(max_workers=5) as executor:
        for result_list in executor.map(_fetch_one, queries):
            jobs.extend(result_list)
    return jobs

# ── SEARCH: TAVILY ───────────────────────────────────────────────────────────

def search_tavily():
    """Search Tavily for job postings across all TAVILY_QUERIES.

    FIX (code review): was sequential — 36 queries × 1-2s = ~60s blocking.
    Now parallelised with 10 workers. Tavily has no strict per-second rate
    limit on paid plans so higher concurrency is safe.
    """
    queries = TAVILY_QUERIES  # defined in config.py

    def _fetch_one(q):
        try:
            r = requests.post(
                "https://api.tavily.com/search",
                json={"api_key": TAVILY_API_KEY, "query": q, "max_results": 5},
                timeout=10,
            )
            results = []
            for item in r.json().get("results", []):
                results.append({
                    "title":       item.get("title", ""),
                    "company":     "",
                    "location":    "",
                    "description": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(item.get("content", "") or ""))).strip()[:5000],
                    "salary_min":  0,
                    "salary_max":  0,
                    "url":         item.get("url", ""),
                    "posted":      "",
                    "source":      "Tavily",
                })
            return results
        except Exception as e:
            print(f"Tavily error ({q[:40]}): {e}")
            return []

    jobs = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        for result_list in executor.map(_fetch_one, queries):
            jobs.extend(result_list)
    return jobs

# ── SEARCH: LINKEDIN ─────────────────────────────────────────────────────────
# Uses LinkedIn's public guest job search endpoint - no account or API key needed.
# Requires: pip install beautifulsoup4

_LI_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer":         "https://www.linkedin.com/",
}
_LI_BASE        = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
_LI_DETAIL_URL  = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

def _li_fetch(keywords, remote=True):
    """Fetch one page of LinkedIn results. Returns list of job dicts."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []
    params = {
        "keywords": keywords,
        "geoId":    "103644278",   # United States
        "f_TPR":    "r604800",     # posted in the last 7 days
        "start":    0,
    }
    if remote:
        params["f_WT"] = "2"       # remote filter
    try:
        r = requests.get(_LI_BASE, params=params, headers=_LI_HEADERS, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        jobs = []
        for card in soup.find_all("li"):
            title_el   = card.find("h3")
            company_el = card.find("h4")
            loc_el     = card.find("span", class_=lambda c: c and "job-search-card__location" in c)
            link_el    = card.find("a", href=True)
            if not (title_el and company_el):
                continue
            loc = loc_el.text.strip() if loc_el else ""
            # For remote queries, skip anything that is not remote or US-wide
            if remote:
                loc_lower = loc.lower()
                if loc_lower and "remote" not in loc_lower and loc_lower not in ("", "united states"):
                    continue
            url = link_el["href"].split("?")[0] if link_el else ""
            jobs.append({
                "title":       title_el.text.strip(),
                "company":     company_el.text.strip(),
                "location":    loc,
                "description": "",
                "salary_min":  0,
                "salary_max":  0,
                "url":         url,
                "posted":      "",
                "source":      "LinkedIn",
            })
        return jobs
    except Exception as e:
        print(f"  LinkedIn fetch error ({keywords}): {e}")
        return []

def _li_fetch_description(job_url: str, max_retries: int = 2) -> tuple:
    """Fetch the full job description from LinkedIn's guest job detail endpoint.
    Extracts job ID from URL, hits the detail API, parses description__text div.
    Returns (description, status) where status is one of:
      "ok"          — description fetched successfully
      "rate_limited" — LinkedIn returned 429, waited and retried
      "no_content"   — 200 response but no description div found
      "http_error"   — non-200, non-429 response
      "error"        — network or parse exception
      "no_job_id"    — URL had no recognisable job ID
    Job always gets rated regardless — empty description falls back to title/company.
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return "", "error"
    # FIX (code review): original regex matched any 7+ digit sequence including
    # tracking params (e.g. ?refId=9876543 would match if the path had no ID).
    # Prefer the path segment: LinkedIn job URLs are /jobs/view/{job_id} or
    # /jobs/{job_id}/. Fall back to any 7+ digit number as a safety net.
    path_m = re.search(r"/(?:view|jobs)/(\d{7,})", job_url)
    m      = path_m or re.search(r"(\d{7,})", job_url)
    if not m:
        return "", "no_job_id"
    job_id = m.group(1)
    for attempt in range(max_retries + 1):
        try:
            r = requests.get(
                _LI_DETAIL_URL.format(job_id=job_id),
                headers=_LI_HEADERS,
                timeout=10,
            )
            if r.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"    ⚠ LinkedIn rate limit — waiting {wait}s before retry...")
                time.sleep(wait)
                continue
            if r.status_code != 200:
                return "", "http_error"
            soup = BeautifulSoup(r.text, "html.parser")
            desc_el = soup.find("div", class_=lambda c: c and "description__text" in c)
            if desc_el:
                raw = desc_el.get_text(" ", strip=True)
                raw = html.unescape(raw)
                raw = re.sub(r"<[^>]+>", " ", raw)
                raw = re.sub(r"\s+", " ", raw).strip()
                return raw[:6000], "ok"
            return "", "no_content"
        except Exception as e:
            if attempt < max_retries:
                time.sleep(5)
                continue
            return "", "error"
    return "", "rate_limited"


def li_enrich_descriptions(jobs: list) -> None:
    """Fetch full descriptions for LinkedIn jobs that don't have one yet.
    Called after dedup + pre-filtering so we only fetch for jobs that reach Claude.
    Mutates description field in place. Randomised 2-5s delays to avoid rate limits.
    Prints progress for each job so you can see it working.
    """
    li_jobs = [j for j in jobs if j.get("source") == "LinkedIn" and not j.get("description")]
    if not li_jobs:
        return
    total = len(li_jobs)
    print(f"  Fetching descriptions for {total} LinkedIn jobs (2-5s delay each)...")
    ok = rate_limited = no_content = errors = 0
    for i, job in enumerate(li_jobs):
        if i > 0:
            time.sleep(random.uniform(2, 5))
        title   = (job.get("title") or "")[:45]
        company = (job.get("company") or "")[:25]
        desc, status = _li_fetch_description(job.get("url", ""))
        if status == "ok":
            job["description"] = desc
            ok += 1
            print(f"    [{i+1}/{total}] ✓ {company} — {title}")
        elif status == "rate_limited":
            rate_limited += 1
            print(f"    [{i+1}/{total}] ⚠ Rate limited (gave up): {company} — {title}")
        elif status == "no_content":
            no_content += 1
            print(f"    [{i+1}/{total}] ~ No description found: {company} — {title}")
        elif status == "http_error":
            errors += 1
            print(f"    [{i+1}/{total}] ✗ HTTP error: {company} — {title}")
        else:
            errors += 1
            print(f"    [{i+1}/{total}] ✗ Error ({status}): {company} — {title}")
    print(f"  LinkedIn descriptions: {ok} fetched, {no_content} empty, "
          f"{rate_limited} rate limited, {errors} errors")


def search_linkedin():
    try:
        from bs4 import BeautifulSoup  # noqa - verify available
    except ImportError:
        print("LinkedIn: beautifulsoup4 not installed - skipping. Run: pip install beautifulsoup4 --break-system-packages")
        return []

    remote_queries = LI_REMOTE_QUERIES  # defined in config.py

    raleigh_queries = LI_RALEIGH_QUERIES  # defined in config.py

    jobs = []

    # Remote searches
    for q in remote_queries:
        time.sleep(1.5)
        results = _li_fetch(q, remote=True)
        jobs.extend(results)
        print(f"  LinkedIn remote ({q}): {len(results)} results")

    # Raleigh local searches - use a North Carolina geoId
    # geoId 103644278 = United States, but LinkedIn will filter by keyword location
    for q in raleigh_queries:
        time.sleep(1.5)
        results = _li_fetch(q, remote=False)
        # Filter to only NC results - "rtp" excluded (ambiguous with Real-Time Payments)
        # FIX: use RALEIGH_TERMS from config.py so local filter stays in sync
        filtered = [j for j in results if any(t in j.get("location", "").lower() for t in RALEIGH_TERMS)]
        jobs.extend(filtered)
        print(f"  LinkedIn Raleigh ({q}): {len(filtered)} results")

    return jobs

# ── SEARCH: HIMALAYAS ─────────────────────────────────────────────────────────

def search_himalayas():
    """
    Free public API - no key required. Max 20 results per request, paginated
    via offset. Searches product, business-analyst, and management categories.
    """
    queries = HIMALAYAS_QUERIES  # defined in config.py
    jobs = []
    base = "https://himalayas.app/jobs/api"
    seen_urls = set()

    for category, keyword in queries:
        for offset in [0, 20]:  # two pages max per query
            try:
                resp = requests.get(
                    base,
                    params={"limit": 20, "offset": offset, "categories": category, "q": keyword},
                    timeout=15,
                )
                if resp.status_code != 200:
                    break
                items = resp.json() if isinstance(resp.json(), list) else resp.json().get("jobs", [])
                if not items:
                    break
                for item in items:
                    title = item.get("title", "") or ""
                    # keyword filter - only keep relevant titles
                    if not any(w in title.lower() for w in [
                        "product manager", "product owner", "product lead",
                        "principal product", "vp product", "head of product",
                        "business analyst", "ba ", "product director",
                        "customer experience", "digital experience"
                    ]):
                        continue
                    url = item.get("applicationLink", "") or ""
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    sal_min = item.get("minSalary") or 0
                    sal_max = item.get("maxSalary") or 0
                    salary  = None
                    if sal_min and item.get("currency", "").upper() == "USD":
                        salary = f"${sal_min:,}-${sal_max:,}" if sal_max else f"${sal_min:,}+"
                    jobs.append({
                        "title":       title,
                        "company":     item.get("companyName", ""),
                        "location":    "Remote",
                        # FIX (see changelog): was using "excerpt" field (~200 char summary).
                    # Switched to "description" which contains the full HTML job posting.
                    # Falls back to "excerpt" if description is empty.
                    "description": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(item.get("description", "") or item.get("excerpt", "") or ""))).strip()[:5000],
                        "url":         url,
                        "salary":      salary,
                        "posted":      item.get("pubDate", ""),
                        "source":      "Himalayas",
                    })
                time.sleep(1)
                if len(items) < 20:
                    break   # fewer than a full page - no more results
            except Exception as e:
                print(f"  Himalayas error ({category}, offset={offset}): {e}")
                break

    print(f"  Himalayas: {len(jobs)} results")
    return jobs


# ── SEARCH: REMOTIVE ──────────────────────────────────────────────────────────

def search_remotive():
    """
    Free public API - no key required. Returns all active remote jobs for a
    given category in a single response. No pagination.
    Delayed ~24 hours vs real-time, which is fine for a daily digest.
    """
    queries = REMOTIVE_QUERIES  # defined in config.py
    jobs = []
    seen_urls = set()
    base = "https://remotive.com/api/remote-jobs"

    for params in queries:
        try:
            resp = requests.get(base, params=params, timeout=20)
            if resp.status_code != 200:
                print(f"  Remotive error ({params}): HTTP {resp.status_code}")
                continue
            items = resp.json().get("jobs", [])
            for item in items:
                url = item.get("url", "") or ""
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                # Candidate location filter - skip non-US-eligible
                location = (item.get("candidate_required_location") or "").lower()
                if location and not any(x in location for x in [
                    "worldwide", "anywhere", "usa", "us only", "united states",
                    "north america", "americas"
                    # Note: do NOT add "" here - "" in any string is always True
                ]):
                    continue
                # Title filter - only keep PM/PO/BA/CX roles
                # Remotive categories are broad (all "product" roles, all "management")
                # so we filter here to avoid sending designers/engineers to Claude.
                # Note: "senior pm" / "lead pm" intentionally not included since
                # "pm" alone is too ambiguous - these rarely appear without "product"
                job_title = item.get("title", "") or ""
                if not any(w in job_title.lower() for w in [
                    "product manager", "product owner", "product lead",
                    "principal product", "vp product", "head of product",
                    "business analyst", "product director", "avp product",
                    "customer experience manager", "customer experience owner",
                    "digital experience", "experience owner", "staff product",
                    "group product", "director of product", "head of customer experience",
                ]):
                    continue
                salary = item.get("salary") or None
                jobs.append({
                    "title":       job_title,
                    "company":     item.get("company_name", ""),
                    "location":    "Remote",
                    "description": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(item.get("description", "") or ""))).strip()[:5000],
                    "url":         url,
                    "salary":      salary,
                    "posted":      item.get("publication_date", ""),
                    "source":      "Remotive",
                })
            time.sleep(1.5)
        except Exception as e:
            print(f"  Remotive error ({params}): {e}")

    print(f"  Remotive: {len(jobs)} results")
    return jobs


# ── SEARCH: USAJOBS ───────────────────────────────────────────────────────────

def search_usajobs():
    """Free REST API. Requires USAJOBS_API_KEY and USAJOBS_EMAIL in .env."""
    if not USAJOBS_API_KEY or not USAJOBS_EMAIL:
        return []

    queries = USAJOBS_QUERIES  # defined in config.py
    jobs = []
    seen_ids = set()
    base = "https://data.usajobs.gov/api/Search"
    headers = {
        "Authorization-Key": USAJOBS_API_KEY,
        "User-Agent":        USAJOBS_EMAIL,
        "Host":              "data.usajobs.gov",
    }

    for keyword in queries:
        for page in [1, 2]:
            try:
                resp = requests.get(
                    base,
                    params={
                        "Keyword":        keyword,
                        "RemoteIndicator": "True",
                        "ResultsPerPage":  25,
                        "Page":            page,
                    },
                    headers=headers,
                    timeout=20,
                )
                if resp.status_code != 200:
                    print(f"  USAJobs error ({keyword} p{page}): HTTP {resp.status_code}")
                    break
                items = resp.json().get("SearchResult", {}).get("SearchResultItems", [])
                if not items:
                    break
                for item in items:
                    d   = item.get("MatchedObjectDescriptor", {})
                    uid = item.get("MatchedObjectId", "")
                    if uid in seen_ids:
                        continue
                    seen_ids.add(uid)
                    # Salary
                    sal_min = d.get("PositionRemuneration", [{}])[0].get("MinimumRange")
                    sal_max = d.get("PositionRemuneration", [{}])[0].get("MaximumRange")
                    salary  = None
                    if sal_min:
                        salary = f"${float(sal_min):,.0f}-${float(sal_max):,.0f}" if sal_max else f"${float(sal_min):,.0f}+"
                    url = (d.get("ApplyURI") or [""])[0]
                    jobs.append({
                        "title":       d.get("PositionTitle", ""),
                        "company":     d.get("OrganizationName", "") or d.get("DepartmentName", ""),
                        "location":    d.get("PositionLocationDisplay", "Remote"),
                        "description": d.get("UserArea", {}).get("Details", {}).get("JobSummary", ""),
                        "url":         url,
                        "salary":      salary,
                        "posted":      d.get("PublicationStartDate", ""),
                        "source":      "USAJobs",
                    })
                time.sleep(1)
                if len(items) < 25:
                    break   # fewer than a full page - no more results
            except Exception as e:
                print(f"  USAJobs error ({keyword} p{page}): {e}")
                break

    print(f"  USAJobs: {len(jobs)} results")
    return jobs



# ── SEARCH: ATS DIRECT (Greenhouse / Lever / Ashby) ──────────────────────────

def search_ats_companies():
    """
    Queries Greenhouse, Lever, and Ashby career APIs directly for ~250 US
    fintech and banking companies. All three APIs are fully public - no key
    needed. 404 means the company does not use that ATS; silently skip.
    Covers: consumer banking, payments, lending, B2B banking, embedded
    finance, infrastructure/API, insurance, wealth, regtech, banking tech.
    """

    # ── Company slugs to try ──────────────────────────────────────────────────
    # Slugs are the URL identifier each company uses on their ATS.
    # Usually matches the company name; mismatches are silently skipped.
    COMPANIES = [
        # ── Consumer / neobanks ───────────────────────────────────────────────
        "dave", "varomoney",
        "nubank",  # Brazilian neobank; Greenhouse confirmed; has US remote + Miami roles
        "cleo", "brigit",
        "found", "relay",
        "tilthq",  # Tilt credit-building app; Ashby confirmed
        "greenlight", "gohenry",
        "daylight",
            "chime",
        # ── Payments ─────────────────────────────────────────────────────────
        "stripe", "marqeta", "lithic", "highnote",
        "dwolla",
        "trustly", "finix", "spreedly", "truv", "versapay",  # Open Banking payments; Lever confirmed
        "anchorage",       # Anchorage Digital - crypto custody; Lever confirmed (most roles will be Skipped)
        "payoneer", "moderntreasury",
         # Global payments platform; Greenhouse confirmed
        "adyen",  # Dutch payments platform; all PM roles on-site (Chicago/SF) - location filter catches
        # ── B2B banking / business banking ───────────────────────────────────
        "mercury", "novo", "bluevineus",         "spendesk", "pleo",
        "melio",   # B2B payments; Greenhouse slug; all roles Tel Aviv on-site - non-US filter catches
        "emburse", "zipcolimited",
        "ramp",  # corporate cards; Ashby slug; all PM roles NYC on-site - location filter catches
        "brex",  # corporate cards; Greenhouse slug; all PM roles NYC/SF on-site
        "sofi",  # neobank; Greenhouse slug; all PM roles SF/Seattle on-site
        # ── Lending / BNPL ────────────────────────────────────────────────────
        "monzo",  # UK digital bank; Greenhouse confirmed; has Remote (US) + NY roles
        "upstart", "amount", "prosper",
        "earnest", "upgrade",
        "ondeck", "oportun", "kapitus", "BestEgg",
        "sezzle", "affirm",
        "kikoff",  # credit-builder; Greenhouse slug; SF on-site
        "wisetack", "opploans",
                # ── Mortgage / real estate finance ───────────────────────────────────
        "blend", "better", "figure", "roofstock",
        "point",
        "ownup",
        # ── Banking infrastructure / embedded finance ─────────────────────────
        "plaid", "mxtechnologiesinc", "galileo", "galileofinancialtechnologies", "unit", "synctera", "treasuryprime",
        "column", "alloy", "sardine", "orum",
        "socure", "stytch", "persona", "jumio", "idme", "incode",         "prove", "entersekt",  # Identity/phone verification; Greenhouse confirmed
        "middesk", "parafin",
        "capchase", "clearco",
        "drivewealth",         "leadbank",
        "pathward",  # banking-as-a-service; Greenhouse slug; all posted roles below $150K
        "checkr",  # background checks; Greenhouse slug; all PM roles Denver/SF on-site
        "lendingtree",  # fintech marketplace; Greenhouse slug; all roles Seattle/Denver on-site
        "whoop",  # wearables; Lever slug; all PM roles Boston on-site
        "alt",  # collectibles fintech; Greenhouse slug; all roles crypto/digital assets
        "oneapp",  # OnePay (Walmart); Ashby slug; all roles crypto or cash advance
        # ── Wealth / investing ────────────────────────────────────────────────
        "betterment", "wealthfront", "acorns",
        "stash",         "tastytrade",
        "robinhood",  # trading/banking; Greenhouse slug; all PM roles on-site
        "altruist",  # RIA platform; Greenhouse slug; all PM roles LA/Dallas on-site
        "alpaca",  # trading API; Greenhouse slug; all roles involve crypto/brokerage
        "paxos",  # crypto infra; Ashby slug; all roles are blockchain
        "securitize",  # blockchain securities; Greenhouse slug
        # ── Insurance (insurtech) ─────────────────────────────────────────────
        "root",
        "ethos", "kin", "branch",
        "openly", "sure",
        "embroker", "newfront",
        "counterpart", "atbayjobs", "federato", "sureify", "ethoslife",
        "lemonade",  # insurtech; Ashby slug; all PM roles TLV/EU on-site
        # ── Regtech / compliance / identity ───────────────────────────────────
        "complyadvantage",
        "employerdirecthealthcare",  # Healthcare benefits fintech; Greenhouse confirmed
        "sentilink",
        "codat",
        # ── Credit / data / scoring ───────────────────────────────────────────
        "array",
        "creditkarma", "nerdwallet", "bankrate",
                "truebill",  # Rocket Money / Truebill; Greenhouse confirmed
        # ── Banking technology vendors ────────────────────────────────────────
        "backbase",
        "thought-machine",
         # Alt investing platform; Greenhouse confirmed
        "engine",  # Business travel/fintech; Greenhouse confirmed
        "bankjoy",
        # ── Digital-forward banks ─────────────────────────────────────────────
        # ── Payroll / HR fintech ──────────────────────────────────────────────
        "gusto", "deel",  # HR/payroll platform; Ashby slug; all roles EMEA region - non-US filter catches
        "aledade", "redventures", "remote",
        "justworks",
        "trinet",
        # ── Earned wage access / pay on demand ───────────────────────────────
        "earnin", "dailypay", "payactiv",
        "rain", "clair",
        "tapcheck",
        # ── Other fintech ─────────────────────────────────────────────────────
        # ── Payments infrastructure (confirmed Greenhouse) ────────────────────
        "form3", "inkind", "laporteusa", "boulevard", "sparkadvisors", "deepintent", "modernhealth", "peakcreditunion", "myfundedfutures",  # real-time payments API provider; has US roles (Zelle, RTP, FedNow)
        "missionlane",  # consumer credit card fintech; Greenhouse confirmed; active PM roles
        # ── Consumer fintech / insurtech (confirmed Ashby) ────────────────────
         # OnePay (Walmart-backed consumer fintech); Ashby slug is 'oneapp'
        "Jerry.ai",  # Jerry insurtech/auto super app; Ashby slug is 'Jerry.ai' (case-sensitive)
        # ── Retail / consumer tech with financial products ────────────────────
        "stitchfix",  # Greenhouse confirmed; Sr PM Financial Systems role seen
        # ── Major US credit unions ────────────────────────────────────────────
        # ── NC / Raleigh-area banks and institutions ──────────────────────────
        # ── Additional confirmed slugs (added 2026-04-02) ────────────────────
        "quinstreet",     # QuinStreet — performance marketing fintech; Greenhouse confirmed
    ]

    # ── Title keywords for filtering ──────────────────────────────────────────
    TARGET_TITLES = [
        "product manager", "product owner", "product lead",
        "principal product", "vp product", "head of product",
        "business analyst", "product director", "avp product",
        "customer experience manager", "customer experience director",
        "digital experience", "experience owner",
        "director of product", "group product", "staff product",
        "technical product manager",
    ]

    # Titles that contain a TARGET_TITLE keyword but are actually wrong roles
    BLOCK_SUFFIXES = [
        "associate", "representative", "specialist", "rep",
        "support agent", "support rep",
    ]

    jobs      = []
    seen_urls = set()

    def _title_match(title):
        t = title.lower()
        if not any(kw in t for kw in TARGET_TITLES):
            return False
        # Block support/CS roles that sneak through via "customer experience"
        if any(t.endswith(sfx) or f" {sfx}," in t or f" {sfx} " in t
               for sfx in BLOCK_SUFFIXES):
            return False
        return True

    def _try_greenhouse(slug, seen_urls):
        try:
            r = requests.get(
                f"https://api.greenhouse.io/v1/boards/{slug}/jobs",
                params={"content": "true"}, timeout=10,
            )
            if r.status_code != 200:
                return []
            result = []
            # FIX (see changelog): Ashby API returns "jobs" key, NOT "jobPostings".
            # The wrong key caused all Ashby boards to silently return 0 results.
            for item in r.json().get("jobs", []):
                title = item.get("title", "")
                if not _title_match(title):
                    continue
                url = item.get("absolute_url", "") or ""
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                loc = item.get("location", {}).get("name", "") or ""
                result.append({
                    "title":       title,
                    "company":     ATS_NAME_OVERRIDES.get(slug, slug.replace("-", " ").title()),
                    "location":    loc,
                    "description": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(item.get("content", "") or ""))).strip()[:5000],
                    "url":         url,
                    "salary":      None,
                    "posted":      item.get("updated_at", ""),
                    "source":      "Greenhouse",
                })
            return result
        except Exception:
            return []

    def _try_lever(slug, seen_urls):
        try:
            r = requests.get(
                f"https://api.lever.co/v0/postings/{slug}",
                params={"mode": "json"}, timeout=8,
            )
            if r.status_code != 200:
                return []
            data = r.json()
            items = data if isinstance(data, list) else []
            result = []
            for item in items:
                title = item.get("text", "")
                if not _title_match(title):
                    continue
                url = item.get("hostedUrl", "") or ""
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                loc = (item.get("categories") or {}).get("location", "") or ""
                # FIX (see changelog): Lever splits the JD across 3 separate fields.
                # Before this fix, only descriptionPlain was used (~1,470 chars of
                # company boilerplate with zero requirements/qualifications). Claude
                # was rating jobs without seeing what the role actually requires.
                #   descriptionPlain = company mission/intro paragraph
                #   additionalPlain  = "What you'll do" + requirements section
                #   lists[]          = bullet-point responsibility/qualification lists
                # Combined total: ~4,000-5,500 chars of full JD content.
                desc_parts = []
                intro = (item.get("descriptionPlain", "") or "").strip()
                if intro:
                    desc_parts.append(intro)
                additional = (item.get("additionalPlain", "") or "").strip()
                if additional:
                    desc_parts.append(additional)
                for lst in (item.get("lists") or []):
                    lst_text = (lst.get("content", "") or "").strip()
                    lst_text = re.sub(r"<[^>]+>", " ", lst_text)
                    lst_text = re.sub(r"\s+", " ", lst_text).strip()
                    if lst_text:
                        desc_parts.append(lst_text)
                full_desc = "\n\n".join(desc_parts)
                result.append({
                    "title":       title,
                    "company":     ATS_NAME_OVERRIDES.get(slug, slug.replace("-", " ").title()),
                    "location":    loc,
                    # FIX (see changelog): 6000 chars (up from 5000) because the
                    # combined Lever fields regularly reach 5,000-5,500 chars for
                    # real jobs. At 5000 we were cutting mid-requirements. GH and
                    # Ashby stay at 5000 - their content beyond that is benefits boilerplate.
                    "description": full_desc[:6000],
                    "url":         url,
                    "salary":      None,
                    "posted":      "",
                    "source":      "Lever",
                })
            return result
        except Exception:
            return []

    def _try_ashby(slug, seen_urls):
        try:
            r = requests.get(
                f"https://api.ashbyhq.com/posting-api/job-board/{slug}",
                timeout=8,
            )
            if r.status_code != 200:
                return []
            result = []
            # FIX (see changelog): Ashby API returns "jobs" key, NOT "jobPostings".
            # The wrong key caused ALL Ashby companies to silently return 0 results.
            for item in r.json().get("jobs", []):
                title = item.get("title", "")
                if not _title_match(title):
                    continue
                url = item.get("jobUrl", "") or item.get("applyUrl", "") or ""
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                loc = item.get("location", "") or ""
                result.append({
                    "title":       title,
                    "company":     ATS_NAME_OVERRIDES.get(slug, slug.replace("-", " ").title()),
                    "location":    loc,
                    # FIX (see changelog): descriptionHtml requires same unescape-first
                    # pipeline as Greenhouse. Also: Ashby has no separate "additional"
                    # or "lists" fields - the full JD is in descriptionHtml.
                    "description": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(item.get("descriptionHtml", "") or ""))).strip()[:5000],
                    "url":         url,
                    "salary":      None,
                    "posted":      item.get("publishedDate", ""),
                    "source":      "Ashby",
                })
            return result
        except Exception:
            return []


    total      = len(COMPANIES)
    print(f"  ATS: checking {total} companies across Greenhouse / Lever / Ashby...")

    # FIX (race condition): original design passed a shared seen_urls set into all
    # three _try_* functions and mutated it from 10 concurrent threads. CPython's GIL
    # makes individual set.add() safe but the check-then-add compound op is NOT atomic,
    # allowing two threads to pass the `if url in seen_urls` check before either adds.
    # Fix: each slug collects its own results independently; dedup happens after joining.
    _ats_lock = threading.Lock()

    def _check_slug(slug):
        slug_seen: set[str] = set()   # thread-local, no sharing
        found  = _try_greenhouse(slug, slug_seen)
        found += _try_lever(slug, slug_seen)
        found += _try_ashby(slug, slug_seen)
        return slug, found

    total_hits = 0
    completed  = 0
    all_found: list[dict] = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_check_slug, slug): slug for slug in COMPANIES}
        for future in as_completed(futures):
            slug, found = future.result()
            completed += 1
            if found:
                total_hits += 1
                with _ats_lock:
                    all_found.extend(found)
                titles = ", ".join(j["title"] for j in found[:2])
                with _print_lock:
                    print(f"    ✓ {slug} ({len(found)} match{'es' if len(found)>1 else ''}): {titles}")
            if completed % 50 == 0:
                with _print_lock:
                    print(f"  ATS: {completed}/{total} checked — {len(all_found)} matches so far")

    # Dedup across slugs after joining (a company on multiple ATSes could return the same URL)
    seen_urls: set[str] = set()
    for j in all_found:
        url = j.get("url", "")
        if url not in seen_urls:
            seen_urls.add(url)
            jobs.append(j)

    print(f"  ATS direct: {len(jobs)} results from {total_hits}/{total} companies")
    return jobs



# ── SEARCH: UKG / ULTIPRO ─────────────────────────────────────────────────────

# Known UltiPro company codes for fintech/banking/insurance companies.
# Format: { "CompanyCode/BoardGuid": "Display Name" }
# URL pattern: https://recruiting.ultipro.com/{CODE}/JobBoard/{GUID}/
# API pattern: https://recruiting.ultipro.com/{CODE}/JobBoard/{GUID}/api/rest/jobboard/v1/list
#
# To add a new company: find the URL of any job posting, extract the code and GUID.
# Example: recruiting.ultipro.com/CHE1007CHEV/JobBoard/604b85b9-c229-47a8-8319-5b9130e7bd81/
#   → code = "CHE1007CHEV", guid = "604b85b9-c229-47a8-8319-5b9130e7bd81"
_ULTIPRO_COMPANIES = {
    # ── Originally confirmed from user job URLs ────────────────────────────────
    "CHE1007CHEV/604b85b9-c229-47a8-8319-5b9130e7bd81": "Chevron Federal Credit Union",
    "FIN1006FIOA/ea26052b-b8a2-489f-b1dc-3acc6bac391d": "FIOA Financial",
    # ── Added 2026-04-02 — confirmed active PM/PO roles and remote eligibility ─
    "UNI1046UFMB/d8f90aad-672e-4f0a-bbc1-a17aa8cf1111": "Atlantic Union Bank",
    # Atlantic Union Bank: $20B+ regional bank headquartered in VA; posts remote
    # digital PM/PO roles eligible in NC, VA, MD, PA, GA.
    # Confirmed: "Digital Product Manager" and "Digital Product Owner III" remote roles.
    "TEG1001TEGR/ad4204e8-c7f7-47f1-8177-c9f64730dccc": "InvestCloud",
    # InvestCloud: wealth management fintech platform; confirmed active PM role on
    # their UltiPro board as of 2026-04-02.
}

_ULTIPRO_SEARCH_URL = (
    "https://recruiting.ultipro.com/{code}/JobBoard/{guid}"
    "/JobBoardView/LoadSearchResults"
)
_ULTIPRO_DETAIL_URL = (
    "https://recruiting.ultipro.com/{code}/JobBoard/{guid}"
    "/OpportunityDetail?opportunityId={job_id}"
)
_ULTIPRO_HEADERS = {
    "Content-Type":    "application/json; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://recruiting.ultipro.com/",
}

def search_ultipro():
    """Search UKG/UltiPro ATS companies for PM/BA roles.

    UltiPro job boards use a POST endpoint (LoadSearchResults) that returns
    paginated JSON with an opportunities list and a totalCount field.
    Each company has a unique code + board GUID from their job URL.

    Correct endpoint (POST):
      /JobBoardView/LoadSearchResults
    NOT the v1 REST API (that requires tenant credentials).
    """
    jobs = []
    seen_ids = set()

    TARGET_TITLE_WORDS = [
        "product manager", "product owner", "product lead",
        "business analyst", "principal product", "staff product",
        "lead product", "digital product", "customer experience",
        "avp product", "vp product",
    ]
    SKIP_TITLE_WORDS = [
        "engineer", "developer", "designer", "marketing", "sales",
        "analyst intern", "associate product",
    ]

    base_payload = {
        "opportunitySearch": {
            "Top": 50,
            TIER_SKIP: 0,
            "QueryString": "",
            "OrderBy": [{"Value": "postedDateDesc", "PropertyName": "PostedDate", "Ascending": False}],
            "Filters": [
                {"t": "TermsSearchFilterDto", "fieldName": 4,  "extra": None, "values": []},
                {"t": "TermsSearchFilterDto", "fieldName": 5,  "extra": None, "values": []},
                {"t": "TermsSearchFilterDto", "fieldName": 6,  "extra": None, "values": []},
                {"t": "TermsSearchFilterDto", "fieldName": 37, "extra": None, "values": []},
            ],
        },
        "matchCriteria": {"PreferredJobs": [], "Education": [], "JobCategories": []},
        "cultureFit": {},
    }

    for code_guid, company_name in _ULTIPRO_COMPANIES.items():
        code, guid = code_guid.split("/", 1)
        url = _ULTIPRO_SEARCH_URL.format(code=code, guid=guid)
        skip = 0
        page_size = 50

        while True:
            # FIX (code review): {**base_payload} only shallow-copies the top level.
            # base_payload["opportunitySearch"] is a nested dict — mutations to it
            # (setting Skip/Top) would bleed back into base_payload on subsequent
            # iterations, causing pagination to start from the wrong offset for the
            # 2nd+ company. Use deepcopy to get a fully independent copy each time.
            payload = copy.deepcopy(base_payload)
            payload["opportunitySearch"][TIER_SKIP] = skip
            payload["opportunitySearch"]["Top"]  = page_size
            try:
                resp = requests.post(url, json=payload, headers=_ULTIPRO_HEADERS, timeout=15)
                if resp.status_code != 200:
                    print(f"  UltiPro error ({company_name}): HTTP {resp.status_code}")
                    break
                data = resp.json()
                opportunities = data.get("opportunities", [])
                total = data.get("totalCount", 0)
                if not opportunities:
                    break

                for item in opportunities:
                    job_id = item.get("opportunityId") or item.get("Id") or ""
                    title  = item.get("title") or item.get("Title") or ""
                    location = (
                        item.get("location") or
                        item.get("Location") or
                        item.get("city") or ""
                    )
                    desc = (
                        item.get("description") or
                        item.get("Description") or
                        item.get("shortDescription") or ""
                    )

                    if not title or job_id in seen_ids:
                        continue
                    seen_ids.add(job_id)

                    title_l = title.lower()
                    if not any(w in title_l for w in TARGET_TITLE_WORDS):
                        continue
                    if any(w in title_l for w in SKIP_TITLE_WORDS):
                        continue

                    if desc:
                        desc = re.sub(r"<[^>]+>", " ", html.unescape(str(desc)))
                        desc = re.sub(r"\s+", " ", desc).strip()[:5000]

                    job_url = _ULTIPRO_DETAIL_URL.format(code=code, guid=guid, job_id=job_id)

                    jobs.append({
                        "title":       title,
                        "company":     company_name,
                        "location":    str(location),
                        "description": desc,
                        "url":         job_url,
                        "salary":      None,
                        "source":      "UltiPro",
                    })

                skip += len(opportunities)
                if skip >= total:
                    break
                time.sleep(0.5)

            except Exception as e:
                print(f"  UltiPro error ({company_name}): {e}")
                break

    print(f"  UltiPro: {len(jobs)} results from {len(_ULTIPRO_COMPANIES)} companies")
    return jobs


def search_weworkremotely():
    feeds = [
        "https://weworkremotely.com/categories/remote-product-jobs.rss",
        "https://weworkremotely.com/categories/remote-management-jobs.rss",  # added: catches PM/PO roles under management category
    ]
    jobs = []
    for feed_url in feeds:
        try:
            r = requests.get(feed_url, timeout=10,
                             headers={"User-Agent": "Mozilla/5.0"})
            root = ET.fromstring(r.content)
            for item in root.findall(".//item"):
                title   = item.findtext("title", "").strip()
                link    = item.findtext("link", "").strip()
                desc    = item.findtext("description", "").strip()
                pubdate = item.findtext("pubDate", "").strip()
                # WWR titles come in multiple formats:
                #   "Company: Job Title"           → most common (e.g. "Equip Health: Product Manager II")
                #   "Job Title at Company"         → older format
                #   "Job Title"                    → fallback
                # The region XML tag also carries the company name and takes precedence.
                company = ""

                # Format 1: "Company: Job Title" — split on first colon
                if ": " in title and not title.startswith("http"):
                    prefix, rest = title.split(": ", 1)
                    # Only treat prefix as a company name if it's short (≤5 words)
                    # and doesn't look like a label ("Role:", "Note:", etc.)
                    _labels = {"role", "note", "update", "position", "job", "hiring", "new"}
                    if len(prefix.split()) <= 5 and prefix.lower() not in _labels:
                        company = prefix.strip()
                        title   = rest.strip()

                # Format 2: "Job Title at Company" — only if company not yet found
                if not company and " at " in title:
                    parts   = title.split(" at ")
                    title   = parts[0].strip()
                    company = parts[-1].strip()

                # Region tag takes precedence over both — it's the most reliable
                region = item.findtext("{https://weworkremotely.com}region", "").strip()
                if region:
                    company = region
                jobs.append({
                    "title":       title,
                    "company":     company,
                    "location":    "Remote",
                    "description": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(desc))).strip()[:5000],
                    "salary_min":  0,
                    "salary_max":  0,
                    "url":         link,
                    "posted":      pubdate[:16] if pubdate else "",
                    "source":      "WeWorkRemotely",
                })
        except Exception as e:
            print(f"  We Work Remotely error ({feed_url}): {e}")
    return jobs

# ── SEARCH: JOBICY ───────────────────────────────────────────────────────────

def search_jobicy():
    """
    Free public JSON API - no key required. US-filtered remote jobs.
    6-hour publish delay (fine for daily digest).
    Queries: management + product titles, accounting-finance, business,
             and direct fintech/banking keyword searches.
    Rate limit: no more than once per hour - daily run is well within limits.
    """
    queries = JOBICY_QUERIES  # defined in config.py
    jobs     = []
    seen_urls = set()
    base     = "https://jobicy.com/api/v2/remote-jobs"

    for params in queries:
        try:
            resp = requests.get(base, params=params, timeout=20)
            if resp.status_code != 200:
                print(f"  Jobicy error ({params.get('tag','?')}): HTTP {resp.status_code}")
                continue
            items = resp.json().get("jobs", [])
            for item in items:
                url = item.get("url", "") or ""
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                # Title filter - only keep relevant PM/PO/BA/CX roles
                title = item.get("jobTitle", "") or ""
                if not any(w in title.lower() for w in [
                    "product manager", "product owner", "product lead",
                    "principal product", "vp product", "head of product",
                    "business analyst", "product director", "avp product",
                    "customer experience", "digital experience", "experience owner",
                ]):
                    continue
                # Salary
                sal_min = item.get("annualSalaryMin") or 0
                sal_max = item.get("annualSalaryMax") or 0
                salary  = None
                if sal_min and str(item.get("salaryCurrency", "")).upper() == "USD":
                    try:
                        salary = f"${int(sal_min):,}-${int(sal_max):,}" if sal_max else f"${int(sal_min):,}+"
                    except (ValueError, TypeError):
                        salary = None
                jobs.append({
                    "title":       title,
                    "company":     item.get("companyName", ""),
                    "location":    "Remote",
                    "description": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(item.get("jobDescription", "") or ""))).strip()[:5000],
                    "url":         url,
                    "salary":      salary,
                    "posted":      item.get("pubDate", ""),
                    "source":      "Jobicy",
                })
            time.sleep(1.5)
        except Exception as e:
            print(f"  Jobicy error ({params.get('tag','?')}): {e}")

    print(f"  Jobicy: {len(jobs)} results")
    return jobs



# ── SEARCH: REMOTEOK ─────────────────────────────────────────────────────────

def search_remoteok():
    """
    Free public JSON API - no key required. Remote-only jobs.
    Returns all recent jobs; we filter by title match after fetching.
    API: https://remoteok.com/api (returns JSON array, first item is metadata)
    Rate limit: be polite - one call per run is fine.
    """
    jobs = []
    try:
        resp = requests.get(
            "https://remoteok.com/api",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=20,
        )
        if resp.status_code != 200:
            print(f"  RemoteOK error: HTTP {resp.status_code}")
            return []
        items = resp.json()
        seen_urls = set()
        for item in items:
            if not isinstance(item, dict) or "position" not in item:
                continue  # skip metadata entry (first item)
            title = item.get("position", "") or ""
            if not any(w in title.lower() for w in [
                "product manager", "product owner", "product lead",
                "principal product", "vp product", "head of product",
                "business analyst", "product director", "avp product",
                "customer experience manager", "customer experience director",
                "digital experience", "experience owner", "staff product",
            ]):
                continue
            url = item.get("url", "") or ""
            if not url:
                url = f"https://remoteok.com/l/{item.get('id', '')}"
            if url in seen_urls:
                continue
            seen_urls.add(url)
            # Salary - RemoteOK returns annual figures when available
            sal_min = item.get("salary_min") or 0
            sal_max = item.get("salary_max") or 0
            salary = None
            if sal_min:
                try:
                    salary = f"${int(sal_min):,}-${int(sal_max):,}" if sal_max else f"${int(sal_min):,}+"
                except (ValueError, TypeError):
                    salary = None
            desc = item.get("description", "") or ""
            desc = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(desc))).strip()
            jobs.append({
                "title":       title,
                "company":     item.get("company", "") or "",
                "location":    "Remote",
                "description": desc[:5000],
                "url":         url,
                "salary":      salary,
                "posted":      (item.get("date", "") or "")[:10],
                "source":      "RemoteOK",
            })
    except Exception as e:
        print(f"  RemoteOK error: {e}")
    print(f"  RemoteOK: {len(jobs)} results")
    return jobs


# ── COMPANY SIGNAL LAYER ──────────────────────────────────────────────────────
# Uses Wikipedia's free REST API (no key required) to fetch a one-sentence
# company description. Results cached locally - each company is only looked
# up once. Falls back gracefully to empty string for unknown/new companies.

def _load_company_cache():
    if os.path.exists(COMPANY_CACHE_FILE):
        try:
            with open(COMPANY_CACHE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_company_cache(cache):
    """Atomically writes the company cache to disk (tmp file + rename)."""
    os.makedirs(os.path.dirname(COMPANY_CACHE_FILE), exist_ok=True)
    tmp = COMPANY_CACHE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cache, f, indent=2)
    os.replace(tmp, COMPANY_CACHE_FILE)

# FIX (code review): Previously _save_company_cache() was called after every single
# lookup, causing one disk write per company during parallel rating (up to 50+/run).
# Instead, accumulate writes in memory and flush once after the rating pass completes.
_company_cache_dirty = False  # True when in-memory cache has unsaved changes

def _flush_company_cache():
    """Write the company cache to disk if any new entries were added this run.
    Called once after all rating is complete rather than after every lookup.
    """
    global _company_cache_dirty
    if not _company_cache_dirty:
        return
    with _company_cache_lock:
        _save_company_cache(_company_cache)
        _company_cache_dirty = False

_company_cache      = _load_company_cache()
_company_cache_lock = threading.Lock()  # protects _company_cache from concurrent writes by rating threads
_print_lock         = threading.Lock()   # prevents interleaved console output from parallel rating workers

def get_company_signal(company_name):
    """
    Returns a one-sentence description of the company from Wikipedia.
    Cached locally in .company_cache.json - never re-fetches a known company.
    Thread-safe: uses a lock to prevent duplicate Wikipedia calls from parallel rating workers.
    Returns empty string if company not found or on any error.
    """
    if not company_name or not company_name.strip():
        return ""
    key = company_name.strip().lower()

    # Check cache under lock first
    with _company_cache_lock:
        if key in _company_cache:
            return _company_cache[key]

    # FIX (code review): TOCTOU race — two threads can both see a cache miss
    # and both fetch Wikipedia for the same company. Fix: claim the cache entry
    # under lock with a sentinel before releasing, so other threads see it as
    # already cached and skip the duplicate fetch.
    with _company_cache_lock:
        if key in _company_cache:          # re-check after acquiring lock
            return _company_cache[key]
        _company_cache[key] = ""           # sentinel: blocks other threads from fetching
        _company_cache_dirty = True

    # Fetch from Wikipedia outside the lock (I/O should not block other threads)
    try:
        resp = requests.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(company_name.strip())}",
            headers={"User-Agent": "JobRadar/1.0 (personal job search tool)"},
            timeout=6,
        )
        if resp.status_code == 200:
            data = resp.json()
            extract = data.get("extract", "")
            if extract:
                # Reject disambiguation pages - they contain "may refer to" and are not useful
                if "may refer to" in extract.lower() or extract.strip().endswith(":"):
                    return ""  # sentinel already set to "" under lock above
                # Reject results where the company name does not appear anywhere
                # (catches wrong Wikipedia matches like "oracle" -> mythology)
                if key not in extract.lower() and key.split()[0] not in extract.lower():
                    return ""  # sentinel already set to "" under lock above
                # Trim to first 2 sentences max
                sentences = extract.split(". ")
                signal = ". ".join(sentences[:2]).strip()
                if not signal.endswith("."):
                    signal += "."
                with _company_cache_lock:
                    # Update from sentinel "" to the real signal value
                    _company_cache[key] = signal
                    # dirty flag already set when sentinel was placed; no change needed
                return signal
        # 404 or other non-200 - company not on Wikipedia (common for startups), cache as empty
        # sentinel already set to "" above; no additional write needed for 404
    except Exception:
        # Network error — leave sentinel in cache (returns "" which is safe).
        # The sentinel prevents infinite retries within the same run, and the
        # dirty flag ensures the empty entry is persisted for future runs.
        pass
    return ""


# FIX (see changelog): Old regex grabbed financial metrics from descriptions
# ("processing $257B annually", "$100M ARR", "$11.2B valuation") and passed
# them to Claude as salary hints. New approach: require salary context words
# (salary, pay, compensation, etc.) within 80 chars of any dollar figure, OR
# the number must be in a plausible annual salary range ($40K-$500K).
_SALARY_CONTEXT_RE = re.compile(
    r'(salary|compensation|base pay|total pay|pay range|annual pay|base salary'
    r'|earn|total comp|tc|starting at|up to|range of)'
    r'[^$]{0,80}\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[kK]?'
    r'|\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[kK]?[^$\w]{0,5}'
    r'(?:[-to]+\s*\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[kK]?)?'
    r'[^\w]{0,30}(?:per year|annually|\/yr|\/year|USD|usd)'
    r'|\b(\d{1,3}(?:,\d{3})+)\s*(?:[-to]+\s*(\d{1,3}(?:,\d{3})+))?'
    r'\s*(?:per year|annually|\/yr|\/year)',
    re.IGNORECASE,
)

def _is_plausible_salary(raw_str):
    """Return True only if the dollar amount looks like an annual salary (not a valuation/ARR)."""
    # Extract the numeric value
    nums = re.findall(r'[\d,]+', raw_str.replace('$', ''))
    if not nums:
        return False
    try:
        val = int(nums[0].replace(',', ''))
        if 'k' in raw_str.lower():
            val *= 1000
    except ValueError:
        return False
    # Plausible annual salary: $40K-$500K. Anything else is a company metric.
    return 40000 <= val <= 500000

def extract_salary_from_text(text):
    """Scan full description text for a salary range and return as readable string.
    
    FIX (see changelog): Requires salary context words OR explicit annual qualifier
    to avoid picking up financial metrics like "$257B ARR" or "$100M raised".
    Also validates the dollar amount is in a plausible annual salary range.
    """
    for m in _SALARY_CONTEXT_RE.finditer(text):
        raw = m.group(0).strip()
        # Skip years and zip codes
        if re.fullmatch(r'\d{4,5}', raw.replace(',', '').replace('$', '').strip()):
            continue
        if _is_plausible_salary(raw):
            return raw
    return None

def rate_job(job):
    full_desc = job.get("description", "")
    pre_salary = extract_salary_from_text(full_desc)
    salary_hint = f"\nSalary found in description: {pre_salary}" if pre_salary else ""

    company_signal = get_company_signal(job.get("company", ""))
    company_hint = f"\nCompany context (from Wikipedia): {company_signal}" if company_signal else ""

    # NOTE: description capped at 6000 chars - Lever combined fields reach 5000-5500
    # chars; extra 1000 ensures requirements section is never cut mid-sentence.
    prompt = f"""You are a job search assistant. Rate this job posting for the candidate below.

CANDIDATE PROFILE:
{PROFILE}

JOB POSTING:
Title: {job.get('title', '(no title)')}
Company: {job.get('company', '(unknown)')}{company_hint}
Location: {job.get('location', '')}
Description: {full_desc[:6000]}{salary_hint}

Return ONLY a JSON object with exactly these three fields:
  "tier": one of exactly these four strings: "Perfect Fit", "Good Fit", "Worth a Look", "Skip"
  "reason": one sentence explaining the rating (mention the key match or the key gap)
  "salary": the salary range exactly as stated in the description (e.g. "$150,000-$180,000", "$160K", "up to $175K") - use null if no salary is mentioned anywhere in the description

Tier guide:
"Perfect Fit"  = 90-100% match. PM, PO, or BA role in digital banking, fintech, consumer-facing banking, payments, onboarding, authentication, or anything closely resembling the candidate's core experience. Right seniority, right domain, no hard disqualifiers.
"Good Fit"     = 70-90% match. Same strong PM/PO/BA skills but different domain (insurance, healthcare, SaaS, retail) OR minor differences in seniority or scope. Still a strong candidate - just needs to pitch the domain transfer.
"Worth a Look" = 60-70% match. Title fits and the candidate meets some or most of the skills, but it may be a stretch - different industry, slightly off seniority, or requires pitching the skillset differently. Worth applying if the role is interesting.
"Skip"         = Anything else. No realistic chance, or a hard disqualifier is present. Rate as Skip ONLY if one of these is confirmed:
  - Managing direct reports - ONLY if the description explicitly requires prior people management experience as a must-have. Leading or coordinating a cross-functional team without direct reports is NOT a disqualifier.
  - On-site or hybrid with required office attendance OUTSIDE the candidate's target metro area. Read carefully - if the description says "hybrid" or "in-person" or "on-site" and the location is NOT in the target metro area, Skip it. But if the description says "remote" as the primary arrangement and mentions in-person as optional or occasional, do NOT skip it. The key question is: would the candidate be required to physically commute to an office outside their target area? IMPORTANT: If the word "Remote" appears in the job TITLE itself (e.g., "Senior PM (Remote)", "Remote - Senior PM"), treat the role as remote regardless of what the Location field shows. Job boards like Adzuna often populate Location with the company's registered office address even for fully remote roles.
  - Staffing agency or contract-to-hire placement. Skip any role posted by a recruiting or staffing firm (Kforce, CyberCoders, Avenue Code, 1872 Consulting, Robert Half, Insight Global, Randstad, TEKsystems, etc.) OR any role explicitly described as contract, temp, or C2H regardless of who posts it.
  - Credit risk, underwriting, or loan origination as the PRIMARY function. IMPORTANT: "Servicing" and "collections" after origination (account management, payment plans, customer support for existing accounts) are NOT the same as origination or underwriting. Post-origination servicing is a valid target - do NOT skip it. Only skip if the role is about evaluating creditworthiness, approving loans, or originating new credit.
  - Compensation range is entirely below $150K (i.e. the TOP of the posted range is below $150K). A range like $140K-$180K or $120K-$155K should NOT be skipped - $150K falls within both those ranges. Only skip if the maximum listed salary is confirmed below $150K.
  - Crypto, blockchain, or web3 as core product focus
  - AI product building as the PRIMARY function. Skip if: the company's core product IS an AI platform/tool, or the role's primary focus is owning/building AI features, AI roadmap, or AI-powered products. Examples of Skip: "own our AI assistant roadmap", "build LLM-powered features", "lead AI product strategy for our platform", "PM for our machine learning products", company whose primary product is an AI tool or AI networking platform. Do NOT skip if: AI is mentioned only as a tool the team uses internally, or the role is a standard PM role at a company that happens to use AI.
  - Non-US remote role - if a company is headquartered outside the US and the description does not explicitly state the role is open to US-based remote candidates, Skip it. European, Baltic, and UK banks hiring remotely are typically hiring within their own region.

IMPORTANT RATING NOTES:
- Authentication, MFA, OTP, identity management, and consumer portal experience are CORE strengths, not just adjacent skills. Roles requiring IAM, authentication platform ownership, login/onboarding flows, or portal experience should be rated Perfect Fit or Good Fit, not downgraded.
- If a JD lists a specific platform (Symitar, Salesforce, nCino, Jack Henry, etc.) as required - not preferred - and there is no evidence the candidate has used it, that is a hard requirement gap. Rate it Worth a Look or Skip depending on how central the platform is, not Perfect Fit or Good Fit.
- If the PROFILE lists specific target companies, roles at those companies in product management, portal experience, or digital banking should be rated at least Good Fit unless a confirmed hard disqualifier is present.

CRITICAL RATING RULES - these override everything else:
1. Missing salary is NEVER a reason to Skip or downgrade. Rate on title and domain fit. The candidate will look up salary themselves.
2. Missing location or unclear remote status is NEVER a reason to Skip or downgrade. Rate on title and domain fit alone.
3. An incomplete or short job description is NEVER a reason to Skip. If the title fits and there are no confirmed hard disqualifiers, rate it Worth a Look or higher.
4. "Cannot assess" or "impossible to evaluate" are NOT valid reasons to Skip. When in doubt, rate Worth a Look so the candidate can decide.
5. Only Skip when you can CONFIRM a hard disqualifier is present - not when you merely suspect one might exist.
6. CONSISTENCY RULE: If your reason sentence identifies a confirmed hard disqualifier (on-site outside target metro, explicit people management required, crypto/blockchain, salary below floor, AI product building as primary, non-US location), your tier MUST be "Skip". Never return "Worth a Look" or "Good Fit" in the same response where you have confirmed a hard disqualifier. The reason and tier must agree.

JSON only. No other text."""

    # FIX (see changelog): Original code called Claude once and returned "Worth a Look"
    # on any rate_limit_error - no retry. With 5 parallel workers and long descriptions,
    # rate limits fired constantly and ~60% of jobs got fake "Rating unavailable" scores.
    # Now: exponential backoff retry (15s -> 30s -> 60s -> 120s). Workers that hit the
    # limit wait their turn rather than immediately giving up.
    max_retries = CLAUDE_MAX_RETRIES
    for attempt in range(max_retries):
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key":         ANTHROPIC_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type":      "application/json",
                },
                json={
                    "model":      "claude-haiku-4-5-20251001",
                    "max_tokens": CLAUDE_MAX_TOKENS,  # 250 was too tight; long reason+salary can hit ~295 chars and truncate mid-JSON
                    "messages":   [{"role": "user", "content": prompt}],
                },
                timeout=CLAUDE_TIMEOUT_SECS,
            )
            resp_json = r.json()
            # Handle API-level errors (rate limits, overload, etc.)
            if "error" in resp_json:
                err_type = resp_json["error"].get("type", "unknown")
                err_msg  = resp_json["error"].get("message", "")
                if err_type in ("overloaded_error", "rate_limit_error"):
                    wait = 15 * (2 ** attempt)  # 15s, 30s, 60s, 120s
                    with _print_lock:
                        print(f"  Rate limit hit (attempt {attempt+1}/{max_retries}) - waiting {wait}s...")
                    time.sleep(wait)
                    continue  # retry
                with _print_lock:
                    print(f"Claude API error ({err_type}): {err_msg}")
                return DEFAULT_TIER, "Rating unavailable", None
            if "content" not in resp_json:
                with _print_lock:
                    print(f"Claude unexpected response: {resp_json}")
                return DEFAULT_TIER, "Rating unavailable", None
            text = resp_json["content"][0]["text"].strip()
            text = text.replace("```json", "").replace("```", "").strip()
            result = json.loads(text)
            tier = result.get("tier", DEFAULT_TIER)
            if tier not in (TIER_PERFECT, TIER_GOOD, TIER_LOOK, TIER_SKIP):
                tier = DEFAULT_TIER
            # FIX (see changelog): Validate Claude's salary extraction before returning.
            # Claude sometimes grabs company metrics ("$257B ARR", "$100M raised") as salary.
            # Run the same plausibility check we use on our own regex extraction.
            # CODE REVIEW FIX: Claude sometimes returns company financial metrics as salary
            # (e.g. "processing $257B annually" -> "$257"). Run the same plausibility
            # check used on our own regex extraction before trusting Claude's value.
            raw_salary = result.get("salary") or None
            if raw_salary and not _is_plausible_salary(str(raw_salary)):
                raw_salary = None
            return tier, result.get("reason", ""), raw_salary
        except json.JSONDecodeError as e:
            # FIX (2026-03-18): was caught by broad Exception and returned immediately.
            # Claude can return malformed JSON transiently — retry with 5s delay.
            with _print_lock:
                print(f"  Claude JSON error (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5)
                continue
            return DEFAULT_TIER, "Rating unavailable", None
        except Exception as e:
            with _print_lock:
                print(f"Claude rating error: {e}")
            return DEFAULT_TIER, "Rating unavailable", None
    # All retries exhausted
    return DEFAULT_TIER, "Rating unavailable - rate limit retries exhausted", None

# ── TIER ORDER ────────────────────────────────────────────────────────────────

TIER_ORDER = {TIER_PERFECT: 0, TIER_GOOD:    1, TIER_LOOK:    2, TIER_SKIP:    3}
TIER_EMOJI = {
    TIER_PERFECT:  "⭐",
    TIER_GOOD:     "🟢",
    TIER_LOOK:     "🟡",
    TIER_SKIP:      "⛔",
}

# ── VACATION BUFFER ───────────────────────────────────────────────────────────

def load_buffer():
    """Loads the vacation job buffer from disk. Returns empty list if missing or corrupt."""
    if not os.path.exists(VACATION_BUFFER):
        return []
    try:
        with open(VACATION_BUFFER) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"  WARNING: vacation_buffer.json is corrupt ({e}) - buffer lost, starting fresh")
        return []

# Maximum jobs to hold in the vacation buffer. A 3-week vacation at 20 jobs/day
# = 420 buffered jobs which would produce an unreadably long digest email.
# FIX (code review): cap at 150 — keeps the best-rated jobs (buffer is sorted
# by tier in build_report_body so top results always make the cut).
_VACATION_BUFFER_MAX = 150

def save_buffer(jobs):
    """Atomically write the vacation buffer to disk.

    FIX (code review): caps at _VACATION_BUFFER_MAX entries so a long vacation
    does not produce an unreadably large digest email. Keeps the most recent jobs
    (newest at the end of the list) up to the cap.
    """
    if len(jobs) > _VACATION_BUFFER_MAX:
        # FIX (code review): sort by tier before truncating so highest-rated jobs
        # survive the cap rather than simply the most-recently-received ones.
        # An early Perfect Fit should not be displaced by later Skip-rated noise.
        _tier_rank = {TIER_PERFECT: 0, TIER_GOOD:    1, TIER_LOOK:    2, TIER_SKIP:    3}
        jobs.sort(key=lambda j: _tier_rank.get(j.get("tier", TIER_SKIP), 9))
        dropped = len(jobs) - _VACATION_BUFFER_MAX
        jobs = jobs[:_VACATION_BUFFER_MAX]
        print(f"  Vacation buffer capped at {_VACATION_BUFFER_MAX} jobs ({dropped} lowest-rated dropped)")
    os.makedirs(os.path.dirname(VACATION_BUFFER), exist_ok=True)
    tmp = VACATION_BUFFER + ".tmp"
    with open(tmp, "w") as f:
        json.dump(jobs, f, indent=2)
    os.replace(tmp, VACATION_BUFFER)

def clear_buffer():
    if os.path.exists(VACATION_BUFFER):
        os.remove(VACATION_BUFFER)

# ── LOCAL JOB DETECTOR ───────────────────────────────────────────────────────

# RALEIGH_TERMS imported from config.py

def is_local_raleigh(job):
    """Returns True if the job appears to be on-site/hybrid in the Raleigh metro."""
    loc = job.get("location", "").lower()
    desc = job.get("description", "").lower()
    combined = loc + " " + desc[:500]  # check location + top of description
    has_raleigh = any(t in combined for t in RALEIGH_TERMS)
    # Don't flag pure remote jobs - a job can mention RTP in a description and still be remote
    is_remote = "remote" in loc or (not loc and "remote" in desc[:200])
    return has_raleigh and not is_remote

# ── EMAIL ─────────────────────────────────────────────────────────────────────

def build_report_body(all_jobs, title):
    """
    Builds the plain-text email body for the daily digest.

    Args:
        all_jobs: list of job dicts, each expected to have:
            tier, reason, title, company, location, description,
            salary_min, salary_max, salary_extracted, salary (string),
            url, posted, source
        title: the email subject line used as the first line of the body

    Returns:
        A plain-text string ready to send via send_email().

    Two rendering paths:
        - has actionable jobs -> full report with sections, job cards, filtered appendix
        - no actionable jobs  -> short "nothing today" message (handled in main(), not here)
    """
    actionable = [j for j in all_jobs if j.get("tier") in (TIER_PERFECT, TIER_GOOD, TIER_LOOK)]
    filtered   = [j for j in all_jobs if j.get("tier") == TIER_SKIP]

    # Split actionable into remote and local - compute once per job (not twice)
    _is_local = {id(j): is_local_raleigh(j) for j in actionable}
    local_jobs  = [j for j in actionable if _is_local[id(j)]]
    remote_jobs = [j for j in actionable if not _is_local[id(j)]]

    perfect_remote = sum(1 for j in remote_jobs if j["tier"] == TIER_PERFECT)
    good_remote    = sum(1 for j in remote_jobs if j["tier"] == TIER_GOOD)
    look_remote    = sum(1 for j in remote_jobs if j["tier"] == TIER_LOOK)
    perfect_local  = sum(1 for j in local_jobs  if j["tier"] == TIER_PERFECT)
    good_local     = sum(1 for j in local_jobs  if j["tier"] == TIER_GOOD)
    look_local     = sum(1 for j in local_jobs  if j["tier"] == TIER_LOOK)

    total_apply = perfect_remote + good_remote + perfect_local + good_local
    total_look  = look_remote + look_local

    lines = [title, ""]

    # ── Good morning greeting
    lines.append("─" * 50)
    if total_apply > 0:
        lines.append(f"Good morning! ☀️  You have {total_apply} job{'s' if total_apply != 1 else ''} worth applying for today"
                     + (f", plus {total_look} more worth a look." if total_look > 0 else "."))
    elif total_look > 0:
        lines.append(f"Good morning! ☀️  Nothing perfect today, but {total_look} job{'s' if total_look != 1 else ''} worth a look.")
    else:
        lines.append("Good morning! ☀️  Quiet day - nothing new worth your time today. Check back tomorrow.")
    lines.append("")

    # ── Motivational quote
    lines.append(f'"{random.choice(QUOTES)}"')
    lines.append("")
    lines.append("─" * 50)
    lines.append("")

    # ── Counts summary
    lines.append(f"Remote - ⭐ {perfect_remote} Perfect Fit  |  🟢 {good_remote} Good Fit  |  🟡 {look_remote} Worth a Look")
    if local_jobs:
        lines.append(f"Raleigh NC - ⭐ {perfect_local} Perfect Fit  |  🟢 {good_local} Good Fit  |  🟡 {look_local} Worth a Look")
    lines.append(f"{len(filtered)} filtered out")
    lines.append("")

    def render_job(job):
        emoji = TIER_EMOJI[job["tier"]]
        sal = ""
        # FIX (see changelog): salary_min must be > 30000 to be a real salary.
        # Some ATS responses return tiny values (e.g. salary_min=2 from a $2B ARR mention).
        if job.get("salary_min") and job["salary_min"] > 30000:
            sal = f"${job['salary_min']:,.0f}"
            if job.get("salary_max") and job["salary_max"] != job["salary_min"]:
                sal += f"-${job['salary_max']:,.0f}"
        if not sal and job.get("salary_extracted"):
            sal = job["salary_extracted"]
        posted = job.get("posted", "")
        out = []
        out.append(f"{emoji} {job['tier'].upper()}  {job['title']} - {job['company']} ({job['location']})")
        out.append(f"  {job['reason']}")
        # FIX (see changelog): description field may contain residual HTML entities
        # (&nbsp; &amp; etc.) that survived the ATS fetch pipeline. Strip them here
        # so the email body shows clean text rather than raw entities.
        desc = html.unescape(job.get("description", "") or "").strip().replace("\n", " ")
        desc = re.sub(r"&[a-z]+;|&#\d+;", " ", desc)  # belt-and-suspenders entity strip
        desc = re.sub(r"\s+", " ", desc).strip()
        if desc:
            snippet = desc[:200] + ("..." if len(desc) > 200 else "")
            out.append(f"  {snippet}")
        meta = [f"Salary: {sal if sal else 'Not listed'}"]
        if posted:
            meta.append(f"Posted: {posted}")
        meta.append(f"Source: {job['source']}")
        out.append("  " + "  |  ".join(meta))
        out.append(f"  {job['url']}")
        out.append("")
        return out

    # ── Remote jobs section
    if remote_jobs:
        lines.append("─" * 50)
        lines.append("🌐 REMOTE JOBS")
        lines.append("─" * 50)
        lines.append("")
        for job in sorted(remote_jobs, key=lambda x: TIER_ORDER[x["tier"]]):
            lines.extend(render_job(job))
    else:
        lines.append("No remote Perfect Fit, Good Fit, or Worth a Look jobs today.")
        lines.append("")

    # ── Raleigh NC local jobs section
    if local_jobs:
        lines.append("─" * 50)
        lines.append("📍 RALEIGH NC - LOCAL / HYBRID")
        lines.append("─" * 50)
        lines.append("")
        for job in sorted(local_jobs, key=lambda x: TIER_ORDER[x["tier"]]):
            lines.extend(render_job(job))

    # ── Filtered appendix
    if filtered:
        lines.append("─" * 50)
        lines.append("FILTERED OUT - review if anything looks wrong")
        lines.append("")
        for job in sorted(filtered, key=lambda x: TIER_ORDER[x["tier"]]):
            emoji = TIER_EMOJI[job["tier"]]
            lines.append(f"{emoji} {job['tier'].upper()}  {job['title']} - {job['company']} ({job['location']})")
            lines.append(f"  {job['reason']}")
            lines.append(f"  {job['url']}")
            lines.append("")

    return "\n".join(lines)

def send_email(subject, body, attachment_path=None):
    """Sends a plain-text email to EMAIL via Gmail SMTP SSL.
    Optionally attaches a file (used to send the daily .md report as an attachment).

    FIX (code review): wrapped in try/except so SMTP failures (rate limits,
    network drop, bad credentials) are logged clearly rather than raising an
    unhandled exception that would silently skip save_seen() in the caller.
    Re-raises after printing so main() knows the send failed.
    """
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"]    = EMAIL
    msg["To"]      = EMAIL
    msg.set_content(body)
    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="text", subtype="markdown",
                filename=os.path.basename(attachment_path),
            )
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(EMAIL, GMAIL_APP_PW)
            s.send_message(msg)
        print(f"Email sent: {subject}")
    except Exception as e:
        print(f"  ERROR: Email failed to send ({e}). Check GMAIL_ADDRESS and GMAIL_APP_PW in .env.")
        raise  # re-raise so caller knows the send failed and can handle save_seen accordingly

# ── MAIN ──────────────────────────────────────────────────────────────────────


def _dashboard_job_key(j):
    """Stable dedup key for dashboard files — company + normalised title.
    Defined at module level so both write functions use identical logic.

    NOTE: must stay in sync with make_job_id() in dashboard.py.
    Uses normalize_title() (same function as dedup_keys) so the key written
    to *-jobs.json matches what the dashboard reads back. Divergence here
    causes the same job to appear as two separate cards when one entry has
    a location suffix and the other doesn't.
    """
    company = (j.get("company") or "").lower().strip()
    title   = normalize_title(j.get("title") or "")
    return f"{company}|{title}"


def write_daily_jobs_json(all_jobs, today, run_time=None):
    """Write actionable jobs to a dated JSON file for the dashboard Kanban board.

    Only Perfect Fit / Good Fit / Worth a Look jobs are written. The dashboard
    reads all *-jobs.json files and merges them so each day accumulates naturally.

    If today's file already exists, existing jobs are preserved and new ones
    are merged in — the file is never overwritten with fewer jobs than it has.
    """
    actionable = [
        j for j in all_jobs
        if j.get("tier") in (TIER_PERFECT, TIER_GOOD, TIER_LOOK)
    ]
    # Timestamp naming: one file per run so multiple daily runs all appear in dashboard
    # run_time is always supplied from main() so both output files share the
    # exact same timestamp and are visually paired in the output directory.
    if run_time is None:
        raise ValueError("run_time must be supplied — pass datetime.now() from main()")
    timestamp = run_time.strftime("%Y-%m-%d-%H%M%S")
    path = os.path.join(_OUTPUT_DIR, f"{timestamp}-jobs.json")
    # FIX (code review): use run_time (not datetime.now()) so run_date matches
    # the filename timestamp even if the run spans midnight.
    run_date = run_time.strftime("%Y-%m-%d")
    serialisable = []
    for j in actionable:
        serialisable.append({
            "title":            j.get("title", ""),
            "company":          j.get("company", ""),
            "location":         j.get("location", ""),
            "url":              j.get("url", ""),
            "source":           j.get("source", ""),
            "tier":             j.get("tier", ""),
            "reason":           j.get("reason", ""),
            "salary_min":       j.get("salary_min", 0),
            "salary_max":       j.get("salary_max", 0),
            "salary_extracted": j.get("salary_extracted") or j.get("salary") or "",
            "description":      (j.get("description") or "")[:2000],
            "date_found":       run_date,
        })

    try:
        os.makedirs(_OUTPUT_DIR, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(serialisable, f, indent=2)
        os.replace(tmp, path)
        print(f"  Dashboard jobs: {os.path.basename(path)} ({len(serialisable)} jobs)")
    except Exception as e:
        print(f"  Warning: could not write dashboard jobs: {e}")


def write_daily_skipped_json(all_jobs, today, run_time=None):
    """Write skipped jobs to a dated JSON file for the dashboard Skipped tab.

    Merges with any existing skipped file for today so multiple runs don't
    overwrite earlier results.
    """
    skipped = [j for j in all_jobs if j.get("tier") == TIER_SKIP]
    if run_time is None:
        raise ValueError("run_time must be supplied — pass datetime.now() from main()")
    timestamp = run_time.strftime("%Y-%m-%d-%H%M%S")
    path = os.path.join(_OUTPUT_DIR, f"{timestamp}-skipped.json")

    if not skipped:
        return

    # FIX (code review): use run_time consistently — same fix as write_daily_jobs_json.
    run_date = run_time.strftime("%Y-%m-%d")
    serialisable = []
    for j in skipped:
        serialisable.append({
            "title":      j.get("title", ""),
            "company":    j.get("company", ""),
            "location":   j.get("location", ""),
            "url":        j.get("url", ""),
            "source":     j.get("source", ""),
            "tier":       TIER_SKIP,
            "reason":     j.get("reason", ""),
            "date_found": run_date,
        })

    try:
        os.makedirs(_OUTPUT_DIR, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(serialisable, f, indent=2)
        os.replace(tmp, path)
        print(f"  Dashboard skipped: {os.path.basename(path)} ({len(serialisable)} jobs)")
    except Exception as e:
        print(f"  Warning: could not write skipped jobs: {e}")


def write_debug_log(all_jobs, raw_counts, run_time=None):
    """
    Writes a full plain-text log of every job collected today - title, company,
    source, URL, rating, reason, salary, and the FULL description as fed to
    Claude. Overwrites the previous day's log on every run.

    FIX: accepts run_time so the header date matches the JSON output files.
    Avoids a midnight-crossing mismatch where jobs/skipped say "Apr 8" but
    the debug log header says "Apr 9".

    Upload debug_job_log.txt to Claude to verify description quality and
    confirm all sources are returning expected content.
    """
    if run_time is None:
        run_time = datetime.now()
    today = run_time.strftime("%Y-%m-%d")
    lines = []
    lines.append("=" * 80)
    lines.append(f"JOB RADAR DEBUG LOG - {today}")
    lines.append(f"Total jobs this run: {len(all_jobs)}")
    lines.append("Source counts:")
    for src, count in sorted(raw_counts.items()):
        lines.append(f"  {src:<20} {count} jobs")
    lines.append("=" * 80)

    # Group by tier for easy scanning
    tier_order = [TIER_PERFECT, TIER_GOOD, TIER_LOOK, TIER_SKIP]
    by_tier = {t: [] for t in tier_order}
    for job in all_jobs:
        tier = job.get("tier", TIER_SKIP)
        by_tier.setdefault(tier, []).append(job)

    for tier in tier_order:
        jobs_in_tier = by_tier.get(tier, [])
        if not jobs_in_tier:
            continue
        lines.append("")
        lines.append("=" * 80)
        lines.append(f"  {tier.upper()}  ({len(jobs_in_tier)} jobs)")
        lines.append("=" * 80)

        for job in jobs_in_tier:
            lines.append("")
            lines.append("─" * 60)
            lines.append(f"TITLE:    {job.get('title', '')}")
            lines.append(f"COMPANY:  {job.get('company', '')}")
            lines.append(f"SOURCE:   {job.get('source', '')}")
            lines.append(f"LOCATION: {job.get('location', '')}")
            lines.append(f"URL:      {job.get('url', '')}")
            lines.append(f"SALARY:   {job.get('salary_extracted') or job.get('salary') or 'not listed'}")
            lines.append(f"RATING:   {job.get('tier', '')}")
            lines.append(f"REASON:   {job.get('reason', '')}")

            desc = job.get("description", "") or ""
            desc_chars = len(desc)
            lines.append(f"DESC LEN: {desc_chars} chars")
            lines.append("DESCRIPTION:")
            if desc:
                lines.append(desc)
            else:
                lines.append("(no description)")
            lines.append("─" * 60)

    try:
        os.makedirs(_OUTPUT_DIR, exist_ok=True)
        with open(DEBUG_LOG_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"  Debug log written: {DEBUG_LOG_FILE} ({len(all_jobs)} jobs, {sum(raw_counts.values())} raw)")
    except Exception as e:
        print(f"  Warning: could not write debug log: {e}")


def _timed_source(name: str, fn, verbose: bool = False):
    """Call a search source function, measure wall-clock latency, catch errors.

    Module-level (not inside main) so it is not re-created on every call.
    Returns (jobs, latency_ms). Always returns a list — never raises.
    """
    t0 = time.monotonic()
    try:
        jobs = fn()
    except Exception as e:
        print(f"  [{name}] Source failed: {e}")
        jobs = []
    latency_ms = int((time.monotonic() - t0) * 1000)
    suffix = f" ({latency_ms}ms)" if verbose else ""
    print(f"  {len(jobs)} results{suffix}")
    return jobs, latency_ms


def main(force_send=False, verbose=False):
    today = date.today()
    on_vacation  = VACATION_START <= today < VACATION_END
    return_day   = today == VACATION_END
    run_started  = datetime.now().isoformat()
    rated: list  = []

    if force_send:
        on_vacation = False
        return_day  = False

    # Open DB connection early so run_id is available throughout
    _db_conn = None
    _db_run_id = None
    try:
        _db_conn = _db_connect()
        _db_run_id = _db_insert_run(_db_conn, run_started)
    except Exception as e:
        print(f"  Warning: could not open radar DB ({e}) — run stats will not be saved")

    try:
        _run_pipeline(force_send, verbose, today, on_vacation, return_day,
                      _db_conn, _db_run_id, run_started)
    except Exception as e:
        # Crashed run — mark DB entry so it does not stay as a phantom open record
        print(f"\n  FATAL: radar crashed — {e}")
        import traceback as _tb; _tb.print_exc()
        if _db_conn and _db_run_id:
            try:
                _db_finish_run(_db_conn, _db_run_id,
                    finished_at=datetime.now().isoformat(),
                    total_raw=0, total_new=0, total_rated=0, report_file=None)
            except Exception:
                pass
    finally:
        if _db_conn:
            try: _db_conn.close()
            except Exception: pass


def _run_pipeline(force_send, verbose, today, on_vacation, return_day,
                  _db_conn, _db_run_id, run_started):
    rated: list  = []

    print(f"Job Radar running - {today}")
    if on_vacation:
        print("Vacation mode: collecting jobs to buffer, no email today")
    if return_day:
        print("Return day! Sending vacation digest.")

    # ── Collect jobs from all sources ─────────────────────────────────────────
    # Order: richest data first -> aggregators -> search engines -> weakest
    source_latencies: dict[str, int] = {}

    print("Searching ATS direct (Greenhouse/Lever/Ashby)...")
    raw, source_latencies["ATS"] = _timed_source("ATS", search_ats_companies, verbose)
    raw_counts = {"ATS": len(raw)}

    print("Searching Adzuna...")
    adzuna, source_latencies["Adzuna"] = _timed_source("Adzuna", search_adzuna, verbose)
    raw += adzuna
    raw_counts["Adzuna"] = len(adzuna)

    print("Searching Jobicy...")
    jobicy, source_latencies["Jobicy"] = _timed_source("Jobicy", search_jobicy, verbose)
    raw += jobicy
    raw_counts["Jobicy"] = len(jobicy)

    print("Searching Himalayas...")
    himalayas, source_latencies["Himalayas"] = _timed_source("Himalayas", search_himalayas, verbose)
    raw += himalayas
    raw_counts["Himalayas"] = len(himalayas)

    print("Searching RemoteOK...")
    rok, source_latencies["RemoteOK"] = _timed_source("RemoteOK", search_remoteok, verbose)
    raw += rok
    raw_counts["RemoteOK"] = len(rok)

    print("Searching Remotive...")
    remotive, source_latencies["Remotive"] = _timed_source("Remotive", search_remotive, verbose)
    raw += remotive
    raw_counts["Remotive"] = len(remotive)

    print("Searching USAJobs...")
    usajobs, source_latencies["USAJobs"] = _timed_source("USAJobs", search_usajobs, verbose)
    raw += usajobs
    raw_counts["USAJobs"] = len(usajobs)

    print("Searching UltiPro/UKG...")
    ultipro, source_latencies["UltiPro"] = _timed_source("UltiPro", search_ultipro, verbose)
    raw += ultipro
    raw_counts["UltiPro"] = len(ultipro)

    print("Searching LinkedIn...")
    li, source_latencies["LinkedIn"] = _timed_source("LinkedIn", search_linkedin, verbose)
    raw += li
    raw_counts["LinkedIn"] = len(li)

    print("Searching Brave...")
    brave, source_latencies["Brave"] = _timed_source("Brave", search_brave, verbose)
    raw += brave
    raw_counts["Brave"] = len(brave)

    print("Searching Tavily...")
    tavily, source_latencies["Tavily"] = _timed_source("Tavily", search_tavily, verbose)
    raw += tavily
    raw_counts["Tavily"] = len(tavily)

    print("Searching We Work Remotely...")
    wwr, source_latencies["WeWorkRemotely"] = _timed_source("WeWorkRemotely", search_weworkremotely, verbose)
    raw += wwr
    raw_counts["WeWorkRemotely"] = len(wwr)

    print(f"Raw total: {len(raw)}")

    # ── Zero-source alerting ──────────────────────────────────────────────────
    # Sources that should always return results when working correctly.
    _EXPECTED_SOURCES = {"ATS", "Adzuna", "LinkedIn", "Brave", "Tavily", "Jobicy"}
    zero_sources = [s for s in _EXPECTED_SOURCES if raw_counts.get(s, 0) == 0]
    if zero_sources:
        print(f"  ⚠️  WARNING: Zero results from: {', '.join(sorted(zero_sources))}")
        print(f"     Check API keys, rate limits, or source availability.")

    # ── Filtered jobs tracking ────────────────────────────────────────────────
    # Track every job that gets dropped and why — written to filtered_log.json
    # at end of run so you can audit what the pipeline is discarding each day.
    filtered_jobs: list[dict] = []

    def _reject(job, reason):
        filtered_jobs.append({
            "title":   job.get("title", ""),
            "company": job.get("company", ""),
            "url":     job.get("url", ""),
            "source":  job.get("source", ""),
            "reason":  reason,
        })

    # ── Category page filter - remove job board search pages before anything else
    passing, rejected = [], []
    for j in raw:
        (rejected if is_category_page(j) else passing).append(j)
    for j in rejected:
        _reject(j, "category_page")
    raw = passing
    print(f"After category filter: {len(raw)}")

    passing, rejected = [], []
    for j in raw:
        (rejected if is_bad_scrape(j) else passing).append(j)
    for j in rejected:
        _reject(j, "bad_scrape")
    raw = passing
    print(f"After bad scrape filter: {len(raw)}")

    # FIX (see changelog): Brave/Tavily web searches return news articles, job board
    # search pages, and aggregator links (HiringCafe, Winzons, WRAL news) that
    # have no company field. These slip through title matching but are not real
    # Backfill company names from URL for Brave/Tavily results with no company field.
    backfilled = 0
    for job in raw:
        if not job.get("company") and job.get("url"):
            url_lower = job["url"].lower()
            for domain_key, company_name in DOMAIN_COMPANY_MAP.items():
                if domain_key in url_lower:
                    job["company"] = company_name
                    backfilled += 1
                    break
    if backfilled:
        print(f"  Company backfill: {backfilled} jobs got company name from URL")

    # Drop any Brave/Tavily/LinkedIn result with an empty company.
    passing, rejected = [], []
    for j in raw:
        if j.get("company") or j.get("source") not in ("Brave", "Tavily", "LinkedIn"):
            passing.append(j)
        else:
            rejected.append(j)
    for j in rejected:
        _reject(j, "empty_company")
    raw = passing
    print(f"After empty-company filter: {len(raw)}")

    passing, rejected = [], []
    for j in raw:
        if is_non_us_location(j):
            rejected.append(j)
            _reject(j, "non_us_location")
        elif is_onsite_non_raleigh(j):
            rejected.append(j)
            _reject(j, "onsite_non_raleigh")
        else:
            passing.append(j)
    raw = passing
    print(f"After location filter: {len(raw)}")

    # ── Salary filter
    passing, rejected = [], []
    for j in raw:
        (rejected if not salary_ok(j) else passing).append(j)
    for j in rejected:
        _reject(j, "below_salary_floor")
    raw = passing
    print(f"After salary filter: {len(raw)}")

    # ── Deduplication against seen history
    # Matches on both normalized company|title AND url - whichever fires first
    seen = load_seen()
    new_jobs = []
    within_run_seen = set()  # catches same job appearing in multiple search results today
    for job in raw:
        keys = dedup_keys(job)
        if any(k in seen for k in keys) or any(k in within_run_seen for k in keys):
            continue
        new_jobs.append(job)
        for k in keys:
            within_run_seen.add(k)
    print(f"New (not seen before): {len(new_jobs)}")

    # ── Enrich LinkedIn jobs with full descriptions before rating ─────────────
    # Called after dedup so we only fetch for jobs that will reach Claude.
    # Mutates description field in place. Randomised 2-5s delays.
    li_enrich_descriptions(new_jobs)

    # ── Pre-filter hard disqualifiers - marked as Skip without calling Claude API
    # Three layers of pre-filtering (fastest to slowest):
    #   1. has_disqualifier()      - keyword scan of title + description
    #   2. is_wrong_title()        - regex match on title alone
    #   3. is_company_prefilter()  - company-name match against structural always-Skip list
    # All three mark the job as Skip and add to disqualified[] without touching Claude.
    clean_jobs = []
    disqualified = []
    n_disq = 0
    n_wrong_title = 0
    n_company_filter = 0
    # FIX (code review): previously is_company_prefilter() was called unconditionally
    # for every job even when has_disqualifier() already matched. Short-circuit so
    # the company scan only runs when the first two checks both pass.
    for job in new_jobs:
        match = has_disqualifier(job)
        if match:
            job["tier"]   = TIER_SKIP
            job["reason"] = f"Auto-disqualified: contains '{match}'"
            job["salary_extracted"] = None
            disqualified.append(job)
            n_disq += 1
        elif is_wrong_title(job):
            job["tier"]   = TIER_SKIP
            job["reason"] = "Auto-skipped: wrong title level or known staffing agency"
            job["salary_extracted"] = None
            disqualified.append(job)
            n_wrong_title += 1
        else:
            co_filter = is_company_prefilter(job)  # only called when both above pass
            if co_filter:
                job["tier"]   = TIER_SKIP
                job["reason"] = co_filter
                job["salary_extracted"] = None
                disqualified.append(job)
                n_company_filter += 1
            else:
                clean_jobs.append(job)
    print(f"Clean (to Claude): {len(clean_jobs)} | Keyword disq: {n_disq} | Wrong title: {n_wrong_title} | Company pre-filter: {n_company_filter}")

    # ── Rate clean jobs with Claude API - 5 parallel workers ─────────────────
    # _print_lock (module-level) ensures console output stays on clean separate lines
    # even when multiple threads complete near-simultaneously. Results are written
    # back into rated[] by index so the final list preserves original order
    # regardless of which thread finishes first. Falls back to "Worth a Look" on error.
    rated = [None] * len(clean_jobs)

    def _rate_one(args):
        i, job = args
        with _print_lock:
            print(f"Rating {i+1}/{len(clean_jobs)}: {job['title']} @ {job['company']}")
        tier, reason, salary_extracted = rate_job(job)
        job["tier"]             = tier
        job["reason"]           = reason
        job["salary_extracted"] = salary_extracted or extract_salary_from_text(job.get("description", ""))
        with _print_lock:
            print(f"  {i+1} -> {tier}")
        return i, job

    # FIX (see changelog): Original code submitted all jobs at once into a
    # single ThreadPoolExecutor(max_workers=5). On a 150-job run this created
    # 5 simultaneous bursts × ~2000 tokens each = hits the 50K/min org limit
    # immediately. Switched to explicit batch loop:
    #   - BATCH_SIZE=3 workers fire simultaneously (parallel within batch)
    #   - 5s sleep between batches (prevents token burst across batches)
    # Effect: ~6000 tokens per 5 seconds = 72K tokens/min headroom.
    # On a normal 50-job run adds ~80s total. Worth it to get real scores.
    # CLAUDE_BATCH_SIZE controls parallelism — see tuning constants at top of file
    BATCH_SIZE = CLAUDE_BATCH_SIZE
    for batch_start in range(0, len(clean_jobs), BATCH_SIZE):
        batch = list(enumerate(clean_jobs[batch_start:batch_start + BATCH_SIZE],
                               start=batch_start))
        with ThreadPoolExecutor(max_workers=BATCH_SIZE) as executor:
            futures = {executor.submit(_rate_one, item): item[0] for item in batch}
            for future in as_completed(futures):
                try:
                    i, job = future.result()
                    rated[i] = job
                except Exception as e:
                    with _print_lock:
                        print(f"Rating error: {e}")
                    i = futures[future]
                    clean_jobs[i]["tier"]             = DEFAULT_TIER
                    clean_jobs[i]["reason"]           = "Rating unavailable"
                    clean_jobs[i]["salary_extracted"] = None
                    rated[i] = clean_jobs[i]
        # Pause between batches to avoid token-rate-limit bursts
        if batch_start + BATCH_SIZE < len(clean_jobs):
            time.sleep(5)
    rated = [j for j in rated if j is not None]

    # FIX (code review): flush company cache once after all rating complete
    # rather than writing to disk after every single lookup during parallel rating.
    _flush_company_cache()

    # ── Prune old output files ────────────────────────────────────────────────
    # Keep only the last KEEP_RUNS sets of run files so the output folder stays
    # small and dashboard loads stay fast. Three runs = today + two previous,
    # which is enough history for the board to work correctly.
    #
    # Files pruned by run count (newest N kept, rest deleted):
    #   *-jobs.json      — one per run, dashboard board source
    #   *-skipped.json   — one per run, dashboard skipped tab source
    #   *-report.md      — one per run, email attachment
    #
    # Files pruned differently:
    #   .seen.json.corrupt — crash backups, keep only the newest one
    #   .company_cache.json — trimmed when it exceeds COMPANY_CACHE_MAX entries
    KEEP_RUNS         = 3
    COMPANY_CACHE_MAX = 2000

    try:
        import glob as _glob
        pruned_files = 0

        # For each run-stamped file type: sort newest-first, delete beyond KEEP_RUNS
        for pattern in (
            f"{_OUTPUT_DIR}/*-jobs.json",
            f"{_OUTPUT_DIR}/*-skipped.json",
            f"{_OUTPUT_DIR}/*-report.md",
        ):
            files = sorted(_glob.glob(pattern), reverse=True)  # newest first (timestamp in name)
            for fpath in files[KEEP_RUNS:]:
                try:
                    os.remove(fpath)
                    pruned_files += 1
                except OSError:
                    pass

        # .seen.json.corrupt — keep only the single most recent crash backup
        corrupt_files = sorted(_glob.glob(f"{_OUTPUT_DIR}/.seen.json.corrupt*"))
        for fpath in corrupt_files[:-1]:
            try:
                os.remove(fpath)
                pruned_files += 1
            except OSError:
                pass

        if pruned_files:
            print(f"  Pruned {pruned_files} old output files (keeping last {KEEP_RUNS} runs)")

    except Exception as e:
        print(f"  Warning: output file pruning failed ({e}) — non-critical")

    # ── Trim company cache if it has grown too large ──────────────────────────
    try:
        with _company_cache_lock:
            if len(_company_cache) > COMPANY_CACHE_MAX:
                trimmed = dict(sorted(_company_cache.items())[COMPANY_CACHE_MAX // 2:])
                dropped = len(_company_cache) - len(trimmed)
                _company_cache.clear()
                _company_cache.update(trimmed)
                _save_company_cache(_company_cache)
                print(f"  Company cache trimmed: removed {dropped} entries ({len(_company_cache)} remain)")
    except Exception as e:
        print(f"  Warning: company cache trim failed ({e}) — non-critical")

    # All jobs (rated + auto-skipped) - marked seen regardless of tier
    all_jobs = rated + disqualified

    # ── Write debug log (overwrites previous day's log) ───────────────────────
    write_debug_log(all_jobs, raw_counts, run_time=datetime.now())

    # NOTE: filtered_log.json removed — SQLite radar_runs.db stores per-run
    # filter breakdowns durably in filter_stats and is queryable via the Health tab.
    if verbose and filtered_jobs:
        by_r: dict[str, int] = {}
        for j in filtered_jobs:
            by_r[j["reason"]] = by_r.get(j["reason"], 0) + 1
        print("  Filter breakdown: " + ", ".join(f"{r}: {c}" for r, c in sorted(by_r.items())))

    # ── Write dashboard JSON files ────────────────────────────────────────────
    run_time = datetime.now()
    write_daily_jobs_json(all_jobs, today, run_time)
    write_daily_skipped_json(all_jobs, today, run_time)

    # ── Persist run stats to SQLite ───────────────────────────────────────────
    # Best-effort — never crashes the radar on DB failure.
    report_filename = f"{run_time.strftime('%Y-%m-%d')}-{'am' if run_time.hour < 12 else 'pm'}-report.md"
    source_new_counts: dict[str, int] = {}
    for j in new_jobs:
        src = j.get("source", "unknown")
        source_new_counts[src] = source_new_counts.get(src, 0) + 1

    if _db_conn and _db_run_id:
        try:
            _db_insert_source_stats(_db_conn, _db_run_id, raw_counts, source_new_counts, source_latencies)
            _db_insert_filter_stats(_db_conn, _db_run_id, filtered_jobs)
            _db_finish_run(
                _db_conn, _db_run_id,
                finished_at=run_time.isoformat(),
                total_raw=sum(raw_counts.values()),
                total_new=len(new_jobs),
                total_rated=len(rated),
                report_file=report_filename,
            )
            print(f"  Run stats saved to DB (run_id={_db_run_id}, {len(filtered_jobs)} filtered)")
        except Exception as e:
            print(f"  Warning: could not save run stats to DB ({e})")
        # NOTE: _db_conn.close() is handled by main()'s finally block

    # ── Mark seen history in memory — save to disk after email confirmed sent.
    # FIX (code review): previously save_seen() was called before email dispatch.
    # If send_email() crashed, jobs were permanently marked seen and never reappeared.
    # Now: mark in memory here, persist to disk inside each branch after send_email().
    for job in new_jobs:
        mark_seen(job, seen)

    # ── Vacation logic
    if return_day:
        # Load buffer + add today's jobs, send digest, clear buffer
        buffered = load_buffer()
        # Dedup by URL before extending — the same job can appear on multiple
        # vacation days if it was seen on day 3 and again on day 7 (different run,
        # same URL). Without this the digest email shows duplicates.
        _buf_urls = {j.get("url") for j in buffered if j.get("url")}
        buffered.extend(j for j in all_jobs if j.get("url") not in _buf_urls)
        if buffered:
            body = build_report_body(
                buffered,
                f"☀️ WELCOME BACK - Job Radar Digest | {VACATION_START.strftime('%b %d')} - {VACATION_END.strftime('%b %d, %Y')}"
            )
            try:
                send_email(f"☀️ Welcome Back - Job Radar Digest ({VACATION_START.strftime('%b %d')}-{VACATION_END.strftime('%b %d')})", body)
            except Exception:
                pass  # error already printed by send_email; save_seen still runs below
        save_seen(seen)  # persist regardless of email success
        clear_buffer()

    elif on_vacation:
        # Save to buffer, no email — safe to persist seen immediately
        buffered = load_buffer()
        _buf_urls = {j.get("url") for j in buffered if j.get("url")}
        new_for_buffer = [j for j in all_jobs if j.get("url") not in _buf_urls]
        buffered.extend(new_for_buffer)
        save_buffer(buffered)
        save_seen(seen)
        print(f"Buffered {len(new_for_buffer)} jobs (deduplicated). Total in buffer: {len(buffered)}")

    else:
        # Normal day - always send an email
        actionable = [j for j in all_jobs if j.get("tier") in (TIER_PERFECT, TIER_GOOD, TIER_LOOK)]
        perfect    = sum(1 for j in actionable if j.get("tier") == TIER_PERFECT)
        good       = sum(1 for j in actionable if j.get("tier") == TIER_GOOD)
        look       = sum(1 for j in actionable if j.get("tier") == TIER_LOOK)
        label      = today.strftime("%A, %B %d, %Y").replace(" 0", " ")
        slot       = "AM" if run_time.hour < 12 else "PM"

        # Build informative subject line with tier counts — easier to scan in inbox
        if actionable:
            subject = (
                f"YOUR DAILY JOB SEARCH SUMMARY - {label} — "
                f"{perfect} Perfect Fit | {good} Good Fit / {len(all_jobs)} total"
            )
            body = build_report_body(all_jobs, f"☀️ YOUR DAILY JOB SEARCH SUMMARY - {label}")
        else:
            subject = f"YOUR DAILY JOB SEARCH SUMMARY - {label} — Quiet day ({len(all_jobs)} scanned)"
            quote = random.choice(QUOTES)
            body = (
                f"☀️ YOUR DAILY JOB SEARCH SUMMARY - {label}\n\n"
                f"─" * 50 + "\n"
                f"Good morning! ☀️  Nothing new worth your time today - "
                f"{len(all_jobs)} posting{'s' if len(all_jobs) != 1 else ''} came through but none made it past the filters.\n\n"
                f'"{quote}"\n\n'
                f"─" * 50 + "\n"
                f"Check back tomorrow."
            )

        # Append zero-source warning to email if any expected sources returned nothing
        if zero_sources:
            body += (
                f"\n\n─" * 50 + "\n"
                f"⚠️  SOURCE WARNING\n"
                f"The following sources returned 0 results and may be broken:\n"
                f"  {', '.join(sorted(zero_sources))}\n"
                f"Check API keys, rate limits, or source availability."
            )
            if not actionable:
                subject = subject.replace("Quiet day", "⚠️ Quiet day")

        # Write .md report file for attachment and local reference
        report_filename = f"{run_time.strftime('%Y-%m-%d')}-{slot.lower()}-report.md"
        report_path = os.path.join(_OUTPUT_DIR, report_filename)
        try:
            os.makedirs(_OUTPUT_DIR, exist_ok=True)
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(body)
        except OSError as e:
            print(f"  Warning: could not write report file ({e})")
            report_path = None

        try:
            send_email(subject, body, attachment_path=report_path)
        except Exception:
            pass  # error already printed by send_email
        save_seen(seen)  # persist regardless of email success

if __name__ == "__main__":
    args = sys.argv[1:]
    force_send  = "--run" in args
    verbose     = "--verbose" in args
    sleep_after = "--sleep-after" in args

    if force_send:
        print("Manual run - bypassing vacation dates, sending email immediately")
    if verbose:
        print("Verbose mode on — source latencies and filter breakdown will be shown")

    main(force_send=force_send, verbose=verbose)

    if sleep_after:
        print("Script complete - putting computer to sleep in 60 seconds...")
        print("(Press Ctrl+C to cancel)")
        time.sleep(60)
        subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], check=False)