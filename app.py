from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import shutil
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import uvicorn
import asyncio

app = FastAPI()

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

templates = Jinja2Templates(directory="templates")

API_KEY = "trien123"

stream_enabled = True   # Mặc định BẬT để Pi gửi frame ngay khi server chạy
latest_frame_url = None
latest_frame_bytes = None
latest_device = "Chưa có"
latest_time = "--:--"
latest_upload_dt = None
latest_detections = []
detection_history = []
frame_count = 0

# --- CƠ CHẾ WEBSOCKET MANAGER ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast_bytes(self, data: bytes):
        for connection in self.active_connections.copy():
            try:
                await connection.send_bytes(data)
            except Exception:
                self.disconnect(connection)

stream_manager = ConnectionManager()
# --------------------------------


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/connect", response_class=HTMLResponse)
async def connect_page(request: Request):
    return templates.TemplateResponse("connect.html", {"request": request})


@app.get("/api/health")
async def health():
    return {"status": "ok", "message": "Hệ thống đang hoạt động"}


@app.get("/api/stream-status")
async def get_stream_status():
    connected = False
    if latest_upload_dt and stream_enabled:
        connected = (datetime.now(VN_TZ) - latest_upload_dt) <= timedelta(seconds=12)

    return {
        "enabled": stream_enabled,
        "connected": connected
    }


@app.post("/api/start-stream")
async def start_stream():
    global stream_enabled
    stream_enabled = True
    return {"status": "ok", "enabled": True}


@app.post("/api/stop-stream")
async def stop_stream():
    global stream_enabled
    stream_enabled = False
    return {"status": "ok", "enabled": False}


@app.get("/api/latest-frame")
async def latest_frame():
    connected = False
    if latest_upload_dt and stream_enabled:
        connected = (datetime.now(VN_TZ) - latest_upload_dt) <= timedelta(seconds=12)

    return {
        "image_url": latest_frame_url,
        "device": latest_device,
        "time": latest_time,
        "enabled": stream_enabled,
        "connected": connected
    }


@app.get("/api/detection-history")
async def get_detection_history():
    return {
        "items": detection_history
    }


@app.post("/api/upload-frame")
async def upload_frame(
    file: UploadFile = File(...),
    device: str = Form("Raspberry / Camera"),
    api_key: str = Form(""),
    detections: str = Form("")
):
    """(CŨ - VẪN GIỮ ĐỀ PHÒNG) API nhận ảnh nén JPEG và list string detections từ Raspberry Pi."""
    global latest_frame_url, latest_frame_bytes, latest_device, latest_time
    global latest_upload_dt, latest_detections, detection_history, frame_count

    if api_key != "trien123":
        raise HTTPException(status_code=403, detail="Sai API Key")

    if not stream_enabled:
        raise HTTPException(status_code=403, detail="Hệ thống chưa bật nhận dữ liệu")

    now_vn = datetime.now(VN_TZ)
    frame_count += 1
    
    file_bytes = await file.read()
    latest_frame_bytes = file_bytes
    
    # Parse detections string (format: "label:conf | label:conf")
    parsed_detections = []
    if detections.strip():
        items = [x.strip() for x in detections.split("|") if x.strip()]
        for item in items:
            try:
                label, confidence = item.split(":")
                parsed_detections.append({
                    "label": label.strip(),
                    "confidence": confidence.strip()
                })
            except ValueError:
                pass

    if parsed_detections:
        # Nhường event loop, đẩy việc ghi file vào thread riêng để không gây lag server
        timestamp = now_vn.strftime("%Y%m%d_%H%M%S_%f")
        ext = Path(file.filename).suffix or ".jpg"
        filename = f"frame_{timestamp}{ext}"
        save_path = UPLOAD_DIR / filename
        
        def save_file():
            with save_path.open("wb") as buffer:
                buffer.write(file_bytes)
        
        await asyncio.to_thread(save_file)
        latest_frame_url = f"/uploads/{filename}"
    else:
        latest_frame_url = None

    latest_device = device
    latest_time = now_vn.strftime("%H:%M:%S")
    latest_upload_dt = now_vn
    latest_detections = parsed_detections

    if parsed_detections:
        history_item = {
            "id": timestamp,
            "time": latest_time,
            "device": device,
            "image_url": latest_frame_url,
            "detections": parsed_detections
        }

        detection_history.insert(0, history_item)
        detection_history = detection_history[:10]

    # Phát qua WebSocket cho các trình duyệt đang xem nếu mún tích hợp
    if latest_frame_bytes:
        await stream_manager.broadcast_bytes(latest_frame_bytes)

    return {
        "status": "ok",
        "image_url": latest_frame_url
    }


