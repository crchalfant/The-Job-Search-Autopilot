# The Job Search Autopilot

A configurable job search automation tool that aggregates listings from multiple sources, filters them against your criteria, rates them with AI, and surfaces the best opportunities.

---

## Project Structure

```
The-Job-Search-Autopilot/
├── scripts/
│   ├── job_radar.py        # Main pipeline (search → filter → rate → email)
│   ├── dashboard.py        # Local UI for reviewing and managing jobs
│   ├── radar_shared.py     # Shared core logic (IDs, normalization, API safety)
│   └── config.py           # Your personal configuration (gitignored)
│
├── output/
│   └── job-radar/          # Generated data (jobs, skipped, board state, DB)
│
├── config.example.py       # Template for user configuration
├── SETUP.txt               # Setup and configuration instructions
├── README.md               # Project documentation
└── LICENSE                 # License template
```

---

## Key Files

- **job_radar.py**  
  Runs the full job discovery pipeline and sends the daily digest.

- **dashboard.py**  
  Local dashboard for reviewing jobs, tracking applications, and managing workflow.

- **radar_shared.py**  
  Centralized shared logic used across the system:
  - job ID generation  
  - title normalization  
  - API request safety  
  - profile sanitization  

  This prevents duplication and keeps the radar and dashboard in sync.

---

## Shared Core Module

`scripts/radar_shared.py` ensures consistency across the system.

Do not duplicate logic from this file. Always import from it.

---

## Contact

GitHub: https://github.com/crchalfant  
Email: Casey.Chalfant@protonmail.com
