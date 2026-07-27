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
  --radius-miles 35 \
  --output boulder_denver_mailing_list.csv
```

### Explicit zip list mode (no pgeocode/pandas needed)

```bash
python3 clinician_mailing_list.py \
  --zips 80301,80302,80303,80304,80305,80310,80026,80027,80501,80503,80504 \
  --output boulder_mailing_list.csv
```

If you omit `--taxonomies`, it defaults to the broad `Psychologist` /
`Counselor` search described below.

### Options

| Flag | Description | Default |
|---|---|---|
| `--zips` | Comma-separated explicit zip codes | — |
| `--center-zip` | Center zip for radius expansion (needs `pgeocode`) | — |
| `--radius-miles` | Radius in miles around `--center-zip` | 25 |
| `--taxonomies` | Semicolon-separated NPI taxonomy search terms (comma-free, see below) | Psychologist; Counselor |
| `--enumeration-type` | `NPI-1` (individuals) or `NPI-2` (organizations) | `NPI-1` |
| `--output` | Output CSV path | `clinician_mailing_list.csv` |
| `--delay` | Seconds between API requests (politeness) | 0.2 |

Exactly one of `--zips` or `--center-zip` must be given.

## Default taxonomy set and why

**Important registry quirk, confirmed against the live API:** `taxonomy_description`
only accepts simple, comma-free search terms. NPI taxonomy descriptions are
officially formatted as `"Category, Qualifier"` (e.g. `Counselor, Professional`
for an LPC, `Counselor, Mental Health` for a mental health counselor,
`Psychologist, Clinical` for a clinical psychologist) — but searching for
that exact, correctly-formatted string returns an API error
(`"No taxonomy codes found with entered description"`) and zero results,
even though it's a real, valid taxonomy. Reformatting the words
(`"Professional Counselor"`) doesn't help either — it just fails
differently. Only single words/phrases with no comma work reliably.

So the script searches broad terms instead:

- **`Psychologist`** → matches every psychologist subtype (Clinical,
  Counseling, School, Cognitive & Behavioral, Clinical Neuropsychologist,
  etc.) since they all contain the word "psychologist."
- **`Counselor`** → matches every counselor subtype, including
  `Counselor, Professional` (Colorado's LPC license) and
  `Counselor, Mental Health`, but also others like `Counselor, Addiction
  (Substance Use Disorder)` and `Counselor, School`.

**To narrow down to just LPCs and mental health counselors**, open the
output CSV in Excel/Sheets and filter the **Primary Taxonomy** column to
exactly `Counselor, Professional` and `Counselor, Mental Health` (and
whichever `Psychologist, ...` subtypes you want to keep). The script pulls
the broader set on purpose so you have that column to filter on, rather
than silently dropping subtypes the registry's search can't target directly.

Edit `--taxonomies` (semicolon-separated) to add/remove broad categories
for future trainings — stick to single words or short comma-free phrases,
e.g. `Social Worker`, `Marriage & Family Therapist`, `Nurse Practitioner`.
Check candidate terms at [taxonomy.nucc.org](https://taxonomy.nucc.org/),
then verify the exact term returns results by testing it directly:
`https://npiregistry.cms.hhs.gov/api/?version=2.1&taxonomy_description=YOUR_TERM&limit=5`

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
