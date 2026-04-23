# lazypaper

Repository: [github.com/FinbarArgus/lazypaper](https://github.com/FinbarArgus/lazypaper).

Daily email with up to **`PAPERS_PER_DAY`** journal articles (one HTML digest per run) sampled from your feeds. Articles are scored against weighted keyword phrases in `config.py` (repository root); each phrase is matched in the **title, abstract, author list, and journal name** (case-insensitive), then one or more picks use **softmax-weighted randomness** so better matches are preferred but not deterministic. If fewer than `PAPERS_PER_DAY` unsent articles exist, the email contains whatever is available. Already-sent articles are stored in a repo-local SQLite database file, **`sent_emails.db`**, which GitHub Actions commits back to your fork after each run.

## Layout

| Path | Role |
|------|------|
| `config.py` | User settings: recipient, `SCHEDULE_*`, `PAPERS_PER_DAY`, `INTERESTS`, `EXCLUSIONS`, `SOURCES` (at repository root) |
| `src/lazypaper/` | Python package: `main.py`, `fetcher.py`, `scorer.py`, `emailer.py`, `sent_store.py`, `cfg.py` (loads root `config.py`) |
| `src/lazypaper/__main__.py` | Entry for `python -m lazypaper` |
| `sent_emails.db` | Local SQLite sent-history store; created automatically on first successful send and committed back to your fork |
| `requirements.txt` | Pip dependencies (run from repo root) |
| `pyproject.toml` | Pytest options (`[tool.pytest]`: `pythonpath`, markers; used locally and in CI) |
| `tests/` | Network smoke tests and mocked pipeline (see *Tests* below) |
| `scripts/check_domains.py` | DNS checks for mail domains and RSS/API hosts (runs in GitHub Actions before send) |
| `.github/workflows/daily_email.yml` | Scheduled run (and optional manual); the `on.schedule` `cron` must match `SCHEDULE_CRON` in the root `config.py` **(does not run pytest)** |
| `.github/workflows/pytest.yml` | **Tests** — `pytest` on push/PR to `main`/`master`, and manual *Run workflow* |
| `.github/workflows/test_paper_email.yml` | Manual “test email” run only |

## What you need

1. Your own fork of this repository. The intended setup is: fork it, edit `config.py`, remove or clear sent\_emails.db and run the workflows from your fork.
2. A [Resend](https://resend.com) account and API key. Each user needs their **own** Resend account; this repository does not share a central sender account.
3. **A Resend-verified sending domain.** In the Resend dashboard, **Domains → Add Domain**, then add the SPF/DKIM DNS records they show and wait for verification. Without this, sending to any address that isn't the email you registered with Resend will fail with `The domain is invalid`.
4. GitHub Actions secrets in **your fork**: **`RESEND_API_KEY`** (required), **`RESEND_FROM`** (strongly recommended, e.g. `LazyPaper <you@yourdomain.com>`; see Resend’s domain step above).

## Fork Setup

1. Fork this repository to your own GitHub account.
2. Clone your fork locally and edit **`config.py`** with your recipient email, schedule, interests, exclusions, and sources.
3. Run the bootstrap command from the repo root:

```bash
./scripts/bootstrap.sh
```

4. The bootstrap script validates **`config.py`**, syncs **`.github/workflows/daily_email.yml`** to `SCHEDULE_CRON`, sets GitHub Actions secrets for **`RESEND_API_KEY`**, **`RESEND_FROM`**, and optional **`LAZYPAPER_TO`**, commits the config/workflow changes, pushes them to your fork, and triggers the test workflow unless you pass `--skip-test`.
5. On the first successful test or scheduled run, the workflow creates **`sent_emails.db`** and commits it back to your fork.

### Bootstrap Prerequisites

- `gh` must be installed and authenticated with `gh auth login`.
- The current checkout must point at a GitHub repo you can write to, typically your fork.
- `git user.name` and `git user.email` must be configured so bootstrap can commit the workflow/config updates.
- You need your own Resend credentials ready before running bootstrap.

### Bootstrap Options

```bash
./scripts/bootstrap.sh --dry-run
./scripts/bootstrap.sh --skip-test
```

`--dry-run` shows what bootstrap would do without changing GitHub or git state. `--skip-test` leaves setup in place without triggering the manual test email workflow.

## Schedule

**You choose when the daily run fires** by setting **`SCHEDULE_MINUTE_UTC`** and **`SCHEDULE_HOUR_UTC`** in **`config.py`** at the repository root (24-hour **UTC**). The constant **`SCHEDULE_CRON`** is derived from them.

GitHub Actions cannot read that file for the schedule trigger, so the bootstrap command keeps the `cron` line under `on.schedule` in **`.github/workflows/daily_email.yml`** in sync with `SCHEDULE_CRON`. If you change the schedule later, rerun `./scripts/bootstrap.sh`.

**Example:** the defaults are **0** minute, **16** hour UTC, i.e. **16:00 UTC**, which is **04:00** New Zealand Standard Time (NZST, UTC+12) or **05:00** local during **NZDT** (UTC+13).

To **check that email works** without waiting for the schedule, use **Actions → Test paper email → Run workflow** (same behaviour as a scheduled run, including updating `sent_emails.db`). From a machine with the [GitHub CLI](https://cli.github.com/):

```bash
gh workflow run test_paper_email.yml
```

You can also use **Actions → Daily paper email → Run workflow**; it does the same job on demand.

Before each send, workflows run **`scripts/check_domains.py`**, which checks that recipient/`from` email domains have MX (or A/AAAA as implicit MX) and that every RSS/API hostname in `SOURCES` resolves. If something fails, the job stops with a short message pointing at `config.py` or secrets (`RESEND_FROM`, `LAZYPAPER_TO`). It also prints a warning if `From` is still Resend's sandbox `onboarding@resend.dev`, because that path will hit the Resend error below unless the recipient matches your Resend account email. You can run the same check locally after `pip install -r requirements.txt`: `python scripts/check_domains.py` (optional env vars as in CI).

## Troubleshooting

- **`resend.exceptions.ValidationError: The domain is invalid`** — Resend refused the `From` address. Either verify your own domain in the Resend dashboard and set the **`RESEND_FROM`** secret to a sender on that domain (e.g. `LazyPaper <news@your-domain.com>`), or make sure the recipient (`RECIPIENT_EMAIL` in `config.py`, or the `LAZYPAPER_TO` secret/env var) is exactly the email you registered with Resend and leave the default `onboarding@resend.dev` sender. If logs showed `from=''`, **`RESEND_FROM` was set but empty** (GitHub still injects the variable); the app now treats blank `RESEND_FROM` / `LAZYPAPER_TO` like unset and falls back to `config.py` defaults.
- **`RESEND_API_KEY is not set`** — Add the `RESEND_API_KEY` GitHub Actions secret (and/or `export` it locally).
- **DNS/feed errors printed by `scripts/check_domains.py`** — Fix the offending RSS URL in `SOURCES` or the email in `config.py` / the secret it names.
- **Sent history was not saved** — Ensure GitHub Actions in your fork has permission to write to the repository contents; the workflow commits `sent_emails.db` back to your default branch after a successful run.

## Customise

- **`config.py`** (repository root) — recipient email, **`SCHEDULE_MINUTE_UTC`** and **`SCHEDULE_HOUR_UTC`** (UTC; keep `.github/workflows/daily_email.yml` in sync, see *Schedule* above), **`PAPERS_PER_DAY`** (how many distinct papers in each daily email), `INTERESTS` weights, **`EXCLUSIONS`** (phrases to drop when they appear in the abstract or in keyword/tag data from the feed), `SOURCES`, and `SELECTION_TEMPERATURE` (lower = pick closer to the top score more often in each draw). Each source is either an RSS URL (`rss`) or a Europe PMC search (`europepmc_query`, e.g. `ISSN:1742-5689`) when the publisher feed is unreliable. Values of `PAPERS_PER_DAY` less than 1 are treated as 1.
- **`LAZYPAPER_TO`** — optional environment variable to override the recipient (defaults to `RECIPIENT_EMAIL` in `config.py`).

## Tests

**GitHub Actions → Tests** (workflow [`pytest.yml`](.github/workflows/pytest.yml)) runs `pytest` on pushes and pull requests to `main` or `master`, and you can run it on demand with **Actions → Tests → Run workflow** (or `gh workflow run pytest.yml` with the [GitHub CLI](https://cli.github.com/)). It is separate from the **Daily paper email** job (the daily schedule does not run the test suite). The tests call your public `SOURCES` over the network and do not send email or write the local sent-history store (the pipeline test mocks the sent-store and Resend path).

## Local run

From the repository root (so `PYTHONPATH=src` resolves to `src/lazypaper` as the `lazypaper` package):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src

# Option A: put secrets in .env (recommended for local full-pipeline runs)
cat > .env <<'EOF'
RESEND_API_KEY=re_...
RESEND_FROM='LazyPaper <onboarding@resend.dev>'
# optional: override recipient instead of using RECIPIENT_EMAIL from config.py
# LAZYPAPER_TO='you@example.com'
EOF

# Option B: export env vars directly instead of using .env
# export RESEND_API_KEY=re_...
# export RESEND_FROM='LazyPaper <onboarding@resend.dev>'

# Optional: run the same domain/feed validation step as CI
python scripts/check_domains.py

# Full local pipeline run, including real email send if secrets are valid
python -m lazypaper
```

## Licence

MIT — use and adapt freely.
