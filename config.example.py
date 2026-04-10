"""
config.example.py  —  Job Radar configuration template

Copy this file to scripts/config.py and fill in your details.
scripts/config.py is gitignored and must never be committed.

Required environment variables (set in .env or system environment):
    ANTHROPIC_API_KEY   — from console.anthropic.com
    BRAVE_API_KEY       — from api.search.brave.com (free tier available)
    TAVILY_API_KEY      — from app.tavily.com (free tier available)
    ADZUNA_APP_ID       — from developer.adzuna.com (free)
    ADZUNA_APP_KEY      — from developer.adzuna.com (free)
    EMAIL_FROM          — Gmail address used to send the digest
    EMAIL_PASSWORD      — Gmail App Password (not your login password)
    EMAIL_TO            — Address that receives the digest (can be same as FROM)
    USAJOBS_API_KEY     — from developer.usajobs.gov (free, optional)
    USAJOBS_EMAIL       — your email, required by USAJobs API (optional)
"""

from datetime import date

# ── SALARY FLOOR ──────────────────────────────────────────────────────────────
MIN_SALARY = 150000  # jobs with confirmed salary below this are filtered out

# ── VACATION MODE ─────────────────────────────────────────────────────────────
# Jobs are buffered during [VACATION_START, VACATION_END) and a single digest
# is sent on VACATION_END. Set both to past dates to disable vacation mode.
VACATION_START = date(2020, 1, 1)
VACATION_END   = date(2020, 1, 2)

# ── CANDIDATE PROFILE ─────────────────────────────────────────────────────────
# Paste into the Claude rating prompt. Keep it factual and concise.
# Update if your role, metrics, or targets change.
PROFILE = """
Name: Your Name
Current role: [Title] at [Company], [Start date] - present
[2-3 bullet points of career highlights and metrics]

Target roles: Senior Product Manager, Senior Product Owner, Lead/Principal PM,
              AVP Product, Director of Product (IC), Senior Business Analyst,
              Customer Experience Manager

Target salary: $150K+
Location: Remote (nationwide) OR on-site/hybrid in [Your City] area only
"""

# ── LOCAL METRO TERMS ─────────────────────────────────────────────────────────
# City/area names used to identify local on-site/hybrid jobs in your target area.
# Replace these with your own city and surrounding suburbs.
# Variable must be named RALEIGH_TERMS — this name is used in job_radar.py.
RALEIGH_TERMS = {  # rename this in config.py to match your city if you like
    "your city", "nearby city 1", "nearby city 2", "nearby city 3",
}

# ── MOTIVATIONAL QUOTES ───────────────────────────────────────────────────────
# Shown in quiet-day emails (no new jobs). Add as many as you like.
QUOTES = [
    "The secret of getting ahead is getting started. - Mark Twain",
    "It always seems impossible until it's done. - Nelson Mandela",
    "You miss 100% of the shots you don't take. - Wayne Gretzky",
]

# ── ATS COMPANY LIST ─────────────────────────────────────────────────────────
# Slugs for Greenhouse, Lever, and Ashby company boards.
# The radar tries all three APIs for each slug automatically.
# Add any company you want to track directly.
COMPANIES = [
    # Fintech / Digital Banking
    "chime",
    "plaid",
    "stripe",
    "mercury",
    "brex",
    "affirm",
    "marqeta",
    # Insurance
    "lemonade",
    # Add more as needed...
]

# ── ATS NAME OVERRIDES ────────────────────────────────────────────────────────
# slug.replace("-", " ").title() works for most names but fails for some.
# Add overrides here: { "slug": "Display Name" }
ATS_NAME_OVERRIDES = {
    # "some-slug": "Correct Display Name",
}

# ── SEARCH QUERIES ────────────────────────────────────────────────────────────

ADZUNA_QUERIES = [
    "senior product manager remote fintech",
    "senior product owner remote",
    "principal product manager remote",
    "senior business analyst remote fintech",
    "product manager digital banking remote",
    "customer experience manager remote",
    # Add local area queries:
    "product manager your-city",
    "senior product manager your-city",
]

BRAVE_QUERIES = [
    "senior product manager remote fintech job opening",
    "senior product owner remote digital banking hiring",
    "principal product manager remote fintech",
    "lead product manager remote payments",
    "senior business analyst remote fintech",
    # Add local queries:
    "product manager your-city job opening",
]

TAVILY_QUERIES = [
    "senior product manager remote fintech job",
    "senior product owner remote digital banking",
    "principal product manager remote fintech hiring",
    "senior business analyst remote fintech job",
    # Add local queries:
    "senior product manager your-city",
]

LI_REMOTE_QUERIES = [
    "senior product manager fintech",
    "senior product owner digital banking",
    "principal product manager",
    "product manager payments",
    "senior business analyst fintech",
    "digital product manager banking",
    "customer experience manager",
]

LI_RALEIGH_QUERIES = [  # local/hybrid job searches for your metro area
    "product manager your-city",
    "senior product manager your-state",
    "product owner your-city",
    "senior product owner your-state",
    "business analyst your-city fintech",
    "customer experience manager your-city",
]

HIMALAYAS_QUERIES = [
    ("product-management", "product manager"),
    ("product-management", "product owner"),
    ("product-management", "digital banking"),
    ("product-management", "digital product manager"),
    ("business-analyst",   "business analyst"),
    ("management",         "product manager"),
]

REMOTIVE_QUERIES = [
    {"category": "product"},
    {"category": "management", "search": "product"},
    {"search": "business analyst"},
]

USAJOBS_QUERIES = [
    "product manager",
    "digital experience",
    "IT specialist",
]

JOBICY_QUERIES = [
    {"geo": "usa", "industry": "management",         "tag": "product manager",          "count": 50},
    {"geo": "usa", "industry": "management",         "tag": "product owner",             "count": 50},
    {"geo": "usa", "industry": "accounting-finance", "tag": "product manager",           "count": 50},
    {"geo": "usa",                                    "tag": "product manager fintech",   "count": 50},
    {"geo": "usa",                                    "tag": "digital product manager",   "count": 50},
]
