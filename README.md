# Permit Review agent

A local Python tool you point at a folder of PDFs. For each PDF it checks that the
permit application form (building, sign, and so on) is completely filled in and that the attachments the
form requires are included, then reports pass or fail with what's missing.

Claude (via the Anthropic API) does the reading: each PDF is sent whole, so Claude sees
both the text and the page images, which matters for scanned pages and drawings.

The folder can be anywhere on your computer. To review files that live in Google Drive,
install [Google Drive for desktop](https://www.google.com/drive/download/) and point the
tool at the synced folder (for example `G:\My Drive\Permits` on Windows or
`~/Library/CloudStorage/GoogleDrive-you@gmail.com/My Drive/Permits` on a Mac).

## Build plan

| Step | What it does | Status |
|------|--------------|--------|
| 1 | Read each PDF in the folder; Claude describes it and splits it into the application form and attachments, with page ranges | done |
| 2 | Pull the list of required attachments out of the form, including conditional ones and whether they apply | done |
| 3 | Check every field on the form is filled in | done |
| 4 | Check the later pages contain each required attachment, and give each PDF a PASS or FAIL | done |
| 5 | Local web page: pick a folder, see PASS/FAIL per PDF and what's missing | **done** |

## Setup (once)

Requires Python 3.10 or newer. On a Mac, the built-in `python3` is usually 3.9, which is
too old. Check with `python3 --version`. If it's below 3.10, install the latest Python from
https://www.python.org/downloads/ (or `brew install python@3.12` if you use Homebrew),
then use `python3.12` (or whichever version you installed) for the first command below.

Run these from the project folder. On macOS/Linux:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest            # should print "11 passed" (no API calls)
```

On Windows:

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest
```

After activating, your prompt starts with `(.venv)` and plain `python` is the right
version. Activate it again (`source .venv/bin/activate`) each time you open a new terminal.

Add your API key:

1. Create a key at https://console.anthropic.com/settings/keys
2. Copy `.env.example` to `.env` and paste the key after `ANTHROPIC_API_KEY=`.
   `.env` is in `.gitignore`, so the key never gets committed.

## Using the web page

```bash
python -m permit_review.web
```

This starts a small server on your computer and opens http://localhost:8765 in your browser.
Leave the terminal open while you use the page, and press Ctrl+C there to stop it.

1. Click **Choose folder…** and pick the folder with the permit PDFs. Your browser will ask
   to confirm "uploading" the files: they only go to the server on your own computer, which
   sends each PDF to Claude for review. Only PDFs directly in that folder are reviewed, not
   ones in subfolders.
2. Click **Review N PDFs**. Each PDF gets a card that fills in as its review finishes
   (two at a time), with a running count of passed and failed at the top.

PDFs still waiting or being reviewed are shown first. Finished results are grouped below
them: **Passed**, then **Failed**, then any PDFs that couldn't be reviewed.
A failed card lists what's missing (blank form fields and missing attachments, with page
numbers), and its breakouts show how many items are correct out of the total, for example
"Form fields (25/30)" or "Required attachments (1/2)". Expand them to see every field and
attachment.

When the run finishes, a **Ready for approval** list above the results shows every passed PDF
with a "Submit for approval" checkbox. **Submit for approval** marks the checked ones as
submitted. This is a mock-up for now: nothing is sent anywhere.

Use `--port 9000` if 8765 is taken, or `--no-browser` to open the page yourself.

## Using the command line

The same review also runs in the terminal. First check it finds your PDFs without spending anything:

```bash
python -m permit_review samples --dry-run
```

Then run it:

```bash
python -m permit_review samples
python -m permit_review "/path/to/Permits" --recursive   # include subfolders
```

Each run prints a review of every PDF and saves the full results as JSON in `reports/`.

## Sample packets and how results are decided

`samples/` holds three packets. Pick that folder on the web page to try them:

| File | Expected result |
|------|-----------------|
| `sign_permit_sample_pass.pdf` | PASS: form complete, and pages 3 and 4 are the description of sign and the plat |
| `sign_permit_sample_fail.pdf` | FAIL: same packet with the plat page removed |
| `sample_permit_packet.pdf` | FAIL: contractor phone is blank and the construction drawings are missing |

In the terminal version, each PDF ends with a result, for example:

```
   Required attachments:
        ok  Description of sign (p3): Page 3 is titled 'Description of Sign'.
        ok  Plat showing sign location (p4): Page 4 is titled 'Plat - Sign Location'.
   Form fields: ... checked, COMPLETE
   RESULT: PASS
```

How attachments are matched:

- A required document counts as attached when a page after the form is **titled or clearly
  labeled** with its name. The rest of the page can be placeholder text; the tool checks the
  document is there, not what it says.
- A box on the form saying "attached" doesn't count on its own; the page has to be there.
- Only documents to attach are checked. Requirements that aren't a document, like "Sign
  meets the 2015 IBC wind load requirements", fees, or code compliance, are left out.
- A conditional item only counts when it applies. If Claude can't tell whether it applies,
  it counts as missing so a person looks at it.

A packet **passes** only when it contains a permit application, every required field is
filled in, and every required attachment is present. The saved JSON has `result`,
`incomplete_fields` and `missing_attachments` for each PDF.

**What to verify (step 5):** on the web page, the three samples give the expected results,
each FAIL lists the right reasons, and a folder of your own works the same way.

### Cost

Each PDF is one request to Claude Opus 5.5. A PDF costs roughly 1,500 to 3,000 input
tokens per page, so a 20-page packet is roughly 15 to 25 cents at current prices
($4 per million input tokens).

### Limits and troubleshooting

- PDFs over about 24 MB or 600 pages are skipped with a message (an API limit).
- *ANTHROPIC_API_KEY is not set* → create `.env` as described above, and run from the project folder.
- *Your API key was rejected* → check the key in `.env`, and that your Anthropic account has credit.

## Project layout

```
permit_review/
  web.py            local web page server: python -m permit_review.web
  static/           the page itself (HTML, CSS, JavaScript)
  cli.py            command line: python -m permit_review <folder>
  review.py         reviews one PDF and decides PASS/FAIL (used by both of the above)
  scanner.py        finds PDFs and counts pages locally (no API)
  claude_client.py  everything that talks to Claude: prompts and the API call
  models.py         the structure Claude's answers must follow
samples/            a made-up permit packet for testing, and the script that builds it
tests/              tests that use a fake Claude, so they run free and offline
```
