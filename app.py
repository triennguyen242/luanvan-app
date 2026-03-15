from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import shutil
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

app = FastAPI()

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

templates = Jinja2Templates(directory="templates")

API_KEY = "trien123"

stream_enabled = False
latest_frame_url = None
latest_device = "Chưa có dữ liệu"
latest_time = "--:--"
latest_upload_dt = None

detection_history = []


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
    api_key: str = Form(...),
    detections: str = Form("")
):
    global latest_frame_url, latest_device, latest_time, latest_upload_dt, detection_history

    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="API key không hợp lệ")

    if not stream_enabled:
        raise HTTPException(status_code=403, detail="Hệ thống chưa bật nhận dữ liệu")

    now_vn = datetime.now(VN_TZ)

    timestamp = now_vn.strftime("%Y%m%d_%H%M%S")
    ext = Path(file.filename).suffix or ".jpg"
    filename = f"frame_{timestamp}{ext}"
    save_path = UPLOAD_DIR / filename

    with save_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    latest_frame_url = f"/uploads/{filename}"
    latest_device = device
    latest_time = now_vn.strftime("%H:%M:%S")
    latest_upload_dt = now_vn

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
        history_item = {
            "id": timestamp,
            "time": latest_time,
            "device": device,
            "image_url": latest_frame_url,
            "detections": parsed_detections
        }

        detection_history.insert(0, history_item)
        detection_history = detection_history[:10]

    return {
        "status": "ok",
        "image_url": latest_frame_url
    }
