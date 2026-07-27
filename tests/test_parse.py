import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clinician_mailing_list import (  # noqa: E402
    DEFAULT_TAXONOMIES,
    OUTPUT_FIELDS,
    fetch_npi_records,
    parse_args,
    parse_record,
)

SAMPLE_RECORD = {
    "number": "1234567890",
    "basic": {
        "first_name": "JANE",
        "last_name": "DOE",
        "credential": "PHD",
    },
    "addresses": [
        {
            "address_purpose": "MAILING",
            "address_1": "PO BOX 1",
            "city": "BOULDER",
            "state": "CO",
            "postal_code": "803010001",
            "telephone_number": "303-555-0100",
        },
        {
            "address_purpose": "LOCATION",
            "address_1": "123 PEARL ST",
            "address_2": "STE 200",
            "city": "BOULDER",
            "state": "CO",
            "postal_code": "803021234",
            "telephone_number": "303-555-0199",
        },
    ],
    "taxonomies": [
        {
            "code": "103TC0700X",
            "desc": "Clinical Psychologist",
            "primary": True,
            "license": "PSY12345",
            "state": "CO",
        },
        {
            "code": "103T00000X",
            "desc": "Psychologist",
            "primary": False,
            "license": "",
            "state": "CO",
        },
    ],
}


class ParseRecordTest(unittest.TestCase):
    def test_picks_location_address_not_mailing(self):
        parsed = parse_record(SAMPLE_RECORD, search_zip="80302", search_taxonomy="Psychologist")
        self.assertEqual(parsed["Address 1"], "123 PEARL ST")
        self.assertEqual(parsed["Address 2"], "STE 200")
        self.assertEqual(parsed["Phone"], "303-555-0199")

    def test_picks_primary_taxonomy(self):
        parsed = parse_record(SAMPLE_RECORD, search_zip="80302", search_taxonomy="Psychologist")
        self.assertEqual(parsed["Primary Taxonomy"], "Clinical Psychologist")
        self.assertEqual(parsed["License Number"], "PSY12345")
        self.assertIn("Psychologist", parsed["All Taxonomies"])
        self.assertIn("Clinical Psychologist", parsed["All Taxonomies"])

    def test_basic_fields(self):
        parsed = parse_record(SAMPLE_RECORD, search_zip="80302", search_taxonomy="Psychologist")
        self.assertEqual(parsed["NPI"], "1234567890")
        self.assertEqual(parsed["First Name"], "JANE")
        self.assertEqual(parsed["Last Name"], "DOE")
        self.assertEqual(parsed["Credential"], "PHD")
        self.assertEqual(parsed["Matched Search Zip"], "80302")
        self.assertEqual(parsed["Matched Search Taxonomy"], "Psychologist")

    def test_all_output_fields_present(self):
        parsed = parse_record(SAMPLE_RECORD, search_zip="80302", search_taxonomy="Psychologist")
        self.assertEqual(set(parsed.keys()), set(OUTPUT_FIELDS))

    def test_no_location_address_falls_back(self):
        record = {**SAMPLE_RECORD, "addresses": [SAMPLE_RECORD["addresses"][0]]}
        parsed = parse_record(record, search_zip="80302", search_taxonomy="Psychologist")
        self.assertEqual(parsed["Address 1"], "PO BOX 1")

    def test_no_taxonomies(self):
        record = {**SAMPLE_RECORD, "taxonomies": []}
        parsed = parse_record(record, search_zip="80302", search_taxonomy="Psychologist")
        self.assertEqual(parsed["Primary Taxonomy"], "")
        self.assertEqual(parsed["License Number"], "")


class TaxonomyArgParsingTest(unittest.TestCase):
    """--taxonomies splits on ';' not ',', because a user-supplied term is
    still allowed to contain a comma even though the live NPPES API rejects
    any taxonomy_description containing one (see FetchErrorsTest below)."""

    def test_default_taxonomies_contain_no_commas(self):
        # Confirmed against the live API: any taxonomy_description containing
        # a comma (e.g. "Counselor, Professional") returns zero results with
        # an "Errors" body, even when that exact string is a valid, existing
        # NUCC taxonomy description. Defaults must stick to comma-free terms
        # (e.g. "Counselor") and let users filter the output CSV afterward.
        self.assertTrue(all("," not in t for t in DEFAULT_TAXONOMIES))

    def test_default_taxonomies_survive_cli_round_trip(self):
        args = parse_args(["--zips", "80302"])
        parsed = [t.strip() for t in args.taxonomies.split(";") if t.strip()]
        self.assertEqual(parsed, DEFAULT_TAXONOMIES)

    def test_custom_taxonomies_with_commas_split_correctly(self):
        args = parse_args([
            "--zips", "80302",
            "--taxonomies", "Counselor, Professional;Counselor, Mental Health",
        ])
        parsed = [t.strip() for t in args.taxonomies.split(";") if t.strip()]
        self.assertEqual(parsed, ["Counselor, Professional", "Counselor, Mental Health"])


def _mock_response(payload):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = payload
    return resp


class FetchErrorsTest(unittest.TestCase):
    """The live NPPES API returns HTTP 200 with an "Errors" body instead of
    an HTTP error status for a rejected taxonomy_description (e.g. one
    containing a comma). This must be surfaced loudly, not treated as zero
    results, or a bad search term silently produces an empty/incomplete
    mailing list with no indication anything went wrong."""

    def test_errors_payload_raises(self):
        session = MagicMock()
        session.get.return_value = _mock_response({
            "Errors": [{
                "description": "No taxonomy codes found with entered description",
                "field": "taxonomy_description",
                "number": "14",
            }]
        })
        with self.assertRaises(SystemExit):
            fetch_npi_records(session, "Counselor, Professional", "80302", "NPI-1", 0)

    def test_normal_results_payload_does_not_raise(self):
        session = MagicMock()
        session.get.return_value = _mock_response({"result_count": 0, "results": []})
        records = fetch_npi_records(session, "Counselor", "80302", "NPI-1", 0)
        self.assertEqual(records, [])


if __name__ == "__main__":
    unittest.main()
