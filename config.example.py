"""
config.example.py  —  Job Search Autopilot configuration template

Copy this file to scripts/config.py and fill in your details.
scripts/config.py is gitignored and must never be committed.

Required environment variables (set in .env or system environment):
    ANTHROPIC_API_KEY   — from console.anthropic.com
    BRAVE_API_KEY       — from api.search.brave.com (free tier available)
    TAVILY_API_KEY      — from app.tavily.com (free tier available)
    ADZUNA_APP_ID       — from developer.adzuna.com (free)
    ADZUNA_APP_KEY      — from developer.adzuna.com (free)
    GMAIL_ADDRESS       — Gmail address used to send the digest
    GMAIL_APP_PW        — Gmail App Password (not your login password)
    USAJOBS_API_KEY     — from developer.usajobs.gov (free, optional)
    USAJOBS_EMAIL       — your email, required by USAJobs API (optional)
"""

from datetime import date

# ── SALARY FLOOR ──────────────────────────────────────────────────────────────
MIN_SALARY = 150000  # set this to your minimum acceptable annual salary (e.g. 150000 for $150K)

# ── VACATION MODE ─────────────────────────────────────────────────────────────
# Jobs are buffered during [VACATION_START, VACATION_END) and a single digest
# is sent on VACATION_END. Set both to past dates to disable vacation mode.
VACATION_START = date(2020, 1, 1)
VACATION_END   = date(2020, 1, 2)

# ── CANDIDATE PROFILE ─────────────────────────────────────────────────────────
# This is what Claude reads when rating every job. Be specific — the better
# your profile, the more accurate your ratings will be.
# Update whenever your role, targets, or priorities change.
PROFILE = """
Name: [Your Name]
Current role: [Your Title] at [Your Company], [Start Date] - present
[Bullet point: key achievement with a metric, e.g. "Grew X from Y to Z"]
[Bullet point: another achievement or area of expertise]

Target roles: [Your Target Role 1], [Your Target Role 2], [Your Target Role 3]

Target salary: $[YOUR_SALARY]+
Location: Remote (nationwide) OR on-site/hybrid in [Your City] area only

Hard constraints (always Skip):
- [Thing you will never do, e.g. "people management as primary responsibility"]
- [Industry or domain you want to avoid]
- [Any other hard no]

Core strengths:
- [Strength 1]
- [Strength 2]
- [Strength 3]
"""

# ── LOCAL METRO TERMS ────────────────────────────────────────────────────────
# City and suburb names for your commutable area. Jobs requiring on-site
# attendance outside this set are filtered out automatically.
# Replace with your own city and surrounding suburbs.
# Variable must be named LOCAL_METRO_TERMS — this name is used in job_radar.py.
LOCAL_METRO_TERMS = {
    "your city",
    "nearby suburb 1",
    "nearby suburb 2",
    "nearby suburb 3",
}

# ── MOTIVATIONAL QUOTES ───────────────────────────────────────────────────────
# Shown in quiet-day emails when no new jobs come through.
QUOTES = [
    "The secret of getting ahead is getting started. - Mark Twain",
    "It always seems impossible until it's done. - Nelson Mandela",
    "You miss 100% of the shots you don't take. - Wayne Gretzky",
]

# ── ATS COMPANY LIST ──────────────────────────────────────────────────────────
# Slugs for Greenhouse, Lever, and Ashby company job boards.
# The radar tries all three APIs for each slug automatically — you don't need
# to know which ATS a company uses, just add the slug.
#
# HOW TO FIND A SLUG:
#   Visit the company's careers page and look at the URL:
#   boards.greenhouse.io/SLUG  →  use SLUG
#   jobs.lever.co/SLUG         →  use SLUG
#   jobs.ashbyhq.com/SLUG      →  use SLUG
#
# If unsure, try the company name lowercased with no spaces. If that doesn't
# work, try with hyphens. Or ask Claude: "What is the ATS slug for [Company]?"
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
    # Add more companies you want to monitor directly:
    # "company-slug",
]

