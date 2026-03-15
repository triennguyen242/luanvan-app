function goToConnectPage() {
  window.location.href = "/connect";
}

function goHome() {
  window.location.href = "/";
}

function addLog(message) {
  const logBox = document.getElementById("logBox");
  if (!logBox) return;

  const item = document.createElement("div");
  item.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
  logBox.prepend(item);
}

async function checkHealth() {
  const apiText = document.getElementById("apiText");

  try {
    const res = await fetch("/api/health?t=" + Date.now(), {
      cache: "no-store"
    });
    await res.json();

    if (apiText) apiText.textContent = "Hoạt động";
    addLog("API hoạt động bình thường.");
  } catch (err) {
    if (apiText) apiText.textContent = "Lỗi kết nối";
    addLog("Không kết nối được API.");
  }
}

async function startStream() {
  try {
    const res = await fetch("/api/start-stream", {
      method: "POST",
      cache: "no-store"
    });
    const data = await res.json();

    if (data.enabled) {
      document.getElementById("statusText").textContent = "Đã kết nối";
      addLog("Đã bật nhận dữ liệu từ thiết bị.");
      refreshPreview();
    }
  } catch (err) {
    addLog("Không bật được kết nối.");
  }
}

async function stopStream() {
  try {
    const res = await fetch("/api/stop-stream", {
      method: "POST",
      cache: "no-store"
    });
    const data = await res.json();

    if (!data.enabled) {
      document.getElementById("statusText").textContent = "Đã ngắt";
      addLog("Đã tắt nhận dữ liệu từ thiết bị.");
    }
  } catch (err) {
    addLog("Không tắt được kết nối.");
  }
}

async function refreshPreview() {
  try {
    const res = await fetch("/api/latest-frame?t=" + Date.now(), {
      cache: "no-store"
    });
    const data = await res.json();

    const img = document.getElementById("previewImage");
    const placeholder = document.getElementById("previewPlaceholder");
    const deviceText = document.getElementById("deviceText");

    if (!img || !placeholder) return;

    if (data.image_url) {
      img.src = data.image_url + "?t=" + Date.now();
      img.classList.remove("hidden");
      img.style.display = "block";

      placeholder.classList.add("hidden");
      placeholder.style.display = "none";
    } else {
      img.classList.add("hidden");
      img.style.display = "none";

      placeholder.classList.remove("hidden");
      placeholder.style.display = "block";
    }

    if (deviceText && data.device) {
      deviceText.textContent = data.device;
    }
  } catch (err) {
    addLog("Không tải được khung hình hiện tại.");
  }
}

function runDetectDemo() {
  const resultList = document.getElementById("resultList");
  if (!resultList) return;

  resultList.innerHTML = `
    <div class="result-item">
      <strong>Bọ cánh cứng</strong>
      <span>Độ tin cậy: 0.95</span>
    </div>
    <div class="result-item">
      <strong>Bướm</strong>
      <span>Độ tin cậy: 0.88</span>
    </div>
    <div class="result-item">
      <strong>Châu chấu</strong>
      <span>Độ tin cậy: 0.91</span>
    </div>
  `;
  addLog("Đã hiển thị dữ liệu nhận diện thử.");
}

window.onload = () => {
  checkHealth();
  refreshPreview();
  setInterval(refreshPreview, 2000);
};
