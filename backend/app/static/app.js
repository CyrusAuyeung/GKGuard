const screens = {
  search: document.querySelector("#searchView"),
  result: document.querySelector("#resultView"),
  route: document.querySelector("#routeView"),
};

const elements = {
  faceFile: document.querySelector("#faceFile"),
  uploadDrop: document.querySelector("#uploadDrop"),
  uploadPreview: document.querySelector("#uploadPreview"),
  uploadHint: document.querySelector("#uploadHint"),
  startSearchBtn: document.querySelector("#startSearchBtn"),
  resultPortrait: document.querySelector("#resultPortrait"),
  routePortrait: document.querySelector("#routePortrait"),
  resultRecordList: document.querySelector("#resultRecordList"),
  routeRecordList: document.querySelector("#routeRecordList"),
  recordTitle: document.querySelector("#recordTitle"),
  recordScene: document.querySelector("#recordScene"),
  recordInfo: document.querySelector("#recordInfo"),
  timeBubble: document.querySelector("#timeBubble"),
  trackProgress: document.querySelector("#trackProgress"),
  campusRouteMap: document.querySelector("#campusRouteMap"),
  routeTimelineRows: document.querySelector("#routeTimelineRows"),
  routePointCount: document.querySelector("#routePointCount"),
  routeStart: document.querySelector("#routeStart"),
  routeEnd: document.querySelector("#routeEnd"),
  summaryDuration: document.querySelector("#summaryDuration"),
  summaryCameraCount: document.querySelector("#summaryCameraCount"),
  summaryFrameCount: document.querySelector("#summaryFrameCount"),
  summaryFinalSimilarity: document.querySelector("#summaryFinalSimilarity"),
  toast: document.querySelector("#toast"),
};

const records = [
  { id: 1, title: "记录1", time: "16:24:18", fullTime: "2025-05-24 16:24:18", location: "C2 教学楼南门", camera: "C2-NM-02 门口通道机", cameraId: "C2-NM-02", similarity: 0.98, note: "检索到与目标人脸高度相似的关键帧", sceneClass: "scene-1", progress: 56 },
  { id: 2, title: "记录2", time: "15:37:42", fullTime: "2025-05-24 15:37:42", location: "图书馆一楼大厅", camera: "C2-NM-02 门口通道机", cameraId: "C2-NM-02", similarity: 0.96, note: "目标从图书馆方向经过大厅入口", sceneClass: "scene-2", progress: 44 },
  { id: 3, title: "记录3", time: "14:12:09", fullTime: "2025-05-24 14:12:09", location: "体育馆东门", camera: "C2-NM-01 广角摄像机", cameraId: "C2-NM-01", similarity: 0.94, note: "侧脸姿态命中，衣着特征一致", sceneClass: "scene-3", progress: 31 },
  { id: 4, title: "记录4", time: "12:05:33", fullTime: "2025-05-24 12:05:33", location: "宿舍区主干道", camera: "C2-NM-03 道路摄像机", cameraId: "C2-NM-03", similarity: 0.92, note: "道路摄像机捕获目标经过", sceneClass: "scene-4", progress: 18 },
  { id: 5, title: "记录5", time: "09:48:57", fullTime: "2025-05-24 09:48:57", location: "校门口", camera: "C2-NM-01 校门摄像机", cameraId: "C2-NM-01", similarity: 0.91, note: "最早关联关键帧，作为路径起点", sceneClass: "scene-5", progress: 8 },
];

const mockRecords = records.map((record) => ({ ...record }));

const routePoints = [
  { id: 1, time: "09:48:57", location: "校门口", x: 26, y: 84, kind: "start" },
  { id: 2, time: "12:05:33", location: "宿舍区主干道", x: 30, y: 56 },
  { id: 3, time: "14:12:09", location: "体育馆东门", x: 38, y: 42 },
  { id: 4, time: "15:37:42", location: "图书馆一楼大厅", x: 52, y: 33 },
  { id: 5, time: "16:05:12", location: "教学楼广场", x: 64, y: 55 },
  { id: 6, time: "16:24:18", location: "C2 教学楼南门", x: 84, y: 24, kind: "end" },
];

const mockRoutePoints = routePoints.map((point) => ({ ...point }));

