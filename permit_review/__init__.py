"""Local agent that reviews building permit application PDFs with Claude.

Package layout:
  scanner        — find/open PDFs and read fillable-form values (no API)
  models         — Pydantic shapes Claude must return
  claude_client  — send a PDF to Claude and parse DocumentOverview
  review         — one-file review used by both the CLI and the web server
  cli            — `python -m permit_review FOLDER`
  web            — `python -m permit_review.web` (local browser UI)
"""
