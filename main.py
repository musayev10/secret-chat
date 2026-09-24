import json
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

# Страница для Faye
@app.get("/faye", response_class=HTMLResponse)
async def get_faye_page():
    return FAYE_HTML

# Страница для Amir
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

    try:
        while True:
            data_raw = await websocket.receive_text()
            data = json.loads(data_raw)
            data["sender"] = user_role
            
            target_role = "faye" if user_role == "amir" else "amir"
            await manager.broadcast(target_role, data)

    except WebSocketDisconnect:
        manager.disconnect(user_role, websocket)

# КОД СТРАНИЦЫ FAYE С ПОДДЕРЖКОЙ IPHONE И HTTPS
FAYE_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Калькулятор</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; user-select: none; }
        body { background: #000; color: #fff; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; height: 100vh; overflow: hidden; }
        #calc-screen { display: flex; flex-direction: column; justify-content: flex-end; height: 100vh; padding: 20px; }
        .calc-display { color: #fff; font-size: 56px; text-align: right; margin-bottom: 20px; min-height: 70px; word-wrap: break-word; }
        .calc-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
        .calc-btn { background: #333; color: #fff; font-size: 28px; height: 75px; border-radius: 40px; border: none; cursor: pointer; }
        .btn-op { background: #ff9f0a; }
        .btn-top { background: #a5a5a5; color: #000; }
        #chat-screen { display: none; flex-direction: column; height: 100vh; background-color: #000; background-size: cover; background-position: center; }
        .header { padding: 40px 15px 10px; background: rgba(28,28,30,0.9); backdrop-filter: blur(10px); display: flex; justify-content: space-between; align-items: center; border-bottom: 0.5px solid #38383a; }
        .header-info { text-align: left; }
        .subtitle { color: #8e8e93; font-size: 11px; }
        .title { color: #fff; font-size: 17px; font-weight: 600; }
        .status-row { display: flex; align-items: center; gap: 5px; margin-top: 2px; }
        .status-dot { width: 6px; height: 6px; border-radius: 3px; background: #30d158; }
        .status-text { color: #8e8e93; font-size: 10px; }
        .header-actions { display: flex; gap: 12px; }
        .icon-btn { background: none; border: none; color: #0a84ff; font-size: 20px; cursor: pointer; }
        .messages { flex: 1; overflow-y: auto; padding: 15px; display: flex; flex-direction: column; gap: 10px; }
        .msg { padding: 10px 14px; border-radius: 18px; max-width: 80%; font-size: 15px; word-break: break-word; }
        .my { background: #0a84ff; align-self: flex-end; color: #fff; }
        .their { background: #2c2c2e; align-self: flex-start; color: #fff; }
        .msg img, .msg video { max-width: 100%; border-radius: 12px; margin-top: 5px; }
        .input-bar { padding: 10px 12px 25px; background: rgba(28,28,30,0.9); display: flex; gap: 8px; align-items: center; }
        .input-bar input[type="text"] { flex: 1; background: #2c2c2e; border: none; color: #fff; padding: 10px 14px; border-radius: 20px; font-size: 15px; outline: none; }
        .btn-circle { background: #0a84ff; border: none; color: #fff; width: 36px; height: 36px; border-radius: 18px; font-size: 16px; display: flex; align-items: center; justify-content: center; cursor: pointer; touch-action: manipulation; }
        #call-modal { display: none; position: fixed; inset: 0; background: #000; z-index: 100; flex-direction: column; }
        #remote-video { width: 100%; height: 100%; object-fit: cover; }
        #local-video { position: absolute; top: 40px; right: 20px; width: 100px; height: 150px; border-radius: 12px; object-fit: cover; border: 2px solid #fff; }
        .call-controls { position: absolute; bottom: 40px; width: 100%; display: flex; justify-content: center; gap: 30px; }
        .end-call-btn { background: #ff3b30; width: 60px; height: 60px; border-radius: 30px; border: none; color: #fff; font-size: 24px; cursor: pointer; }
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
            <button class="calc-btn" style="grid-column: span 2; border-radius: 40px; text-align: left; padding-left: 30px;" onclick="press('0')">0</button>
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
        const SERVER_URL = (location.protocol==='https:'?'wss://':'ws://')+location.host+"/ws?device_key=key_faye_phone_7730";
        let ws, mediaRecorder, audioChunks = [], pc, localStream;

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
                if (data.sender === 'faye') return;
                if (data.type === 'text') addMsg(data.text, 'their');
                if (data.type === 'image') addMsg(`<img src="${data.src}">`, 'their', true);
                if (data.type === 'video') addMsg(`<video src="${data.src}" controls playsinline></video>`, 'their', true);
                if (data.type === 'audio') addMsg(`<audio src="${data.src}" controls></audio>`, 'their', true);
                if (data.type === 'webrtc_offer') handleCallOffer(data.offer);
                if (data.type === 'webrtc_answer') pc && pc.setRemoteDescription(new RTCSessionDescription(data.answer));
                if (data.type === 'webrtc_ice') pc && pc.addIceCandidate(new RTCIceCandidate(data.candidate));
                if (data.type === 'webrtc_end') closeCallUI();
            };
            ws.onclose = () => {
                document.getElementById('status').innerText = 'переподключение...';
                document.getElementById('dot').style.backgroundColor = '#ff453a';
                setTimeout(connectWS, 3000);
            };
        }

        function sendText() {
            const input = document.getElementById('msgInput');
            if (!input.value.trim()) return;
            ws.send(JSON.stringify({ type: 'text', text: input.value }));
            addMsg(input.value, 'my');
            input.value = '';
        }

        function sendMedia(input) {
            const file = input.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = (e) => {
                const type = file.type.startsWith('image') ? 'image' : 'video';
                ws.send(JSON.stringify({ type, src: e.target.result }));
                const tag = type === 'image' ? `<img src="${e.target.result}">` : `<video src="${e.target.result}" controls playsinline></video>`;
                addMsg(tag, 'my', true);
            };
            reader.readAsDataURL(file);
        }

        function setupVoiceBtn() {
            const btn = document.getElementById('voiceBtn');
            const start = async (e) => {
                e.preventDefault();
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    const options = MediaRecorder.isTypeSupported('audio/mp4') ? { mimeType: 'audio/mp4' } : {};
                    mediaRecorder = new MediaRecorder(stream, options);
                    audioChunks = [];
                    mediaRecorder.ondataavailable = ev => audioChunks.push(ev.data);
                    mediaRecorder.start();
                    btn.style.background = '#ff3b30';
                } catch(err) { alert("Ошибка микрофона: Разрешите доступ к микрофону в настройках браузера"); }
            };
            const stop = (e) => {
                e.preventDefault();
                if (!mediaRecorder || mediaRecorder.state === 'inactive') return;
                btn.style.background = '#0a84ff';
                mediaRecorder.stop();
                mediaRecorder.onstop = () => {
                    const mime = mediaRecorder.mimeType || 'audio/mp4';
                    const blob = new Blob(audioChunks, { type: mime });
                    const reader = new FileReader();
                    reader.onload = (ev) => {
                        ws.send(JSON.stringify({ type: 'audio', src: ev.target.result }));
                        addMsg(`<audio src="${ev.target.result}" controls></audio>`, 'my', true);
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

        function addMsg(content, type, isHTML = false) {
            const box = document.getElementById('messages');
            const div = document.createElement('div');
            div.className = `msg ${type}`;
            if (isHTML) div.innerHTML = content;
            else div.innerText = content;
            box.appendChild(div);
            box.scrollTop = box.scrollHeight;
        }

        async function startCall() {
            try {
                localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
                document.getElementById('call-modal').style.display = 'flex';
                document.getElementById('local-video').srcObject = localStream;
                initPeer();
                localStream.getTracks().forEach(track => pc.addTrack(track, localStream));
                const offer = await pc.createOffer();
                await pc.setLocalDescription(offer);
                ws.send(JSON.stringify({ type: 'webrtc_offer', offer }));
            } catch(e) { alert("Ошибка камеры/микрофона. Разрешите доступ в браузере."); }
        }

        async function handleCallOffer(offer) {
            if (confirm("Входящий видеовызов! Ответить?")) {
                try {
                    localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
                    document.getElementById('call-modal').style.display = 'flex';
                    document.getElementById('local-video').srcObject = localStream;
                    initPeer();
                    localStream.getTracks().forEach(track => pc.addTrack(track, localStream));
                    await pc.setRemoteDescription(new RTCSessionDescription(offer));
                    const answer = await pc.createAnswer();
                    await pc.setLocalDescription(answer);
                    ws.send(JSON.stringify({ type: 'webrtc_answer', answer }));
                } catch(e) { alert("Не удалось открыть камеру"); }
            }
        }

        function initPeer() {
            pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] });
            pc.onicecandidate = e => e.candidate && ws.send(JSON.stringify({ type: 'webrtc_ice', candidate: e.candidate }));
            pc.ontrack = e => document.getElementById('remote-video').srcObject = e.streams[0];
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

# КОД СТРАНИЦЫ AMIR
AMIR_HTML = FAYE_HTML.replace("key_faye_phone_7730", "key_amir_pc_9981").replace("Faye and boyfriend", "Amir and Faye").replace("Любимый", "Любимая")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