const buildings = [
  { name: "体育馆", x: 31, y: 28, w: 14, h: 12 },
  { name: "图书馆", x: 50, y: 19, w: 15, h: 12 },
  { name: "教学楼", x: 77, y: 13, w: 15, h: 13 },
  { name: "宿舍区", x: 20, y: 47, w: 13, h: 12 },
  { name: "广场", x: 61, y: 61, w: 12, h: 10 },
  { name: "校门", x: 23, y: 78, w: 11, h: 8 },
];

let selectedRecordIndex = 0;
let uploadedImageUrl = "";
let uploadedFile = null;
let activeSource = "mock";
let toastTimer = null;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function formatPercent(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  return `${Math.round(number * 100)}%`;
}

function parseTimeSeconds(value) {
  const match = String(value || "").match(/^(\d{1,2}):(\d{2}):(\d{2})$/);
  if (!match) return null;
  return Number(match[1]) * 3600 + Number(match[2]) * 60 + Number(match[3]);
}

function formatDuration(seconds) {
  if (!Number.isFinite(seconds) || seconds <= 0) return "--";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  if (hours) return `${hours}小时${minutes}分`;
  if (minutes) return `${minutes}分${secs}秒`;
  return `${secs}秒`;
}

function switchScreen(name) {
  Object.entries(screens).forEach(([key, screen]) => {
    screen?.classList.toggle("is-active", key === name);
  });
}

function showToast(message) {
  if (!elements.toast) return;
  elements.toast.textContent = message;
  elements.toast.classList.add("is-visible");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => elements.toast.classList.remove("is-visible"), 2200);
}

function portraitMarkup() {
  if (uploadedImageUrl) return `<img src="${uploadedImageUrl}" alt="上传的人脸图片" />`;
  return '<span class="portrait-art" aria-hidden="true"></span>';
}

function recordThumbMarkup(record) {
  if (record.frameUrl) {
    return `<span class="mini-face has-thumb"><img src="${escapeHtml(record.frameUrl)}" alt="${escapeHtml(record.title)} 缩略图" /></span>`;
  }
  return '<span class="mini-face" aria-hidden="true"></span>';
}

function syncPortraits() {
  [elements.uploadPreview, elements.resultPortrait, elements.routePortrait].forEach((target) => {
    if (!target) return;
    target.innerHTML = portraitMarkup();
  });
}

function loadImage(file) {
  if (!file) return;
  if (!file.type.startsWith("image/")) {
    showToast("请选择 JPG 或 PNG 图片。");
    return;
  }
  const reader = new FileReader();
  reader.addEventListener("load", () => {
    uploadedFile = file;
    uploadedImageUrl = String(reader.result || "");
    elements.uploadHint.textContent = `${file.name} 已就绪`;
    syncPortraits();
    showToast("目标照片已加载。");
  });
  reader.readAsDataURL(file);
}

function resetToMockData() {
  records.splice(0, records.length, ...mockRecords.map((record) => ({ ...record })));
  routePoints.splice(0, routePoints.length, ...mockRoutePoints.map((point) => ({ ...point })));
  activeSource = "mock";
}

function applyC1Result(result) {
  if (!result?.records?.length) {
    throw new Error(result?.warning || "C1 没有返回匹配记录");
  }

  records.splice(0, records.length, ...result.records.map((record, index) => ({
    ...record,
    id: index + 1,
    title: record.title || `记录${index + 1}`,
    sceneClass: record.sceneClass || `scene-${(index % 5) + 1}`,
    progress: Number.isFinite(Number(record.progress)) ? Number(record.progress) : Math.min(92, 10 + index * 14),
  })));

  const incomingRoute = result.routePoints?.length ? result.routePoints : records.map((record, index) => ({
    id: index + 1,
    time: record.time,
    location: record.location,
    x: 22 + ((index * 15) % 62),
    y: 76 - ((index * 11) % 48),
  }));
  routePoints.splice(0, routePoints.length, ...incomingRoute.map((point, index) => ({
    ...point,
    id: index + 1,
    kind: index === 0 ? "start" : index === incomingRoute.length - 1 ? "end" : point.kind,
  })));

  if (result.person?.representativeFaceUrl) {
    uploadedImageUrl = result.person.representativeFaceUrl;
    syncPortraits();
  }

  activeSource = "c1";
}

