"""Command line entry point.

    python -m permit_review "C:\\Permits\\October"
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from permit_review import claude_client
from permit_review.review import review_pdf
from permit_review.scanner import find_pdfs


def parse_args(argv=None):
    p = argparse.ArgumentParser(prog="permit_review", description="Review building permit PDFs in a folder.")
    p.add_argument("folder", type=Path, help="Folder that contains the permit PDFs")
    p.add_argument("--recursive", action="store_true", help="Also look in subfolders")
    p.add_argument("--dry-run", action="store_true", help="List the PDFs without calling Claude")
    p.add_argument("--out", type=Path, default=Path("reports"), help="Where to save results (default: reports)")
    return p.parse_args(argv)


def main(argv=None, client=None) -> int:
    args = parse_args(argv)
    load_dotenv()

    if not args.folder.is_dir():
        print(f"Folder not found: {args.folder}", file=sys.stderr)
        return 2

    pdfs = find_pdfs(args.folder, recursive=args.recursive)
    print(f"Found {len(pdfs)} PDF(s) in {args.folder}\n")
    if not pdfs:
        return 0

    if not args.dry_run and client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.", file=sys.stderr)
            return 2
        client = claude_client.make_client()

    results = []
    for pdf in pdfs:
        name = pdf.path.relative_to(args.folder)
        pages = "?" if pdf.page_count is None else pdf.page_count
        print(f"== {name}  ({pages} pages)")
        if args.dry_run:
            entry = {"file": str(name), "page_count": pdf.page_count}
            if pdf.error:
                entry["error"] = pdf.error
        else:
            try:
                entry, overview = review_pdf(client, pdf, str(name))
            except anthropic.AuthenticationError:
                print("Your API key was rejected. Check ANTHROPIC_API_KEY in .env.", file=sys.stderr)
                return 2
            if overview:
                _print_overview(overview)

        if "error" in entry:
            print(f"   ERROR: {entry['error']}")
        print()
        results.append(entry)

    if not args.dry_run:
        args.out.mkdir(parents=True, exist_ok=True)
        out_file = args.out / f"review-{datetime.now():%Y%m%d-%H%M%S}.json"
        out_file.write_text(json.dumps({"folder": str(args.folder), "files": results}, indent=2))
        print(f"Saved results to {out_file}")
    return 0


def _print_overview(overview):
    tag = "permit application" if overview.is_permit_application else "NOT a permit application"
    print(f"   [{tag}] {overview.summary}")
    for s in overview.sections:
        pages = f"p{s.start_page}" if s.start_page == s.end_page else f"p{s.start_page}-{s.end_page}"
        print(f"   - {pages:>9}  {s.kind:<16} {s.title}")
    if overview.required_attachments:
        print("   Required attachments:")
        for a in overview.required_attachments:
            if a.applies == "no":
                mark = "-"
            else:
                mark = "ok" if a.satisfied else "MISSING"
            where = f" (p{', '.join(map(str, a.found_on_pages))})" if a.found_on_pages else ""
            print(f"   {mark:>7}  {a.name}{where}: {a.evidence}")
            if a.condition:
                print(f"            only {a.condition}; applies here: {a.applies}. {a.applies_reason}")
    if overview.form_fields:
        missing = overview.incomplete_fields()
        result = "COMPLETE" if not missing else f"INCOMPLETE ({len(missing)} missing)"
        print(f"   Form fields: {len(overview.form_fields)} checked, {result}")
        for f in missing:
            detail = f": {f.note}" if f.note else ""
            print(f"   ! {f.label} (p{f.page}) is {f.status}{detail}")
    if overview.passed():
        print("   RESULT: PASS")
    else:
        reasons = []
        if not overview.is_permit_application:
            reasons.append("no permit application form found")
        reasons += [f"field '{f.label}' {f.status}" for f in overview.incomplete_fields()]
        reasons += [f"missing {a.name}" for a in overview.missing_attachments()]
        print(f"   RESULT: FAIL ({'; '.join(reasons)})")