@app.get("/api/latest-frame-image")
async def latest_frame_image():
    """Trả về JPEG frame mới nhất trực tiếp từ bộ nhớ (nhanh hơn static file)."""
    if latest_frame_bytes is None:
        raise HTTPException(status_code=404, detail="Chưa có frame")
    return Response(content=latest_frame_bytes, media_type="image/jpeg")


@app.get("/api/stats")
async def get_stats():
    """Thống kê realtime: số côn trùng, thiết bị, trạng thái kết nối."""
    connected = False
    if latest_upload_dt and stream_enabled:
        connected = (datetime.now(VN_TZ) - latest_upload_dt) <= timedelta(seconds=12)

    # Đếm theo loại
    label_counts = {}
    for det in latest_detections:
        label = det["label"]
        label_counts[label] = label_counts.get(label, 0) + 1

    return {
        "connected": connected,
        "enabled": stream_enabled,
        "device": latest_device,
        "time": latest_time,
        "frame_count": frame_count,
        "total_objects": len(latest_detections),
        "details": label_counts,
        "detections": latest_detections
    }

@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    await stream_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        stream_manager.disconnect(websocket)

@app.websocket("/ws/upload")
async def websocket_upload(websocket: WebSocket):
    await websocket.accept()
    global latest_frame_bytes, latest_device, latest_time, latest_upload_dt, latest_detections, frame_count
    
    try:
        while True:
            # 1. Nhận cục diện mô tả (Text JSON)
            data_text = await websocket.receive_text()
            meta_data = json.loads(data_text)
            
            # 2. Nhận nguyên cục ảnh (Binary Bytes)
            data_bytes = await websocket.receive_bytes()
            
            if meta_data.get("api_key") != API_KEY:
                await websocket.close(code=1008)
                break
                
            if not stream_enabled:
                continue

            now_vn = datetime.now(VN_TZ)
            frame_count += 1
            latest_frame_bytes = data_bytes
            
            # Parse detections
            detections_str = meta_data.get("detections", "")
            parsed_detections = []
            if detections_str.strip():
                items = [x.strip() for x in detections_str.split("|") if x.strip()]
                for item in items:
                    try:
                        label, confidence = item.split(":")
                        parsed_detections.append({
                            "label": label.strip(),
                            "confidence": confidence.strip()
                        })
                    except ValueError:
                        pass
            
            latest_device = meta_data.get("device", "Raspberry Pi Camera")
            latest_time = now_vn.strftime("%H:%M:%S")
            latest_upload_dt = now_vn
            latest_detections = parsed_detections

            await stream_manager.broadcast_bytes(latest_frame_bytes)
            
    except WebSocketDisconnect:
        print("[UPLOAD] Pi disconnected.")
    except Exception as e:
        print(f"[UPLOAD] Lỗi: {e}")

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    print(f"[SERVER] Đang khởi động Web Server luanvan-app-main...")
    print(f"[SERVER] Mở trình duyệt Web tại: http://localhost:{port} (local) hoặc trên Render")
    print("[SERVER] Chú ý: Hãy chắc chắn bạn đã CHO PHÉP (Allow) Python băng qua Tường lửa (Windows Firewall)!")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
