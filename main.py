import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
