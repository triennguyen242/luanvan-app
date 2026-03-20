from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
import shutil
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
latest_frame_bytes = None  # Lưu frame JPEG trong bộ nhớ để serve nhanh
latest_device = "Chưa có dữ liệu"
latest_time = "--:--"
latest_upload_dt = None
latest_detections = []  # Danh sách detection hiện tại

detection_history = []
frame_count = 0  # Đếm số frame đã nhận


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
    global latest_frame_url, latest_frame_bytes, latest_device, latest_time
    global latest_upload_dt, latest_detections, detection_history, frame_count

    if api_key != API_KEY:
        print(f"[UPLOAD] ✘ API key sai từ {device}")
        raise HTTPException(status_code=401, detail="API key không hợp lệ")

    if not stream_enabled:
        raise HTTPException(status_code=403, detail="Hệ thống chưa bật nhận dữ liệu")

    now_vn = datetime.now(VN_TZ)
    frame_count += 1

    # Đọc file vào bộ nhớ để serve nhanh
    file_bytes = await file.read()
    latest_frame_bytes = file_bytes

    # Vẫn lưu file cho history
    timestamp = now_vn.strftime("%Y%m%d_%H%M%S_%f")
    ext = Path(file.filename).suffix or ".jpg"
    filename = f"frame_{timestamp}{ext}"
    save_path = UPLOAD_DIR / filename

    with save_path.open("wb") as buffer:
        buffer.write(file_bytes)

    latest_frame_url = f"/uploads/{filename}"
    latest_device = device
    latest_time = now_vn.strftime("%H:%M:%S")
    latest_upload_dt = now_vn

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
        detection_history = detection_history[:50]  # Giữ 50 mục

    # Log mỗi 10 frame
    if frame_count % 10 == 1:
        det_str = ", ".join([f"{d['label']}({d['confidence']})" for d in parsed_detections]) or "none"
        print(f"[UPLOAD] ✔ Frame #{frame_count} từ {device} | Detections: {det_str}")

    return {
        "status": "ok",
        "image_url": latest_frame_url,
        "frame_count": frame_count
    }


@app.get("/api/latest-frame-image")
async def latest_frame_image():
    """Trả về JPEG frame mới nhất trực tiếp từ bộ nhớ (nhanh hơn static file)."""
    if latest_frame_bytes is None:
        raise HTTPException(status_code=404, detail="Chưa có frame")
    return Response(content=latest_frame_bytes, media_type="image/jpeg")


async def frame_generator():
    """Generator sinh ra luồng video MJPEG từ các frame trong bộ nhớ"""
    last_count = 0
    while True:
        if not stream_enabled:
            await asyncio.sleep(0.5)
            continue
            
        if frame_count > last_count and latest_frame_bytes:
            last_count = frame_count
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + latest_frame_bytes + b'\r\n')
        
        # Ngủ tối đa ~20FPS (50ms) để không ngốn CPU
        await asyncio.sleep(0.05)


@app.get("/api/video-stream")
async def video_stream():
    """Endpoint truyền video mượt mà qua chuẩn MJPEG (multipart/x-mixed-replace)"""
    return StreamingResponse(frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame")


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

if __name__ == "__main__":
    print("[SERVER] Đang khởi động Web Server luanvan-app-main...")
    print("[SERVER] Chú ý: Hãy chắc chắn bạn đã CHO PHÉP (Allow) Python băng qua Tường lửa (Windows Firewall)!")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
