# Job Search Autopilot

A personal job search automation tool — and a practical introduction to vibe coding.

This project does two things. It runs every morning, searches 12 job sources, rates every listing with Claude AI, and emails you a ranked digest. And it's designed so that anyone — developer or not — can pick it up, describe what they want to an AI, and make it their own without writing code from scratch.

If you're job hunting, it saves you hours of manual searching. If you're new to AI-assisted development, it's a real working project you can learn on.

## Screenshots

**Dashboard**
<img width="1260" height="1265" alt="Kanban board showing job pipeline" src="https://github.com/user-attachments/assets/9c8fb520-2f11-40e9-a718-ae59daeab776" />

**Health tab**
<img width="1268" height="1230" alt="Run history and source coverage" src="https://github.com/user-attachments/assets/55dcd4e5-2989-49d3-808f-cee621c99720" />

**Skipped jobs**
<img width="1244" height="1262" alt="Auto-filtered jobs available for audit" src="https://github.com/user-attachments/assets/5501d01e-d704-4d52-9410-c87641cb9d55" />

**Example email digest**
<img width="2017" height="1199" alt="Daily email digest sorted by tier" src="https://github.com/user-attachments/assets/9432d4f5-86ae-4c44-8317-69df992a1a17" />

**Console output**
<img width="2550" height="1392" alt="Console output during a radar run" src="https://github.com/user-attachments/assets/f126e80a-4b7a-4d2b-adfa-76faf148a652" />

## What it does

- Searches 12 sources: ATS direct (Greenhouse/Lever/Ashby), Adzuna, LinkedIn, Brave, Tavily, WeWorkRemotely, Jobicy, Himalayas, Remotive, USAJobs, UltiPro/UKG, RemoteOK
- Filters out non-US roles, onsite roles outside your metro, below-salary-floor postings, staffing agencies, and noise pages
- Rates each job with Claude AI (Perfect Fit / Good Fit / Worth a Look / Skip) based on your profile
- Emails a daily digest sorted by tier
- Tracks your pipeline on a Kanban dashboard (Reviewing → Applied → Interviewing)

## Making it yours — vibe coding with AI

This tool is built to be customized. The filters, search queries, company list, and rating logic are all plain text or simple Python lists — readable and editable even if you are not a developer.

The fastest way to personalize it is to upload the files directly into Claude or ChatGPT and describe what you want in plain English. You do not need to understand every line of code. Just tell the AI what to change and it handles the syntax. This is vibe coding — you drive with plain English, the AI does the editing.

### How to do it

