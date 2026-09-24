import json
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.responses import HTMLResponse, Response
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
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(chat_history[-200:], f, ensure_ascii=False)
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

# Service Worker для фонового режима PWA
SW_SCRIPT = """
self.addEventListener('install', (e) => {
    self.skipWaiting();
});

self.addEventListener('activate', (e) => {
    e.waitUntil(clients.claim());
});

self.addEventListener('push', (e) => {
    const data = e.data ? e.data.json() : { title: 'Калькулятор', body: 'Новое сообщение' };
    e.waitUntil(
        self.registration.showNotification(data.title, {
            body: data.body,
            icon: 'https://cdn-icons-png.flaticon.com/512/3658/3658932.png',
            vibrate: [200, 100, 200]
        })
    );
});
"""

@app.get("/sw.js")
async def get_sw():
    return Response(content=SW_SCRIPT, media_type="application/javascript")

@app.get("/manifest.json")
async def get_manifest():
    return {
        "name": "Калькулятор",
        "short_name": "Калькулятор",
        "start_url": "/faye",
        "display": "standalone",
        "background_color": "#000000",
        "theme_color": "#17212b",
        "icons": [
            {
                "src": "https://cdn-icons-png.flaticon.com/512/3658/3658932.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "https://cdn-icons-png.flaticon.com/512/3658/3658932.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }

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

    await websocket.send_json({"type": "history", "data": chat_history})

    try:
        while True:
            data_raw = await websocket.receive_text()
            data = json.loads(data_raw)
            data["sender"] = user_role

            msg_type = data.get("type")
            # Сохраняем текстовые, медиа и записи вызовов в историю
            if msg_type in ["text", "image", "video", "audio", "call_log"]:
                chat_history.append(data)
                save_history()

            target_role = "faye" if user_role == "amir" else "amir"
            await manager.broadcast(target_role, data)

    except WebSocketDisconnect:
        manager.disconnect(user_role, websocket)

FAYE_HTML = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    
    <link rel="manifest" href="/manifest.json">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="Калькулятор">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="theme-color" content="#17212b">
    
    <title>Калькулятор</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; user-select: none; -webkit-tap-highlight-color: transparent; }
        html, body { height: 100dvh; background: #000; color: #fff; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; overflow: hidden; }
        
        #calc-screen { display: flex; flex-direction: column; justify-content: flex-end; height: 100dvh; padding: 16px 20px 28px; background: #000; }
        .calc-display { color: #fff; font-size: 52px; text-align: right; margin-bottom: 16px; min-height: 65px; word-wrap: break-word; font-weight: 300; }
        .calc-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
        .calc-btn { background: #2c2c2e; color: #fff; font-size: 26px; height: clamp(52px, 11vh, 70px); border-radius: 35px; border: none; cursor: pointer; display: flex; align-items: center; justify-content: center; }
        .calc-btn:active { opacity: 0.6; }
        .btn-op { background: #ff9f0a; }
        .btn-top { background: #a5a5a5; color: #000; }

        #chat-screen { display: none; flex-direction: column; height: 100dvh; background: #0e1621; }
        
        .header { padding: 35px 16px 10px; background: #17212b; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #101721; z-index: 10; }
        .header-left { display: flex; align-items: center; gap: 12px; }
        .avatar { width: 42px; height: 42px; border-radius: 50%; background: linear-gradient(135deg, #0088cc, #39b54a); display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 18px; color: #fff; }
        .header-info { text-align: left; }
        .title { color: #f5f5f5; font-size: 16px; font-weight: 600; }
        .status-row { display: flex; align-items: center; gap: 6px; margin-top: 2px; }
        .status-dot { width: 7px; height: 7px; border-radius: 50%; background: #ff453a; }
        .status-text { color: #7f91a4; font-size: 12px; }
        
        .header-actions { display: flex; gap: 16px; align-items: center; }
        .icon-btn { background: none; border: none; color: #6c7e94; cursor: pointer; display: flex; align-items: center; justify-content: center; padding: 4px; }
        .icon-btn:active { color: #5288c1; }
        .icon-btn svg { width: 22px; height: 22px; fill: currentColor; }

        .messages { flex: 1; overflow-y: auto; padding: 14px; display: flex; flex-direction: column; gap: 8px; -webkit-overflow-scrolling: touch; }
        .msg { padding: 9px 13px; border-radius: 16px; max-width: 80%; font-size: 15px; word-break: break-word; line-height: 1.35; position: relative; }
        .my { background: #2b5278; align-self: flex-end; color: #fff; border-bottom-right-radius: 4px; }
        .their { background: #182533; align-self: flex-start; color: #f5f5f5; border-bottom-left-radius: 4px; }
        .call-log-msg { align-self: center; background: rgba(23, 33, 43, 0.8); color: #7f91a4; font-size: 13px; border-radius: 12px; padding: 6px 14px; border: 1px solid rgba(255,255,255,0.05); }
        .msg img, .msg video { max-width: 100%; border-radius: 12px; margin-top: 4px; display: block; }
        .msg audio { max-width: 210px; height: 38px; margin-top: 4px; }

        .input-bar { padding: 8px 12px 20px; background: #17212b; display: flex; gap: 10px; align-items: center; border-top: 1px solid #101721; }
        .input-bar input[type="text"] { flex: 1; background: #0e1621; border: 1px solid #242f3d; color: #fff; padding: 10px 16px; border-radius: 22px; font-size: 15px; outline: none; }
        .btn-send { background: #5288c1; border: none; color: #fff; width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0; }
        .btn-send svg { width: 18px; height: 18px; fill: #fff; margin-left: 2px; }

        #incoming-modal { display: none; position: fixed; inset: 0; background: rgba(14, 22, 33, 0.95); z-index: 200; flex-direction: column; align-items: center; justify-content: center; gap: 30px; text-align: center; }
        .caller-avatar { width: 100px; height: 100px; border-radius: 50%; background: linear-gradient(135deg, #0088cc, #39b54a); display: flex; align-items: center; justify-content: center; font-size: 42px; font-weight: bold; animation: pulse 1.8s infinite; }
        @keyframes pulse { 0% { transform: scale(0.98); box-shadow: 0 0 0 0 rgba(82, 136, 193, 0.7); } 70% { transform: scale(1.05); box-shadow: 0 0 0 25px rgba(82, 136, 193, 0); } 100% { transform: scale(0.98); box-shadow: 0 0 0 0 rgba(82, 136, 193, 0); } }
        .caller-title { font-size: 22px; font-weight: 600; color: #fff; }
        .caller-sub { font-size: 14px; color: #7f91a4; margin-top: 6px; }
        .call-buttons { display: flex; gap: 40px; margin-top: 20px; }
        .btn-call-act { width: 68px; height: 68px; border-radius: 50%; border: none; color: #fff; font-size: 26px; display: flex; align-items: center; justify-content: center; cursor: pointer; }
        .btn-accept { background: #34c759; }
        .btn-decline { background: #ff3b30; }

        #call-modal { display: none; position: fixed; inset: 0; background: #000; z-index: 100; flex-direction: column; }
        #remote-video { width: 100%; height: 100%; object-fit: cover; background: #111; }
        #local-video { position: absolute; top: 40px; right: 16px; width: 105px; height: 155px; border-radius: 12px; object-fit: cover; border: 2px solid rgba(255,255,255,0.8); background: #222; }
        .call-controls { position: absolute; bottom: 40px; width: 100%; display: flex; justify-content: center; gap: 30px; }
        .end-call-btn { background: #ff3b30; width: 64px; height: 64px; border-radius: 50%; border: none; color: #fff; font-size: 26px; cursor: pointer; display: flex; align-items: center; justify-content: center; }
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
            <button class="calc-btn" style="grid-column: span 2; border-radius: 35px; text-align: left; padding-left: 26px;" onclick="press('0')">0</button>
            <button class="calc-btn" onclick="press('.')">,</button>
            <button class="calc-btn btn-op" onclick="press('=')">=</button>
        </div>
    </div>

    <div id="chat-screen">
        <div class="header">
            <div class="header-left">
                <div class="avatar" id="avatar-icon">L</div>
                <div class="header-info">
                    <div class="title" id="chat-title">Любимый</div>
                    <div class="status-row">
                        <div class="status-dot" id="dot"></div>
                        <div class="status-text" id="status">подключение...</div>
                    </div>
                </div>
            </div>
            <div class="header-actions">
                <button class="icon-btn" onclick="reqNotify()" title="Включить уведомления">
                    <svg viewBox="0 0 24 24"><path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.89 2 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/></svg>
                </button>
                <button class="icon-btn" onclick="changeBg()" title="Сменить фон">
                    <svg viewBox="0 0 24 24"><path d="M12 3c-4.97 0-9 4.03-9 9 0 2.12.74 4.07 1.97 5.61L4.35 19.4c-.39.39-.39 1.02 0 1.41.39.39 1.02.39 1.41 0l1.9-1.9C9.22 19.54 10.57 20 12 20c4.97 0 9-4.03 9-9s-4.03-9-9-9zm0 15c-3.31 0-6-2.69-6-6s2.69-6 6-6 6 2.69 6 6-2.69 6-6 6z"/></svg>
                </button>
                <button class="icon-btn" onclick="startCall()" title="Видеовызов">
                    <svg viewBox="0 0 24 24"><path d="M17 10.5V7c0-.55-.45-1-1-1H4c-.55 0-1 .45-1 1v10c0 .55.45 1 1 1h12c.55 0 1-.45 1-1v-3.5l4 4v-11l-4 4z"/></svg>
                </button>
            </div>
        </div>

        <div class="messages" id="messages"></div>

        <div class="input-bar">
            <button class="icon-btn" onclick="document.getElementById('mediaInput').click()">
                <svg viewBox="0 0 24 24"><path d="M16.5 6v11.5c0 2.21-1.79 4-4 4s-4-1.79-4-4V5c0-1.38 1.12-2.5 2.5-2.5s2.5 1.12 2.5 2.5v10.5c0 .55-.45 1-1 1s-1-.45-1-1V6H10v9.5c0 1.38 1.12 2.5 2.5 2.5s2.5-1.12 2.5-2.5V5c0-2.21-1.79-4-4-4S7 2.79 7 5v12.5c0 3.04 2.46 5.5 5.5 5.5s5.5-2.46 5.5-5.5V6h-1.5z"/></svg>
            </button>
            <input type="file" id="mediaInput" accept="image/*,video/*" style="display:none" onchange="sendMedia(this)">

            <input type="text" id="msgInput" placeholder="Сообщение..." onkeypress="if(event.key==='Enter') sendText()">

            <button class="icon-btn" id="voiceBtn" title="Голосовое">
                <svg viewBox="0 0 24 24"><path d="M12 14c1.66 0 2.99-1.34 2.99-3L15 5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5.3-3c0 3-2.54 5.1-5.3 5.1S6.7 14 6.7 11H5c0 3.41 2.72 6.23 6 6.72V21h2v-3.28c3.28-.48 6-3.3 6-6.72h-1.7z"/></svg>
            </button>
            <button class="btn-send" onclick="sendText()">
                <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
            </button>
        </div>
    </div>

    <input type="file" id="bgInput" accept="image/*" style="display:none" onchange="setBg(this)">

    <div id="incoming-modal">
        <div class="caller-avatar" id="caller-av">A</div>
        <div>
            <div class="caller-title" id="caller-name">Входящий видеовызов</div>
            <div class="caller-sub">Секретный вызов...</div>
        </div>
        <div class="call-buttons">
            <button class="btn-call-act btn-decline" onclick="declineCall()">📞</button>
            <button class="btn-call-act btn-accept" onclick="acceptCall()">📹</button>
        </div>
    </div>

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
        let ws, mediaRecorder, audioChunks = [], pc, localStream, pendingOffer = null, ringToneInterval = null;
        let callStartTime = null;

        // Регистрация Service Worker для PWA
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js').catch(err => console.log('SW reg error:', err));
        }

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
                document.getElementById('status').innerText = 'в сети';
                document.getElementById('dot').style.backgroundColor = '#30d158';
            };
            ws.onmessage = async (e) => {
                const data = JSON.parse(e.data);

                if (data.type === 'history') {
                    document.getElementById('messages').innerHTML = '';
                    data.data.forEach(msg => renderMessage(msg));
                    return;
                }

                if (data.sender === MY_ROLE) return;

                if (["text", "image", "video", "audio", "call_log"].includes(data.type)) {
                    renderMessage(data);
                    playNotifSound();
                    showNotification(data);
                }

                if (data.type === 'webrtc_offer') showIncomingCall(data.offer);
                if (data.type === 'webrtc_answer') handleCallAnswer(data.answer);
                if (data.type === 'webrtc_ice') handleIceCandidate(data.candidate);
                if (data.type === 'webrtc_end') closeCallUI();
            };
            ws.onclose = () => {
                document.getElementById('status').innerText = 'соединение...';
                document.getElementById('dot').style.backgroundColor = '#ff453a';
                setTimeout(connectWS, 3000);
            };
        }

        function renderMessage(data) {
            const isMy = data.sender === MY_ROLE;
            const cls = isMy ? 'my' : 'their';

            if (data.type === 'call_log') {
                addCallLogMsg(data.text);
                return;
            }

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

        function sendCallLog(text) {
            const msg = { type: 'call_log', text };
            ws.send(JSON.stringify(msg));
            renderMessage({...msg, sender: MY_ROLE});
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

                    mediaRecorder = new MediaRecorder(stream, { mimeType });
                    audioChunks = [];
                    mediaRecorder.ondataavailable = ev => audioChunks.push(ev.data);
                    mediaRecorder.start();
                    btn.style.color = '#ff3b30';
                } catch(err) { 
                    alert("Разрешите микрофон в настройках браузера!"); 
                }
            };

            const stop = (e) => {
                e.preventDefault();
                if (!mediaRecorder || mediaRecorder.state === 'inactive') return;
                btn.style.color = '#6c7e94';
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

        function addCallLogMsg(text) {
            const box = document.getElementById('messages');
            const div = document.createElement('div');
            div.className = 'call-log-msg';
            div.innerText = text;
            box.appendChild(div);
            box.scrollTop = box.scrollHeight;
        }

        function playNotifSound() {
            try {
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                const osc = ctx.createOscillator();
                const gain = ctx.createGain();
                osc.type = 'sine';
                osc.frequency.setValueAtTime(587.33, ctx.currentTime);
                osc.frequency.setValueAtTime(880, ctx.currentTime + 0.1);
                gain.gain.setValueAtTime(0.2, ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.start();
                osc.stop(ctx.currentTime + 0.3);
            } catch(e){}
        }

        function startRingtone() {
            stopRingtone();
            ringToneInterval = setInterval(() => { playNotifSound(); }, 1000);
        }
        function stopRingtone() { if(ringToneInterval) clearInterval(ringToneInterval); }

        function reqNotify() {
            if ("Notification" in window) {
                Notification.requestPermission().then(p => {
                    if (p === 'granted') {
                        new Notification("Калькулятор", { body: "Уведомления включены! 🔔" });
                    } else {
                        alert("Уведомления заблокированы в настройках браузера!");
                    }
                });
            }
        }

        function showNotification(data) {
            if ("Notification" in window && Notification.permission === "granted") {
                let text = 'Новое сообщение';
                if (data.type === 'text') text = data.text;
                if (data.type === 'call_log') text = data.text;
                
                new Notification("Калькулятор", { 
                    body: text,
                    icon: 'https://cdn-icons-png.flaticon.com/512/3658/3658932.png'
                });
            }
        }

        function createPeerConnection() {
            pc = new RTCPeerConnection({ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }, { urls: 'stun:stun1.l.google.com:19302' }] });
            pc.onicecandidate = e => e.candidate && ws.send(JSON.stringify({ type: 'webrtc_ice', candidate: e.candidate }));
            pc.ontrack = e => {
                const remoteVid = document.getElementById('remote-video');
                remoteVid.srcObject = e.streams[0];
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
                callStartTime = Date.now();
            } catch(e) { 
                alert("Ошибка доступа к камере или микрофону!"); 
            }
        }

        function showIncomingCall(offer) {
            pendingOffer = offer;
            document.getElementById('incoming-modal').style.display = 'flex';
            startRingtone();
        }

        async function acceptCall() {
            stopRingtone();
            document.getElementById('incoming-modal').style.display = 'none';
            try {
                localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
                document.getElementById('call-modal').style.display = 'flex';
                document.getElementById('local-video').srcObject = localStream;

                createPeerConnection();
                localStream.getTracks().forEach(track => pc.addTrack(track, localStream));

                await pc.setRemoteDescription(new RTCSessionDescription(pendingOffer));
                const answer = await pc.createAnswer();
                await pc.setLocalDescription(answer);
                ws.send(JSON.stringify({ type: 'webrtc_answer', answer }));
                callStartTime = Date.now();
            } catch(e) { 
                alert("Не удалось включить камеру/микрофон."); 
                closeCallUI(); 
            }
        }

        function declineCall() {
            stopRingtone();
            document.getElementById('incoming-modal').style.display = 'none';
            ws.send(JSON.stringify({ type: 'webrtc_end' }));
            sendCallLog("📞 Пропущенный видеовызов");
            pendingOffer = null;
        }

        async function handleCallAnswer(answer) {
            if (pc) await pc.setRemoteDescription(new RTCSessionDescription(answer));
        }

        async function handleIceCandidate(candidate) {
            if (pc && pc.remoteDescription) await pc.addIceCandidate(new RTCIceCandidate(candidate));
        }

        function endCall() {
            ws.send(JSON.stringify({ type: 'webrtc_end' }));
            if (callStartTime) {
                const durationSec = Math.round((Date.now() - callStartTime) / 1000);
                const mins = Math.floor(durationSec / 60);
                const secs = durationSec % 60;
                sendCallLog(`📹 Видеовызов завершен (${mins > 0 ? mins + ' мин ' : ''}${secs} сек)`);
            } else {
                sendCallLog("📹 Видеовызов завершен");
            }
            closeCallUI();
        }

        function closeCallUI() {
            stopRingtone();
            if (localStream) localStream.getTracks().forEach(t => t.stop());
            if (pc) pc.close();
            document.getElementById('incoming-modal').style.display = 'none';
            document.getElementById('call-modal').style.display = 'none';
            callStartTime = null;
        }
    </script>
</body>
</html>
"""

AMIR_HTML = FAYE_HTML.replace("key_faye_phone_7730", "key_amir_pc_9981").replace("faye", "amir").replace("Любимый", "Любимая").replace("id=\"avatar-icon\">L", "id=\"avatar-icon\">F")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
