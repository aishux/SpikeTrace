/* ================= CONFIG ================= */
const AgentApiBaseUrl = "http://127.0.0.1:8000";
const AGENT_NAME = "spiketrace";
const USER_ID = "spiketrace_ui_user";

/* ================= STATE ================= */
let sessionId = null;
let sessionCreated = false;
let attachedFile = null;
let fillerInterval = null;

/* ================= DOM ================= */
const chatContainer = document.querySelector(".chat-list");
const typingForm = document.querySelector(".typing-form");
const typingInput = document.querySelector(".typing-input");
const fileInput = document.querySelector("#file-input");
const suggestions = document.querySelectorAll(".suggestion");
const toggleThemeButton = document.querySelector("#theme-toggle-button");
const resetChatButton = document.querySelector("#reset-chat-button");

/* ================= UI HELPERS ================= */
function addMessage(html, cls) {
    const div = document.createElement("div");
    div.className = `message ${cls}`;
    div.innerHTML = html;
    chatContainer.appendChild(div);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return div;
}

// FIX: Renamed function to avoid conflict with variables
function appendUserMessage(text, file = null) {
    let attachmentHtml = "";
    
    if (file && file.type.startsWith("image/")) {
        const imgUrl = URL.createObjectURL(file);
        attachmentHtml = `<img src="${imgUrl}" class="attachment-preview" onclick="openLightbox('${imgUrl}')" alt="User upload">`;
    } 
    else if (file) {
        attachmentHtml = `<div class="file-attachment-card"><span class="material-symbols-rounded">description</span> ${file.name}</div>`;
    }

    return addMessage(`
    <div class="message-content">
      <span class="avatar material-symbols-rounded">face</span>
      <div class="message-bubble">
          ${attachmentHtml}
          <p class="text">${text}</p>
      </div>
    </div>
  `, "outgoing");
}

function appendAgentMessage(initialText) {
    return addMessage(`
    <div class="message-content">
      <span class="avatar material-symbols-rounded">smart_toy</span>
      <div class="message-bubble">
        <p class="text bubble-analysing">${initialText}</p>
      </div>
    </div>
  `, "incoming");
}

/* ================= LIGHTBOX LOGIC ================= */
const lightboxModal = document.getElementById("lightbox-modal");
const lightboxImg = document.getElementById("lightbox-img");
const closeLightbox = document.querySelector(".close-lightbox");

// Expose this globally so inline HTML onclicks work
window.openLightbox = function(src) {
    if(lightboxImg && lightboxModal) {
        lightboxImg.src = src;
        lightboxModal.classList.add("active");
        document.body.style.overflow = "hidden";
    }
};

function closeLightboxFunc() {
    if(lightboxModal) {
        lightboxModal.classList.remove("active");
        setTimeout(() => { if(lightboxImg) lightboxImg.src = ""; }, 300);
        document.body.style.overflow = "auto";
    }
}

if(closeLightbox) closeLightbox.onclick = closeLightboxFunc;
if(lightboxModal) lightboxModal.onclick = (e) => {
    if (e.target === lightboxModal) closeLightboxFunc();
};

/* ================= SESSION ================= */
async function ensureSession() {
    if (sessionCreated) return sessionId;

    try {
        const res = await fetch(
            `${AgentApiBaseUrl}/apps/${AGENT_NAME}/users/${USER_ID}/sessions`,
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    app_name: AGENT_NAME,
                    user_id: USER_ID
                })
            }
        );

        const json = await res.json();
        sessionId = json.id;
        sessionCreated = true;
        return sessionId;
    } catch (e) {
        console.error("Session creation failed", e);
        return null;
    }
}

/* ================= FILE → BASE64 ================= */
function fileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result.split(",")[1]);
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

/* ================= PAYLOAD ================= */
async function buildPayload(text) {
    const parts = [{ text }];

    if (attachedFile) {
        const base64 = await fileToBase64(attachedFile);
        parts.push({
            inlineData: {
                displayName: attachedFile.name,
                data: base64,
                mimeType: attachedFile.type
            }
        });
        // Note: We do not nullify attachedFile here immediately 
        // because we might need it for UI, handled by clearAttachment()
    }

    return {
        appName: AGENT_NAME,
        userId: USER_ID,
        sessionId,
        newMessage: {
            role: "user",
            parts
        }
    };
}

/* ================= FILLERS ================= */
const fillers = [
    "Confirming carbon spike in the requested region…",
    "Correlating error rates and retries across services…",
    "Checking recent deployments for regressions…",
    "Quantifying excess runtime waste and emissions impact…",
    "Summarising root cause and remediation steps…"
];

function startFillers(bubbleText) {
    let i = 0;
    bubbleText.textContent = fillers[i];
    fillerInterval = setInterval(() => {
        i = (i + 1) % fillers.length;
        bubbleText.textContent = fillers[i];
    }, 4000); // Speed up slightly for better UX
}

function stopFillers() {
    if (fillerInterval) clearInterval(fillerInterval);
    fillerInterval = null;
}

function base64ToBlob(base64, mimeType) {
    let cleanBase64 = base64.replace(/-/g, '+').replace(/_/g, '/');
    const padding = cleanBase64.length % 4;
    if (padding > 0) cleanBase64 += '='.repeat(4 - padding);

    const byteCharacters = atob(cleanBase64);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    return new Blob([new Uint8Array(byteNumbers)], { type: mimeType });
}