1. Go to [claude.ai](https://claude.ai) or [chatgpt.com](https://chatgpt.com)
2. Upload `job_radar.py` and `config.example.py` as attachments
3. Paste one of the prompts below with your details filled in
4. Copy the updated code back into your files and run it

You can do multiple rounds — start with the basics (profile, city, titles) and iterate from there. The AI can also help you debug errors, add new features, or explain what any part of the code does.

**Debugging tip:** If something breaks, paste the full error message plus the last 20 lines of console output into Claude or ChatGPT. You do not need to understand the error yourself — just describe what you were trying to do when it happened.

### Example prompts

**Set up for your role and location:**
```
I've attached job_radar.py and config.example.py. I'm a [your role] looking
for [target roles] in the [your city] area. Can you:
- Update TARGET_TITLES for my role type
- Set LOCAL_METRO_TERMS to my metro (city and nearby suburbs: [list them])
- Fill in all the search query lists with my actual target titles and industry
- Rewrite the PROFILE block for my background: [brief summary]
- Rewrite the Claude rating prompt tier definitions for my situation
```

**Add hard filters:**
```
I want to automatically skip jobs that mention [thing you hate], [industry
you don't want], and any contract positions. Can you add these to
HARD_DISQUALIFIERS in job_radar.py and explain what each one does?
```

**Build your company watchlist:**
```
Can you help me find the Greenhouse, Lever, and Ashby ATS slugs for these
companies and add them to the COMPANIES list in config.example.py: [list]
```

**Tune the rating prompt:**
```
The Claude rating prompt in job_radar.py is generic. I'm a [your role].
Can you rewrite the Perfect Fit, Good Fit, Worth a Look, and Skip tier
definitions for my situation? My target roles are [roles]. My core
strengths are [strengths]. Things I won't do: [list].
```

**Debug a crash:**
```
I ran python scripts/job_radar.py --run and got this error:
[paste the full error message]

Here is the last 20 lines of console output:
[paste console output]

What is wrong and how do I fix it?
```

**Debug quiet days (no jobs in the email):**
```
The radar ran and sent a quiet day email — 0 jobs made it through. Here
is the filter breakdown from the console output:
[paste the filter breakdown lines]

My target roles are [your roles]. My location is remote nationwide OR
on-site in [your city]. What is likely causing everything to be filtered?
```

The `SETUP.txt` file has more detailed prompts for each specific part.

## What you can customize

### In `config.py` (your personal file, never committed to GitHub)

**`PROFILE`** — the most important thing to personalize. Claude reads this when rating every single job. Write it like a concise professional summary: your current role, your background, what you are targeting, your strengths, and your hard constraints (location, salary, types of work you will not do). The more specific you are, the better the ratings.

**`MIN_SALARY`** — your salary floor as a plain number (e.g. `120000` for $120K). Jobs with a confirmed range entirely below this are filtered before Claude sees them. Jobs with no salary listed always pass through.

**`LOCAL_METRO_TERMS`** — your city and surrounding suburb names. The radar uses this to identify local hybrid and onsite roles and show them in a separate section of your email. Leave it empty if you only want remote roles.

**`COMPANIES`** — the direct ATS company watchlist. The radar checks Greenhouse, Lever, and Ashby job boards for every company in this list on every run. See [Adding companies](#adding-companies-to-the-ats-list) below.

**`VACATION_START / VACATION_END`** — set both to past dates if you are not on vacation. During vacation the radar buffers results and sends one digest when you return.

**Search queries** (`ADZUNA_QUERIES`, `BRAVE_QUERIES`, `TAVILY_QUERIES`, `LI_REMOTE_QUERIES`, `LI_LOCAL_QUERIES`, `HIMALAYAS_QUERIES`, `REMOTIVE_QUERIES`, `JOBICY_QUERIES`) — tailor these to your exact job titles and industry keywords. All query lists ship with `[Your Role]` and `[Your Industry]` placeholders.

### In `job_radar.py`

**`TARGET_TITLES`** — keyword list inside `search_ats_companies()` that controls which ATS job titles are considered relevant. Anything that does not match at least one keyword is dropped before any other processing. Ships with PM/PO/BA titles as examples — update this for your role type.

**`HARD_DISQUALIFIERS`** — phrases that auto-skip a job before it reaches Claude. Use this for things you are 100% certain you never want: specific industries, contract-only language, unwanted tech stacks.

**`_COMPANY_PREFILTER`** — staffing agencies and job aggregators to block by company name. Add any agencies you keep seeing in your results.

**`SALARY_FLOOR_EXEMPT`** — companies you know pay well above your floor even when a search snippet shows a misleadingly low number. Add employers in your target industry where you trust the compensation.

**`_URL_CITY_RE` and `_LOC_CITY_RE`** — two regex lists that catch onsite roles outside your area. Pre-loaded with major US metros and international cities. Remove any cities within your commutable area.

**Claude rating prompt** — the tier definitions and rules Claude uses to score every job. Find the section starting with `90-100%` in `job_radar.py`. Edit this in plain English to describe your situation. Claude follows this literally, so specificity pays off here more than anywhere else.

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
# Edit scripts/config.py — use the AI prompts above to fill it in quickly
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

Getting all the keys takes about 15 minutes. Here's exactly where to go for each one.

### Anthropic (Claude AI) — required

Used to rate every job. The only paid service — costs roughly $1–5/month at normal usage.

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Create an account and add a payment method (no subscription — pay per use)
3. Go to **API Keys** in the left sidebar → **Create Key**
4. Copy the key — it starts with `sk-ant-`

### Brave Search — required

Used to search the web for job postings. Free tier is plenty.

1. Go to [api.search.brave.com](https://api.search.brave.com)
2. Click **Get Started** → create a free account
3. Go to **API Keys** → **Create API Key** → select the **Free** plan (2,000 req/month)
4. Copy the key — it starts with `BSA`

### Tavily — required

A second search engine used as a backup to Brave. Free tier is plenty.

1. Go to [app.tavily.com](https://app.tavily.com)
2. Sign up for a free account
3. Your API key is shown on the dashboard immediately after signup
4. Copy the key — it starts with `tvly-`

### Adzuna — required

A job board API that returns structured listings with salary data. Completely free.

1. Go to [developer.adzuna.com](https://developer.adzuna.com)
2. Click **Register** → create a free account
3. Go to **Dashboard** → **API Access Details**
4. Copy both your **App ID** and **App Key** — you need both

### Gmail App Password — required

The radar sends your daily email via Gmail. You need an App Password, not your regular login password. App Passwords are 16-character codes that let apps access your Gmail without exposing your main password.

**Before you start:** your Google account must have 2-Step Verification enabled.

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
   (or: Google Account → Security → 2-Step Verification → scroll to App passwords)
2. Under **App name**, type something like `Job Radar`
3. Click **Create**
4. Copy the 16-character password shown — it looks like `xxxx xxxx xxxx xxxx`
5. Use your Gmail address as `GMAIL_ADDRESS` and this password as `GMAIL_APP_PW`

> If you don't see the App passwords option, make sure 2-Step Verification is turned on first at [myaccount.google.com/security](https://myaccount.google.com/security).

### USAJobs — optional

Only needed if you want federal government job listings. Skip this if you don't.

1. Go to [developer.usajobs.gov](https://developer.usajobs.gov)
2. Click **Request an API Key** and fill in the form (approved instantly)
3. You'll receive the key by email
4. Set both `USAJOBS_API_KEY` (the key) and `USAJOBS_EMAIL` (the email you registered with)

## Adding companies to the ATS list

The `COMPANIES` list in `config.py` is the most powerful part of the tool. Direct ATS access means you see new postings the moment they go live, often before they appear on any aggregator.

### Finding a company's slug

| ATS | URL pattern | Slug |
|---|---|---|
| Greenhouse | `boards.greenhouse.io/stripe` | `stripe` |
| Lever | `jobs.lever.co/plaid` | `plaid` |
| Ashby | `jobs.ashbyhq.com/mercury` | `mercury` |

The radar tries all three APIs for each slug automatically — you do not need to know which ATS a company uses.

### Tips for finding slugs

- Try the company name lowercased with no spaces first (`wealthsimple`, `nerdwallet`)
- If that returns nothing, try with hyphens (`cash-app`)
- Browse `boards.greenhouse.io` to search Greenhouse companies directly
- Ask Claude: "What is the Greenhouse/Lever/Ashby ATS slug for [Company Name]?"

## Project structure

```text
job-search-profile/
├── scripts/
│   ├── job_radar.py        ← main radar (run this daily)
│   ├── dashboard.py        ← Flask Kanban dashboard
│   ├── radar_shared.py     ← shared utilities (IDs, normalization, validation)
│   └── config.py           ← your personal config (gitignored)
├── config.example.py       ← copy to scripts/config.py and fill in
├── .env.example            ← copy to .env and fill in API keys
├── requirements.txt
├── SETUP.txt               ← full setup guide with customization prompts
├── README.md
├── LICENSE
└── output/
    └── job-radar/          ← runtime files (gitignored)
```

## Output files

All runtime files live in `output/job-radar/` (gitignored). The radar keeps only the last 3 runs and prunes automatically.

| File | Purpose |
|---|---|
| `*-jobs.json` | Rated jobs for the dashboard board tab |
| `*-skipped.json` | Skipped jobs for the dashboard skipped tab |
| `*-report.md` | Email report attachment |
| `.seen.json` | Deduplication history (60-day rolling window) |
| `board_state.json` | Dashboard card positions and notes |
| `radar_runs.db` | SQLite run history for the Health tab |
| `debug_job_log.txt` | Full job log for debugging source quality |

## License

MIT + Commons Clause. Free to use for personal job searching. Reach out before building anything commercial on top of it. See `LICENSE` for details.
