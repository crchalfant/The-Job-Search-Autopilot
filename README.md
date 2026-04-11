# Job Search Autopilot

A personal job search automation tool that aggregates listings from 11 sources daily, filters them against your criteria, rates them with Claude AI, and emails you a ranked digest each morning.

## What it does

- Searches 11 sources: ATS direct (Greenhouse/Lever/Ashby), Adzuna, LinkedIn, Brave, Tavily, WeWorkRemotely, Jobicy, Himalayas, Remotive, USAJobs, UltiPro/UKG
- Filters out non-US roles, onsite-outside-your-city roles, below-salary-floor postings, staffing agencies, and noise pages
- Rates each job with Claude AI (Perfect Fit / Good Fit / Worth a Look / Skip) based on your profile
- Emails a daily digest sorted by tier with a Kanban dashboard to track your pipeline

## Project structure

```text
job-search-profile/
├── scripts/
│   ├── job_radar.py        ← main radar (run this daily)
│   ├── dashboard.py        ← Flask Kanban dashboard
│   ├── radar_shared.py     ← shared core logic (IDs, normalization, API safety, validation)
│   └── config.py           ← your personal config (gitignored)
├── config.example.py       ← copy to scripts/config.py and fill in
├── .env.example            ← copy to .env and fill in API keys
├── requirements.txt
├── SETUP.txt               ← full setup guide with AI customization prompts
├── README.md               ← project documentation
├── LICENSE
└── output/
    └── job-radar/          ← runtime files (gitignored)
```

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set up API keys

```bash
cp .env.example .env
# Edit .env and fill in your API keys
```

### 3. Set up your config

```bash
cp config.example.py scripts/config.py
# Edit scripts/config.py with your profile, salary floor, city, and company list
```

### 4. Run it

```bash
python scripts/job_radar.py --run
```

Add `--verbose` to see source latencies and filter breakdown. Full setup instructions are in `SETUP.txt`.

## Scheduling

**macOS/Linux** — add a cron job:

```cron
0 7 * * 1-5 cd /path/to/job-search-profile && python scripts/job_radar.py --run
```

**Windows** — use Task Scheduler pointing to `python scripts/job_radar.py --run`.

## API keys needed

| Service | Where to get it | Cost |
|---|---|---|
| Anthropic | console.anthropic.com | Pay per use (~$1-5/month) |
| Brave Search | api.search.brave.com | Free (2,000 req/month) |
| Tavily | app.tavily.com | Free (1,000 req/month) |
| Adzuna | developer.adzuna.com | Free |
| USAJobs | developer.usajobs.gov | Free (optional) |

Gmail requires an App Password, not your regular login password.

## Shared core module: `scripts/radar_shared.py`

The project now includes a shared core module:

```text
scripts/radar_shared.py
```

This file centralizes logic that should not be duplicated across `job_radar.py` and `dashboard.py`.

### What it handles

- Job title normalization
- Stable job ID generation
- Safer external API request handling
- Profile sanitization before sending data to AI APIs
- Shared config validation helpers

### Why it exists

Earlier versions duplicated some of this logic in multiple places. That created avoidable risk:

- duplicate jobs could reappear
- rejected jobs could come back
- dashboard state could drift from radar state
- API failures could degrade silently

`radar_shared.py` fixes that by making shared behavior explicit and reusable.

### Contributor rule

Do not re-implement normalization, job ID generation, or shared API safety logic in other files. Import from `radar_shared.py` instead.

## Making it yours — use AI to customise everything

This tool is built to be customised. The filters, search queries, company list, and rating logic are all plain text or Python lists, readable and easy to change even if you are not a developer.

The fastest way to personalise it is to upload the files directly into Claude or ChatGPT and describe what you want. You do not need to understand every line of code. Just tell the AI what to change and it handles the syntax. This is sometimes called "vibe coding."

### How to do it

1. Go to claude.ai or chatgpt.com
2. Upload `job_radar.py` and `config.example.py` as attachments
3. Describe what you want changed. Use the prompts below as a starting point
4. Copy the updated code back into your files and run it