async function fetchC1Search() {
  if (!uploadedFile) throw new Error("请先上传目标人脸图片");
  const formData = new FormData();
  formData.append("file", uploadedFile, uploadedFile.name || "query.jpg");
  const response = await fetch("/c1/search/person-by-image?top_k=5&max_gap_sec=3", {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail?.detail?.message || `C1 接口返回 ${response.status}`);
  }
  return response.json();
}

function renderRecordLists() {
  const html = records.map((record, index) => `
    <button class="record-card ${index === selectedRecordIndex ? "is-active" : ""}" type="button" data-index="${index}">
      ${recordThumbMarkup(record)}
      <span>
        <strong>${escapeHtml(record.title)}</strong>
        <span>${escapeHtml(record.time)}</span>
        <span>${escapeHtml(record.cameraId || "C1")}</span>
      </span>
    </button>
  `).join("");
  elements.resultRecordList.innerHTML = html;
  elements.routeRecordList.innerHTML = html;

  document.querySelectorAll(".record-card").forEach((button) => {
    button.addEventListener("click", () => {
      selectedRecordIndex = Number(button.dataset.index || 0);
      renderRecordLists();
      renderSelectedRecord();
    });
  });
}

function renderSelectedRecord() {
  const record = records[selectedRecordIndex];
  elements.recordTitle.textContent = record.title;
  elements.recordScene.className = `camera-scene ${record.frameUrl ? "has-frame" : record.sceneClass}`;
  elements.recordScene.querySelectorAll(".scene-frame").forEach((node) => node.remove());
  if (record.frameUrl) {
    const image = document.createElement("img");
    image.className = "scene-frame";
    image.src = record.frameUrl;
    image.alt = `${record.title} 监控关键帧`;
    elements.recordScene.prepend(image);
  }
  elements.recordScene.querySelector(".scene-time").innerHTML = record.fullTime.replace(" ", "&nbsp;&nbsp;");
  elements.timeBubble.textContent = record.time;
  elements.trackProgress.style.left = `${record.progress}%`;
  elements.timeBubble.style.left = `${record.progress}%`;
  elements.recordInfo.innerHTML = `
    <div class="info-item"><span>出现时间：</span><strong>${escapeHtml(record.fullTime)}</strong></div>
    <div class="info-item"><span>相似度：</span><strong>${escapeHtml(formatPercent(record.similarity))}</strong></div>
    <div class="info-item"><span>位置：</span><strong>${escapeHtml(record.location)}</strong></div>
    <div class="info-item"><span>说明：</span><strong>${escapeHtml(record.note)}</strong></div>
    <div class="info-item"><span>摄像头：</span><strong>${escapeHtml(record.camera)}</strong></div>
    <div class="info-item"><span>数据来源：</span><strong>${activeSource === "c1" ? "C1 CampusVision" : "本地模拟"}</strong></div>
  `;
}

function renderRouteMap() {
  const linePoints = routePoints.map((point) => `${point.x},${point.y}`).join(" ");
  elements.campusRouteMap.innerHTML = `
    ${buildings.map((building) => `<span class="map-building" style="left:${building.x}%;top:${building.y}%;width:${building.w}%;height:${building.h}%">${escapeHtml(building.name)}</span>`).join("")}
    <svg class="route-line" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <polyline points="${linePoints}" fill="none" stroke="rgba(36,111,245,.16)" stroke-width="5.8" stroke-linecap="round" stroke-linejoin="round"></polyline>
      <polyline points="${linePoints}" fill="none" stroke="#246ff5" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"></polyline>
    </svg>
    ${routePoints.map((point) => `
      <span class="map-point ${point.kind || ""}" style="left:${point.x}%;top:${point.y}%">${point.kind === "start" ? "起" : point.kind === "end" ? "终" : point.id}</span>
      <span class="map-label" style="left:${point.x}%;top:${point.y}%">${escapeHtml(point.location)}</span>
    `).join("")}
    <div class="map-legend">
      <span><i class="start-dot">起</i>起点</span>
      <span><i class="end-dot">终</i>终点</span>
      <span><i>1</i>轨迹点</span>
      <span><i class="camera-dot"></i>摄像头</span>
    </div>
  `;
}

