# Commander field harvest

Use this branch whenever dispatch, steering, heartbeat, or handback behaves differently from the current skill. Harvest at the next safe checkpoint instead of waiting for final cleanup.

## 1. Capture the replay

Record expected behavior, observed behavior, independent evidence, recovery, and affected harness in `/tmp/commander/field-notes/<date>.md`. Keep field notes outside repositories and skill files while the incident is still uncertain. **Complete when:** another commander could reproduce the failure and distinguish it from the product task.

## 2. Classify the observation

Choose exactly one disposition:

- **patch** — a replayable commander mechanic whose absence changes behavior;
- **proposal** — plausible but not yet replayable, or owned by another governing skill;
- **reject** — duplicate, stale, product-specific, or a no-op versus model defaults.

Check the existing skill, disclosed adapters, pending proposals, and current git diff before deciding. Put each meaning in one source of truth: generic mechanics in `SKILL.md`, harness-only mechanics in that harness adapter.

Style charter: all rule prose and hard-lesson paragraphs are in English, in a single layer only. The former bilingual English-header + non-English-body format was abolished in internal 4.0.0; retain the one layer that carries the full information and never add a new double-layer rule. Role vocabulary is fixed — **worker / commander / Mastermind** (plus *the user*; *owner* only as a possessive). Retired predecessor names are never roles. Project titles and personal names appear only inside incident citations, never in rule text. **Complete when:** every field observation has one disposition and one owner; none is silently carried forward.

## 3. Apply at a safe checkpoint

A single methodology owner patches the smallest behavior-changing unit while implementation workers stay off the skill surface. Preserve unrelated dirty changes. Use progressive disclosure for harness or branch-specific detail, bump the skill version according to its existing convention, and prune superseded wording rather than layering a second rule over it.

## 4. Verify and close

Replay the mechanic where safe; run helper tests when scripts changed; run the no-op, duplication, relevance, and negation checks sentence by sentence. Record why rejected observations were not promoted. A promoted field note can remain as evidence, but the skill—not the note—is authoritative. **Complete when:** the new path is demonstrated or explicitly marked proposal-only, and the next heartbeat no longer depends on remembered chat context.
