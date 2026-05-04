# Spec-Driven Development Workflow

This project uses Spec-Driven Development (SDD) via [GitHub spec-kit v0.8.4](https://github.com/github/spec-kit/releases/tag/v0.8.4). This document is the operational guide; the binding principles live in [`.specify/memory/constitution.md`](../.specify/memory/constitution.md). When the two disagree, the constitution wins.

## Overview

SDD reverses the usual order of operations. Instead of writing code and documenting it after, you write the spec first, get alignment on what is being built and why, then let the spec drive the plan, tasks, and implementation. For a single-maintainer project this might sound like overhead; in practice it pays for itself the first time you have to revisit a decision two weeks later, or the first time an AI agent needs context about why a particular constraint exists.

The point of using a spec-driven workflow on this project specifically is that the v1 design intent is already captured in `Modifier25_Defender_Spec.docx` in the parent directory. SDD lets us translate that intent into per-feature specs that the agent and a future reviewer can verify against. It also gives the Compliance Guard a clear architectural precedent: the development process itself separates intent (spec), design (plan), and execution (tasks and implementation).

The constitution at `.specify/memory/constitution.md` is the source of truth for binding principles. Every plan must be evaluated against it at the Constitution Check gate.

## The v0.8.4 Workflow

Slash commands shipped with v0.8.4 (verified against `.claude/skills/` after `specify init`):

| Command | Purpose | Phase |
|---------|---------|-------|
| `/speckit-constitution` | Establish or amend project governing principles | Setup or governance change |
| `/speckit-specify` | Define requirements and user stories for a new feature | Spec |
| `/speckit-clarify` | Surface underspecified areas in the current spec via up-to-5 targeted questions | Spec (optional) |
| `/speckit-plan` | Produce a technical implementation plan from the approved spec | Plan |
| `/speckit-tasks` | Generate a dependency-ordered task list from the plan | Tasks |
| `/speckit-checklist` | Produce a custom quality checklist for the feature | Plan or Tasks (optional) |
| `/speckit-analyze` | Cross-artifact consistency analysis across spec, plan, and tasks | Pre-implement (optional but recommended) |
| `/speckit-implement` | Execute the task list against the plan and spec | Implement |
| `/speckit-taskstoissues` | Convert tasks into GitHub issues | Optional, only when working with a GitHub remote |

Git extension commands (used automatically by hooks before and after each major command):

| Command | Purpose |
|---------|---------|
| `/speckit-git-initialize` | Initialize the git repository (idempotent) |
| `/speckit-git-feature` | Create a feature branch with sequential or timestamp numbering |
| `/speckit-git-commit` | Auto-commit changes after a spec-kit command completes |
| `/speckit-git-remote` | Detect or set the GitHub remote URL |
| `/speckit-git-validate` | Validate the current branch follows naming conventions |

## Per-Feature Sequence

For every new feature:

1. **`/speckit-specify`** with a description of what is being built and why. This produces `specs/<NNN-slug>/spec.md`. For the first feature on this project, the description is "translate the v1 design captured in Modifier25_Defender_Spec.docx into a spec-kit feature spec preserving all EPICs, acceptance criteria, data contracts, and risk register"; see `specs/001-modifier-25-defender/` once it exists.
2. **`/speckit-clarify`** (optional, recommended for novel features). Surfaces underspecified areas as targeted questions; answers fold back into the spec. Skip for features where the spec was authored carefully and the design intent is fixed (the v1 translation is one such case, though clarify can still be run if helpful).
3. **`/speckit-plan`**. Produces `plan.md` and the supporting design artifacts under the same `specs/<NNN-slug>/` directory. The Constitution Check gate at the top of the plan template MUST be evaluated against `.specify/memory/constitution.md` before Phase 0 research and again after Phase 1 design.
4. **`/speckit-tasks`**. Produces `tasks.md`. Tasks are grouped by user story and ordered by dependency.
5. **`/speckit-analyze`** (optional but recommended for the first feature). Produces a cross-artifact consistency report. Address all surfaced issues or explicitly accept them in writing before moving to implement.
6. **`/speckit-implement`**. Executes the task list. CI quality gates must pass before merge.

Each step's auto-commit hook is enabled by default in `.specify/extensions.yml` and is mostly optional; the constitution-related and feature-creation hooks are mandatory.

## Branch Convention

- **Branch name format**: `feature/<NNN>-<slug>` matching the spec directory name.
- **Numbering strategy**: sequential (`001`, `002`, ...). This is the spec-kit default and the project's accepted convention; see the `BRANCH_NUMBERING_CONFIRM` open question in the constitution for the deferred explicit confirmation.
- **PR review**: required even for solo work. Self-review with a 24-hour cool-off period satisfies the requirement during the solo phase.
- **CI gates**: all PR-blocking quality gates (retrieval recall, verdict accuracy, compliance guard recall, RAGAS faithfulness, latency, lint, type, format, em-dash check) MUST pass before merge. `--no-verify`, force-push to main, and admin override merges are forbidden.

## Local Commands and Wrappers

`uv tool install` puts `specify` on PATH; from any directory in the repo:

```powershell
# show installed version
specify version

# the slash commands are invoked through Claude Code, not via specify CLI directly
```

There are no project-local wrapper scripts beyond the spec-kit-installed ones in `.specify/scripts/powershell/` and `.specify/extensions/git/scripts/powershell/`. Inspect those if you need to know what a hook actually does at the shell level.

## What Lives Where

```
modifier-25-defender/
├── .specify/
│   ├── memory/
│   │   └── constitution.md            # binding principles, this is the contract
│   ├── templates/                     # spec, plan, tasks, checklist, constitution templates
│   ├── scripts/powershell/            # spec-kit shell helpers
│   ├── extensions/git/                # git extension scripts and hook definitions
│   ├── extensions.yml                 # hook configuration
│   ├── workflows/speckit/             # workflow definition for the agent
│   └── integrations/{claude,speckit}.manifest.json
├── .claude/
│   └── skills/                        # speckit-* skills used by Claude Code
├── specs/
│   └── <NNN-slug>/                    # one directory per feature
│       ├── spec.md                    # /speckit-specify output
│       ├── plan.md                    # /speckit-plan output
│       ├── research.md                # /speckit-plan Phase 0 output
│       ├── data-model.md              # /speckit-plan Phase 1 output
│       ├── contracts/                 # /speckit-plan Phase 1 output
│       ├── quickstart.md              # /speckit-plan Phase 1 output
│       └── tasks.md                   # /speckit-tasks output
├── docs/
│   └── SPEC_DRIVEN_DEVELOPMENT.md     # this file
├── app/, eval/, ui/, data/, infra/    # added incrementally as specs land
└── ...
```

## Reference Materials and Where the Design Came From

The v1 design intent for this project predates spec-kit init. The following documents in the parent directory of this project (`C:\Users\arunv\Documents\JARALL_MM\`) are the canonical sources:

- `Modifier25_Defender_Spec.docx`: the v1 technical specification. Source of truth for feature `001-modifier-25-defender`. Contains the EPIC structure, acceptance criteria with `AC-XXX-N` identifiers, data contracts, eval methodology, and risk register.
- `Modifier25_Defender_OnePager.docx`: executive summary for non-engineering stakeholders. Useful for plain-language framing of project purpose.
- `JARALL_EHR_Integration_Brief.docx`: technical context for the EHR landscape (NextGen, eClinicalWorks). Out of scope for v1 but informs the v2 deferred backlog noted in the spec and constitution.
- `README.md` (parent): the public-facing project README.

These documents are referenced from the per-feature specs but MUST NOT be edited as part of feature work. If the design intent itself changes, that is a separate change captured in a new revision of the source document and reflected in a fresh spec under `specs/<NNN-slug>/`.

## When to Amend the Constitution vs. Write a Spec

- **Spec change**: new feature, new acceptance criterion, new module, new piece of UI. Goes through `/speckit-specify` and the per-feature workflow.
- **Constitution change**: change to a binding principle, change to the tech stack at the category level, change to test discipline, change to the development workflow itself. Goes through `/speckit-constitution`, requires a Sync Impact Report, and follows semver (MAJOR for breaking, MINOR for additive, PATCH for clarifications).

If you are unsure, write a spec first. The constitution is for things that, once changed, change every spec that follows.
