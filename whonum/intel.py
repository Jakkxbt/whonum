import phonenumbers
from phonenumbers import geocoder, carrier, timezone as tz, number_type, PhoneNumberType

TYPE_MAP = {
    PhoneNumberType.MOBILE: "Mobile",
    PhoneNumberType.FIXED_LINE: "Fixed Line",
    PhoneNumberType.FIXED_LINE_OR_MOBILE: "Fixed / Mobile",
    PhoneNumberType.VOIP: "VoIP",
    PhoneNumberType.PREMIUM_RATE: "Premium Rate",
    PhoneNumberType.TOLL_FREE: "Toll Free",
    PhoneNumberType.PERSONAL_NUMBER: "Personal Number",
    PhoneNumberType.PAGER: "Pager",
    PhoneNumberType.SHARED_COST: "Shared Cost",
    PhoneNumberType.UNKNOWN: "Unknown",
}

# ISO 3166-1 alpha-2 → country name fallback for when geocoder returns empty
_REGION_NAMES = {
    "GB": "United Kingdom", "US": "United States", "CA": "Canada",
    "AU": "Australia", "DE": "Germany", "FR": "France", "ES": "Spain",
    "IT": "Italy", "NL": "Netherlands", "BE": "Belgium", "SE": "Sweden",
    "NO": "Norway", "DK": "Denmark", "FI": "Finland", "PL": "Poland",
    "RU": "Russia", "CN": "China", "IN": "India", "JP": "Japan",
    "KR": "South Korea", "BR": "Brazil", "MX": "Mexico", "AR": "Argentina",
    "ZA": "South Africa", "NG": "Nigeria", "KE": "Kenya", "EG": "Egypt",
    "SA": "Saudi Arabia", "AE": "UAE", "IL": "Israel", "TR": "Turkey",
    "PK": "Pakistan", "BD": "Bangladesh", "PH": "Philippines", "TH": "Thailand",
    "VN": "Vietnam", "ID": "Indonesia", "MY": "Malaysia", "SG": "Singapore",
    "HK": "Hong Kong", "NZ": "New Zealand", "IE": "Ireland", "PT": "Portugal",
    "GR": "Greece", "CZ": "Czech Republic", "RO": "Romania", "HU": "Hungary",
    "UA": "Ukraine", "GG": "Guernsey", "JE": "Jersey", "IM": "Isle of Man",
}


def parse_number(phone_str: str, default_region: str = None) -> dict:
    """Parse and analyse a phone number. Returns intel dict."""
    try:
        parsed = phonenumbers.parse(phone_str, default_region)
    except phonenumbers.NumberParseException as e:
        raise ValueError(str(e))

    if not phonenumbers.is_possible_number(parsed):
        raise ValueError("Not a possible phone number")

    valid = phonenumbers.is_valid_number(parsed)
    ntype = number_type(parsed)
    e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    region_code = phonenumbers.region_code_for_number(parsed) or "ZZ"

    country = (geocoder.country_name_for_number(parsed, "en")
               or _REGION_NAMES.get(region_code, f"+{parsed.country_code}"))
    region = geocoder.description_for_number(parsed, "en") or ""
    carrier_name = carrier.name_for_number(parsed, "en") or "Unknown"
    timezones = list(tz.time_zones_for_number(parsed))

    # Tidy timezones
    if timezones == ["Etc/Unknown"]:
        timezones = []

    return {
        "raw": phone_str,
        "e164": e164,
        "e164_digits": e164.lstrip("+"),
        "international": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
        "national": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL),
        "valid": valid,
        "country_code": str(parsed.country_code),
        "region_code": region_code,
        "country": country,
        "region": region if region != country else "",
        "type": TYPE_MAP.get(ntype, "Unknown"),
        "carrier": carrier_name,
        "timezones": timezones,
    }
