import os
import time
import uuid

from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv

from openai import OpenAI, APIError, RateLimitError, AuthenticationError, APITimeoutError
from huggingface_hub import InferenceClient
from huggingface_hub.utils import HfHubHTTPError

load_dotenv()

# ---- Configuration ----
PROVIDER = os.getenv("PROVIDER", "huggingface")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini") 
HF_MODEL = os.getenv("HF_MODEL", "Qwen/Qwen2.5-7B-Instruct")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
HF_API_KEY = os.getenv("HF_TOKEN")

class ChatBot:
    def __init__(self, provider="huggingface", model=None, system_prompt=None,
                 max_history_turns=10, max_retries=3, max_tokens=500):
        self.provider = provider
        self.max_history_turns = max_history_turns
        self.max_retries = max_retries
        self.max_tokens = max_tokens
        
        # --- ENHANCED FOOTBALL SYSTEM PROMPT (Prompt Engineering Added) ---
        default_football_prompt = (
            "You are a strict Football (Soccer) Expert Assistant. "
            "You must ONLY answer questions related to football, such as players, clubs, matches, leagues, history, rules, and tactics. "
            "If a user asks about ANY other topic, politely refuse and state you only answer football-related queries. "
            "Do not provide code or answer math questions. "
            "\n\nRESPONSE GUIDELINES: "
            "1. ADAPTIVE DETAIL: Match the detail level of the user's query. If the user asks a short, brief question, give a concise and direct answer. If they ask a detailed question or ask 'explain', provide an in-depth and comprehensive explanation. "
            "2. FOLLOW-UP QUESTION: At the very end of every valid football-related response, ALWAYS ask exactly ONE engaging follow-up question related to the topic discussed to keep the conversation going (e.g., 'Would you like to know more about [related topic]?', or 'Who do you think is the best player in this team?')."
        )
        
        self.system_prompt = system_prompt or default_football_prompt
        self.history = [{"role": "system", "content": self.system_prompt}]

        if provider == "openai":
            self.model = model or OPENAI_MODEL
            self.client = OpenAI(api_key=OPENAI_API_KEY)
        elif provider == "huggingface":
            self.model = model or HF_MODEL
            self.client = InferenceClient(model=self.model, token=HF_API_KEY)

    def _trim_history(self):
        system_msg = self.history[0]
        convo = self.history[1:]
        max_msgs = self.max_history_turns * 2
        if len(convo) > max_msgs:
            convo = convo[-max_msgs:]
        self.history = [system_msg] + convo

    def send(self, user_message):
        self.history.append({"role": "user", "content": user_message})
        self._trim_history()

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                if self.provider == "openai":
                    resp = self.client.chat.completions.create(
                        model=self.model, messages=self.history, max_tokens=self.max_tokens, temperature=0.7,
                    )
                    reply = resp.choices[0].message.content
                else:
                    resp = self.client.chat_completion(
                        messages=self.history, max_tokens=self.max_tokens, temperature=0.7,
                    )
                    reply = resp.choices[0].message.content

                self.history.append({"role": "assistant", "content": reply})
                return reply
            except Exception as e:
                last_error = str(e)
                time.sleep(2 ** attempt)

        self.history.pop()
        return f"❌ Failed: {last_error}"

# ---- Flask app ----
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-change-me")

# Structure: { session_id: { 'conversations': { convo_id: ChatBot_Instance } } }
user_sessions = {}

def get_user_data():
    if "sid" not in session:
        session["sid"] = str(uuid.uuid4())
    sid = session["sid"]
    if sid not in user_sessions:
        user_sessions[sid] = {'conversations': {}}
    return user_sessions[sid]

@app.route("/")
def index():
    return render_template("index.html", provider=PROVIDER)

# ---- CONVERSATION APIs ----
@app.route("/api/conversations", methods=["GET"])
def list_conversations():
    data = get_user_data()
    convos = []
    for cid, bot in data['conversations'].items():
        # Title generate karein (pehlay message ke shuru ke alfaaz)
        title = "New Chat"
        if len(bot.history) > 1:
            title = bot.history[1]['content'][:25] + "..."
        convos.append({"id": cid, "title": title})
    return jsonify({"conversations": list(reversed(convos))}) # Newest first

@app.route("/api/conversations", methods=["POST"])
def create_conversation():
    data = get_user_data()
    cid = str(uuid.uuid4())
    data['conversations'][cid] = ChatBot(provider=PROVIDER)
    return jsonify({"id": cid})

@app.route("/api/conversations/<cid>", methods=["DELETE"])
def delete_conversation(cid):
    data = get_user_data()
    if cid in data['conversations']:
        del data['conversations'][cid]
    return jsonify({"status": "deleted"})

# ---- CHAT & HISTORY APIs (Updated with convo_id) ----
@app.route("/chat", methods=["POST"])
def chat():
    req_data = request.get_json(silent=True) or {}
    message = (req_data.get("message") or "").strip()
    convo_id = req_data.get("convo_id")
    
    data = get_user_data()
    if not convo_id or convo_id not in data['conversations']:
        return jsonify({"error": "Invalid conversation ID"}), 400
        
    bot = data['conversations'][convo_id]
    reply = bot.send(message)
    return jsonify({"reply": reply})

@app.route("/history", methods=["GET"])
def history():
    convo_id = request.args.get("convo_id")
    data = get_user_data()
    if not convo_id or convo_id not in data['conversations']:
        return jsonify({"history": []})
    bot = data['conversations'][convo_id]
    return jsonify({"history": bot.history[1:]})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
