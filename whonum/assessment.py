"""
SIM-farm / virtual-number risk assessment.

Combines offline signals (line type, carrier) with any online source results
(spam databases, IPQualityScore) into a single scored verdict that works for
every number, with or without API keys.

Honest scope: this reliably flags VoIP / virtual / CPaaS numbers and numbers
clustered across spam databases — the profile of most spoofing, OTP-resale and
SIM-box-adjacent abuse. A SIM farm built on genuine prepaid mobile SIMs may
still present as a clean mobile line; catching those needs a line-intel API
(IPQS prepaid + recent-abuse, or Twilio Lookup). Treat the verdict as a risk
indicator, not proof.
"""
import re

# Known CPaaS / VoIP / virtual-number carriers frequently abused by SIM farms,
# OTP resale and number-spoofing operations. Matched case-insensitively as
# substrings against the carrier name resolved by libphonenumber.
VOIP_CARRIERS = (
    "twilio", "bandwidth", "telnyx", "plivo", "vonage", "nexmo", "sinch",
    "voxbone", "bics", "flowroute", "commio", "inteliquent", "peerless",
    "neutral tandem", "messagebird", "message bird", "onoff", "textnow",
    "google", "skype", "level 3", "level3", "voip", "voipms", "voip.ms",
    "bandwidth.com", "zadarma", "didww", "callwithus",
)

SPAM_SOURCES = {"NoMoRobo", "WhoCalledMe", "800notes", "SpamCalls",
                "ShouldIAnswer", "CallerCenter"}


def _has(detail, *needles):
    d = (detail or "").lower()
    return any(n in d for n in needles)


def assess(intel: dict, results: list[dict]) -> dict:
    """Score SIM-farm / virtual-number risk.

    Returns {score:int 0-100, level:str, label:str, signals:[str]}.
    """
    signals = []
    score = 0

    line_type = (intel.get("type") or "").lower()
    carrier = (intel.get("carrier") or "").lower()
    carrier_disp = intel.get("carrier") or ""

    # --- Offline signals (available for every number, no API key) ---
    if "voip" in line_type:
        score += 45
        signals.append("line type is VoIP (libphonenumber)")

    if carrier and carrier != "unknown" and any(v in carrier for v in VOIP_CARRIERS):
        score += 40
        signals.append(f"carrier '{carrier_disp}' is a known VoIP/CPaaS provider")

    if "mobile" in line_type and (not carrier or carrier == "unknown"):
        score += 10
        signals.append("mobile line with no resolvable carrier")

    if not intel.get("valid", True):
        score += 10
        signals.append("number is possible but not valid for its range")

    # --- Online signals from source results ---
    found = [r for r in results if r.get("found") is True]

    # IPQualityScore — strongest online signal when a key is configured
    for r in found:
        if r["name"] == "IPQualityScore":
            d = r.get("detail") or ""
            if _has(d, "voip"):
                score += 35
                signals.append("IPQS: VoIP line")
            if _has(d, "prepaid"):
                score += 20
                signals.append("IPQS: prepaid line")
            if _has(d, "risky"):
                score += 25
                signals.append("IPQS: flagged risky")
            mfs = re.search(r"fraud (\d+)", d.lower())
            if mfs:
                fs = int(mfs.group(1))
                if fs >= 85:
                    score += 30
                    signals.append(f"IPQS fraud score {fs}/100")
                elif fs >= 60:
                    score += 15
                    signals.append(f"IPQS fraud score {fs}/100")

    # Spam-database clustering
    spam_hits = [r["name"] for r in found if r["name"] in SPAM_SOURCES]
    if len(spam_hits) >= 3:
        score += 30
        signals.append(f"reported across {len(spam_hits)} spam databases")
    elif len(spam_hits) >= 1:
        score += 12
        signals.append(f"reported in {len(spam_hits)} spam database(s)")

    score = min(score, 100)

    if score >= 70:
        level, label = "HIGH", "LIKELY SIM FARM / virtual-number abuse"
    elif score >= 40:
        level, label = "ELEVATED", "VoIP / virtual number — caution"
    elif score >= 15:
        level, label = "LOW", "minor risk signals"
    else:
        level, label = "CLEAN", "no SIM-farm / virtual-number signals"

    return {"score": score, "level": level, "label": label, "signals": signals}
