const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("user-input");
const resetBtn = document.getElementById("reset-btn");
const modeDisplay = document.getElementById("current-mode-display");
const radioButtons = document.querySelectorAll('input[name="prompting-tech"]');

// Handle active prompting mode label switches
radioButtons.forEach(radio => {
  radio.addEventListener("change", (e) => {
    const formattedValue = e.target.value.charAt(0).toUpperCase() + e.target.value.slice(1);
    modeDisplay.textContent = formattedValue;
  });
});

function getSelectedPromptingMode() {
  const selected = document.querySelector('input[name="prompting-tech"]:checked');
  return selected ? selected.value : "zero-shot";
}

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

  const typingEl = addMessage("Analyzing tactics...", "typing");
  const selectedMode = getSelectedPromptingMode();

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ 
        message: text,
        prompting_mode: selectedMode 
      }),
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
    addMessage("Network error — is the pitch server running?", "error");
  } finally {
    inputEl.disabled = false;
    inputEl.focus();
  }
});

resetBtn.addEventListener("click", async () => {
  await fetch("/reset", { method: "POST" });
  messagesEl.innerHTML = "";
  addMessage("Pitch cleared! Ask me anything about football.", "bot");
});

// Football Specific Welcome Message
addMessage("Welcome to the Football AI Arena! ⚽ Ask me anything about rules, tactics, leagues, players, or historical stats.", "bot");
