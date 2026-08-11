# Contributing to fleet-commander

Thanks for your interest. This project is maintained by a small team and we
welcome contributions that improve the skillbook's accuracy and coverage.

## How to contribute

1. **Open an issue first** for anything beyond a typo fix — describe the
   incident or gap that motivates the change.
2. Fork the repo and create a feature branch from `main`.
3. Make your changes. If adding a new rule, include the date and a one-line
   description of the incident that produced it.
4. Run the tests: `python3 -m pytest scripts/tests/`
5. Open a pull request against `main`.

## What makes a good contribution

- **Incident-backed rules** — every guardrail should trace to a real failure.
  "This seems like a good idea" is not enough; "this broke on 2026-XX-XX
  because..." is.
- **Worker adapter additions** — if you run a fleet with an agent not yet
  covered (Cursor, Aider, etc.), a new adapter file following the existing
  pattern is welcome.
- **Bug fixes to return-channel.py** — include a test case that reproduces the
  bug.

## What we won't merge

- Theoretical rules without incident backing.
- Changes that remove dates from existing rules.
- Additions to SKILL.md that belong in a companion file.

## Style

- Plain Markdown, no front-matter in docs (except SKILL.md which carries skill
  metadata).
- Lines wrapped at 80 characters where practical.
- Dates in ISO 8601 (YYYY-MM-DD).

## License

By contributing you agree that your contributions are licensed under the
[MIT License](LICENSE).
