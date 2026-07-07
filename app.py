import os
import time
import uuid

from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv

from openai import OpenAI, APIError, RateLimitError, AuthenticationError, APITimeoutError
from huggingface_hub import InferenceClient
from huggingface_hub.utils import HfHubHTTPError

load_dotenv()

# ---- Configuration (all from environment / .env, never hard-coded) ----
PROVIDER = os.getenv("PROVIDER", "huggingface")           # "openai" or "huggingface"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
HF_MODEL = os.getenv("HF_MODEL", "Qwen/Qwen2.5-7B-Instruct")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
HF_API_KEY = os.getenv("HF_API_KEY")

if PROVIDER == "openai" and not OPENAI_API_KEY:
    raise RuntimeError("PROVIDER is 'openai' but OPENAI_API_KEY is not set. Add it to your .env file.")
if PROVIDER == "huggingface" and not HF_API_KEY:
    raise RuntimeError("PROVIDER is 'huggingface' but HF_API_KEY is not set. Add it to your .env file.")


class ChatBot:
    """Same chatbot logic as the notebook: works with OpenAI or Hugging Face,
    keeps trimmed conversation history, retries on rate limits/timeouts,
    and returns clear messages on auth/model/limit errors instead of crashing."""

    def __init__(self, provider="huggingface", model=None, system_prompt=None,
                 max_history_turns=10, max_retries=3, max_tokens=500):
        self.provider = provider
        self.max_history_turns = max_history_turns
        self.max_retries = max_retries
        self.max_tokens = max_tokens
        self.system_prompt = system_prompt or "You are a helpful, concise assistant."
        self.history = [{"role": "system", "content": self.system_prompt}]

        if provider == "openai":
            self.model = model or OPENAI_MODEL
            self.client = OpenAI(api_key=OPENAI_API_KEY)
        elif provider == "huggingface":
            self.model = model or HF_MODEL
            self.client = InferenceClient(model=self.model, token=HF_API_KEY)
        else:
            raise ValueError("provider must be 'openai' or 'huggingface'")

    def _trim_history(self):
        system_msg = self.history[0]
        convo = self.history[1:]
        max_msgs = self.max_history_turns * 2
        if len(convo) > max_msgs:
            convo = convo[-max_msgs:]
        self.history = [system_msg] + convo

    def _call_openai(self, messages):
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=0.7,
        )
        choice = resp.choices[0]
        return choice.message.content, choice.finish_reason

    def _call_huggingface(self, messages):
        resp = self.client.chat_completion(
            messages=messages,
            max_tokens=self.max_tokens,
            temperature=0.7,
        )
        choice = resp.choices[0]
        finish_reason = getattr(choice, "finish_reason", None)
        return choice.message.content, finish_reason

    def send(self, user_message, prompting_mode="zero-shot"):
        self.history.append({"role": "user", "content": user_message})
        self._trim_history()

        # Dynamic context framing based on prompting technique selection
        system_msg = self.history[0]
        convo_history = self.history[1:]
        
        examples = []
        if prompting_mode == "one-shot":
            examples = [
                {"role": "user", "content": "Optimize this code: 'for i in range(len(x)): print(x[i])'"},
                {"role": "assistant", "content": "Optimized approach:\n```python\nfor item in x:\n    print(item)\n```"}
            ]
        elif prompting_mode == "few-shot":
            examples = [
                {"role": "user", "content": "Optimize this code: 'for i in range(len(x)): print(x[i])'"},
                {"role": "assistant", "content": "Optimized approach:\n```python\nfor item in x:\n    print(item)\n```"},
                {"role": "user", "content": "Explain recursion in one sentence."},
                {"role": "assistant", "content": "Recursion is a programming method where a function calls itself to solve smaller instances of the same problem."}
            ]

        # Combine system prompt + custom dynamic shots + current conversation context
        payload_messages = [system_msg] + examples + convo_history

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                if self.provider == "openai":
                    reply, finish_reason = self._call_openai(payload_messages)
                else:
                    reply, finish_reason = self._call_huggingface(payload_messages)

                self.history.append({"role": "assistant", "content": reply})

                if finish_reason == "length":
                    reply += ("\n\n⚠️ [Response was cut off — it hit the max_tokens limit "
                              f"({self.max_tokens}). Increase max_tokens for longer replies.]")
                return reply

            except RateLimitError:
                last_error = "rate limit"
            except APITimeoutError:
                last_error = "timeout"
            except AuthenticationError:
                self.history.pop()
                return "❌ Authentication failed. Double-check your OpenAI API key."
            except HfHubHTTPError as e:
                status = getattr(e.response, "status_code", None)
                if status == 401:
                    self.history.pop()
                    return "❌ Authentication failed. Double-check your Hugging Face API token."
                elif status == 403:
                    self.history.pop()
                    return ("❌ 403 Forbidden: your token doesn't have permission to call Inference "
                            "Providers. Create a new token at huggingface.co/settings/tokens and pick "
                            "type 'Read', or enable 'Make calls to Inference Providers' on a fine-grained token.")
                elif status == 429:
                    last_error = "rate limit"
                elif status == 400 and "model_not_supported" in str(e):
                    self.history.pop()
                    return (f"❌ Model '{self.model}' isn't available through any Inference Provider "
                            "right now. Try 'Qwen/Qwen2.5-7B-Instruct' or check the model's page on "
                            "huggingface.co for an 'Inference Providers' section.")
                else:
                    self.history.pop()
                    return f"❌ Hugging Face API error ({status}): {e}"
            except APIError as e:
                self.history.pop()
                return f"❌ OpenAI API error: {e}"
            except Exception as e:
                self.history.pop()
                return f"❌ Unexpected error: {e}"

            wait = 2 ** attempt
            time.sleep(wait)

        self.history.pop()
        return f"❌ Failed after {self.max_retries} retries due to repeated {last_error} errors."

    def reset(self):
        self.history = [{"role": "system", "content": self.system_prompt}]


# ---- Flask app ----
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-change-me")

chat_sessions = {}


def get_bot():
    if "sid" not in session:
        session["sid"] = str(uuid.uuid4())
    sid = session["sid"]
    if sid not in chat_sessions:
        chat_sessions[sid] = ChatBot(
            provider=PROVIDER,
            system_prompt="You are a friendly and knowledgeable assistant. Keep answers concise.",
        )
    return chat_sessions[sid]


@app.route("/")
def index():
    return render_template("index.html", provider=PROVIDER)


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    prompting_mode = data.get("prompting_mode", "zero-shot")
    
    if not message:
        return jsonify({"error": "Empty message"}), 400
        
    bot = get_bot()
    reply = bot.send(message, prompting_mode=prompting_mode)
    return jsonify({"reply": reply})


@app.route("/reset", methods=["POST"])
def reset():
    bot = get_bot()
    bot.reset()
    return jsonify({"status": "cleared"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