function renderRouteTimeline() {
  elements.routeTimelineRows.innerHTML = routePoints.map((point) => `
    <div class="timeline-row">
      <b>${point.id}</b>
      <span>${escapeHtml(point.time)}</span>
      <strong>${escapeHtml(point.location)}</strong>
    </div>
  `).join("");

  const startPoint = routePoints[0];
  const endPoint = routePoints[routePoints.length - 1];
  const cameras = new Set(records.map((record) => record.cameraId || record.camera).filter(Boolean));
  const sortedSeconds = routePoints.map((point) => parseTimeSeconds(point.time)).filter((value) => value !== null).sort((left, right) => left - right);
  const duration = sortedSeconds.length > 1 ? sortedSeconds[sortedSeconds.length - 1] - sortedSeconds[0] : null;
  elements.routePointCount.textContent = String(routePoints.length);
  elements.routeStart.textContent = startPoint?.location || "--";
  elements.routeEnd.textContent = endPoint?.location || "--";
  elements.summaryDuration.textContent = formatDuration(duration);
  elements.summaryCameraCount.textContent = `${Math.max(cameras.size, 1)}路`;
  elements.summaryFrameCount.textContent = String(records.length);
  elements.summaryFinalSimilarity.textContent = formatPercent(records[0]?.similarity);
}

async function startSearch() {
  elements.startSearchBtn.disabled = true;
  elements.startSearchBtn.textContent = "检索中...";
  showToast(uploadedFile ? "正在调用 C1 检索服务。" : "未上传图片，使用本地模拟数据。");
  try {
    if (uploadedFile) {
      const result = await fetchC1Search();
      applyC1Result(result);
      showToast(`C1 返回 ${records.length} 条关联记录。`);
    } else {
      resetToMockData();
    }
  } catch (error) {
    resetToMockData();
    showToast(`${error.message}，已回退本地模拟。`);
  } finally {
    elements.startSearchBtn.disabled = false;
    elements.startSearchBtn.innerHTML = '<span class="search-action-icon" aria-hidden="true"></span>开始检索';
    selectedRecordIndex = 0;
    renderRecordLists();
    renderSelectedRecord();
    renderRouteMap();
    renderRouteTimeline();
    switchScreen("result");
  }
}

function downloadText(filename, content) {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 500);
}

function bindEvents() {
  elements.uploadDrop.addEventListener("click", () => elements.faceFile.click());
  elements.faceFile.addEventListener("change", (event) => loadImage(event.target.files?.[0]));
  elements.uploadDrop.addEventListener("dragover", (event) => {
    event.preventDefault();
    elements.uploadDrop.classList.add("is-dragging");
  });
  elements.uploadDrop.addEventListener("dragleave", () => elements.uploadDrop.classList.remove("is-dragging"));
  elements.uploadDrop.addEventListener("drop", (event) => {
    event.preventDefault();
    elements.uploadDrop.classList.remove("is-dragging");
    loadImage(event.dataTransfer.files?.[0]);
  });
  elements.startSearchBtn.addEventListener("click", startSearch);
  document.querySelector("#openRouteBtn").addEventListener("click", () => { switchScreen("route"); showToast("已打开人物路线图。"); });
  document.querySelector("#backToResultBtn").addEventListener("click", () => switchScreen("result"));
  document.querySelector("#showAllBtn").addEventListener("click", () => showToast(`当前已显示全部 ${records.length} 条检索结果。`));
  document.querySelector("#fullRouteBtn").addEventListener("click", () => showToast(`完整 ${routePoints.length} 个轨迹点已展开。`));
  document.querySelector("#playBtn").addEventListener("click", () => showToast("关键帧时间线已定位到当前记录。"));
  document.querySelector("#exportFrameBtn").addEventListener("click", () => {
    const record = records[selectedRecordIndex];
    downloadText(`GKGuard-${record.title}.txt`, JSON.stringify(record, null, 2));
    showToast("截图信息已导出。实际截图导出可接入桌面端捕获能力。");
  });
  document.querySelector("#exportRouteBtn").addEventListener("click", () => {
    downloadText("GKGuard-route.json", JSON.stringify({ routePoints, records }, null, 2));
    showToast("路线图数据已导出。");
  });
}

syncPortraits();
renderRecordLists();
renderSelectedRecord();
renderRouteMap();
renderRouteTimeline();
bindEvents();