# Job Search Autopilot

A personal job search automation tool that aggregates listings from 11 sources daily, filters them against your criteria, rates them with Claude AI, and emails you a ranked digest each morning.

## What it does

- Searches 11 sources: ATS direct (Greenhouse/Lever/Ashby), Adzuna, LinkedIn, Brave, Tavily, WeWorkRemotely, Jobicy, Himalayas, Remotive, USAJobs, UltiPro/UKG
- Filters out non-US roles, onsite-outside-your-city roles, below-salary-floor postings, staffing agencies, and noise pages
- Rates each job with Claude AI (Perfect Fit / Good Fit / Worth a Look / Skip) based on your profile
- Emails a daily digest sorted by tier with a Kanban dashboard to track your pipeline

## Project structure

```
job-search-profile/
├── scripts/
│   ├── job_radar.py        ← main radar (run this daily)
│   ├── dashboard.py        ← Flask Kanban dashboard
│   └── config.py           ← your personal config (gitignored)
├── config.example.py       ← copy to scripts/config.py and fill in
├── .env.example            ← copy to .env and fill in API keys
├── requirements.txt
├── SETUP.txt               ← full setup guide with AI customization prompts
└── output/
    └── job-radar/          ← runtime files (gitignored)
```

## Quick Start

**1. Install dependencies**
```bash
pip install -r requirements.txt
```

**2. Set up API keys**
```bash
cp .env.example .env
# Edit .env and fill in your API keys
```

**3. Set up your config**
```bash
cp config.example.py scripts/config.py
# Edit scripts/config.py with your profile, salary floor, city, and company list
```

**4. Run it**
```bash
python scripts/job_radar.py --run
```

Add `--verbose` to see source latencies and filter breakdown. Full setup instructions are in `SETUP.txt`.

## Scheduling

macOS/Linux — add a cron job:
```
0 7 * * 1-5 cd /path/to/job-search-profile && python scripts/job_radar.py --run
```

Windows — use Task Scheduler pointing to `python scripts/job_radar.py --run`.

## API keys needed

| Service | Where to get it | Cost |
|---|---|---|
| Anthropic | console.anthropic.com | Pay per use (~$1-5/month) |
| Brave Search | api.search.brave.com | Free (2,000 req/month) |
| Tavily | app.tavily.com | Free (1,000 req/month) |
| Adzuna | developer.adzuna.com | Free |
| USAJobs | developer.usajobs.gov | Free (optional) |

