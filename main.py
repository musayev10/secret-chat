import json
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_DEVICES = {
    "key_amir_pc_9981": "amir",
    "key_amir_phone_4412": "amir",
    "key_faye_phone_7730": "faye"
}

# --- СОХРАНЕНИЕ ИСТОРИИ ЧАТА ---
HISTORY_FILE = "chat_history.json"
chat_history = []

if os.path.exists(HISTORY_FILE):
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            chat_history = json.load(f)
    except Exception:
        chat_history = []

def save_history():
    try:
        # Храним последние 150 сообщений, чтобы не перегружать память телефона
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(chat_history[-150:], f, ensure_ascii=False)
    except Exception:
        pass

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {"amir": [], "faye": []}

    async def connect(self, user_role: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_role].append(websocket)

    def disconnect(self, user_role: str, websocket: WebSocket):
        if websocket in self.active_connections.get(user_role, []):
            self.active_connections[user_role].remove(websocket)

    async def broadcast(self, target_role: str, message: dict):
        for connection in self.active_connections.get(target_role, []):
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

@app.get("/faye", response_class=HTMLResponse)
async def get_faye_page():
    return FAYE_HTML

@app.get("/amir", response_class=HTMLResponse)
async def get_amir_page():
    return AMIR_HTML

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, device_key: str = ""):
    if device_key not in ALLOWED_DEVICES:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_role = ALLOWED_DEVICES[device_key]
    await manager.connect(user_role, websocket)

    # При подключении сразу отправляем сохраненную историю сообщений
    await websocket.send_json({"type": "history", "data": chat_history})

    try:
        while True:
            data_raw = await websocket.receive_text()
            data = json.loads(data_raw)
            data["sender"] = user_role

            msg_type = data.get("type")

            # Сохраняем в историю только сообщения (текст, фото, видео, аудио)
            if msg_type in ["text", "image", "video", "audio"]:
                chat_history.append(data)
                save_history()

            target_role = "faye" if user_role == "amir" else "amir"
            await manager.broadcast(target_role, data)

    except WebSocketDisconnect:
        manager.disconnect(user_role, websocket)

