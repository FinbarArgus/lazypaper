# lazypaper

Repository: [github.com/FinbarArgus/lazypaper](https://github.com/FinbarArgus/lazypaper).

Daily email with up to **`PAPERS_PER_DAY`** journal articles (one HTML digest per run) sampled from your feeds. Articles are scored against weighted keywords in `config.py` (repository root), then chosen with **softmax-weighted randomness** so the best matches are preferred but not deterministic. If fewer than `PAPERS_PER_DAY` unsent articles exist, the email contains whatever is available. Already-sent articles are stored in `sent_articles.json` (repository root) and skipped.

## Layout

| Path | Role |
|------|------|
| `config.py` | User settings: recipient, `SCHEDULE_*`, `PAPERS_PER_DAY`, `INTERESTS`, `SOURCES` (at repository root) |
| `src/lazypaper/` | Python package: `main.py`, `fetcher.py`, `scorer.py`, `emailer.py`, `cfg.py` (loads root `config.py`) |
| `src/lazypaper/__main__.py` | Entry for `python -m lazypaper` |
| `sent_articles.json` | Tracked at repo root; updated by the Actions workflows after a send |
| `requirements.txt` | Pip dependencies (run from repo root) |
| `.github/workflows/daily_email.yml` | Scheduled run (and optional manual); the `on.schedule` `cron` must match `SCHEDULE_CRON` in the root `config.py` |
| `.github/workflows/test_paper_email.yml` | Manual “test email” run only |

## What you need

1. A public GitHub repository named **lazypaper** (push this folder to it).
2. A [Resend](https://resend.com) account and API key.
3. GitHub Actions secrets on the repo:
   - **`RESEND_API_KEY`** — required.
   - **`RESEND_FROM`** — optional. Verified sender like `LazyPaper <papers@yourdomain.com>`. If omitted, the default in `config.py` is used (Resend’s onboarding address only works for testing to your own inbox).

## Schedule

**You choose when the daily run fires** by setting **`SCHEDULE_MINUTE_UTC`** and **`SCHEDULE_HOUR_UTC`** in **`config.py`** at the repository root (24-hour **UTC**). The constant **`SCHEDULE_CRON`** is derived from them.

GitHub Actions cannot read that file for the schedule trigger, so you must also set the `cron` line under `on.schedule` in **`.github/workflows/daily_email.yml`** to the same value as `SCHEDULE_CRON` (e.g. after editing the config, print it with `PYTHONPATH=src` from the repo root: `python -c "from lazypaper.cfg import SCHEDULE_CRON; print(SCHEDULE_CRON)"` and paste the result into the workflow).

**Example:** the defaults are **0** minute, **16** hour UTC, i.e. **16:00 UTC**, which is **04:00** New Zealand Standard Time (NZST, UTC+12) or **05:00** local during **NZDT** (UTC+13).

To **check that email works** without waiting for the schedule, use **Actions → Test paper email → Run workflow** (same behaviour as a scheduled run, including updating `sent_articles.json` if a paper was sent). From a machine with the [GitHub CLI](https://cli.github.com/):

```bash
gh workflow run test_paper_email.yml
```

You can also use **Actions → Daily paper email → Run workflow**; it does the same job on demand.

## Customise

- **`config.py`** (repository root) — recipient email, **`SCHEDULE_MINUTE_UTC`** and **`SCHEDULE_HOUR_UTC`** (UTC; keep `.github/workflows/daily_email.yml` in sync, see *Schedule* above), **`PAPERS_PER_DAY`** (how many distinct papers in each daily email), `INTERESTS` weights, `SOURCES`, and `SELECTION_TEMPERATURE` (lower = pick closer to the top score more often in each draw). Each source is either an RSS URL (`rss`) or a Europe PMC search (`europepmc_query`, e.g. `ISSN:1742-5689`) when the publisher feed is unreliable. Values of `PAPERS_PER_DAY` less than 1 are treated as 1.
- **`LAZYPAPER_TO`** — optional environment variable to override the recipient (defaults to `RECIPIENT_EMAIL` in `config.py`).

## Local run

From the repository root (so `PYTHONPATH=src` resolves to `src/lazypaper` as the `lazypaper` package):

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
