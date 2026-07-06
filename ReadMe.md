# Chatbot using OpenAI / Hugging Face APIs

A simple, provider-agnostic chatbot built in a single Jupyter notebook. Supports both the **OpenAI API** and the **Hugging Face Inference API** — switch with one variable, no code changes needed.

## Features
- Works with OpenAI **or** Hugging Face (your choice)
- Maintains conversation history, auto-trimmed to avoid runaway token usage
- Retries on rate limits / timeouts with exponential backoff
- Graceful handling of authentication errors (no crashes)
- Detects and flags responses truncated by the `max_tokens` limit
- Includes automated test prompts + a live interactive chat cell

## Setup

1. Install dependencies:
   ```
   pip install openai huggingface_hub
   ```

2. Get an API key:
   - **OpenAI** → https://platform.openai.com/api-keys
   - **Hugging Face** → https://huggingface.co/settings/tokens (create a **Read** token)

3. Open `chatbot_project.ipynb` in Jupyter or Google Colab.

4. In the config cell, set:
   ```python
   PROVIDER = "openai"        # or "huggingface"
   ```

5. Provide your key one of two ways:
   - **`getpass` (default)** — just run the cells; you'll be prompted to paste your key each kernel session. Never saved or printed anywhere.
   - **`.env` file (optional, for local repeated runs)** — create a file named `.env` next to the notebook:
     ```
     HF_API_KEY=your_token_here
     OPENAI_API_KEY=your_token_here
     ```
     Then set `USE_DOTENV = True` in the API-key cell. **`.env` is already excluded via `.gitignore`** — never remove that entry, or your key could end up on GitHub.

6. Run all cells top to bottom (Kernel/Runtime → Restart & Run All).

7. Chat with the bot using the interactive cell, or run the test-prompts cell for automated examples.

## ⚠️ API Key Safety
- Never paste a real API key into chat, code comments, or commit messages.
- Never hard-code a key directly into the notebook — if this repo is pushed to GitHub (even a private repo can go public by accident), the key is exposed and should be treated as compromised.
- If a key is ever exposed, revoke it immediately at the provider's dashboard and generate a new one.

## Running the Web App (Flask)

This project also includes a deployable Flask web app (`app.py`) with a simple chat UI, built on the same `ChatBot` logic as the notebook.

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and fill in your real values:
   ```
   cp .env.example .env
   ```
   Set `PROVIDER`, the matching API key (`HF_API_KEY` or `OPENAI_API_KEY`), and a random `FLASK_SECRET_KEY`.

3. Run the app:
   ```
   python app.py
   ```

4. Open **http://127.0.0.1:5000** in your browser and start chatting.

**How it works:** each browser gets a session cookie; the server keeps one `ChatBot` instance (with its own conversation history) per session in memory. This resets if the server restarts, and isn't shared across multiple worker processes — fine for a demo/single-instance deployment. For production with multiple workers, swap the in-memory `chat_sessions` dict for Redis or a database.

**Deploying for real (optional):** for anything beyond local testing, run behind a production WSGI server instead of `python app.py`, e.g.:
```
pip install gunicorn
gunicorn -w 1 -b 0.0.0.0:8000 app:app
```
(Keep `-w 1` unless you've moved session storage out of memory, since multiple workers won't share the in-memory dict.)

## Project Structure
```
app.py                  # Flask web app (deployable chatbot)
templates/index.html    # chat UI page
static/style.css        # chat UI styling
static/script.js        # chat UI frontend logic
requirements.txt        # Python dependencies
.env.example            # template for your .env file (no real keys)
chatbot_project.ipynb   # notebook: setup, ChatBot class, tests, error-handling demos
README.md               # this file
.gitignore              # excludes .env and other local artifacts from version control
```

## Configuration Notes
- Default models: `gpt-4o-mini` (OpenAI) and `meta-llama/Llama-3.2-3B-Instruct` (Hugging Face) — change these in the config cell to any chat-capable model your provider supports.
- Conversation history is capped at the last 10 turns by default (`max_history_turns` in `ChatBot`).
- `max_tokens` controls response length and is configurable per `ChatBot` instance.

## Error Handling
| Situation | Behavior |
|---|---|
| Rate limit hit | Retries automatically with exponential backoff (up to 3 attempts) |
| Timeout | Retries automatically |
| Invalid/expired API key | Returns a clear error message instead of crashing |
| Response hits `max_tokens` | Reply is returned with a warning that it was cut off |