### Things you will need AI to help you update

- `PROFILE` in `config.py` — rewrite this to describe your background, target roles, strengths, and hard constraints. This is the most important thing to get right.
- `LOCAL_METRO_TERMS` in `config.py` — replace the placeholder values with your actual city and surrounding suburbs
- `MIN_SALARY` in `config.py` — set to your salary floor as a plain number (for example `120000`)
- All search query lists in `config.py` — `ADZUNA_QUERIES`, `BRAVE_QUERIES`, `TAVILY_QUERIES`, `LI_REMOTE_QUERIES`, `LI_LOCAL_QUERIES`, `HIMALAYAS_QUERIES`, `REMOTIVE_QUERIES`, `JOBICY_QUERIES` — replace the `[Your Role]` and `[Your Industry]` placeholders with your actual target titles and industry
- `TARGET_TITLES` in `job_radar.py` — the keyword list that controls which job titles are even considered. If this does not match your role type, almost everything will be filtered before Claude sees it
- `HARD_DISQUALIFIERS` in `job_radar.py` — add phrases for industries, domains, or contract types you never want to see
- `SALARY_FLOOR_EXEMPT` in `job_radar.py` — add well-known employers in your field that reliably pay above your floor, to prevent false salary-filter dropouts
- `_URL_CITY_RE` and `_LOC_CITY_RE` in `job_radar.py` — remove any cities within your commutable area from the block lists so local roles are not accidentally filtered
- Claude rating prompt in `job_radar.py` — rewrite the tier definitions so Perfect Fit, Good Fit, Worth a Look, and Skip reflect your actual situation and domain

### Example prompts to get you started

- "I've attached `job_radar.py` and `config.example.py`. I'm a software engineer looking for senior engineering roles in the Seattle area. Can you update `TARGET_TITLES` for engineering roles, set `LOCAL_METRO_TERMS` to the Seattle metro, update all the search query lists for software engineering, and rewrite the `PROFILE` block for my background?"
- "I want to block all jobs mentioning Salesforce as a hard requirement, healthcare domain, and contract-only positions. Can you add these to `HARD_DISQUALIFIERS` in `job_radar.py`?"
- "I work in data science. Can you update `TARGET_TITLES` for data roles, rewrite the Claude rating prompt so ML and data engineering score as Perfect Fit, fill in all the search queries for data science, and suggest companies for the `COMPANIES` list?"
- "Can you help me find the Greenhouse/Lever/Ashby ATS slugs for these companies and add them to the `COMPANIES` list: [your list]?"
- "The rating prompt is generic. I'm a UX designer targeting senior design roles. Can you rewrite the tier definitions for my situation?"
- "I ran the radar and got this error: [paste the full error message and the last few lines of console output before it]. Here is the relevant section of `job_radar.py`: [paste the section]. What is wrong and how do I fix it?"

The `SETUP.txt` file has more detailed prompts for each specific part. Start there if you want step-by-step guidance.

**Debugging tip:** If something breaks, the full error message plus the last 20 lines of console output is almost always enough context for Claude or ChatGPT to diagnose and fix the problem. You do not need to understand the error yourself. Just paste it in and describe what you were trying to do when it happened.

## What you can customise

### In `config.py` (your personal file, never committed to GitHub)

**`PROFILE`** — the most important thing to personalise. Claude reads this when rating every single job. Write it like a concise professional summary: your current role, your background, what you are targeting, your strengths, and your hard constraints (location, salary, types of work you will not do). The more specific you are, the better the ratings.

**`MIN_SALARY`** — your salary floor as a plain number (for example `100000` for $100K). Jobs with a confirmed range entirely below this are filtered before Claude sees them. Jobs with no salary listed always pass through.

**`LOCAL_METRO_TERMS`** — replace this with your own city and surrounding suburb names. The radar uses this list to identify local hybrid and onsite roles and show them in a separate section of your email digest. Leave it empty if you only want remote roles.

