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
      const resultList = document.getElementById("resultList");

      if (statusText) statusText.textContent = "Đã ngắt";
      if (deviceText) deviceText.textContent = "Chưa có dữ liệu";

      if (resultList) {
        resultList.innerHTML = `
          <div class="result-empty">Chưa có dữ liệu nhận diện</div>
        `;
      }

      addLog("Đã tắt nhận dữ liệu từ thiết bị.");
      refreshPreview();
    }
  } catch (err) {
    addLog("Không tắt được kết nối.");
  }
}

function renderDetectionResults(data) {
  const resultList = document.getElementById("resultList");
  if (!resultList) return;

  if (!data.image_url) {
    resultList.innerHTML = `
      <div class="result-empty">Chưa có dữ liệu nhận diện</div>
    `;
    return;
  }

  if (Array.isArray(data.detections) && data.detections.length > 0) {
    resultList.innerHTML = data.detections.map(item => `
      <div class="result-item fade-item">
        <strong>${item.label}</strong>
        <span>Độ tin cậy: ${item.confidence}</span>
      </div>
    `).join("");
    return;
  }

  resultList.innerHTML = `
    <div class="result-item fade-item">
      <strong>Ảnh mới đã nhận</strong>
      <span>Thiết bị: ${data.device || "Không xác định"}</span>
    </div>
    <div class="result-item fade-item">
      <strong>Thời gian</strong>
      <span>${data.time || "--:--:--"}</span>
    </div>
    <div class="result-item fade-item">
      <strong>Trạng thái</strong>
      <span>Chưa có nhãn nhận diện chi tiết</span>
    </div>
  `;
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

    renderDetectionResults(data);
  } catch (err) {
    addLog("Không tải được khung hình hiện tại.");
  }
}

function runDetectDemo() {
  refreshPreview();
  addLog("Đã làm mới dữ liệu nhận diện.");
}

window.onload = () => {
  checkHealth();
  refreshPreview();
  setInterval(refreshPreview, 2000);
};