# --- ШАБЛОН ДЛЯ FAYE ---
FAYE_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <title>Калькулятор</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; user-select: none; -webkit-tap-highlight-color: transparent; }
        html, body { height: 100dvh; background: #000; color: #fff; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; overflow: hidden; }
        
        /* КАЛЬКУЛЯТОР ДЛЯ СЛАБЫХ ЭКРАНОВ (Samsung A02) */
        #calc-screen { display: flex; flex-direction: column; justify-content: flex-end; height: 100dvh; padding: 12px 16px 24px; }
        .calc-display { color: #fff; font-size: 48px; text-align: right; margin-bottom: 12px; min-height: 60px; word-wrap: break-word; font-weight: 300; }
        .calc-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
        .calc-btn { background: #2c2c2e; color: #fff; font-size: 24px; height: clamp(48px, 11vh, 68px); border-radius: 35px; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; }
        .calc-btn:active { opacity: 0.7; }
        .btn-op { background: #ff9f0a; }
        .btn-top { background: #8e8e93; color: #000; }

        /* ЧАТ */
        #chat-screen { display: none; flex-direction: column; height: 100dvh; background-color: #000; background-size: cover; background-position: center; }
        .header { padding: 35px 12px 10px; background: #1c1c1e; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #2c2c2e; z-index: 10; }
        .header-info { text-align: left; }
        .subtitle { color: #8e8e93; font-size: 11px; }
        .title { color: #fff; font-size: 16px; font-weight: 600; }
        .status-row { display: flex; align-items: center; gap: 6px; margin-top: 2px; }
        .status-dot { width: 7px; height: 7px; border-radius: 50%; background: #ff453a; }
        .status-text { color: #8e8e93; font-size: 11px; }
        .header-actions { display: flex; gap: 12px; }
        .icon-btn { background: none; border: none; color: #0a84ff; font-size: 22px; cursor: pointer; padding: 4px; }

        .messages { flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 8px; -webkit-overflow-scrolling: touch; }
        .msg { padding: 8px 12px; border-radius: 16px; max-width: 82%; font-size: 14px; word-break: break-word; line-height: 1.35; }
        .my { background: #0a84ff; align-self: flex-end; color: #fff; }
        .their { background: #2c2c2e; align-self: flex-start; color: #fff; }
        .msg img, .msg video { max-width: 100%; border-radius: 10px; margin-top: 4px; display: block; }
        .msg audio { max-width: 210px; height: 36px; margin-top: 4px; }

        .input-bar { padding: 8px 10px 18px; background: #1c1c1e; display: flex; gap: 8px; align-items: center; }
        .input-bar input[type="text"] { flex: 1; background: #2c2c2e; border: none; color: #fff; padding: 9px 12px; border-radius: 18px; font-size: 14px; outline: none; }
        .btn-circle { background: #0a84ff; border: none; color: #fff; width: 36px; height: 36px; border-radius: 50%; font-size: 16px; display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0; }

        /* ОКНО ЗВОНКА */
        #call-modal { display: none; position: fixed; inset: 0; background: #000; z-index: 100; flex-direction: column; }
        #remote-video { width: 100%; height: 100%; object-fit: cover; background: #111; }
        #local-video { position: absolute; top: 35px; right: 15px; width: 95px; height: 140px; border-radius: 10px; object-fit: cover; border: 2px solid #fff; background: #222; }
        .call-controls { position: absolute; bottom: 35px; width: 100%; display: flex; justify-content: center; gap: 30px; }
        .end-call-btn { background: #ff3b30; width: 58px; height: 58px; border-radius: 50%; border: none; color: #fff; font-size: 24px; cursor: pointer; }
    </style>
</head>
<body>
    <div id="calc-screen">
        <div class="calc-display" id="display">0</div>
        <div class="calc-grid">
            <button class="calc-btn btn-top" onclick="press('C')">C</button>
            <button class="calc-btn btn-top" onclick="press('(')">(</button>
            <button class="calc-btn btn-top" onclick="press(')')">)</button>
            <button class="calc-btn btn-op" onclick="press('/')">÷</button>
            <button class="calc-btn" onclick="press('7')">7</button>
            <button class="calc-btn" onclick="press('8')">8</button>
            <button class="calc-btn" onclick="press('9')">9</button>
            <button class="calc-btn btn-op" onclick="press('*')">×</button>
            <button class="calc-btn" onclick="press('4')">4</button>
            <button class="calc-btn" onclick="press('5')">5</button>
            <button class="calc-btn" onclick="press('6')">6</button>
            <button class="calc-btn btn-op" onclick="press('-')">-</button>
            <button class="calc-btn" onclick="press('1')">1</button>
            <button class="calc-btn" onclick="press('2')">2</button>
            <button class="calc-btn" onclick="press('3')">3</button>
            <button class="calc-btn btn-op" onclick="press('+')">+</button>
            <button class="calc-btn" style="grid-column: span 2; border-radius: 35px; text-align: left; padding-left: 24px;" onclick="press('0')">0</button>
            <button class="calc-btn" onclick="press('.')">,</button>
            <button class="calc-btn btn-op" onclick="press('=')">=</button>
        </div>
    </div>

    <div id="chat-screen">
        <div class="header">
            <div class="header-info">
                <div class="subtitle">Faye and boyfriend</div>
                <div class="title">Любимый</div>
                <div class="status-row">
                    <div class="status-dot" id="dot"></div>
                    <div class="status-text" id="status">подключение...</div>
                </div>
            </div>
            <div class="header-actions">
                <button class="icon-btn" onclick="changeBg()">🎨</button>
                <button class="icon-btn" onclick="startCall()">📹</button>
            </div>
        </div>
        <div class="messages" id="messages"></div>
        <div class="input-bar">
            <button class="btn-circle" onclick="document.getElementById('mediaInput').click()">📎</button>
            <input type="file" id="mediaInput" accept="image/*,video/*" style="display:none" onchange="sendMedia(this)">
            <input type="text" id="msgInput" placeholder="Сообщение..." onkeypress="if(event.key==='Enter') sendText()">
            <button class="btn-circle" id="voiceBtn">🎤</button>
            <button class="btn-circle" onclick="sendText()">➤</button>
        </div>
    </div>

    <input type="file" id="bgInput" accept="image/*" style="display:none" onchange="setBg(this)">

    <div id="call-modal">
        <video id="remote-video" autoplay playsinline></video>
        <video id="local-video" autoplay playsinline muted></video>
        <div class="call-controls">
            <button class="end-call-btn" onclick="endCall()">📞</button>
        </div>
    </div>

    <script>
        let inputStr = '';
        const PIN = '20092010';
        const MY_ROLE = 'faye';
        const SERVER_URL = (location.protocol==='https:'?'wss://':'ws://')+location.host+"/ws?device_key=key_faye_phone_7730";
        let ws, mediaRecorder, audioChunks = [], pc, localStream, iceCandidatesQueue = [];

        function press(val) {
            const display = document.getElementById('display');
            if (val === 'C') { inputStr = ''; display.innerText = '0'; }
            else if (val === '=') {
                if (inputStr === PIN) openChat();
                else {
                    try { inputStr = eval(inputStr).toString(); display.innerText = inputStr; }
                    catch { display.innerText = 'Ошибка'; inputStr = ''; }
                }
            } else { inputStr += val; display.innerText = inputStr; }
        }

        function openChat() {
            document.getElementById('calc-screen').style.display = 'none';
            document.getElementById('chat-screen').style.display = 'flex';
            connectWS();
            setupVoiceBtn();
        }

        function connectWS() {
            ws = new WebSocket(SERVER_URL);
            ws.onopen = () => {
                document.getElementById('status').innerText = 'в сети (защищено)';
                document.getElementById('dot').style.backgroundColor = '#30d158';
            };
            ws.onmessage = async (e) => {
                const data = JSON.parse(e.data);

                // Загрузка сохраненной истории при первом входе
                if (data.type === 'history') {
                    document.getElementById('messages').innerHTML = '';
                    data.data.forEach(msg => renderMessage(msg));
                    return;
                }

                if (data.sender === MY_ROLE) return;

                if (["text", "image", "video", "audio"].includes(data.type)) {
                    renderMessage(data);
                }

                // Сигналы видеовызова WebRTC
                if (data.type === 'webrtc_offer') handleCallOffer(data.offer);
                if (data.type === 'webrtc_answer') handleCallAnswer(data.answer);
                if (data.type === 'webrtc_ice') handleIceCandidate(data.candidate);
                if (data.type === 'webrtc_end') closeCallUI();
            };
            ws.onclose = () => {
                document.getElementById('status').innerText = 'переподключение...';
                document.getElementById('dot').style.backgroundColor = '#ff453a';
                setTimeout(connectWS, 3000);
            };
        }

        function renderMessage(data) {
            const isMy = data.sender === MY_ROLE;
            const cls = isMy ? 'my' : 'their';
            if (data.type === 'text') addMsg(data.text, cls);
            if (data.type === 'image') addMsg(`<img src="${data.src}">`, cls, true);
            if (data.type === 'video') addMsg(`<video src="${data.src}" controls playsinline></video>`, cls, true);
            if (data.type === 'audio') addMsg(`<audio src="${data.src}" controls></audio>`, cls, true);
        }

        function sendText() {
            const input = document.getElementById('msgInput');
            if (!input.value.trim()) return;
            const msg = { type: 'text', text: input.value };
            ws.send(JSON.stringify(msg));
            renderMessage({...msg, sender: MY_ROLE});
            input.value = '';
        }

        function sendMedia(input) {
            const file = input.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = (e) => {
                const type = file.type.startsWith('image') ? 'image' : 'video';
                const msg = { type, src: e.target.result };
                ws.send(JSON.stringify(msg));
                renderMessage({...msg, sender: MY_ROLE});
            };
            reader.readAsDataURL(file);
        }

        function setupVoiceBtn() {
            const btn = document.getElementById('voiceBtn');
            const start = async (e) => {
                e.preventDefault();
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    let mimeType = 'audio/webm';
                    if (MediaRecorder.isTypeSupported('audio/mp4')) mimeType = 'audio/mp4';
                    else if (MediaRecorder.isTypeSupported('audio/ogg')) mimeType = 'audio/ogg';

                    mediaRecorder = new MediaRecorder(stream, { mimeType });
                    audioChunks = [];
                    mediaRecorder.ondataavailable = ev => audioChunks.push(ev.data);
                    mediaRecorder.start();
                    btn.style.background = '#ff3b30';
                } catch(err) { alert("Включите доступ к микрофону в браузере!"); }
            };

            const stop = (e) => {
                e.preventDefault();
                if (!mediaRecorder || mediaRecorder.state === 'inactive') return;
                btn.style.background = '#0a84ff';
                mediaRecorder.stop();
                mediaRecorder.onstop = () => {
                    const blob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
                    const reader = new FileReader();
                    reader.onload = (ev) => {
                        const msg = { type: 'audio', src: ev.target.result };
                        ws.send(JSON.stringify(msg));
                        renderMessage({...msg, sender: MY_ROLE});
                    };
                    reader.readAsDataURL(blob);
                };
            };

            btn.addEventListener('touchstart', start, {passive: false});
            btn.addEventListener('touchend', stop, {passive: false});
            btn.addEventListener('mousedown', start);
            btn.addEventListener('mouseup', stop);
        }

        function changeBg() { document.getElementById('bgInput').click(); }
        function setBg(input) {
            const file = input.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = e => document.getElementById('chat-screen').style.backgroundImage = `url('${e.target.result}')`;
            reader.readAsDataURL(file);
        }

        function addMsg(content, typeClass, isHTML = false) {
            const box = document.getElementById('messages');
            const div = document.createElement('div');
            div.className = `msg ${typeClass}`;
            if (isHTML) div.innerHTML = content;
            else div.innerText = content;
            box.appendChild(div);
            box.scrollTop = box.scrollHeight;
        }

        /* WEBRTC ИСПРАВЛЕНИЕ ЧЕРНОГО ЭКРАНА */
        function createPeerConnection() {
            pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] });
            iceCandidatesQueue = [];

            pc.onicecandidate = e => {
                if (e.candidate) ws.send(JSON.stringify({ type: 'webrtc_ice', candidate: e.candidate }));
            };
            pc.ontrack = e => {
                const remoteVid = document.getElementById('remote-video');
                if (remoteVid.srcObject !== e.streams[0]) remoteVid.srcObject = e.streams[0];
            };
        }

        async function startCall() {
            try {
                localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
                document.getElementById('call-modal').style.display = 'flex';
                document.getElementById('local-video').srcObject = localStream;

                createPeerConnection();
                localStream.getTracks().forEach(track => pc.addTrack(track, localStream));

                const offer = await pc.createOffer();
                await pc.setLocalDescription(offer);
                ws.send(JSON.stringify({ type: 'webrtc_offer', offer }));
            } catch(e) { alert("Камера/Микрофон недоступны"); }
        }

        async function handleCallOffer(offer) {
            if (confirm("Входящий видеовызов! Ответить?")) {
                try {
                    localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
                    document.getElementById('call-modal').style.display = 'flex';
                    document.getElementById('local-video').srcObject = localStream;

                    createPeerConnection();
                    localStream.getTracks().forEach(track => pc.addTrack(track, localStream));

                    await pc.setRemoteDescription(new RTCSessionDescription(offer));
                    drainIceQueue();

                    const answer = await pc.createAnswer();
                    await pc.setLocalDescription(answer);
                    ws.send(JSON.stringify({ type: 'webrtc_answer', answer }));
                } catch(e) { alert("Не удалось запустить видео"); }
            }
        }

        async function handleCallAnswer(answer) {
            if (pc) {
                await pc.setRemoteDescription(new RTCSessionDescription(answer));
                drainIceQueue();
            }
        }

        async function handleIceCandidate(candidate) {
            if (pc && pc.remoteDescription) {
                await pc.addIceCandidate(new RTCIceCandidate(candidate));
            } else {
                iceCandidatesQueue.push(candidate);
            }
        }

        function drainIceQueue() {
            while (iceCandidatesQueue.length > 0) {
                const cand = iceCandidatesQueue.shift();
                pc.addIceCandidate(new RTCIceCandidate(cand));
            }
        }

        function endCall() {
            ws.send(JSON.stringify({ type: 'webrtc_end' }));
            closeCallUI();
        }

        function closeCallUI() {
            if (localStream) localStream.getTracks().forEach(t => t.stop());
            if (pc) pc.close();
            document.getElementById('call-modal').style.display = 'none';
        }
    </script>
</body>
</html>
"""

# --- ШАБЛОН ДЛЯ AMIR ---
AMIR_HTML = FAYE_HTML.replace("key_faye_phone_7730", "key_amir_pc_9981").replace("faye", "amir").replace("Faye and boyfriend", "Amir and Faye").replace("Любимый", "Любимая")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