**`COMPANIES`** — the direct ATS company watchlist. The radar checks Greenhouse, Lever, and Ashby job boards for every company in this list on every run. See the section below for how to find slugs.

**`VACATION_START / VACATION_END`** — set both to past dates if you are not on vacation. During vacation the radar buffers results and sends one digest when you return.

**Search queries** (`ADZUNA_QUERIES`, `BRAVE_QUERIES`, `TAVILY_QUERIES`, `LI_REMOTE_QUERIES`, `LI_LOCAL_QUERIES`, `HIMALAYAS_QUERIES`, `REMOTIVE_QUERIES`, `JOBICY_QUERIES`) — tailor these to your exact job titles and industry keywords. All query lists ship with `[Your Role]` and `[Your Industry]` placeholders. Replace them with your actual targets.

### In `job_radar.py`

**`TARGET_TITLES`** — keyword list that controls which job titles are considered relevant. Anything that does not match at least one keyword is dropped before any other processing. Ships with PM/PO/BA titles as examples. Update this for your role type.

**`HARD_DISQUALIFIERS`** — phrases that auto-skip a job before it reaches Claude. Use this for things you are 100% certain you never want: specific industries, contract-only language, unwanted tech stacks. Ships empty so you can add your own without inherited assumptions.

**`_COMPANY_PREFILTER`** — staffing agencies and job aggregators to block by company name. Ships with a few well-known ones. Add any agencies you keep seeing in your results.

**`SALARY_FLOOR_EXEMPT`** — companies you know pay well above your floor even when a search snippet shows a misleadingly low number. Ships empty. Add employers in your target industry where you trust the compensation.

**`_URL_CITY_RE` and `_LOC_CITY_RE`** — two lists that catch onsite-outside-your-area jobs. Pre-loaded with major US metros and international cities. Remove any cities within your commutable area. Add cities you want to block.

**Claude rating prompt** — the tier definitions and rules Claude uses to score every job. Find the section starting with `"Perfect Fit" = 90-100%` in `job_radar.py`. Edit this in plain English to describe your situation: what makes an ideal role, what your core strengths are, what your hard nos are. Claude follows this literally, so specificity pays off here more than anywhere else.

## Adding companies to the ATS list

The `COMPANIES` list in `config.py` is the most powerful part of the tool. Direct ATS access means you see new postings the moment they go live, often before they show up on any aggregator.

### Finding a company's slug

| ATS | URL pattern | Slug |
|---|---|---|
| Greenhouse | `boards.greenhouse.io/stripe` | `stripe` |
| Lever | `jobs.lever.co/plaid` | `plaid` |
| Ashby | `jobs.ashbyhq.com/mercury` | `mercury` |

The radar tries all three APIs for each slug automatically. You do not need to know which one a company uses, just add the slug.

### Tips for finding slugs

- Try the company name lowercased with no spaces first (`wealthsimple`, `nerdwallet`)
- If that returns nothing, try with hyphens (`cash-app`)
- Browse `boards.greenhouse.io` to search Greenhouse companies directly
- Ask Claude: "What is the Greenhouse/Lever/Ashby ATS slug for [Company Name]?"

## Output files

All runtime files live in `output/job-radar/` (gitignored). The radar keeps only the last 3 runs worth of data and prunes automatically.

| File | Purpose |
|---|---|
| `*-jobs.json` | Rated jobs for the dashboard board tab |
| `*-skipped.json` | Skipped jobs for the dashboard skipped tab |
| `*-report.md` | Email report attachment |
| `.seen.json` | Dedup history (60-day rolling window) |
| `board_state.json` | Dashboard card positions and notes |
| `radar_runs.db` | SQLite run history for the Health tab |
| `debug_job_log.txt` | Full job log for debugging source quality |

## Acknowledgements

Special thanks to [devpyle](https://github.com/devpyle) for the early help and inspiration that got this project off the ground.

## Contact

GitHub: https://github.com/crchalfant  
Email: Casey.Chalfant@protonmail.com

## License

MIT + Commons Clause. Free to use for personal job searching. Reach out before building anything commercial on top of it. See `LICENSE` for details.
