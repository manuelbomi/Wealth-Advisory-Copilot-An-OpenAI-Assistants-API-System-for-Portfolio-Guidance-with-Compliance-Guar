// Vanilla JS SSE chat client -- no framework, no build step.
//
// The backend streams Server-Sent-Events-formatted chunks over a POST response
// body (see app/api/routes_chat.py). The browser's native `EventSource` only
// supports GET, so we read the fetch() response body as a stream ourselves and
// parse the same "event: <type>\ndata: <json>\n\n" framing by hand.

const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const clientSelect = document.getElementById("client-select");
const modeBadge = document.getElementById("mode-badge");

function appendMessage(role, text) {
  const el = document.createElement("div");
  el.className = `msg ${role}`;
  el.textContent = text;
  chatLog.appendChild(el);
  chatLog.scrollTop = chatLog.scrollHeight;
  return el;
}

async function loadClients() {
  const res = await fetch("/api/clients");
  const clients = await res.json();
  clientSelect.innerHTML = "";
  for (const c of clients) {
    const opt = document.createElement("option");
    opt.value = c.client_id;
    opt.textContent = `${c.client_id} - ${c.display_name} (${c.risk_profile})`;
    clientSelect.appendChild(opt);
  }
}

async function loadReadiness() {
  try {
    const res = await fetch("/readyz");
    const data = await res.json();
    modeBadge.textContent = data.mock_mode ? "offline mock mode" : "live OpenAI mode";
  } catch {
    modeBadge.textContent = "unknown";
  }
}

/**
 * Parse one SSE "event: X\ndata: Y" block into {type, data}.
 */
function parseEventBlock(block) {
  let type = "message";
  let data = "";
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) type = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  return { type, data: data ? JSON.parse(data) : {} };
}

async function sendMessage(clientId, message) {
  appendMessage("user", message);
  const assistantEl = appendMessage("assistant", "");
  let assistantText = "";

  const res = await fetch(`/api/chat/${encodeURIComponent(clientId)}/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });

  if (!res.ok || !res.body) {
    assistantEl.textContent = `Request failed (${res.status}).`;
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sepIndex;
    while ((sepIndex = buffer.indexOf("\n\n")) !== -1) {
      const rawBlock = buffer.slice(0, sepIndex);
      buffer = buffer.slice(sepIndex + 2);
      if (!rawBlock.trim()) continue;

      const { type, data } = parseEventBlock(rawBlock);

      if (type === "tool_call") {
        appendMessage("tool", `-> calling tool: ${data.tool_name}(${JSON.stringify(data.arguments)})`);
      } else if (type === "tool_result") {
        appendMessage("tool", `<- ${data.tool_name} result: ${JSON.stringify(data.result).slice(0, 200)}`);
      } else if (type === "guardrail") {
        if (data.action === "blocked") {
          appendMessage("guardrail-blocked", `[guardrail: BLOCKED] ${data.reason}`);
        } else if (data.action === "annotated") {
          appendMessage("guardrail-annotated", `[guardrail: annotated] ${data.reason}`);
        }
      } else if (type === "token") {
        assistantText += data.delta;
        assistantEl.textContent = assistantText;
        chatLog.scrollTop = chatLog.scrollHeight;
      } else if (type === "error") {
        appendMessage("system", `Error: ${data.message}`);
      } else if (type === "done") {
        // no-op; run metadata (run_id/thread_id) is available in data if needed.
      }
    }
  }
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;
  chatInput.value = "";
  chatForm.querySelector("button").disabled = true;
  try {
    await sendMessage(clientSelect.value, message);
  } catch (err) {
    appendMessage("system", `Error: ${err}`);
  } finally {
    chatForm.querySelector("button").disabled = false;
    chatInput.focus();
  }
});

loadClients();
loadReadiness();
