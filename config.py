"""Edit INTERESTS and SOURCES here."""

RECIPIENT_EMAIL = "finbar.argus@auckland.ac.nz"

# Higher weight = stronger match when the phrase appears in title or abstract.
INTERESTS: dict[str, int] = {
    "autonomic neuroscience": 5,
    "microvasculature": 5,
    "parameter identifiability": 5,
    "uncertainty quantification": 5,
    "digital twin": 4,
    "computational biology": 3,
    "parameter estimation": 3,
    "Bayesian": 3,
    "cardiovascular": 3,
    "sensitivity analysis": 3,
    "neuroscience": 3,
    "physiology": 3,
    "mathematical model": 2,
    "identifiability": 4,
    "systems biology": 2,
    "mathematical biology": 2,
}

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
]

# Softmax temperature for weighted random pick (lower = more greedy).
SELECTION_TEMPERATURE = 0.5

# Optional override via env in CI: default Resend sandbox sender.
DEFAULT_RESEND_FROM = "LazyPaper <onboarding@resend.dev>"