Gmail requires an [App Password](https://myaccount.google.com/apppasswords) — not your regular login password.

---

## Making it yours — use AI to customise everything

This tool is built to be customised. The filters, search queries, company list, and rating logic are all plain text or Python lists — easy to read and easy to change even if you are not a developer.

The fastest way to personalise it is to **upload the files directly into Claude or ChatGPT** and describe what you want. You don't need to understand every line of code. Just tell the AI what to change and it will handle the syntax. This approach — using plain English to drive code changes — is sometimes called "vibe coding" and it works really well for a project like this.

**How to do it:**

1. Go to [claude.ai](https://claude.ai) or [chatgpt.com](https://chatgpt.com)
2. Upload `job_radar.py` and `config.example.py` as attachments
3. Describe what you want changed
4. Copy the updated code back into your files

**Example prompts to get you started:**

> *"I've attached job_radar.py and config.example.py. I'm a software engineer looking for senior engineering and tech lead roles in the Seattle area. Can you update TARGET_TITLES, set RALEIGH_TERMS to match the Seattle metro, and rewrite the PROFILE block for my background?"*

> *"I want to filter out all jobs that mention Salesforce as a hard requirement, all healthcare roles, and anything that's a contract position. Can you add these to HARD_DISQUALIFIERS in job_radar.py?"*

> *"I work in data science. Can you update TARGET_TITLES for data science roles, rewrite the Claude rating prompt so it scores data engineering and ML roles as Perfect Fit, and suggest 20 data-focused companies for the COMPANIES list?"*

> *"Can you help me find the Greenhouse/Lever/Ashby slugs for these companies and add them to the COMPANIES list: [your list]?"*

> *"The rating prompt currently describes a product manager. Can you rewrite it for a UX designer targeting senior design roles?"*

The `SETUP.txt` file has more detailed prompts for each specific part of the tool — start there if you want step-by-step guidance.

---

## What you can customise

### In `config.py` (your personal file, never committed to GitHub)

**`PROFILE`** — the most important thing to personalise. Claude reads this when rating every single job. Write it like a concise professional summary: your current role, your background, what you are targeting, your strengths, and your hard constraints (location, salary, types of work you won't do). The more specific you are, the better the ratings.

**`MIN_SALARY`** — your salary floor as a plain number (e.g. `150000`). Jobs with a confirmed range entirely below this are filtered before Claude sees them. Jobs with no salary listed always pass through.

**`RALEIGH_TERMS`** — replace this with your own city and surrounding suburb names. The radar uses this list to identify local hybrid and onsite roles and show them in a separate section of your email digest. Leave it empty if you only want remote roles.

**`COMPANIES`** — the direct ATS company watchlist. The radar checks Greenhouse, Lever, and Ashby job boards for every company in this list on every run. See the section below for how to find slugs.

**`VACATION_START` / `VACATION_END`** — set both to past dates if you are not on vacation. During vacation the radar buffers results and sends one digest when you return.

**Search queries** (`ADZUNA_QUERIES`, `BRAVE_QUERIES`, `TAVILY_QUERIES`, `LI_REMOTE_QUERIES`, `LI_RALEIGH_QUERIES`) — tailor these to your exact job titles and industry keywords. Better queries mean more relevant results from each source.

### In `job_radar.py`

**`TARGET_TITLES`** — keyword list that controls which job titles are considered relevant. Anything that does not match at least one keyword is dropped before any other processing. Ships with PM/PO/BA titles as examples — update this for your role type.

**`HARD_DISQUALIFIERS`** — phrases that auto-skip a job before it reaches Claude. Use this for things you are 100% certain you never want: specific industries, contract-only language, unwanted tech stacks. Ships empty so you can add your own without inherited assumptions.

**`_COMPANY_PREFILTER`** — staffing agencies and job aggregators to block by company name. Ships with a few well-known ones. Add any agencies you keep seeing in your results.

**`SALARY_FLOOR_EXEMPT`** — companies you know pay well above your floor even when a search snippet shows a misleadingly low number. Ships empty — add employers in your target industry where you trust the compensation.

**`_URL_CITY_RE` and `_LOC_CITY_RE`** — two lists that catch onsite-outside-your-area jobs. Pre-loaded with major US metros and international cities. Remove any cities within your commutable area; add cities you want to block.

**Claude rating prompt** — the tier definitions and rules Claude uses to score every job. Find the section starting with `"Perfect Fit" = 90-100%` in `job_radar.py`. Edit this in plain English to describe your situation: what makes an ideal role, what your core strengths are, what your hard nos are. Claude follows this literally, so specificity pays off here more than anywhere else.

---

## Adding companies to the ATS list

The `COMPANIES` list in `config.py` is the most powerful part of the tool. Direct ATS access means you see new postings the moment they go live, often before they show up on any aggregator.

**Finding a company's slug:**

| ATS | URL pattern | Slug |
|---|---|---|
| Greenhouse | `boards.greenhouse.io/stripe` | `stripe` |
| Lever | `jobs.lever.co/plaid` | `plaid` |
| Ashby | `jobs.ashbyhq.com/mercury` | `mercury` |

The radar tries all three APIs for each slug automatically — you don't need to know which one a company uses, just add the slug.

**Tips for finding slugs:**
- Try the company name lowercased with no spaces first (`wealthsimple`, `nerdwallet`)
- If that returns nothing, try with hyphens (`cash-app`)
- Browse [boards.greenhouse.io](https://boards.greenhouse.io) to search Greenhouse companies directly
- Ask Claude: *"What is the Greenhouse/Lever/Ashby ATS slug for [Company Name]?"*

---

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

Special thanks to [devpyle](https://github.com/devpyle/) for the early help and inspiration that got this project off the ground.

## License

MIT + Commons Clause. Free to use for personal job searching. Reach out before building anything commercial on top of it — see `LICENSE` for details.
