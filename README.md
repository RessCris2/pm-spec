# pm-spec

[中文](README.zh-CN.md)

An agent skill that writes an **as-built functional spec** of an existing
codebase and keeps it current on every pull request.

The spec is for people who did not write the code: product managers,
designers, testers, new engineers. It covers entities and their
relationships, entity lifecycles, the business rules the code enforces, key
flows, pages, and prototypes for what is missing. Every fact links to the
source lines that prove it, and a script checks every link.

It is not a PRD. Code shows what the system does, not why it was built or how
success is measured; those questions are collected for a person to answer.

## What you get

```
docs/spec/
├── spec.md          # the spec
├── changes.md       # what changed in the spec, per pull request
├── diagrams/        # PlantUML sources and rendered SVGs
└── prototypes/      # SVG prototypes, drawn only after the ASCII draft is confirmed
```

`spec.md` sections: Readers · Overview · Entities · Relations · Lifecycles ·
Decisions (business rules) · Flows · Pages · Gaps · Proposals · Open
questions.

## How it works

| Step | Done by |
|---|---|
| Find where entities, states, rules, pages and entry points are defined | `scripts/scan.py` |
| Name the readers, inventory everything in scope, write each section | the model (subagents for large codebases) |
| Verify every link, line range and quote; flag facts with no source | `scripts/check_spec.py` |
| Cut repeated and unneeded content | an independent subagent (`references/reviewer.md`) |
| Render PlantUML to SVG, locally | `scripts/render_diagrams.py` |

Writing rules: one fact in one place; cut what does not change the reader's
understanding; as-is and proposals kept apart; 〔推断〕 for readings the code
does not prove, 〔未知〕 for what is not in the code.

Prototypes are drawn as ASCII first. The SVG is drawn only after a person
confirms the logic and wording.

## Keeping it current

On a pull request, `check_spec.py --diff <base> --fix-lines`:

- shifts line numbers of facts whose code only moved, and follows renames;
- lists facts whose cited lines changed, for the agent to re-read and rewrite;
- lists changed code that no fact cites, for the agent to check for new
  entities, states, rules or pages.

The agent updates only what changed, logs it in `changes.md`, commits to the
PR branch and comments a summary. No spec change, no commit.

Run it locally by asking the agent to update the spec, or on every PR with
`templates/spec-update.yml` (GitHub Actions, `anthropics/claude-code-action`;
needs an `ANTHROPIC_API_KEY` secret; costs API usage per run; skips PRs from
forks).

## Install

```bash
git clone https://github.com/RessCris2/pm-spec.git ~/.claude/skills/pm-spec
```

Then ask, for example: "根据代码写一份功能规格" or "Write a functional spec
for this repository".

Requirements: Python 3.10+, git. For diagrams: `plantuml` on PATH, or Java
and `PLANTUML_JAR=/path/to/plantuml.jar`. Diagrams are never sent to a remote
renderer.

## Tests

```bash
python3 -m unittest discover -s tests
```

## License

MIT
