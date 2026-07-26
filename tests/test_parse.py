import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clinician_mailing_list import parse_record, OUTPUT_FIELDS  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
