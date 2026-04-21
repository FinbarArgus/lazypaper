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
| `scripts/check_domains.py` | DNS checks for mail domains and RSS/API hosts (runs in GitHub Actions before send) |
| `.github/workflows/daily_email.yml` | Scheduled run (and optional manual); the `on.schedule` `cron` must match `SCHEDULE_CRON` in the root `config.py` |
| `.github/workflows/test_paper_email.yml` | Manual “test email” run only |

## What you need

1. A public GitHub repository named **lazypaper** (push this folder to it).
2. A [Resend](https://resend.com) account and API key.
3. **A Resend-verified sending domain.** In the Resend dashboard, **Domains → Add Domain**, then add the SPF/DKIM DNS records they show and wait for verification. Without this, sending to any address that isn't the email you registered with Resend will fail with `The domain is invalid`.
4. GitHub Actions secrets on the repo:
   - **`RESEND_API_KEY`** — required.
   - **`RESEND_FROM`** — strongly recommended. Use a sender on your verified domain, e.g. `LazyPaper <papers@yourdomain.com>`. If omitted, `config.py`'s default `LazyPaper <onboarding@resend.dev>` is used, which **only works when the recipient equals the email you signed up to Resend with**.

## Schedule

**You choose when the daily run fires** by setting **`SCHEDULE_MINUTE_UTC`** and **`SCHEDULE_HOUR_UTC`** in **`config.py`** at the repository root (24-hour **UTC**). The constant **`SCHEDULE_CRON`** is derived from them.

GitHub Actions cannot read that file for the schedule trigger, so you must also set the `cron` line under `on.schedule` in **`.github/workflows/daily_email.yml`** to the same value as `SCHEDULE_CRON` (e.g. after editing the config, print it with `PYTHONPATH=src` from the repo root: `python -c "from lazypaper.cfg import SCHEDULE_CRON; print(SCHEDULE_CRON)"` and paste the result into the workflow).

**Example:** the defaults are **0** minute, **16** hour UTC, i.e. **16:00 UTC**, which is **04:00** New Zealand Standard Time (NZST, UTC+12) or **05:00** local during **NZDT** (UTC+13).

To **check that email works** without waiting for the schedule, use **Actions → Test paper email → Run workflow** (same behaviour as a scheduled run, including updating `sent_articles.json` if a paper was sent). From a machine with the [GitHub CLI](https://cli.github.com/):

```bash
gh workflow run test_paper_email.yml
```

You can also use **Actions → Daily paper email → Run workflow**; it does the same job on demand.

Before each send, workflows run **`scripts/check_domains.py`**, which checks that recipient/`from` email domains have MX (or A/AAAA as implicit MX) and that every RSS/API hostname in `SOURCES` resolves. If something fails, the job stops with a short message pointing at `config.py` or secrets (`RESEND_FROM`, `LAZYPAPER_TO`). It also prints a warning if `From` is still Resend's sandbox `onboarding@resend.dev`, because that path will hit the Resend error below unless the recipient matches your Resend account email. You can run the same check locally after `pip install -r requirements.txt`: `python scripts/check_domains.py` (optional env vars as in CI).

## Troubleshooting

- **`resend.exceptions.ValidationError: The domain is invalid`** — Resend refused the `From` address. Either verify your own domain in the Resend dashboard and set the **`RESEND_FROM`** secret to a sender on that domain (e.g. `LazyPaper <news@your-domain.com>`), or make sure the recipient (`RECIPIENT_EMAIL` in `config.py`, or the `LAZYPAPER_TO` secret/env var) is exactly the email you registered with Resend and leave the default `onboarding@resend.dev` sender.
- **`RESEND_API_KEY is not set`** — Add the `RESEND_API_KEY` GitHub Actions secret (and/or `export` it locally).
- **DNS/feed errors printed by `scripts/check_domains.py`** — Fix the offending RSS URL in `SOURCES` or the email in `config.py` / the secret it names.

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
