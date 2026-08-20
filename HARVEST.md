# Commander field harvest

Use this branch whenever dispatch, steering, heartbeat, or handback behaves differently from the current skill. Harvest at the next safe checkpoint instead of waiting for final cleanup.

## 1. Capture the replay

Record expected behavior, observed behavior, independent evidence, recovery, and affected harness in `~/fleet/<concern>/evidence/field-notes/<date>.md`. Keep field notes outside repositories and skill files while the incident is still uncertain. **Complete when:** another commander could reproduce the failure and distinguish it from the product task.

## 2. Classify the observation

Choose exactly one disposition:

- **patch** — a replayable commander mechanic whose absence changes behavior;
- **proposal** — plausible but not yet replayable, or owned by another governing skill;
- **reject** — duplicate, stale, product-specific, or a no-op versus model defaults.

Check the existing skill, disclosed adapters, pending proposals, and current git diff before deciding. Put each meaning in one source of truth: generic mechanics in `SKILL.md`, harness-only mechanics in that harness adapter.

Style charter: rule prose in English; hard-lesson paragraphs may be Chinese — single layer only (the bilingual English-header + Chinese-body 双层体例 was abolished at 4.0.0; keep whichever layer carries more information, never add a new double-layer rule); role vocabulary is fixed — **worker / commander / Mastermind** (plus *the user*; *owner* only as a possessive). "overseer" is a retired skill name, never a role. Project titles and personal names appear only inside incident citations, never in rule text. **Complete when:** every field observation has one disposition and one owner; none is silently carried forward.

## 3. Apply at a safe checkpoint

**改 frontmatter 前先记住:YAML 纯量里不能出现裸 `: `(冒号+空格)。** 往 `scope:` / `description:` 之类的**未加引号**的值里追加一句带冒号的英文小标题(如 `4.9.0 hardens EVIDENCE: acceptance must…`)会当场把 frontmatter 弄坏,而**故障是静默的**——skill 仍在、正文照读,只是列表里的 description 退化成 H1 标题(2026-07-26 实锤,靠 skill 列表那一行的变化才发现)。用破折号代替冒号,或给整个值加引号 / 改块标量 `>`。改完扫一遍确认每一行 value 里都没有 `: `。

A single methodology owner patches the smallest behavior-changing unit while implementation workers stay off the skill surface. Preserve unrelated dirty changes. Use progressive disclosure for harness or branch-specific detail, bump the skill version according to its existing convention, and prune superseded wording rather than layering a second rule over it.

## 4. Verify and close

Replay the mechanic where safe; run helper tests when scripts changed; run the no-op, duplication, relevance, and negation checks sentence by sentence. Record why rejected observations were not promoted. A promoted field note can remain as evidence, but the skill—not the note—is authoritative. **Complete when:** the new path is demonstrated or explicitly marked proposal-only, and the next heartbeat no longer depends on remembered chat context.

**Security-output sanitation is a tree-wide acceptance gate, not a final-report promise.** When a lane can read credentials, tokens, PII, or private payloads, its job contract must forbid reproducing values and require placeholders plus `file:line`. Before acceptance, scan **every deliverable in the concern's output tree** for the relevant value shapes; sanitizing only the synthesis leaves raw lane reports as a second disclosure. If a literal escaped, redact it without printing it again, republish the corrected artifact so the ledger hash matches, and re-run both positive (the old shape is gone) and negative (the finding and source location remain) checks. (Live 2026-08-16: a supply-chain lane kept the final report secret-safe but copied both audited credentials into its raw report; the commander caught it only with a whole-tree scan.)
