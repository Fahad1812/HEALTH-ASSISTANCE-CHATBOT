const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const chatListEl = document.getElementById("chat-list");
const newChatBtn = document.getElementById("new-chat-btn");

let currentConvoId = null;

// UI Helper: Message add karna
function addMessage(text, cls) {
  const div = document.createElement("div");
  div.className = `msg ${cls}`;
  div.textContent = text;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

// Sidebar Helper: Chats render karna
async function loadConversations() {
  const res = await fetch("/api/conversations");
  const data = await res.json();
  chatListEl.innerHTML = "";
  
  data.conversations.forEach(convo => {
    const div = document.createElement("div");
    div.className = `chat-item ${convo.id === currentConvoId ? 'active' : ''}`;
    
    const titleSpan = document.createElement("span");
    titleSpan.textContent = convo.title;
    
    const delBtn = document.createElement("button");
    delBtn.innerHTML = "🗑️";
    delBtn.className = "delete-btn";
    delBtn.title = "Delete Chat";
    
    // Delete action
    delBtn.onclick = async (e) => {
      e.stopPropagation(); // Parent div click trigger na ho
      await fetch(`/api/conversations/${convo.id}`, { method: "DELETE" });
      if (currentConvoId === convo.id) {
        currentConvoId = null;
        messagesEl.innerHTML = "";
        inputEl.disabled = true;
        sendBtn.disabled = true;
      }
      loadConversations();
    };
    
    // Select Chat action
    div.onclick = () => {
      currentConvoId = convo.id;
      loadHistory();
      loadConversations(); // Active class update karne ke liye
    };
    
    div.appendChild(titleSpan);
    div.appendChild(delBtn);
    chatListEl.appendChild(div);
  });
}

// History API call
async function loadHistory() {
  if (!currentConvoId) return;
  messagesEl.innerHTML = ""; // Screen clear karein
  inputEl.disabled = false;
  sendBtn.disabled = false;
  inputEl.focus();

  const res = await fetch(`/history?convo_id=${currentConvoId}`);
  const data = await res.json();
  
  if (data.history && data.history.length > 0) {
    data.history.forEach(msg => {
      if (msg.role !== "system") {
        addMessage(msg.content, msg.role === "user" ? "user" : "bot");
      }
    });
  } else {
    // ⚽ THEME UPDATE HERE: Welcome message ko football ke hisaab se set kiya hai
    addMessage("⚽ Kickoff! Ask me anything about football clubs, players, tactics, or history.", "bot");
  }
}

// Nayi Chat Create Karna
newChatBtn.onclick = async () => {
  const res = await fetch("/api/conversations", { method: "POST" });
  const data = await res.json();
  currentConvoId = data.id;
  await loadConversations();
  loadHistory();
};

// Message bhejna
formEl.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text || !currentConvoId) return;

  addMessage(text, "user");
  inputEl.value = "";
  inputEl.disabled = true;
  sendBtn.disabled = true;

  const typingEl = addMessage("Typing...", "typing");

  try {
    const res = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, convo_id: currentConvoId }),
    });
    const data = await res.json();
    typingEl.remove();

    if (!res.ok) {
      addMessage(data.error || "Something went wrong.", "error");
    } else {
      addMessage(data.reply, data.reply.startsWith("❌") ? "error" : "bot");
    }
  } catch (err) {
    typingEl.remove();
    addMessage("Network error.", "error");
  } finally {
    inputEl.disabled = false;
    sendBtn.disabled = false;
    inputEl.focus();
    // Navbar me chat ka title update karne ke liye
    loadConversations(); 
  }
});

// App Initialize hone par 1 chat create karein agar koi nahi hai
window.onload = async () => {
  const res = await fetch("/api/conversations");
  const data = await res.json();
  if (data.conversations.length === 0) {
    await newChatBtn.onclick();
  } else {
    currentConvoId = data.conversations[0].id;
    await loadConversations();
    loadHistory();
  }
};
