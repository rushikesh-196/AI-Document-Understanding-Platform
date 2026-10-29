Plan & Notes — Gemini key helper

Date: 2026-08-14

What was added
- backend/.env.template
  - A safe template for local environment variables. Copy to backend/.env and fill in real secrets locally (do NOT commit).
- backend/START_WITH_KEY.ps1
  - PowerShell helper that:
    - Reads backend/.env (if present) for GEMINI_API_KEY (masked in prompts)
    - Prompts the user to enter a GEMINI_API_KEY securely (hidden input) if not using an existing key
    - Sets GEMINI_API_KEY in the current PowerShell session and starts python app.py
    - Does not write secrets back into repository files
- services/llm_service.py was updated earlier to prefer GEMINI_API_KEY / GOOGLE_API_KEY env vars (no hardcoded keys remain)

How to use
1. Copy backend/.env.template -> backend/.env and edit locally (recommended), or set an environment variable directly.
2. From PowerShell, run:
   cd "<project>/backend"
   .\START_WITH_KEY.ps1
3. Follow the prompts to use the .env key or enter one for the session.
4. The script will start the backend in the same session so GEMINI_API_KEY is available at runtime.

Security notes
- NEVER commit backend/.env containing real secrets.
- Rotate your Gemini key if it was ever exposed in public logs or repositories.

Next steps
- Test end-to-end with an uploaded document that triggers LLM extraction to confirm the LLM uses the provided key.
- Remove Structured Layout from the user-facing result page (done): the frontend no longer shows the Structured Layout tab; backend generation is retained.
- Optionally add a small unit/health endpoint that reports whether the LLM config is available (no secret returned, only "available: true/false") for easier smoke tests.
