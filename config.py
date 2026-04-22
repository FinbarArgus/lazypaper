"""Edit INTERESTS, schedule, and SOURCES here."""

RECIPIENT_EMAIL = "farg967@aucklanduni.ac.nz"

# When to run the daily email in GitHub Actions: minute and hour in **UTC** (0–59 / 0–23).
# Example: 16, 0 → 16:00 UTC, which is 04:00 the same calendar day in NZST (UTC+12) or
# 05:00 local during NZDT (UTC+13). Change these to your preferred time, then set the
# `on.schedule` cron in `.github/workflows/daily_email.yml` to the same as `SCHEDULE_CRON` below.
SCHEDULE_MINUTE_UTC = 0
SCHEDULE_HOUR_UTC = 16
SCHEDULE_CRON = f"{SCHEDULE_MINUTE_UTC} {SCHEDULE_HOUR_UTC} * * *"

# Keyword phrases -> weight. Higher weight = stronger match. Matching is case-insensitive and
# counts occurrences in the article title, abstract, author list, and journal name.
INTERESTS: dict[str, int] = {
    "autonomic neuroscience": 5,
    "microvasculature": 5,
    "uncertainty quantification": 3,
    "digital twin": 3,
    "computational biology": 3,
    "parameter estimation": 3,
    "Bayesian": 3,
    "cardiovascular": 2,
    "sensitivity analysis": 2,
    "neuroscience": 3,
    "physiology": 3,
    "mathematical model": 2,
    "identifiability": 5,
    "systems biology": 2,
    "mathematical biology": 2,
}

# Phrases: if any appear in the abstract or in feed keyword/tag fields, the article is skipped.
# Matching is case-insensitive substring match.
EXCLUSIONS: list[str] = [
    "Immune system",
]

# Each entry is one RSS/Atom feed. Add or remove feeds as you like.
SOURCES: list[dict[str, str]] = [
    {"journal": "Nature (Physiology)", "rss": "https://www.nature.com/subjects/physiology.rss"},
    {"journal": "Nature (Neuroscience)", "rss": "https://www.nature.com/subjects/neuroscience.rss"},
    {"journal": "Science", "rss": "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=science"},
    {
        "journal": "PLOS Computational Biology",
        "rss": "https://journals.plos.org/ploscompbiol/feed/atom",
    },
    {
        "journal": "Journal of The Royal Society Interface",
        # Publisher RSS is often blocked (Cloudflare); Europe PMC mirrors metadata by ISSN.
        "europepmc_query": "ISSN:1742-5689",
    },
    {
        "journal": "Bulletin of Mathematical Biology",
        "rss": "https://link.springer.com/search.rss?facet-journal-id=11538",
    },
    {"journal": "IEEE JBHI", "rss": "https://ieeexplore.ieee.org/rss/TOC6221020.XML"},
    {
        "journal": "The Journal of Physiology",
        "rss": "https://physoc.onlinelibrary.wiley.com/feed/14697793/most-recent",
    },
    {
        "journal": "AJP Heart and Circulatory Physiology",
        "rss": "https://journals.physiology.org/action/showFeed?type=etoc&feed=rss&jc=ajpheart",
    },
    {
        "journal": "Europe PMC (General Physiology)",
        "europepmc_query": '(physiology OR "cardiovascular physiology" OR "autonomic neuroscience") AND SRC:MED',
    },
    {
        "journal": "Europe PMC (Neuroscience)",
        "europepmc_query": '(neuroscience OR neurophysiology OR "autonomic nervous system") AND SRC:MED',
    },
    {
        "journal": "Europe PMC (Math/Comp Bio)",
        "europepmc_query": '("mathematical model" OR "systems biology" OR "parameter estimation" OR "identifiability") AND SRC:MED',
    },
    {
        "journal": "Europe PMC (Biomechanics/Hemodynamics)",
        "europepmc_query": '(microvasculature OR hemodynamics OR "blood flow") AND SRC:MED',
    },
    {
        "journal": "Europe PMC (Cardiovascular + Hemodynamics)",
        "europepmc_query": '("cardiovascular physiology" OR hemodynamics OR "blood flow" OR microvasculature) AND SRC:MED',
    },
    {
        "journal": "Europe PMC (Autonomic + Neurophysiology)",
        "europepmc_query": '("autonomic nervous system" OR "autonomic neuroscience" OR neurophysiology) AND SRC:MED',
    },
    {
        "journal": "Europe PMC (UQ + Parameter Estimation)",
        "europepmc_query": '("uncertainty quantification" OR "parameter estimation" OR identifiability OR Bayesian) AND SRC:MED',
    },
    {
        "journal": "Europe PMC (Systems/Math Biology)",
        "europepmc_query": '("systems biology" OR "mathematical biology" OR "mathematical model" OR "computational biology") AND SRC:MED',
    },
    {
        "journal": "Europe PMC (Mechanistic Modeling)",
        "europepmc_query": '("mechanistic model" OR "differential equation" OR "inverse problem") AND SRC:MED',
    },
]

# Softmax temperature for weighted random pick (lower = more greedy).
SELECTION_TEMPERATURE = 0.5

# How many distinct papers to include in one daily email (and record as sent at once).
PAPERS_PER_DAY = 1

# Per-day config: keys are lowercase weekday names ("monday" … "sunday") or "default".
# The entry whose key matches today's UTC weekday is used; falls back to "default" if not found.
#
# year_min / year_max  — only consider papers published in this range (None = no limit).
# extra_weights        — additional scoring signals on top of INTERESTS keyword matching.
#   Supported keys:
#     "citations"      — log(1 + citation_count) × weight  (Europe PMC sources only; 0 for RSS)
#     "recency"        — max(0, 10 − years_ago) × weight   (all sources)
#     "low_page_count" — max(0, 20 − page_count) × weight  (Europe PMC sources only; 0 for RSS)
DAILY_SCHEDULE: dict = {
    "monday": {
        "year_min": None,
        "year_max": None,
        "extra_weights": {},
    },
    "tuesday": {
        "year_min": 1950,
        "year_max": 2010,
        "extra_weights": {"citations": 2},
    },
    "wednesday": {
        "year_min": 1990,
        "year_max": 2020,
        "extra_weights": {"citations": 1, "low_page_count": 2},
    },
    "thursday": {
        "year_min": None,
        "year_max": None,
        "extra_weights": {"recency": 2},
    },
    "friday": {
        "year_min": 2000,
        "year_max": None,
        "extra_weights": {"citations": 2},
    },
    # Example: prefer recent, highly-cited papers on Mondays:
    # "monday": {
    #     "year_min": 2021,
    #     "year_max": None,
    #     "extra_weights": {"citations": 2, "recency": 1},
    # },
}
DEFAULT_RESEND_FROM = "LazyPaper <onboarding@resend.dev>"
