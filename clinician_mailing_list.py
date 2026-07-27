#!/usr/bin/env python3
"""Build a mailing-address list of clinicians near a zip code, using the
public NPPES NPI Registry (npiregistry.cms.hhs.gov).

See README.md for usage, data-source rationale, and compliance notes.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from typing import Iterable

import requests
from requests.adapters import HTTPAdapter, Retry

NPPES_URL = "https://npiregistry.cms.hhs.gov/api/"
NPPES_VERSION = "2.1"
MAX_LIMIT_PER_REQUEST = 200
MAX_SKIP = 1000  # NPPES registry cap; total retrievable per query is ~1200

DEFAULT_TAXONOMIES = [
    "Psychologist",
    "Counselor",
]

OUTPUT_FIELDS = [
    "NPI",
    "First Name",
    "Last Name",
    "Credential",
    "Primary Taxonomy",
    "All Taxonomies",
    "Address 1",
    "Address 2",
    "City",
    "State",
    "ZIP",
    "Phone",
    "License Number",
    "License State",
    "Matched Search Zip",
    "Matched Search Taxonomy",
]


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=4,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def zips_within_radius(center_zip: str, radius_miles: float) -> list[str]:
    """Expand a center zip code to all US zip codes within radius_miles,
    using pgeocode's (offline, GeoNames-derived) postal code dataset."""
    try:
        import pgeocode
    except ImportError as exc:
        raise SystemExit(
            "pgeocode is required for --center-zip/--radius-miles mode. "
            "Install it with `pip install pgeocode`, or use --zips with an "
            "explicit comma-separated zip list instead."
        ) from exc

    nomi = pgeocode.Nominatim("us")
    center = nomi.query_postal_code(center_zip)
    if center is None or center.latitude != center.latitude:  # NaN check
        raise SystemExit(f"Could not find coordinates for zip code {center_zip!r}.")

    all_codes = nomi._data  # pgeocode's underlying dataframe of all US zips
    dist = pgeocode.GeoDistance("us")

    nearby = []
    for postal_code in all_codes["postal_code"].dropna().unique():
        postal_code = str(postal_code).strip()
        if not postal_code:
            continue
        try:
            miles = dist.query_postal_code(center_zip, postal_code) * 0.621371
        except Exception:
            continue
        if miles == miles and miles <= radius_miles:  # skip NaN
            nearby.append(postal_code)

    if not nearby:
        raise SystemExit(
            f"No zip codes found within {radius_miles} miles of {center_zip}."
        )
    return sorted(set(nearby))


