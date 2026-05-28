"""
WHONUM source modules.
Each module: async def check_<source>(client, intel) -> dict
intel = dict from intel.parse_number()
Return: {name, url, found: bool|None, detail: str|None, error: str|None}

found semantics:
  True  = number confirmed active / flagged / present on platform
  False = number not found / clean in this database
  None  = could not determine (rate limited, anti-bot, etc.)
"""
import re
import os
import httpx

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
HEADERS = {
    "User-Agent": UA,
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _r(name: str, url: str, found, detail: str = None, error: str = None) -> dict:
    return {"name": name, "url": url, "found": found, "detail": detail, "error": error}


def _safe_json(r):
    try:
        return r.json()
    except Exception:
        return {}


# ── Platform Presence ─────────────────────────────────────────────────────────

async def check_whatsapp(client: httpx.AsyncClient, intel: dict) -> dict:
    name = "WhatsApp"
    digits = intel["e164_digits"]
    url = f"https://wa.me/{digits}"
    try:
        r = await client.get(url, headers=HEADERS, timeout=12)
        text = r.text.lower()
        if any(x in text for x in ["invalid", "link you've tried", "not available", "doesn't exist"]):
            return _r(name, url, False, "not on WhatsApp")
        if any(x in text for x in ["open whatsapp", "send message", "whatsapp.com/dl", "api.whatsapp.com"]):
            return _r(name, url, True, f"active — {url}")
        if r.status_code == 200 and "whatsapp" in text:
            return _r(name, url, True, f"active — {url}")
        return _r(name, url, None, None, f"status {r.status_code}")
    except Exception as e:
        return _r(name, url, None, None, str(e)[:60])


async def check_telegram(client: httpx.AsyncClient, intel: dict) -> dict:
    name = "Telegram"
    # Public t.me/+{e164} links work for numbers that have linked public presence
    e164 = intel["e164"]
    url = f"https://t.me/{e164}"
    try:
        r = await client.get(url, headers=HEADERS, timeout=10)
        text = r.text.lower()
        if "this number has not been registered" in text or "invalid" in text:
            return _r(name, url, False, "not registered (public)")
        # Telegram always returns 200 — can't confirm without app
        return _r(name, url, None, "requires Telegram app to confirm")
    except Exception as e:
        return _r(name, url, None, "requires Telegram app to confirm")


async def check_viber(client: httpx.AsyncClient, intel: dict) -> dict:
    name = "Viber"
    digits = intel["e164_digits"]
    # Viber has no public web lookup — return the invite link for manual check
    viber_url = f"viber://add?number={digits}"
    return _r(name, "https://www.viber.com", None, f"manual check: {viber_url}")


# ── Spam / Scam Databases ─────────────────────────────────────────────────────

async def check_nomorobo(client: httpx.AsyncClient, intel: dict) -> dict:
    """NoMoRobo — US robocall/telemarketer registry."""
    name = "NoMoRobo"
    digits = intel["e164_digits"]
    url = f"https://www.nomorobo.com/lookup/{digits}"
    try:
        r = await client.get(url, headers=HEADERS, timeout=12)
        text = r.text.lower()
        if any(x in text for x in ["robocaller", "telemarketer", "spam caller", "this is a robocaller"]):
            m = re.search(r'<h2[^>]*>([^<]+)</h2>', r.text)
            detail = m.group(1).strip() if m else "robocaller flagged"
            return _r(name, url, True, detail)
        if any(x in text for x in ["not found", "not in our database", "no reports"]):
            return _r(name, url, False, "clean — not in database")
        if r.status_code == 200:
            return _r(name, url, False, "not listed")
        return _r(name, url, None, None, f"status {r.status_code}")
    except Exception as e:
        return _r(name, url, None, None, str(e)[:60])


async def check_whocalledme(client: httpx.AsyncClient, intel: dict) -> dict:
    """WhoCalledMe — community-sourced caller reports."""
    name = "WhoCalledMe"
    digits = intel["e164_digits"]
    url = f"https://www.whocalledme.com/PhoneNumber/{digits}"
    try:
        r = await client.get(url, headers=HEADERS, timeout=12)
        text = r.text
        m = re.search(r'(\d+)\s*(?:report|comment|user)', text, re.I)
        count = int(m.group(1)) if m else 0
        cat = re.search(r'(?:category|type)[^>]*>\s*([A-Za-z][A-Za-z ]+?)\s*<', text, re.I)
        category = cat.group(1).strip() if cat else ""
        if r.status_code == 200:
            detail = f"{count} reports" + (f" · {category}" if category else "")
            return _r(name, url, count > 0, detail)
        return _r(name, url, None, None, f"status {r.status_code}")
    except Exception as e:
        return _r(name, url, None, None, str(e)[:60])


async def check_shouldianswer(client: httpx.AsyncClient, intel: dict) -> dict:
    """ShouldIAnswer — spam/danger scoring, strong UK/EU coverage."""
    name = "ShouldIAnswer"
    digits = intel["e164_digits"]
    url = f"https://www.shouldianswer.com/phone-number/{digits}"
    try:
        r = await client.get(url, headers=HEADERS, timeout=12)
        text = r.text
        score_m = re.search(r'"ratingValue"\s*:\s*"?(-?\d+(?:\.\d+)?)"?', text)
        count_m = re.search(r'"reviewCount"\s*:\s*"?(\d+)"?', text)
        score = score_m.group(1) if score_m else None
        count = int(count_m.group(1)) if count_m else 0
        if score and float(score) < 0:
            return _r(name, url, True, f"score {score} · {count} opinions — DANGEROUS")
        if r.status_code == 200:
            detail = f"{count} opinions" + (f" · score {score}" if score else "")
            return _r(name, url, count > 0, detail)
        return _r(name, url, None, None, f"status {r.status_code}")
    except Exception as e:
        return _r(name, url, None, None, str(e)[:60])


async def check_800notes(client: httpx.AsyncClient, intel: dict) -> dict:
    """800notes — international spam/scam call tracker."""
    name = "800notes"
    digits = intel["e164_digits"]
    url = f"https://800notes.com/Phone.aspx/{digits}"
    try:
        r = await client.get(url, headers=HEADERS, timeout=12)
        if r.status_code == 404:
            return _r(name, url, False, "no reports")
        text = r.text
        m = re.search(r'(\d+)\s*(?:post|comment|report)', text, re.I)
        count = int(m.group(1)) if m else 0
        cat = re.search(r'(?:spam type|category)[^>]*>\s*([A-Za-z][A-Za-z /]+?)\s*<', text, re.I)
        category = cat.group(1).strip() if cat else ""
        if r.status_code == 200:
            detail = f"{count} posts" + (f" · {category}" if category else "")
            return _r(name, url, count > 0, detail if count else "no reports")
        return _r(name, url, None, None, f"status {r.status_code}")
    except Exception as e:
        return _r(name, url, None, None, str(e)[:60])


async def check_spamcalls(client: httpx.AsyncClient, intel: dict) -> dict:
    """SpamCalls.net — international spam call database."""
    name = "SpamCalls"
    digits = intel["e164_digits"]
    url = f"https://spamcalls.net/en/search?q={digits}"
    try:
        r = await client.get(url, headers=HEADERS, timeout=12)
        text = r.text
        count_m = re.search(r'(\d+)\s*report', text, re.I)
        count = int(count_m.group(1)) if count_m else 0
        cat_m = re.search(r'spam type[:\s]+([A-Za-z][A-Za-z ]+)', text, re.I)
        category = cat_m.group(1).strip() if cat_m else ""
        if r.status_code == 200:
            detail = f"{count} reports" + (f" · {category}" if category else "")
            return _r(name, url, count > 0, detail)
        return _r(name, url, None, None, f"status {r.status_code}")
    except Exception as e:
        return _r(name, url, None, None, str(e)[:60])


async def check_callercenter(client: httpx.AsyncClient, intel: dict) -> dict:
    """CallerCenter — community caller ID with ratings."""
    name = "CallerCenter"
    digits = intel["e164_digits"]
    url = f"https://www.callercenter.com/{digits}"
    try:
        r = await client.get(url, headers=HEADERS, timeout=12)
        if r.status_code == 404:
            return _r(name, url, False, "no reports")
        text = r.text
        m = re.search(r'(\d+)\s*(?:report|rating|review)', text, re.I)
        count = int(m.group(1)) if m else 0
        rat = re.search(r'"ratingValue"\s*:\s*"?(\d+(?:\.\d+)?)"?', text)
        rating = rat.group(1) if rat else None
        if r.status_code == 200:
            detail = f"{count} reports" + (f" · {rating}/5" if rating else "")
            return _r(name, url, count > 0, detail if count else "no reports")
        return _r(name, url, None, None, f"status {r.status_code}")
    except Exception as e:
        return _r(name, url, None, None, str(e)[:60])


async def check_hiya(client: httpx.AsyncClient, intel: dict) -> dict:
    """Hiya — caller ID and real-time fraud/spam detection."""
    name = "Hiya"
    digits = intel["e164_digits"]
    url = f"https://www.hiya.com/number/{digits}"
    try:
        r = await client.get(url, headers=HEADERS, timeout=12)
        text = r.text.lower()
        if any(x in text for x in ["fraud", "scam", "robocall", "telemarketer", "spam"]):
            m = re.search(r'"(?:category|callType|label)"\s*:\s*"([^"]+)"', r.text)
            detail = m.group(1) if m else "flagged"
            return _r(name, url, True, f"flagged: {detail}")
        if r.status_code == 200:
            return _r(name, url, False, "not flagged")
        return _r(name, url, None, None, f"status {r.status_code}")
    except Exception as e:
        return _r(name, url, None, None, str(e)[:60])


async def check_truecaller(client: httpx.AsyncClient, intel: dict) -> dict:
    """Truecaller — name lookup, spam scoring, caller ID database."""
    name = "Truecaller"
    cc = intel["region_code"].lower()
    national = re.sub(r'\D', '', intel["national"])
    url = f"https://www.truecaller.com/search/{cc}/{national}"
    try:
        r = await client.get(url, headers=HEADERS, timeout=12)
        text = r.text
        m = re.search(r'"name"\s*:\s*"([^"]{2,80})"', text)
        name_found = m.group(1) if m else None
        spam_m = re.search(r'"spamScore"\s*:\s*(\d+)', text)
        spam_score = spam_m.group(1) if spam_m else None
        if name_found and name_found.lower() not in ("truecaller", "search", "phone number", ""):
            detail = f"Name: {name_found}"
            if spam_score and int(spam_score) > 0:
                detail += f" · spam score {spam_score}"
            return _r(name, url, True, detail)
        if r.status_code == 200:
            return _r(name, url, None, "no public name data")
        return _r(name, url, None, None, f"status {r.status_code}")
    except Exception as e:
        return _r(name, url, None, None, str(e)[:60])


# ── Carrier / Line Intelligence ───────────────────────────────────────────────

async def check_numlookup(client: httpx.AsyncClient, intel: dict) -> dict:
    """NumLookup — free carrier and line-type API (rate limited without key).
    Set NUMLOOKUP_KEY for higher limits."""
    name = "NumLookup"
    digits = intel["e164_digits"]
    url = f"https://api.numlookupapi.com/v1/validate/{digits}"
    key = os.environ.get("NUMLOOKUP_KEY", "")
    params = {"apikey": key} if key else {}
    try:
        r = await client.get(url, params=params, headers=HEADERS, timeout=10)
        data = _safe_json(r)
        if data.get("valid"):
            parts = [data.get("line_type", ""), data.get("carrier", ""), data.get("country_name", "")]
            detail = " · ".join(p for p in parts if p)
            return _r(name, url, True, detail or "valid")
        if r.status_code == 200:
            return _r(name, url, False, "invalid / not active")
        return _r(name, url, None, None, f"status {r.status_code}")
    except Exception as e:
        return _r(name, url, None, None, str(e)[:60])


# ── Optional API-Key Sources ──────────────────────────────────────────────────

async def check_ipqs(client: httpx.AsyncClient, intel: dict) -> dict:
    """IPQualityScore — fraud score, VoIP/SIM farm detection, line type.
    Free: 200 lookups/month. Set IPQS_KEY env var.
    High fraud score + VoIP = likely SIM farm / spoofed number."""
    name = "IPQualityScore"
    key = os.environ.get("IPQS_KEY", "")
    if not key:
        return _r(name, "https://ipqualityscore.com", None, None, "set IPQS_KEY")
    digits = intel["e164_digits"]
    url = f"https://www.ipqualityscore.com/api/json/phone/{key}/{digits}"
    try:
        r = await client.get(
            url,
            params={"strictness": 1, "allow_prepaid": "true",
                    "country[]": intel["region_code"]},
            headers=HEADERS, timeout=10
        )
        data = _safe_json(r)
        if data.get("success"):
            score = data.get("fraud_score", 0)
            line_type = data.get("line_type", "unknown")
            carrier = data.get("carrier", "")
            risky = data.get("risky", False)
            voip = data.get("voip", False)
            prepaid = data.get("prepaid", False)
            parts = [f"fraud {score}/100", line_type]
            if carrier:
                parts.append(carrier)
            if voip:
                parts.append("⚠ VOIP")
            if prepaid:
                parts.append("prepaid")
            if risky:
                parts.append("⚠ RISKY")
            detail = " · ".join(parts)
            return _r(name, url, score > 60 or risky or voip, detail)
        return _r(name, url, None, None, data.get("message", f"status {r.status_code}"))
    except Exception as e:
        return _r(name, url, None, None, str(e)[:60])


async def check_abstract(client: httpx.AsyncClient, intel: dict) -> dict:
    """AbstractAPI — phone validation with carrier & line type.
    Free: 250/month. Set ABSTRACT_PHONE_KEY env var."""
    name = "AbstractAPI"
    key = os.environ.get("ABSTRACT_PHONE_KEY", "")
    if not key:
        return _r(name, "https://app.abstractapi.com/api/phone-validation", None, None, "set ABSTRACT_PHONE_KEY")
    url = "https://phonevalidation.abstractapi.com/v1/"
    try:
        r = await client.get(url, params={"api_key": key, "phone": intel["e164"]},
                             headers=HEADERS, timeout=10)
        data = _safe_json(r)
        if data.get("valid"):
            parts = [data.get("type", ""), data.get("carrier", ""),
                     (data.get("country") or {}).get("name", "")]
            detail = " · ".join(p for p in parts if p)
            return _r(name, url, True, detail)
        return _r(name, url, False, "invalid number")
    except Exception as e:
        return _r(name, url, None, None, str(e)[:60])


async def check_numverify(client: httpx.AsyncClient, intel: dict) -> dict:
    """Numverify — carrier + line type API.
    Free: 100/month. Set NUMVERIFY_KEY env var."""
    name = "Numverify"
    key = os.environ.get("NUMVERIFY_KEY", "")
    if not key:
        return _r(name, "https://numverify.com", None, None, "set NUMVERIFY_KEY")
    url = "http://apilayer.net/api/validate"
    try:
        r = await client.get(
            url,
            params={"access_key": key, "number": intel["e164"],
                    "country_code": intel["region_code"], "format": 1},
            timeout=10
        )
        data = _safe_json(r)
        if data.get("valid"):
            detail = " · ".join(filter(None, [
                data.get("line_type"), data.get("carrier"), data.get("location")
            ]))
            return _r(name, url, True, detail)
        return _r(name, url, False, "invalid / not found")
    except Exception as e:
        return _r(name, url, None, None, str(e)[:60])


# ── Registry ──────────────────────────────────────────────────────────────────

ALL_MODULES = [
    # Platform presence
    check_whatsapp,
    check_telegram,
    check_viber,
    # Spam / scam / robocall databases
    check_nomorobo,
    check_whocalledme,
    check_shouldianswer,
    check_800notes,
    check_spamcalls,
    check_callercenter,
    check_hiya,
    check_truecaller,
    # Carrier / line intelligence
    check_numlookup,
    # Optional API-key sources (skipped if key not set)
    check_ipqs,
    check_abstract,
    check_numverify,
]

SOURCE_NAMES = {m.__name__.replace("check_", ""): m for m in ALL_MODULES}
