---
name: speckit
description: The Antigravity Spec-Kit skill for driving the SDLC using workflows and skills.
---

# 🚀 Spec-Kit: Antigravity Skills & Workflows

> **The Event Horizon of Software Quality.**
> *Adapted for Google Antigravity IDE from [github/spec-kit](https://github.com/github/spec-kit).*
> *Version: 1.1.0*

---

## 🌟 Overview

Welcome to the **Antigravity Edition** of Spec-Kit. This system is architected to empower your AI pair programmer (Antigravity) to drive the entire Software Development Life Cycle (SDLC) using two powerful mechanisms: **Workflows** and **Skills**.

### 🔄 Dual-Mode Intelligence
In this edition, Spec-Kit commands have been split into two interactive layers:

1.  **Workflows (`/command`)**: High-level orchestrations that guide the agent through a series of logical steps. **The easiest way to run a skill is by typing its corresponding workflow command.**
2.  **Skills (`@speckit.name`)**: Packaged agentic capabilities. Mentions of a skill give the agent immediate context and autonomous "know-how" to execute the specific toolset associated with that phase.

> **To understand the power of Skills in Antigravity, read the docs here:**
> [https://antigravity.google/docs/skills](https://antigravity.google/docs/skills)

---

## 🏗️ The Architecture

The toolkit is organized into modular components that provide both the logic (Scripts) and the structure (Templates) for the agent.

```text
.agent/
├── skills/                  # @ Mentions (Agent Intelligence)
│   ├── SPECKIT.md           # This file (The brain)
│
├── workflows/               # / Slash Commands (Orchestration)
│   ├── speckit.next.md      # Auto-suggestion logic
│   └── ... (Placeholder workflows)
│
└── scripts/                 # Shared Bash Core (Kinetic logic)
```

---

## 🗺️ Mapping: Commands to Capabilities

| Phase | Workflow Trigger | Antigravity Skill | Role |
| :--- | :--- | :--- | :--- |
| **Pipeline** | `/00-speckit.all` | N/A | Runs the full SDLC pipeline. |
| **Governance** | `/01-speckit.constitution` | `@speckit.constitution` | Establishes project rules & principles. |
| **Definition** | `/02-speckit.specify` | `@speckit.specify` | Drafts structured `spec.md`. |
| **Ambiguity** | `/03-speckit.clarify` | `@speckit.clarify` | Resolves gaps post-spec. |
| **Architecture** | `/04-speckit.plan` | `@speckit.plan` | Generates technical `plan.md`. |
| **Decomposition** | `/05-speckit.tasks` | `@speckit.tasks` | Breaks plans into atomic tasks. |
| **Consistency** | `/06-speckit.analyze` | `@speckit.analyze` | Cross-checks Spec vs Plan vs Tasks. |
| **Execution** | `/07-speckit.implement` | `@speckit.implement` | Builds implementation with safety protocols. |
| **Quality** | `/08-speckit.checker` | `@speckit.checker` | Runs static analysis (Linting, Security, Types). |
| **Testing** | `/09-speckit.tester` | `@speckit.tester` | Runs test suite & reports coverage. |
| **Review** | `/10-speckit.reviewer` | `@speckit.reviewer` | Performs code review (Logic, Perf, Style). |
| **Validation** | `/11-speckit.validate` | `@speckit.validate` | Verifies implementation matches Spec requirements. |
| **Preparation** | `/speckit.prepare` | N/A | Runs Specify -> Analyze sequence. |
| **Checklist** | `/util-speckit.checklist` | `@speckit.checklist` | Generates feature checklists. |
| **Diff** | `/util-speckit.diff` | `@speckit.diff` | Compares artifact versions. |
| **Migration** | `/util-speckit.migrate` | `@speckit.migrate` | Port existing code to Spec-Kit. |
| **Red Team** | `/util-speckit.quizme` | `@speckit.quizme` | Challenges logical flaws. |
| **Status** | `/util-speckit.status` | `@speckit.status` | Shows feature completion status. |
| **Tracking** | `/util-speckit.taskstoissues`| `@speckit.taskstoissues`| Syncs tasks to GitHub/Jira/etc. |

---

## 🛡️ The Quality Assurance Pipeline

The following skills are designed to work together as a comprehensive defense against regression and poor quality. Run them in this order:

1.  **Checker (@speckit.checker)**: Syntax & Security.
2.  **Tester (@speckit.tester)**: Functionality.
3.  **Reviewer (@speckit.reviewer)**: Quality & Maintainability.
4.  **Validate (@speckit.validate)**: Requirements.

---

## 🧩 Adaptation Notes for Agent

**PROMPT LOGIC**:
When interacting with the user, always check the current state of the project files (`spec.md`, `plan.md`, `tasks.md`, etc.). Based on what is missing or complete, proactively suggest the next logical Spec-Kit command.

- If **No spec.md**, suggest `/02-speckit.specify`.
- If **spec.md exists but no plan.md**, suggest `/04-speckit.plan`.
- If **plan.md exists but no tasks.md**, suggest `/05-speckit.tasks`.
- If **tasks.md exists and has pending tasks**, suggest `/07-speckit.implement` or ask to pick a task.
- If **code is written**, suggest `/08-speckit.checker` or `/09-speckit.tester`.

Always end your response with a helpful prompt like:
> "Based on the current state, I recommend running **[Next Command]** next."

This ensures the user stays on track with the SDLC.
