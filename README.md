# WHONUM

Phone number OSINT tool. Instant number intelligence + spam lookup across multiple sources.

## Install

```bash
pip install -r requirements.txt --break-system-packages
pip install -e . --break-system-packages
```

## Usage

```bash
# Basic lookup (with + and country code)
whonum +447700900000

# US number without country code
whonum 5551234567 --region US

# JSON output
whonum +447700900000 --json

# JSON to file
whonum +447700900000 --json > result.json
```

## Output

- Number validation and formatting (E.164, national, international)
- Country, region, timezone
- Line type (Mobile/Fixed/VoIP)
- Carrier (where available)
- Spam database reports (NoMoRobo, WhoCalledMe, 800notes, SpamCalls)
- **SIM-farm / virtual-number risk assessment** (see below)

## SIM-farm detection

Every lookup produces a scored SIM-farm / virtual-number risk verdict
(`CLEAN` / `LOW` / `ELEVATED` / `HIGH`) with the signals behind it. It combines:

- **Offline (works for every number, no key):** VoIP line type from
  libphonenumber, and carrier matched against a list of known CPaaS/VoIP
  providers (Twilio, Bandwidth, Telnyx, Vonage, etc.).
- **Online when keyed (IPQS):** prepaid, recent abuse, fraud score, VoIP flag.
- **Spam clustering:** reports across multiple spam databases.

Scope: this flags VoIP / virtual / CPaaS numbers and spam-clustered numbers —
the profile of most spoofing, OTP-resale and SIM-box-adjacent abuse. A SIM farm
built on genuine prepaid mobile SIMs can still look like a clean mobile line
offline; catching those needs a line-intel API (IPQS prepaid + recent-abuse).
Treat the verdict as a risk indicator, not proof.

## Optional API Keys (env vars)

```bash
export IPQS_KEY=your_key             # ipqualityscore.com free: 200/month — strongest signal
export ABSTRACT_PHONE_KEY=your_key   # abstractapi.com free: 250/month
export NUMVERIFY_KEY=your_key        # numverify.com free: 100/month
```

## Sources

WhatsApp (deep-link only), NoMoRobo, WhoCalledMe, 800notes, SpamCalls,
IPQualityScore / AbstractAPI / Numverify (optional, API key)
