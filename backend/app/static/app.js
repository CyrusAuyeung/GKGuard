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
  toast: document.querySelector("#toast"),
};

const records = [
  { id: 1, title: "记录1", time: "16:24:18", fullTime: "2025-05-24 16:24:18", location: "C2 教学楼南门", camera: "C2-NM-02 门口通道机", cameraId: "C2-NM-02", similarity: 0.98, note: "检索到与目标人脸高度相似的关键帧", sceneClass: "scene-1", progress: 56 },
  { id: 2, title: "记录2", time: "15:37:42", fullTime: "2025-05-24 15:37:42", location: "图书馆一楼大厅", camera: "C2-NM-02 门口通道机", cameraId: "C2-NM-02", similarity: 0.96, note: "目标从图书馆方向经过大厅入口", sceneClass: "scene-2", progress: 44 },
  { id: 3, title: "记录3", time: "14:12:09", fullTime: "2025-05-24 14:12:09", location: "体育馆东门", camera: "C2-NM-01 广角摄像机", cameraId: "C2-NM-01", similarity: 0.94, note: "侧脸姿态命中，衣着特征一致", sceneClass: "scene-3", progress: 31 },
  { id: 4, title: "记录4", time: "12:05:33", fullTime: "2025-05-24 12:05:33", location: "宿舍区主干道", camera: "C2-NM-03 道路摄像机", cameraId: "C2-NM-03", similarity: 0.92, note: "道路摄像机捕获目标经过", sceneClass: "scene-4", progress: 18 },
  { id: 5, title: "记录5", time: "09:48:57", fullTime: "2025-05-24 09:48:57", location: "校门口", camera: "C2-NM-01 校门摄像机", cameraId: "C2-NM-01", similarity: 0.91, note: "最早关联关键帧，作为路径起点", sceneClass: "scene-5", progress: 8 },
];

const routePoints = [
  { id: 1, time: "09:48:57", location: "校门口", x: 26, y: 84, kind: "start" },
  { id: 2, time: "12:05:33", location: "宿舍区主干道", x: 30, y: 56 },
  { id: 3, time: "14:12:09", location: "体育馆东门", x: 38, y: 42 },
  { id: 4, time: "15:37:42", location: "图书馆一楼大厅", x: 52, y: 33 },
  { id: 5, time: "16:05:12", location: "教学楼广场", x: 64, y: 55 },
  { id: 6, time: "16:24:18", location: "C2 教学楼南门", x: 84, y: 24, kind: "end" },
];

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
  return `${Math.round(Number(value) * 100)}%`;
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
    uploadedImageUrl = String(reader.result || "");
    elements.uploadHint.textContent = `${file.name} 已就绪`;
    syncPortraits();
    showToast("目标照片已加载。");
  });
  reader.readAsDataURL(file);
}

function renderRecordLists() {
  const html = records.map((record, index) => `
    <button class="record-card ${index === selectedRecordIndex ? "is-active" : ""}" type="button" data-index="${index}">
      <span class="mini-face" aria-hidden="true"></span>
      <span>
        <strong>${escapeHtml(record.title)}</strong>
        <span>${escapeHtml(record.time)}</span>
        <span>${escapeHtml(record.cameraId)}</span>
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
  elements.recordScene.className = `camera-scene ${record.sceneClass}`;
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
    <div class="info-item"><span>记录编号：</span><strong>${escapeHtml(record.title)}</strong></div>
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
}

function startSearch() {
  elements.startSearchBtn.disabled = true;
  elements.startSearchBtn.textContent = "检索中...";
  showToast("正在检索历史关键帧。");
  window.setTimeout(() => {
    elements.startSearchBtn.disabled = false;
    elements.startSearchBtn.innerHTML = '<span class="search-action-icon" aria-hidden="true"></span>开始检索';
    selectedRecordIndex = 0;
    renderRecordLists();
    renderSelectedRecord();
    switchScreen("result");
    showToast("已检索到 5 条关联记录。");
  }, 520);
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
  document.querySelector("#showAllBtn").addEventListener("click", () => showToast("当前已显示全部 5 条检索结果。"));
  document.querySelector("#fullRouteBtn").addEventListener("click", () => showToast("完整 6 个轨迹点已展开。"));
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