def fetch_npi_records(
    session: requests.Session,
    taxonomy_description: str,
    postal_code: str,
    enumeration_type: str,
    delay: float,
) -> list[dict]:
    """Fetch all NPI records matching a taxonomy + postal code, paginating
    through NPPES's skip/limit window."""
    results: list[dict] = []
    skip = 0
    while True:
        params = {
            "version": NPPES_VERSION,
            "taxonomy_description": taxonomy_description,
            "postal_code": postal_code,
            "address_purpose": "LOCATION",
            "enumeration_type": enumeration_type,
            "limit": MAX_LIMIT_PER_REQUEST,
            "skip": skip,
        }
        resp = session.get(NPPES_URL, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()

        if payload.get("Errors"):
            # NPPES returns HTTP 200 with an "Errors" body (e.g. for
            # taxonomy_description values it can't parse, such as ones
            # containing a comma) rather than a normal HTTP error, so this
            # must be checked explicitly or it fails silently as zero results.
            messages = "; ".join(e.get("description", str(e)) for e in payload["Errors"])
            raise SystemExit(
                f"NPPES API rejected the search for taxonomy_description="
                f"{taxonomy_description!r}: {messages}. Tip: the registry's "
                f"search only accepts simple comma-free terms."
            )

        batch = payload.get("results", [])
        results.extend(batch)

        if len(batch) < MAX_LIMIT_PER_REQUEST:
            break
        skip += MAX_LIMIT_PER_REQUEST
        if skip > MAX_SKIP:
            print(
                f"  warning: hit NPPES pagination cap for "
                f"{taxonomy_description!r} in {postal_code}; results may be "
                f"truncated. Consider narrowing the search.",
                file=sys.stderr,
            )
            break
        time.sleep(delay)

    time.sleep(delay)
    return results


def parse_record(record: dict, search_zip: str, search_taxonomy: str) -> dict:
    basic = record.get("basic", {})
    addresses = record.get("addresses", [])
    taxonomies = record.get("taxonomies", [])

    location = next(
        (a for a in addresses if a.get("address_purpose") == "LOCATION"),
        addresses[0] if addresses else {},
    )
    primary_tax = next((t for t in taxonomies if t.get("primary")), None)
    if primary_tax is None and taxonomies:
        primary_tax = taxonomies[0]
    primary_tax = primary_tax or {}

    return {
        "NPI": record.get("number", ""),
        "First Name": basic.get("first_name", ""),
        "Last Name": basic.get("last_name", ""),
        "Credential": basic.get("credential", ""),
        "Primary Taxonomy": primary_tax.get("desc", ""),
        "All Taxonomies": "; ".join(sorted({t.get("desc", "") for t in taxonomies if t.get("desc")})),
        "Address 1": location.get("address_1", ""),
        "Address 2": location.get("address_2", ""),
        "City": location.get("city", ""),
        "State": location.get("state", ""),
        "ZIP": location.get("postal_code", ""),
        "Phone": location.get("telephone_number", ""),
        "License Number": primary_tax.get("license", ""),
        "License State": primary_tax.get("state", ""),
        "Matched Search Zip": search_zip,
        "Matched Search Taxonomy": search_taxonomy,
    }


def build_mailing_list(
    zip_codes: Iterable[str],
    taxonomies: Iterable[str],
    enumeration_type: str,
    delay: float,
) -> list[dict]:
    session = build_session()
    by_npi: dict[str, dict] = {}

    zip_codes = list(zip_codes)
    taxonomies = list(taxonomies)
    total = len(zip_codes) * len(taxonomies)
    done = 0

    for zip_code in zip_codes:
        for taxonomy in taxonomies:
            done += 1
            print(f"[{done}/{total}] {taxonomy!r} near {zip_code} ...", file=sys.stderr)
            records = fetch_npi_records(session, taxonomy, zip_code, enumeration_type, delay)
            for record in records:
                parsed = parse_record(record, zip_code, taxonomy)
                npi = parsed["NPI"]
                if npi and npi not in by_npi:
                    by_npi[npi] = parsed

    return list(by_npi.values())


def write_csv(rows: list[dict], output_path: str) -> None:
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    zip_group = parser.add_mutually_exclusive_group(required=True)
    zip_group.add_argument("--zips", help="Comma-separated explicit zip codes")
    zip_group.add_argument("--center-zip", help="Center zip code for radius expansion")

    parser.add_argument(
        "--radius-miles", type=float, default=25,
        help="Radius in miles around --center-zip (default: 25)",
    )
    parser.add_argument(
        "--taxonomies",
        default=";".join(DEFAULT_TAXONOMIES),
        help="Semicolon-separated NPI taxonomy search terms. The NPI "
             "registry's search only matches simple words/phrases with NO "
             "commas (e.g. 'Psychologist', 'Counselor', 'Family Medicine') "
             "-- a term like 'Counselor, Professional' returns an API error "
             "and zero results. Use broad terms and filter the output CSV's "
             "Primary Taxonomy column afterward to narrow to specific "
             "subtypes.",
    )
    parser.add_argument(
        "--enumeration-type", default="NPI-1", choices=["NPI-1", "NPI-2"],
        help="NPI-1 = individual providers, NPI-2 = organizations (default: NPI-1)",
    )
    parser.add_argument("--output", default="clinician_mailing_list.csv")
    parser.add_argument(
        "--delay", type=float, default=0.2,
        help="Seconds to wait between API requests (default: 0.2)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    if args.zips:
        zip_codes = [z.strip() for z in args.zips.split(",") if z.strip()]
    else:
        print(f"Expanding {args.center_zip} to zips within {args.radius_miles} miles...", file=sys.stderr)
        zip_codes = zips_within_radius(args.center_zip, args.radius_miles)
        print(f"Found {len(zip_codes)} zip codes to search: {', '.join(zip_codes)}", file=sys.stderr)

    taxonomies = [t.strip() for t in args.taxonomies.split(";") if t.strip()]

    rows = build_mailing_list(zip_codes, taxonomies, args.enumeration_type, args.delay)
    write_csv(rows, args.output)
    print(f"Wrote {len(rows)} unique clinicians to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
