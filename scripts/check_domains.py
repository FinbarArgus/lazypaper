#!/usr/bin/env python3
"""Validate mail-related domains (MX / implicit MX) and RSS feed hostnames (DNS). Exit 1 on failure."""

from __future__ import annotations

import importlib.util
import os
import sys
from email.utils import parseaddr
from pathlib import Path
from urllib.parse import urlparse

import dns.resolver
import dns.exception

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.py"
SRC_PATH = ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from lazypaper.local_env import load_local_env

load_local_env()


def _load_config():
    spec = importlib.util.spec_from_file_location("lazypaper_config", CONFIG_PATH)
    if spec is None or spec.loader is None:
        print(f"ERROR: Could not load {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _domain_from_email(addr: str) -> str | None:
    addr = (addr or "").strip()
    if not addr or "@" not in addr:
        return None
    dom = addr.rsplit("@", 1)[-1].strip().lower()
    return dom or None


def _from_header_addresses(header: str) -> list[str]:
    header = (header or "").strip()
    if not header:
        return []
    _, email = parseaddr(header)
    if email:
        return [email]
    return []


def _collect_mail_domains(config) -> list[tuple[str, str]]:
    """(label, domain) for clear error messages."""
    out: list[tuple[str, str]] = []

    def add(label: str, addr: str) -> None:
        dom = _domain_from_email(addr)
        if dom:
            out.append((label, dom))

    add("RECIPIENT_EMAIL (config.py)", config.RECIPIENT_EMAIL)

    for addr in _from_header_addresses(config.DEFAULT_RESEND_FROM):
        add("DEFAULT_RESEND_FROM (config.py)", addr)

    rf = os.environ.get("RESEND_FROM", "").strip()
    if rf:
        for addr in _from_header_addresses(rf):
            add("RESEND_FROM (GitHub secret / env)", addr)

    lt = os.environ.get("LAZYPAPER_TO", "").strip()
    if lt and "@" in lt:
        add("LAZYPAPER_TO (env)", lt)

    seen: set[str] = set()
    dedup: list[tuple[str, str]] = []
    for label, dom in out:
        if dom not in seen:
            seen.add(dom)
            dedup.append((label, dom))
    return dedup


def _collect_feed_hosts(config) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for src in config.SOURCES:
        journal = src.get("journal", "?")
        if src.get("rss"):
            host = urlparse(src["rss"]).hostname
            if host:
                out.append((f"RSS ({journal})", host.lower()))
        if src.get("europepmc_query"):
            out.append((f"Europe PMC API ({journal})", "www.ebi.ac.uk"))
    seen: set[str] = set()
    dedup: list[tuple[str, str]] = []
    for label, h in out:
        if h not in seen:
            seen.add(h)
            dedup.append((label, h))
    return dedup


def _mail_domain_ok(domain: str) -> str | None:
    """Return error message or None if OK (MX records or implicit MX via A/AAAA)."""
    try:
        answers = dns.resolver.resolve(domain, "MX")
        if len(answers) > 0:
            return None
    except dns.resolver.NXDOMAIN:
        return "domain does not exist (NXDOMAIN)"
    except dns.resolver.NoAnswer:
        pass
    except dns.resolver.LifetimeTimeout:
        return "DNS lookup timed out"
    except dns.exception.DNSException as e:
        return f"DNS error: {e}"

    for rtype in ("A", "AAAA"):
        try:
            ans = dns.resolver.resolve(domain, rtype)
            if len(ans) > 0:
                return None
        except dns.resolver.NXDOMAIN:
            return "domain does not exist (NXDOMAIN)"
        except dns.resolver.NoAnswer:
            continue
        except dns.resolver.LifetimeTimeout:
            return "DNS lookup timed out"
        except dns.exception.DNSException as e:
            return f"DNS error ({rtype}): {e}"

    return "no MX, A, or AAAA records (cannot receive mail)"


def _host_resolves(domain: str) -> str | None:
    """Return error message or None if hostname resolves."""
    for rtype in ("A", "AAAA"):
        try:
            ans = dns.resolver.resolve(domain, rtype)
            if len(ans) > 0:
                return None
        except dns.resolver.NXDOMAIN:
            return "hostname does not exist (NXDOMAIN)"
        except dns.resolver.NoAnswer:
            continue
        except dns.resolver.LifetimeTimeout:
            return "DNS lookup timed out"
        except dns.exception.DNSException as e:
            return f"DNS error ({rtype}): {e}"
    return "no A or AAAA records"


def main() -> int:
    if not CONFIG_PATH.is_file():
        print(f"ERROR: Missing {CONFIG_PATH}", file=sys.stderr)
        return 1

    config = _load_config()
    errors: list[str] = []

    print("Mail-related domains (must exist and accept mail per MX or A/AAAA fallback):\n")
    for label, dom in _collect_mail_domains(config):
        err = _mail_domain_ok(dom)
        if err:
            msg = f"INVALID  {dom}  ({label}): {err}"
            print(msg)
            errors.append(msg)
        else:
            print(f"OK       {dom}  ({label})")

    print("\nFeed / API hostnames (must resolve in DNS):\n")
    for label, host in _collect_feed_hosts(config):
        err = _host_resolves(host)
        if err:
            msg = f"INVALID  {host}  ({label}): {err}"
            print(msg)
            errors.append(msg)
        else:
            print(f"OK       {host}  ({label})")

    if errors:
        print("\n--- Domain validation failed ---", file=sys.stderr)
        for e in errors:
            print(e, file=sys.stderr)
        print(
            "\nFix invalid addresses in config.py or GitHub secrets (RESEND_FROM, LAZYPAPER_TO), "
            "or correct RSS URLs in SOURCES.",
            file=sys.stderr,
        )
        return 1

    rf_env = os.environ.get("RESEND_FROM", "").strip()
    effective_from_header = rf_env or config.DEFAULT_RESEND_FROM
    from_emails = _from_header_addresses(effective_from_header)
    from_domain = _domain_from_email(from_emails[0]) if from_emails else None

    recipient_addr = (os.environ.get("LAZYPAPER_TO") or config.RECIPIENT_EMAIL or "").strip()

    print("\nAll domain checks passed.")

    sys.stdout.flush()
    if from_domain == "resend.dev":
        print(
            "\nWARNING: 'From' still uses the Resend sandbox sender (resend.dev).\n"
            "Resend only accepts this sender when the recipient equals the email on your "
            "Resend account;\nsending to any other address will fail with 'The domain is invalid'.\n"
            "Verify your own domain in Resend, then set the RESEND_FROM secret to "
            "'Your Name <you@your-verified-domain>'.\n"
            f"Current recipient: {recipient_addr or '(unset)'}"
        )
    elif from_domain:
        print(
            "\nNOTE: Custom From domains must be verified in your Resend dashboard "
            "(DNS checks here are necessary but not sufficient to send)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
