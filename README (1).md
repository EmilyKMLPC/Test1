# Clinician Mailing List Builder

Builds a CSV mailing list of individual clinicians (name + practice mailing
address) near a given zip code, for promoting continuing education /
in-person training events.

## Data source and why it's used

This tool queries the **NPPES NPI Registry** (`npiregistry.cms.hhs.gov`), the
free public database maintained by CMS of every licensed healthcare provider
in the US. It was chosen deliberately over scraping Google Business listings
or other directories:

- It's a federal public dataset explicitly designed for programmatic /
  bulk lookup — no terms-of-service conflict (Google's Places/Maps
  Platform terms, by contrast, explicitly prohibit using their data to
  build a mailing list).
- It returns **practice mailing addresses**, not home addresses.
- It's filterable by taxonomy (specialty/license type) and postal code.

**What it does NOT give you:** email addresses. The NPI registry doesn't
publish them, and scraping the web for individual providers' emails runs
into CAN-SPAM and site-terms-of-service issues. Recommended approach for
email: use this list for a **physical-mail invitation** (postcard/letter)
with a QR code / short URL where recipients opt in to receive email
updates about the training. That gives you a compliant, opt-in email list
alongside the compliant mailing-address list.

## Setup

```bash
pip install -r requirements.txt
```

`requests` is required always. `pgeocode` (pulls in `pandas`) is only
needed if you use `--center-zip`/`--radius-miles` mode; `--zips` mode with
an explicit list works with just `requests`.

> `pgeocode` downloads a US postal-code/lat-long dataset from GeoNames on
> first use and caches it locally (`~/.cache/pgeocode/`). That download,
> and the NPI registry queries themselves, require normal outbound
> internet access — run this from your own machine or an environment
> without a restrictive network allowlist.

## Usage

### Radius mode (reusable for any city)

```bash
python3 clinician_mailing_list.py \
  --center-zip 80302 \
  --radius-miles 20 \
  --taxonomies "Psychologist;Psychologist, Clinical;Psychologist, Counseling;Counselor, Professional;Counselor, Mental Health" \
  --output boulder_mailing_list.csv
```

### Explicit zip list mode (no pgeocode/pandas needed)

```bash
python3 clinician_mailing_list.py \
  --zips 80301,80302,80303,80304,80305,80310,80026,80027,80501,80503,80504 \
  --output boulder_mailing_list.csv
```

If you omit `--taxonomies`, it defaults to the psychologist / licensed
professional counselor / mental health counselor set described below.

### Options

| Flag | Description | Default |
|---|---|---|
| `--zips` | Comma-separated explicit zip codes | — |
| `--center-zip` | Center zip for radius expansion (needs `pgeocode`) | — |
| `--radius-miles` | Radius in miles around `--center-zip` | 25 |
| `--taxonomies` | Semicolon-separated NPI taxonomy descriptions to search | Psychologist; Psychologist, Clinical; Psychologist, Counseling; Counselor, Professional; Counselor, Mental Health |
| `--enumeration-type` | `NPI-1` (individuals) or `NPI-2` (organizations) | `NPI-1` |
| `--output` | Output CSV path | `clinician_mailing_list.csv` |
| `--delay` | Seconds between API requests (politeness) | 0.2 |

Exactly one of `--zips` or `--center-zip` must be given.

## Default taxonomy set and why

The three categories you asked about map to these NPI taxonomy
descriptions. **Note the registry uses "Category, Qualifier" order**
(e.g. `Counselor, Professional`, not `Professional Counselor`) — the
search only matches literal substrings, so getting this order backwards
silently returns zero results for that category instead of erroring.

- **Psychologist** → `Psychologist`, `Psychologist, Clinical`, `Psychologist, Counseling`
- **Licensed Professional Counselor** (Colorado's LPC license) → `Counselor, Professional`
- **Mental Health Counselor** → `Counselor, Mental Health`

Because the search matches substrings, `Psychologist` alone also
incidentally catches related types like `Psychologist, School` and
`Clinical Neuropsychologist` (which contains the substring
"psychologist"). It will *not* catch counselor-type records unless you
search their exact "Counselor, ..." description.

Edit `--taxonomies` (semicolon-separated) to add/remove specialties for
future trainings — check the exact wording at
[taxonomy.nucc.org](https://taxonomy.nucc.org/) first, e.g.
`Social Worker, Clinical`, `Marriage & Family Therapist`,
`Psychiatric/Mental Health, Nurse Practitioner`.

## Output columns

`NPI, First Name, Last Name, Credential, Primary Taxonomy, All Taxonomies,
Address 1, Address 2, City, State, ZIP, Phone, License Number, License
State, Matched Search Zip, Matched Search Taxonomy`

Records are de-duplicated by NPI number across all zip/taxonomy
combinations searched.

## Compliance notes

- This pulls **public federal registry data** with no scraping and no
  ToS violation.
- No emails are collected or inferred — don't add scraped emails to this
  list downstream without a compliant (opt-in) source.
- Physical mail to a business/practice address for a professional CE
  offering is standard commercial mail; still identify your organization
  clearly and honor any removal requests.