async function fetchArtifact(appName, userId, sessionId, artifactName) {
    const res = await fetch(
        `${AgentApiBaseUrl}/apps/${appName}/users/${userId}/sessions/${sessionId}/artifacts/${artifactName}`
    );
    const json = await res.json();
    const base64Data = json.inlineData?.data || json.data; 
    if (!base64Data) throw new Error("No image data found in artifact response");
    return base64ToBlob(base64Data, "image/png");
}

/* ================= RUN AGENT ================= */
async function runAgent(text) {
    await ensureSession();

    // 1. Create agent bubble
    const bubble = appendAgentMessage("Analysing…");
    const bubbleText = bubble.querySelector(".text");
    startFillers(bubbleText);

    try {
        const payload = await buildPayload(text);
        
        const res = await fetch(`${AgentApiBaseUrl}/run`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const events = await res.json();
        stopFillers();

        let finalText = null;
        let finalImageArtifact = null;

        // Walk backwards to find final output
        for (let i = events.length - 1; i >= 0; i--) {
            const evt = events[i];
            const parts = evt.content?.parts || [];

            for (const part of parts) {
                if (finalText === null && part.text) finalText = part.text;
                if (finalImageArtifact === null && part.artifact) finalImageArtifact = part.artifact;
            }

            if (finalImageArtifact === null && evt.actions && evt.actions.artifactDelta) {
                const filenames = Object.keys(evt.actions.artifactDelta);
                const imageFile = filenames.find(name => name.endsWith('.png') || name.endsWith('.jpg'));
                if (imageFile) {
                    finalImageArtifact = {
                        name: imageFile,
                        mime_type: imageFile.endsWith('.png') ? "image/png" : "image/jpeg"
                    };
                }
            }
            if (finalText !== null && finalImageArtifact !== null) break;
        }

        // Render Text
        bubbleText.classList.remove("bubble-analysing");
        // Ensure 'marked' is loaded in your HTML (<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>)
        bubbleText.innerHTML = typeof marked !== 'undefined' 
            ? marked.parse(finalText || "Done.") 
            : (finalText || "Done.");

        // Render Image Artifact
        if (finalImageArtifact && finalImageArtifact.mime_type?.startsWith("image/")) {
            const blobRes = await fetchArtifact(AGENT_NAME, USER_ID, sessionId, finalImageArtifact.name);
            const imgUrl = URL.createObjectURL(blobRes);
            
            const container = document.createElement("div");
            container.className = "image-attachment-container";
            // Use CSS classes instead of inline styles where possible, but keeping logic consistent
            container.innerHTML = `
                <img src="${imgUrl}" style="max-width:100%; border-radius:12px; cursor:zoom-in; margin-top:10px;" onclick="openLightbox('${imgUrl}')">
                <a href="${imgUrl}" download="${finalImageArtifact.name}" style="display:block; margin-top:5px; color:#9aa0ff; text-decoration:none;">⬇ Download image</a>
            `;
            bubble.querySelector(".message-bubble").appendChild(container);
        }

    } catch (err) {
        stopFillers();
        console.error(err);
        bubbleText.textContent = "⚠️ Error connecting to agent.";
    }
}

/* ================= MAIN EVENT HANDLERS ================= */

// 1. Sending Messages
typingForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = typingInput.value.trim();
    
    // Validate: must have text OR file
    if (!text && !attachedFile) return;

    // Display user message immediately
    const displayMessage = text || (attachedFile ? `Analyzing ${attachedFile.name}...` : "");
    appendUserMessage(displayMessage, attachedFile);

    // Prepare text for agent
    const textToSend = text || "Analyze the attached media.";

    // Clear Text UI (File UI cleared inside runAgent after payload build)
    typingInput.value = "";
    document.body.classList.add("hide-header");

    // Run Agent
    runAgent(textToSend);
});

// 2. Suggestions
suggestions.forEach(suggestion => {
    suggestion.addEventListener("click", () => {
        const type = suggestion.getAttribute('data-type');
        
        if (type === 'text') {
            // Text Suggestion: Send immediately
            const text = suggestion.querySelector(".text").innerText;
            appendUserMessage(text);
            document.body.classList.add("hide-header");
            runAgent(text);
        } else {
            // File Suggestion: Open File Dialog
            if (type === 'video') fileInput.accept = "video/*";
            else if (type === 'audio') fileInput.accept = "audio/*";
            else if (type === 'image') fileInput.accept = "image/*";
            else fileInput.removeAttribute("accept");
            
            fileInput.click();
        }
    });
});

// 3. Reset Chat (Consolidated)
resetChatButton.addEventListener("click", () => {
    chatContainer.innerHTML = "";
    typingInput.value = "";
    sessionId = null;
    sessionCreated = false;
    document.body.classList.remove("hide-header");
});

// 4. Theme Toggle
const loadThemeFromLocalstorage = () => {
    const isLightMode = (localStorage.getItem("themeColor") === "light_mode");
    document.body.classList.toggle("light_mode", isLightMode);
    toggleThemeButton.innerText = isLightMode ? "dark_mode" : "light_mode";
}

toggleThemeButton.addEventListener("click", () => {
    const isLightMode = document.body.classList.toggle("light_mode");
    localStorage.setItem("themeColor", isLightMode ? "light_mode" : "dark_mode");
    toggleThemeButton.innerText = isLightMode ? "dark_mode" : "light_mode";
});

// Init
loadThemeFromLocalstorage();