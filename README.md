# Permit Review agent

A local Web Page written in Python you point at a folder of PDFs. For each PDF it checks that the  
permit application form (building, sign, and so on) is completely filled in and that the attachments the  
form requires are included, then reports pass or fail with what's missing.

Claude (via the Anthropic API) does the reading: each PDF is sent whole, so Claude sees
both the text and the page images, which matters for scanned pages and drawings.

## Create Folder (once)

1. Create a folder on your hard drive. The folder can be anywhere on your computer.
2. Copy the files in the `sample_permits` file of this repo into that folder

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
python3 -m pytest            # should print "11 passed" (no API calls)
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

This starts a small server on your computer and opens http://localhost:8765 in your browser. **NOTE:** if you need to change the default port of 8765 edit line 120 in the web.py file  
Leave the terminal open while you use the page, and press Ctrl+C there to stop it.

1. Open Chrome and go to: http://localhost:8765
2. Click **Choose folder…** and pick the folder with the permit PDFs. Your browser will ask

   to confirm "uploading" the files: they only go to the server on your own computer, which sends each PDF to Claude for review. Only PDFs directly in that folder are reviewed, not ones in subfolders.
3. Click **Review PDFs**. Each PDF gets a card that fills in as its review finishes

   (two at a time), with a running count of passed and failed at the top.
4. Once the review is complete, a **Ready for approval** list above the results shows every passed PDF with a "**Submit for approval**" checkbox. Please note, this is a mock-up for now: nothing is sent anywhere.

## Additional Information

PDFs still waiting or being reviewed are shown first. Finished results are grouped below  
them: **Passed**, then **Failed**, then any PDFs that couldn't be reviewed.  
A failed card lists what's missing (blank form fields and missing attachments, with page  
numbers), and its breakouts show how many items are correct out of the total, for example  
"Form fields (25/30)" or "Required attachments (1/2)". Expand them to see every field and  
attachment.

## Build plan

| Step | What it does | Status |
|------|--------------|--------|
| 1 | Read each PDF in the folder; Claude describes it and splits it into the application form and attachments, with page ranges | done |
| 2 | Pull the list of required attachments out of the form, including conditional ones and whether they apply | done |
| 3 | Check every field on the form is filled in | done |
| 4 | Check the later pages contain each required attachment, and give each PDF a PASS or FAIL | done |
| 5 | Local web page: pick a folder, see PASS/FAIL per PDF and what's missing | **done** |
