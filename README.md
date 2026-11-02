# GTwebdashboard

A project built on the **3-layer architecture** for reliable, AI-orchestrated workflows.

## Architecture

```
directives/   ← Layer 1: SOPs — what to do (Markdown)
execution/    ← Layer 3: Python scripts — deterministic tools
.tmp/         ← Intermediate files (auto-generated, not committed)
.env          ← API keys & secrets (not committed)
```

**Layer 2 (Orchestration)** is the AI agent itself — it reads directives, calls execution scripts in the right order, handles errors, and updates directives with learnings.

## Getting Started

1. **Set up secrets**: Copy `.env` and fill in your API keys.
2. **Add credentials**: Place `credentials.json` (Google OAuth) in the project root.
3. **Read a directive**: Start in `directives/` to understand any workflow.
4. **Run an execution script**: Call the relevant script in `execution/`.

## Key Principles

- **Deliverables** live in cloud services (Google Sheets, Slides, etc.)
- **Intermediates** live in `.tmp/` — always regenerable, never committed
- **Directives** are living documents — update them as you learn
- **Self-anneal**: when something breaks, fix the script, test it, update the directive

## Directory Structure

```
GTwebdashboard/
├── AGENTS.md          # AI agent instructions (mirrored to CLAUDE.md, GEMINI.md)
├── CLAUDE.md
├── GEMINI.md
├── README.md
├── .env               # Secrets (gitignored)
├── .gitignore
├── credentials.json   # Google OAuth (gitignored)
├── token.json         # Google OAuth token (gitignored)
├── directives/        # Layer 1 — SOPs in Markdown
├── execution/         # Layer 3 — Python scripts
└── .tmp/              # Intermediate files (gitignored)
```
