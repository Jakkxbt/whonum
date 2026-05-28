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
- WhatsApp presence check
- Spam database reports (WhoCalledMe, ShouldIAnswer, 800notes)
- Truecaller name lookup attempt

## Optional API Keys (env vars)

```bash
export NUMVERIFY_KEY=your_key   # numverify.com free tier: 100/month
export NUMLOOKUP_KEY=your_key   # numlookupapi.com free tier
```

## Sources

WhatsApp, Truecaller, WhoCalledMe, ShouldIAnswer, 800notes, NumLookup, Numverify (optional)
