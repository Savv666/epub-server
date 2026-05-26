import json
from pathlib import Path
from urllib.parse import urlparse

GENERIC_FIRST_DOMAINS = [
    "wuxiaworld.com",
    "novelbin.com",
    "novelbin.me",
    "novelfull.com",
    "novelonlinefull.com",
    "novelall.com",
    "lightnovelworld.com",
    "lightnovelworld.co",
    "readnovelfull.com",
    "webnovel.com",
]

FREEWEBNOVEL_DOMAINS = ["freewebnovel.com"]

LOCKED_ERROR_PHRASES = [
    "registered users",
    "only available to registered users",
    "login",
    "log in",
    "please log in",
    "restricted",
    "private",
    "not authorized",
    "not authorised",
    "adult content",
    "requires login",
    "access denied",
    "forbidden",
    "cloudflare",
    "captcha",
]

def load_json(path: Path, default=None):
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def domain_from_url(url):
    parsed = urlparse(str(url or ""))
    return parsed.netloc.lower().replace("www.", "")


def domain_matches(url, domains):
    domain = domain_from_url(url)
    return any(domain == known or domain.endswith("." + known) for known in domains)


def looks_like_phrase_match(text, phrases):
    lower = str(text or "").lower()
    return any(phrase in lower for phrase in phrases)
