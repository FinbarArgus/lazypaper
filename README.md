# lazypaper

Repository: [github.com/FinbarArgus/lazypaper](https://github.com/FinbarArgus/lazypaper).

Daily email with up to **`PAPERS_PER_DAY`** journal articles (one HTML digest per run) sampled from your feeds. Articles are scored against weighted keyword phrases in `config.py` (repository root); each phrase is matched in the **title, abstract, author list, and journal name** (case-insensitive), then one or more picks use **softmax-weighted randomness** so better matches are preferred but not deterministic. If fewer than `PAPERS_PER_DAY` unsent articles exist, the email contains whatever is available. Already-sent articles are stored using the **`DATABASE_URL`** secret (see *What you need*), or in a local **`sent_articles.json`** if you run without a database.

## Layout

| Path | Role |
|------|------|
| `config.py` | User settings: recipient, `SCHEDULE_*`, `PAPERS_PER_DAY`, `INTERESTS`, `EXCLUSIONS`, `SOURCES` (at repository root) |
| `src/lazypaper/` | Python package: `main.py`, `fetcher.py`, `scorer.py`, `emailer.py`, `sent_store.py`, `cfg.py` (loads root `config.py`) |
| `src/lazypaper/__main__.py` | Entry for `python -m lazypaper` |
| `sent_articles.json` | Optional local file when `DATABASE_URL` is unset (gitignored if you use it; not used in default GitHub Actions) |
| `scripts/schema_sent_postgres.sql` | Create the `sent_article` table (run once in Neon/Supabase/psql) |
| `scripts/migrate_sent_json_to_pg.py` | One-time import from `sent_articles.json` into Postgres |
| `requirements.txt` | Pip dependencies (run from repo root) |
| `scripts/check_domains.py` | DNS checks for mail domains and RSS/API hosts (runs in GitHub Actions before send) |
| `.github/workflows/daily_email.yml` | Scheduled run (and optional manual); the `on.schedule` `cron` must match `SCHEDULE_CRON` in the root `config.py` |
| `.github/workflows/test_paper_email.yml` | Manual “test email” run only |

## What you need

1. A public GitHub repository named **lazypaper** (push this folder to it).
2. A [Resend](https://resend.com) account and API key.
3. **A Resend-verified sending domain.** In the Resend dashboard, **Domains → Add Domain**, then add the SPF/DKIM DNS records they show and wait for verification. Without this, sending to any address that isn't the email you registered with Resend will fail with `The domain is invalid`.
4. **Where to store “already sent” (needs one URL, never commit it to git).** A free [Neon](https://neon.tech) database is enough:
   1. Sign up, create a project, open the **SQL Editor**.
   2. Paste the contents of [`scripts/schema_sent_postgres.sql`](scripts/schema_sent_postgres.sql) and run it.
   3. In Neon, copy the **connection string** (a URI that starts with `postgresql://` or `postgres://`). Add `?sslmode=require` at the end if the connection test fails.
   4. In GitHub: your repo **Settings → Secrets and variables → Actions → New repository secret** — name **`DATABASE_URL`**, value = that string.
5. **Other** Actions secrets: **`RESEND_API_KEY`** (required), **`RESEND_FROM`** (strongly recommended, e.g. `LazyPaper <you@yourdomain.com>`; see Resend’s domain step above).

## Schedule

**You choose when the daily run fires** by setting **`SCHEDULE_MINUTE_UTC`** and **`SCHEDULE_HOUR_UTC`** in **`config.py`** at the repository root (24-hour **UTC**). The constant **`SCHEDULE_CRON`** is derived from them.

GitHub Actions cannot read that file for the schedule trigger, so you must also set the `cron` line under `on.schedule` in **`.github/workflows/daily_email.yml`** to the same value as `SCHEDULE_CRON` (e.g. after editing the config, print it with `PYTHONPATH=src` from the repo root: `python -c "from lazypaper.cfg import SCHEDULE_CRON; print(SCHEDULE_CRON)"` and paste the result into the workflow).

**Example:** the defaults are **0** minute, **16** hour UTC, i.e. **16:00 UTC**, which is **04:00** New Zealand Standard Time (NZST, UTC+12) or **05:00** local during **NZDT** (UTC+13).

To **check that email works** without waiting for the schedule, use **Actions → Test paper email → Run workflow** (same behaviour as a scheduled run, including recording sends in PostgreSQL). From a machine with the [GitHub CLI](https://cli.github.com/):

```bash
gh workflow run test_paper_email.yml
```

You can also use **Actions → Daily paper email → Run workflow**; it does the same job on demand.

Before each send, workflows run **`scripts/check_domains.py`**, which checks that recipient/`from` email domains have MX (or A/AAAA as implicit MX) and that every RSS/API hostname in `SOURCES` resolves. If something fails, the job stops with a short message pointing at `config.py` or secrets (`RESEND_FROM`, `LAZYPAPER_TO`). It also prints a warning if `From` is still Resend's sandbox `onboarding@resend.dev`, because that path will hit the Resend error below unless the recipient matches your Resend account email. You can run the same check locally after `pip install -r requirements.txt`: `python scripts/check_domains.py` (optional env vars as in CI).

## Troubleshooting

- **`resend.exceptions.ValidationError: The domain is invalid`** — Resend refused the `From` address. Either verify your own domain in the Resend dashboard and set the **`RESEND_FROM`** secret to a sender on that domain (e.g. `LazyPaper <news@your-domain.com>`), or make sure the recipient (`RECIPIENT_EMAIL` in `config.py`, or the `LAZYPAPER_TO` secret/env var) is exactly the email you registered with Resend and leave the default `onboarding@resend.dev` sender. If logs showed `from=''`, **`RESEND_FROM` was set but empty** (GitHub still injects the variable); the app now treats blank `RESEND_FROM` / `LAZYPAPER_TO` like unset and falls back to `config.py` defaults.
- **`RESEND_API_KEY is not set`** — Add the `RESEND_API_KEY` GitHub Actions secret (and/or `export` it locally).
- **DNS/feed errors printed by `scripts/check_domains.py`** — Fix the offending RSS URL in `SOURCES` or the email in `config.py` / the secret it names.
- **Database connection errors** — Ensure `DATABASE_URL` in GitHub **Secrets** matches your Neon/Supabase string, the `sent_article` table exists (run [`scripts/schema_sent_postgres.sql`](scripts/schema_sent_postgres.sql)), and the database allows SSL connections from the internet (Neon/Supabase defaults do).

## Customise

- **`config.py`** (repository root) — recipient email, **`SCHEDULE_MINUTE_UTC`** and **`SCHEDULE_HOUR_UTC`** (UTC; keep `.github/workflows/daily_email.yml` in sync, see *Schedule* above), **`PAPERS_PER_DAY`** (how many distinct papers in each daily email), `INTERESTS` weights, **`EXCLUSIONS`** (phrases to drop when they appear in the abstract or in keyword/tag data from the feed), `SOURCES`, and `SELECTION_TEMPERATURE` (lower = pick closer to the top score more often in each draw). Each source is either an RSS URL (`rss`) or a Europe PMC search (`europepmc_query`, e.g. `ISSN:1742-5689`) when the publisher feed is unreliable. Values of `PAPERS_PER_DAY` less than 1 are treated as 1.
- **`LAZYPAPER_TO`** — optional environment variable to override the recipient (defaults to `RECIPIENT_EMAIL` in `config.py`).

**Local use without a database:** unset `DATABASE_URL` and the app will use a local [`sent_articles.json`](sent_articles.json) at the repo root (gitignored).

## Local run

From the repository root (so `PYTHONPATH=src` resolves to `src/lazypaper` as the `lazypaper` package):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src
export RESEND_API_KEY=re_...
# optional: export RESEND_FROM='LazyPaper <onboarding@resend.dev>'
# for Postgres (else sent_articles.json is used):
# export DATABASE_URL='postgresql://user:pass@host/db?sslmode=require'
python -m lazypaper
```

## Licence

MIT — use and adapt freely.
