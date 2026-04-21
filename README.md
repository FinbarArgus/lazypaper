# lazypaper

Repository: [github.com/FinbarArgus/lazypaper](https://github.com/FinbarArgus/lazypaper).

Daily email with one journal article sampled from your feeds. Articles are scored against weighted keywords in `src/lazypaper/config.py`, then chosen with **softmax-weighted randomness** so the best matches are preferred but not deterministic. Already-sent articles are stored in `sent_articles.json` and skipped.

## What you need

1. A public GitHub repository named **lazypaper** (push this folder to it).
2. A [Resend](https://resend.com) account and API key.
3. GitHub Actions secrets on the repo:
   - **`RESEND_API_KEY`** — required.
   - **`RESEND_FROM`** — optional. Verified sender like `LazyPaper <papers@yourdomain.com>`. If omitted, the default in `src/lazypaper/config.py` is used (Resend’s onboarding address only works for testing to your own inbox).

## Schedule

The workflow runs daily at **16:00 UTC**, which is **04:00 New Zealand Standard Time (NZST, UTC+12)**. During **NZDT (UTC+13)** the same cron fires at **05:00** local time.

To **check that email works** without waiting for the schedule, use **Actions → Test paper email → Run workflow** (same behaviour as a scheduled run, including updating `sent_articles.json` if a paper was sent). From a machine with the [GitHub CLI](https://cli.github.com/):

```bash
gh workflow run test_paper_email.yml
```

You can also use **Actions → Daily paper email → Run workflow**; it does the same job on demand.

## Customise

- **`src/lazypaper/config.py`** — recipient email, `INTERESTS` weights, `SOURCES`, and `SELECTION_TEMPERATURE` (lower = pick closer to the top score more often). Each source is either an RSS URL (`rss`) or a Europe PMC search (`europepmc_query`, e.g. `ISSN:1742-5689`) when the publisher feed is unreliable.
- **`LAZYPAPER_TO`** — optional environment variable to override the recipient (defaults to `RECIPIENT_EMAIL` in `config.py`).

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src
export RESEND_API_KEY=re_...
# optional: export RESEND_FROM='LazyPaper <onboarding@resend.dev>'
python -m lazypaper
```

## Licence

MIT — use and adapt freely.
