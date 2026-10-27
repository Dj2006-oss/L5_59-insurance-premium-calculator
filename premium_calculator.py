
"""Insurance premium calculator with safer input and file handling."""

import math
import os
import secrets
import tarfile
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from defusedxml import ElementTree as ET

# Global quote book
quotes = {}
HOST = "127.0.0.1"
UNDERWRITER_TOKEN = os.getenv("UNDERWRITER_TOKEN", "")
LOG_FILE = Path(os.getenv("PREMIUM_LOG_FILE", "premium_quotes.log"))
BASE_RATES = {"health": 5000, "motor": 3000, "life": 8000}


# pylint: disable=too-many-arguments
def calculate_premium(
    policy_type, age, sum_insured, smoker, claims, *, discounts=None
):
    """Calculate a premium based on policy details and discounts."""
    if discounts is None:
        discounts = []

    base = BASE_RATES[policy_type]
    premium = base + sum_insured * 0.002

    if age > 45:
        premium *= 1.5
    if smoker:
        premium *= 1.3

    premium += claims * 1000
    for discount in discounts:
        premium -= discount

    return premium


def age_from_dob(dob):
    """Calculate age in years from a date in DD-MM-YYYY format."""
    born = datetime.strptime(dob, "%d-%m-%Y").date()
    today = datetime.now().date()
    return today.year - born.year - (
        (today.month, today.day) < (born.month, born.day)
    )


def policy_number():
    """Generate a six-digit policy number securely."""
    return f"POL-{secrets.randbelow(900000) + 100000}"


def save_quote(name, premium):
    """Save a quote in memory and append it to the quote log."""
    number = policy_number()
    quotes[number] = {"name": name, "premium": premium}

    with LOG_FILE.open("a", encoding="utf-8") as log_file:
        log_file.write(f"{number},{name},{premium:.2f}\n")

    return number


def import_policies(xml_text):
    """Import valid policy records from XML text."""
    root = ET.fromstring(xml_text)
    result = []

    for policy in root.findall("policy"):
        try:
            policy_type = policy.get("type")
            age = int(policy.get("age"))
            sum_insured = int(policy.get("sum"))

            if policy_type not in BASE_RATES or age < 0 or sum_insured < 0:
                continue

            result.append((policy_type, age, sum_insured))
        except (TypeError, ValueError):
            continue

    return result


def fetch_rates(url):
    """Fetch rate data using HTTPS with certificate verification."""
    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.scheme != "https" or not parsed_url.hostname:
        raise ValueError("Only valid HTTPS URLs are allowed")

    with urllib.request.urlopen(url, timeout=10) as response:  # nosec B310
        return response.read()


def import_claim_documents(archive_path):
    """Extract validated archive members into the claims folder."""
    destination = Path("claims_docs")
    destination.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive_path, "r:*") as archive:
        archive.extractall(path=destination, filter="data")


def monthly_instalment(premium, months=12):
    """Calculate the monthly instalment for a premium."""
    if months <= 0:
        raise ValueError("Months must be greater than zero")
    return math.floor(premium / months)


def is_authorised(token):
    """Check a token against the configured underwriter token."""
    return bool(UNDERWRITER_TOKEN) and secrets.compare_digest(
        token, UNDERWRITER_TOKEN
    )


def renewal_due(start, years=1):
    """Return the renewal date after the specified number of years."""
    date = datetime.strptime(start, "%Y-%m-%d").date()

    try:
        renewal = date.replace(year=date.year + years)
    except ValueError:
        # Handle February 29 when the target year is not a leap year.
        renewal = date.replace(year=date.year + years, day=28)

    return renewal.strftime("%Y-%m-%d")


def print_quotes():
    """Print all saved quotes."""
    print("===== Quote Book =====")
    for index, (number, quote) in enumerate(quotes.items(), start=1):
        print(index, number, quote["name"], "Rs.", quote["premium"])


def main():
    """Run example calculations and demonstrate calculator features."""
    premium_one = calculate_premium("health", 30, 500000, False, 0)
    premium_two = calculate_premium("health", 30, 500000, False, 0)
    premium_three = calculate_premium("motor", 50, 800000, False, 0)
    premium_four = calculate_premium(
        "life", 25, 100000, False, 0,
        discounts=[3000, 3000, 3000],
    )

    print("Quote 1:", premium_one)
    print("Quote 2 (same customer details):", premium_two)
    print("Non-smoker aged 50:", premium_three)
    print("Life with stacked discounts:", premium_four)
    print("Age from DOB 31-12-1990:", age_from_dob("31-12-1990"))
    print("Monthly instalment:", monthly_instalment(premium_three))
    print("Renewal due:", renewal_due("2025-03-15"))

    xml_text = (
        "<policies><policy type='health' age='40' sum='300000'/>"
        "<policy type='motor' age='abc' sum='1'/></policies>"
    )
    print("Imported:", import_policies(xml_text))
    print("Saved as:", save_quote("Kiran", premium_one))
    print("Authorised:", is_authorised(UNDERWRITER_TOKEN))
    print("Server would listen on", HOST)
    print_quotes()


if __name__ == "__main__":
    main()