# ── ATS NAME OVERRIDES ────────────────────────────────────────────────────────
# The radar generates display names from slugs automatically, but some slugs
# don't convert cleanly. Add corrections here: { "slug": "Display Name" }
ATS_NAME_OVERRIDES = {
    # "some-slug": "Correct Display Name",
}

# ── SEARCH QUERIES ────────────────────────────────────────────────────────────
# Replace [Your Role] and [Your Industry] with your actual target role keywords
# and industry. Use partial keywords — "product manager" matches "Senior Product
# Manager", "Lead Product Manager", etc.
#
# TIP: Upload this file to Claude or ChatGPT and ask it to generate tailored
# query lists based on your target roles and industry. See SETUP.txt for a
# ready-made prompt.

ADZUNA_QUERIES = [
    # Remote role queries — replace with your target role and industry
    "[Your Role] remote",
    "[Your Role] remote [Your Industry]",
    "senior [Your Role] remote",
    "lead [Your Role] remote",
    "[Your Role] remote [Your Industry] hiring",
    # Local area queries — replace your-city with your actual city
    "[Your Role] your-city",
    "senior [Your Role] your-city",
]

BRAVE_QUERIES = [
    # Written like natural search phrases for best results
    "senior [Your Role] remote [Your Industry] job opening",
    "[Your Role] remote [Your Industry] hiring",
    "lead [Your Role] remote [Your Industry]",
    "senior [Your Role] remote [Your Industry]",
    # Local queries
    "[Your Role] your-city job opening",
]

TAVILY_QUERIES = [
    "senior [Your Role] remote [Your Industry] job",
    "[Your Role] remote [Your Industry]",
    "lead [Your Role] remote [Your Industry] hiring",
    "senior [Your Role] remote [Your Industry] job opening",
    # Local queries
    "senior [Your Role] your-city",
]

LI_REMOTE_QUERIES = [
    # Short keyword phrases work best for LinkedIn
    "senior [Your Role]",
    "lead [Your Role]",
    "principal [Your Role]",
    "[Your Role] [Your Industry]",
    "senior [Your Role] [Your Industry]",
    "director [Your Role]",
]

LI_LOCAL_QUERIES = [
    # Local/hybrid searches — replace your-city and your-state
    "[Your Role] your-city",
    "senior [Your Role] your-state",
    "lead [Your Role] your-city",
    "[Your Role] your-city [Your Industry]",
]

HIMALAYAS_QUERIES = [
    # Format: ("category", "keyword")
    # Valid categories: product-management, business-analyst, management,
    #                   software-development, design, data-science, marketing
    ("management", "[your-role]"),
    ("management", "[your-role] [your-industry]"),
    # Add more category/keyword pairs for your role type:
    # ("your-category", "your keyword"),
]

REMOTIVE_QUERIES = [
    # Category-based search — adjust category to match your field
    # Common categories: product, software-dev, devops, design, marketing,
    #                    data, finance, hr, qa, writing, teaching
    {"category": "management"},
    {"category": "management", "search": "[your role keyword]"},
    {"search": "[your role keyword]"},
]

USAJOBS_QUERIES = [
    # Keywords for USAJobs federal positions — only relevant if you want
    # to include government roles. Leave as-is or update for your field.
    "[Your Role]",
    "[Your Industry] specialist",
    "IT specialist",
]

JOBICY_QUERIES = [
    # Format: geo, industry, tag, count
    # Valid industries: management, accounting-finance, business, tech, design,
    #                   marketing, hr, legal, healthcare
    {"geo": "usa", "industry": "management", "tag": "[your role]",          "count": 50},
    {"geo": "usa", "industry": "management", "tag": "[your role] [industry]","count": 50},
    # Add more queries for your industry:
    # {"geo": "usa", "industry": "your-industry", "tag": "your keyword", "count": 50},
]
