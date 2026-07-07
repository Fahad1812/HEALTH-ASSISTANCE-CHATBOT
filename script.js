const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("user-input");
const resetBtn = document.getElementById("reset-btn");

function addMessage(text, cls) {
  const div = document.createElement("div");
  div.className = `msg ${cls}`;
  div.textContent = text;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

formEl.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text) return;

  addMessage(text, "user");
  inputEl.value = "";
  inputEl.disabled = true;

  const typingEl = addMessage("Typing...", "typing");

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });
    const data = await res.json();
    typingEl.remove();

    if (!res.ok) {
      addMessage(data.error || "Something went wrong.", "error");
    } else {
      const isError = data.reply.startsWith("❌");
      addMessage(data.reply, isError ? "error" : "bot");
    }
  } catch (err) {
    typingEl.remove();
    addMessage("Network error — is the server running?", "error");
  } finally {
    inputEl.disabled = false;
    inputEl.focus();
  }
});

resetBtn.addEventListener("click", async () => {
  await fetch("/reset", { method: "POST" });
  messagesEl.innerHTML = "";
  addMessage("Conversation cleared. Say hi!", "bot");
});

addMessage("Hi! Ask me anything.", "bot");
