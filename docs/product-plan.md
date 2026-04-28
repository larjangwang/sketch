# Product Plan

## Product Direction

Build a local-first Windows desktop assistant for Thai architects and engineers. The app should shorten drafting preparation time by reading sketches and project details, producing structured draft data, checking drawing-package completeness, and exporting early PDF/DXF deliverables.

The first version intentionally avoids NAS/server deployment. Every project is stored locally, with optional manual backup/export later.

## MVP Scope

- Project intake for low-rise residential or small commercial pilot projects
- Sketch/reference import
- Gemini-assisted sketch extraction into JSON
- Human review surface for AI results
- Thai permit drawing checklist covering architecture, structure, electrical, plumbing, sanitary, built-in, and specifications
- Draft export package with checklist CSV, HTML summary, PDF summary, and DXF placeholder
- Installer-ready packaging path

## Technical Decisions

- Python/Tkinter is used for the first runnable scaffold because the machine has Python 3.12 but no .NET SDK installed.
- SQLite stores metadata locally under `Documents/AI-Construction-Drawing`.
- Gemini is used as an AI assistant only. It does not certify compliance.
- DXF/PDF export starts as deterministic placeholders and should evolve into a geometry-driven sheet engine.
- Inno Setup is the recommended installer for MVP distribution.

## Future .NET Path

When a .NET SDK is available, the UI can move to WPF or WinUI 3 while reusing these concepts:

- Local SQLite project store
- Project folder layout
- Gemini extraction worker contract
- Checklist/rules model
- Export package concept

## Compliance Note

The app can flag missing information and organize drawing packages, but final permit readiness must be reviewed, signed, and sealed by licensed Thai professionals according to the relevant authority and project type.
