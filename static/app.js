async function goToConnectPage() {
  try {
    await fetch("/api/start-stream", {
      method: "POST",
      cache: "no-store"
    });
  } catch (err) {
    console.log("Không bật được stream trước khi chuyển trang.");
  }

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
  item.classList.add("log-item");
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

async function stopStream() {
  try {
    const res = await fetch("/api/stop-stream", {
      method: "POST",
      cache: "no-store"
    });
    const data = await res.json();

    if (!data.enabled) {
      const statusText = document.getElementById("statusText");
      const deviceText = document.getElementById("deviceText");

      if (statusText) statusText.textContent = "Đã ngắt";
      if (deviceText) deviceText.textContent = "Chưa có dữ liệu";

      addLog("Đã tắt nhận dữ liệu từ thiết bị.");
      refreshPreview();
    }
  } catch (err) {
    addLog("Không tắt được kết nối.");
  }
}

function showHistoryImage(imageUrl) {
  const img = document.getElementById("previewImage");
  const placeholder = document.getElementById("previewPlaceholder");

  if (!img || !placeholder) return;

  img.src = imageUrl + "?t=" + Date.now();
  img.classList.remove("hidden");
  img.style.display = "block";

  placeholder.classList.add("hidden");
  placeholder.style.display = "none";
}

function renderDetectionHistory(items) {
  const resultList = document.getElementById("resultList");
  if (!resultList) return;

  if (!items || items.length === 0) {
    resultList.innerHTML = `
      <div class="result-empty">Chưa có dữ liệu nhận diện</div>
    `;
    return;
  }

  resultList.innerHTML = items.map((item) => {
    const labels = item.detections
      .map(det => `${det.label} (${det.confidence})`)
      .join(", ");

    return `
      <div class="result-item fade-item history-item" onclick="showHistoryImage('${item.image_url}')">
        <strong>${labels}</strong>
        <span>Thiết bị: ${item.device}</span>
        <span>Thời gian: ${item.time}</span>
      </div>
    `;
  }).join("");
}

async function refreshDetectionHistory() {
  try {
    const res = await fetch("/api/detection-history?t=" + Date.now(), {
      cache: "no-store"
    });
    const data = await res.json();
    renderDetectionHistory(data.items || []);
  } catch (err) {
    addLog("Không tải được lịch sử nhận diện.");
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
    const statusText = document.getElementById("statusText");

    if (img && placeholder) {
      if (data.image_url) {
        img.src = data.image_url + "?t=" + Date.now();
        img.classList.remove("hidden");
        img.style.display = "block";
        img.classList.add("pulse-frame");

        placeholder.classList.add("hidden");
        placeholder.style.display = "none";
      } else {
        img.classList.add("hidden");
        img.style.display = "none";

        placeholder.classList.remove("hidden");
        placeholder.style.display = "block";
      }
    }

    if (deviceText) {
      deviceText.textContent = data.connected
        ? (data.device || "Thiết bị")
        : "Chưa có dữ liệu";
    }

    if (statusText) {
      if (data.connected) {
        statusText.textContent = "Đã kết nối";
      } else if (data.enabled) {
        statusText.textContent = "Đang chờ thiết bị";
      } else {
        statusText.textContent = "Đã ngắt";
      }
    }

    await refreshDetectionHistory();
  } catch (err) {
    addLog("Không tải được khung hình hiện tại.");
  }
}

function runDetectDemo() {
  refreshDetectionHistory();
  addLog("Đã làm mới lịch sử nhận diện.");
}

window.onload = () => {
  checkHealth();
  refreshPreview();
  setInterval(refreshPreview, 2000);
};
