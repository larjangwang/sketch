# Copilot Instructions

- This project is a local-first Windows desktop MVP for Thai construction drawing assistance.
- Prefer simple, dependency-light Python code until a .NET SDK is available for a WPF/WinUI rewrite.
- Keep all generated project data local by default under the user's Documents folder.
- Never hard-code API keys. Gemini keys must come from user settings or environment variables.
- Treat all AI output as draft data that requires licensed architect/engineer review.
- Keep export logic deterministic and auditable; do not silently infer legal compliance.
- Use Thai UI text where the end user sees workflow, checklist, or drawing-package terms.
