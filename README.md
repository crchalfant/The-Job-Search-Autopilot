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

## Customising for yourself

All personalisation lives in `scripts/config.py`. The key things to update:

- **`PROFILE`** — your name, current role, target roles, and career summary. This is what Claude reads when rating each job, so the more accurate it is, the better your ratings will be.
- **`MIN_SALARY`** — your minimum acceptable salary as a number (e.g. `150000`).
- **`RALEIGH_TERMS`** — replace with your own city and surrounding metro area names. Any job requiring on-site attendance outside these terms gets filtered out automatically.
- **`COMPANIES`** — the ATS company list (see below).
- **`VACATION_START` / `VACATION_END`** — set both to past dates if you are not on vacation.

The search queries (`ADZUNA_QUERIES`, `BRAVE_QUERIES`, `LI_REMOTE_QUERIES` etc.) are all in config.py too. Tailor them to your target job titles and industries for better results.

**Tip:** The `SETUP.txt` file includes ready-to-use prompts you can paste into Claude or ChatGPT to generate your profile block, search queries, and ATS company list from scratch.

## Adding companies to the ATS list

The `COMPANIES` list in `config.py` is the most powerful feature. The radar checks Greenhouse, Lever, and Ashby job boards directly for every company in the list — you see roles before they hit the aggregator sites.

**Finding a company's slug:**

The slug is usually just the company name lowercased, sometimes with hyphens for spaces. You can find it by visiting the company's careers page and looking at the URL:

| ATS | URL pattern | Slug |
|---|---|---|
| Greenhouse | `boards.greenhouse.io/stripe` | `stripe` |
| Lever | `jobs.lever.co/plaid` | `plaid` |
| Ashby | `jobs.ashbyhq.com/mercury` | `mercury` |

The radar tries all three APIs for each slug automatically, so you don't need to know which one a company uses — just add the slug and it figures it out.

**Examples of slugs that differ from the company name:**

```python
"cash-app",       # not "cashapp"
"affirm",         # straightforward
"wealthsimple",   # no space
"nerdwallet",     # no space
```

If you are not sure of a slug, try the company name lowercased with no spaces first. If that returns nothing, try it with hyphens. You can also search for the company on [Greenhouse's job board list](https://boards.greenhouse.io) or paste the company into Claude or ChatGPT and ask for their likely ATS slug.

## Tuning the Claude rating prompt

The rating prompt in `job_radar.py` controls how Claude scores each job. Find the section that starts with `"Perfect Fit" = 90-100%` and edit the tier definitions and hard disqualifiers to match your situation.

For example you can:
- Change which industries count as Perfect Fit vs Good Fit
- Add or remove hard disqualifiers (e.g. company size, specific platforms required)
- Add companies you have already applied to so they get skipped automatically

The `SETUP.txt` file includes a ready-made prompt to paste into Claude or ChatGPT that walks you through tuning the rating logic for your specific background.

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

## License

MIT + Commons Clause. Free to use for personal job searching. Reach out before building anything commercial on top of it — see `LICENSE` for details.
