# TDD Skill

Self-contained TDD skill vendored into this repo.

## Read before writing any test

1. [SKILL.md](tdd/SKILL.md) — red/green/refactor workflow, anti-patterns, per-cycle checklist
2. [tests.md](tdd/tests.md) — good vs bad test examples
3. [mocking.md](tdd/mocking.md) — mock at system boundaries only
4. [interface-design.md](tdd/interface-design.md) — design for testability
5. [deep-modules.md](tdd/deep-modules.md) — small interface, deep implementation
6. [refactoring.md](tdd/refactoring.md) — refactor candidates after GREEN

## QueryCraft TDD evidence requirement

Every task commit triple MUST demonstrate TDD:
- `test(T-XXX):` commit **before** `feat(T-XXX):` commit.
- Test commit must fail without the feat commit (proves detection of absence).
- Report TDD evidence per task in Wave Final Report.
- **No horizontal slices** — one RED→GREEN cycle at a time, not all tests then all code.
