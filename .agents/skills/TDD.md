# TDD Skill — Project-Local Pointer

This project uses the global TDD skill at `~/.agents/skills/tdd/`.

## Read before writing any test

1. `~/.agents/skills/tdd/SKILL.md` — red/green/refactor workflow, anti-patterns, per-cycle checklist
2. `~/.agents/skills/tdd/tests.md` — good vs bad test examples
3. `~/.agents/skills/tdd/mocking.md` — mock at system boundaries only
4. `~/.agents/skills/tdd/interface-design.md` — design for testability
5. `~/.agents/skills/tdd/deep-modules.md` — small interface, deep implementation
6. `~/.agents/skills/tdd/refactoring.md` — refactor candidates after GREEN

## QueryCraft TDD evidence requirement

Every task commit triple MUST demonstrate TDD:
- `test(T-XXX):` commit **before** `feat(T-XXX):` commit.
- Test commit must fail without the feat commit (proves detection of absence).
- Report TDD evidence per task in Wave Final Report.
- **No horizontal slices** — one RED→GREEN cycle at a time, not all tests then all code.
