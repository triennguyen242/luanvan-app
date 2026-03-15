from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import shutil
from datetime import datetime

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

API_KEY = "trien123"

stream_enabled = False
latest_frame_url = None
latest_device = "Chưa có dữ liệu"
latest_time = "--:--"

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
    return {"enabled": stream_enabled}

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
    return {
        "image_url": latest_frame_url,
        "device": latest_device,
        "time": latest_time
    }

@app.post("/api/upload-frame")
async def upload_frame(
    file: UploadFile = File(...),
    device: str = Form("Raspberry / Camera"),
    api_key: str = Form(...)
):
    global latest_frame_url, latest_device, latest_time

    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="API key không hợp lệ")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = Path(file.filename).suffix or ".jpg"
    filename = f"frame_{timestamp}{ext}"
    save_path = UPLOAD_DIR / filename

    with save_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    latest_frame_url = f"/uploads/{filename}"
    latest_device = device
    latest_time = datetime.now().strftime("%H:%M:%S")

    return {"status": "ok", "image_url": latest_frame_url}