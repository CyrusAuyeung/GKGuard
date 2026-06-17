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
  resultSourceBadge: document.querySelector("#resultSourceBadge"),
  resultCountBadge: document.querySelector("#resultCountBadge"),
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
  desktopUpdatePanel: document.querySelector("#desktopUpdatePanel"),
  checkUpdateBtn: document.querySelector("#checkUpdateBtn"),
  updateStatus: document.querySelector("#updateStatus"),
  newSearchBtn: document.querySelector("#newSearchBtn"),
  routeNewSearchBtn: document.querySelector("#routeNewSearchBtn"),
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
let matchedPersonImageUrl = "";
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

function sourceLabel() {
  return activeSource === "c1" ? "CampusVision C1" : "本地模拟";
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

  const resetScroll = () => {
    window.scrollTo(0, 0);
    document.scrollingElement?.scrollTo(0, 0);
  };
  resetScroll();
  window.requestAnimationFrame(resetScroll);
  window.setTimeout(resetScroll, 80);
}

function showToast(message) {
  if (!elements.toast) return;
  elements.toast.textContent = message;
  elements.toast.classList.add("is-visible");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => elements.toast.classList.remove("is-visible"), 2200);
}

function portraitMarkup() {
  const portraitUrl = uploadedImageUrl || matchedPersonImageUrl;
  if (portraitUrl) return `<img src="${portraitUrl}" alt="目标人物照片" />`;
  return '<span class="portrait-art" aria-hidden="true"></span>';
}

function recordThumbMarkup(record) {
  const thumbUrl = record.thumbnailUrl || record.faceUrl || record.frameUrl;
  if (thumbUrl) {
    return `<span class="mini-face has-thumb"><img src="${escapeHtml(thumbUrl)}" alt="${escapeHtml(record.title)} 缩略图" /></span>`;
  }
  return '<span class="mini-face" aria-hidden="true"></span>';
}

function bindRecordThumbnailFallbacks() {
  document.querySelectorAll(".mini-face.has-thumb img").forEach((image) => {
    image.addEventListener("error", () => {
      const wrapper = image.closest(".mini-face");
      wrapper?.classList.remove("has-thumb");
      image.remove();
    });
  });
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
    matchedPersonImageUrl = "";
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

function resetSearchInput() {
  uploadedFile = null;
  uploadedImageUrl = "";
  matchedPersonImageUrl = "";
  selectedRecordIndex = 0;
  if (elements.faceFile) elements.faceFile.value = "";
  if (elements.uploadHint) elements.uploadHint.textContent = "支持 JPG / PNG，建议上传清晰正脸照片";
  resetToMockData();
  syncPortraits();
  renderRecordLists();
  renderSelectedRecord();
  renderRouteMap();
  renderRouteTimeline();
  switchScreen("search");
  showToast("已返回上传页，可选择新的目标照片。");
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
    matchedPersonImageUrl = result.person.representativeFaceUrl;
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

async function connectC1AfterFailure(error) {
  const desktopBridge = window.gkguardDesktop;
  const isDesktop = new URLSearchParams(window.location.search).get("desktop") === "1";
  if (!desktopBridge?.connectC1 || !isDesktop) {
    return false;
  }

  showToast("CampusVision C1 暂不可用，请在软件内输入服务器密码。");
  const result = await desktopBridge.connectC1(error?.message || "CampusVision C1 服务当前不可用").catch(() => null);
  if (result?.connected) {
    showToast(result.prompted ? "CampusVision C1 已连接，正在重新检索。" : "CampusVision C1 已可用，正在重新检索。");
    return true;
  }
  showToast("仍未检测到 CampusVision C1，将使用本地模拟。请确认服务器密码和校园网连接。");
  return false;
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
  if (elements.resultSourceBadge) elements.resultSourceBadge.textContent = sourceLabel();
  if (elements.resultCountBadge) elements.resultCountBadge.textContent = `${records.length} 条`;
  bindRecordThumbnailFallbacks();

  document.querySelectorAll(".record-card").forEach((button) => {
    button.addEventListener("click", () => {
      selectedRecordIndex = Number(button.dataset.index || 0);
      renderRecordLists();
      renderSelectedRecord();
    });
  });
}

function setUpdateStatus(label, disabled = false) {
  if (!elements.checkUpdateBtn || !elements.updateStatus) return;
  elements.updateStatus.textContent = label;
  elements.checkUpdateBtn.disabled = disabled;
}

async function initDesktopUpdateEntry() {
  const desktopBridge = window.gkguardDesktop;
  const isDesktop = new URLSearchParams(window.location.search).get("desktop") === "1";
  if (!desktopBridge || !isDesktop || !elements.desktopUpdatePanel || !elements.checkUpdateBtn) {
    return;
  }

  elements.desktopUpdatePanel.hidden = false;
  const appInfo = await desktopBridge.getAppInfo().catch(() => null);
  if (appInfo?.version) {
    setUpdateStatus(`检查更新 v${appInfo.version}`);
  }

  let updateStage = "idle";
  let latestUpdate = null;
  desktopBridge.onUpdateEvent?.((event) => {
    if (event?.type === "download-progress") {
      updateStage = "downloading";
      setUpdateStatus(`下载中 ${event.percent}%`, true);
    }
    if (event?.type === "update-downloaded") {
      updateStage = "downloaded";
      setUpdateStatus("重启安装");
      showToast("新版已在应用内下载完成，点击即可重启安装。");
    }
    if (event?.type === "error") {
      updateStage = "idle";
      setUpdateStatus("检查更新");
      showToast(`更新失败：${event.message}`);
    }
  });

  elements.checkUpdateBtn.addEventListener("click", async () => {
    if (updateStage === "downloaded") {
      setUpdateStatus("正在重启...", true);
      await desktopBridge.installUpdate?.();
      return;
    }

    if (latestUpdate?.updateAvailable && updateStage === "available") {
      setUpdateStatus("开始下载...", true);
      const downloadResult = await desktopBridge.downloadUpdate();
      if (downloadResult?.embedded === false) {
        updateStage = "idle";
        setUpdateStatus("检查更新");
        elements.checkUpdateBtn.disabled = false;
        showToast("已打开 GitHub Release。正式安装版会在应用内更新。");
        return;
      }
      if (updateStage !== "downloaded") {
        updateStage = "downloading";
        setUpdateStatus("下载中...", true);
      }
      showToast("新版正在应用内下载。");
      return;
    }

    setUpdateStatus("检查中...", true);
    try {
      latestUpdate = await desktopBridge.checkForUpdates();
      if (latestUpdate.updateAvailable) {
        updateStage = latestUpdate.downloaded ? "downloaded" : "available";
        setUpdateStatus(updateStage === "downloaded" ? "重启安装" : `应用内更新 ${latestUpdate.latestVersion}`);
        showToast(updateStage === "downloaded" ? "新版已下载完成，点击即可重启安装。" : `发现新版 ${latestUpdate.latestVersion}，再次点击将在应用内下载。`);
      } else {
        updateStage = "idle";
        setUpdateStatus("已是最新版", true);
        showToast(`当前已是最新版本 ${latestUpdate.currentVersion}。`);
        window.setTimeout(() => setUpdateStatus(`检查更新 v${latestUpdate.currentVersion}`), 2400);
      }
    } catch (error) {
      setUpdateStatus("检查更新");
      showToast(`检查更新失败：${error.message}`);
    } finally {
      if (updateStage !== "downloading" && (!latestUpdate || latestUpdate.updateAvailable)) {
        elements.checkUpdateBtn.disabled = false;
      }
    }
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
    <div class="info-item"><span>数据来源：</span><strong>${sourceLabel()}</strong></div>
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
  elements.startSearchBtn.innerHTML = '<svg class="ui-icon search-action-icon" aria-hidden="true"><use href="#icon-search"></use></svg>检索中...';
  showToast(uploadedFile ? "正在调用 CampusVision C1 检索服务。" : "未上传图片，使用本地模拟数据。");
  try {
    if (uploadedFile) {
      const result = await fetchC1Search();
      applyC1Result(result);
      showToast(`CampusVision C1 返回 ${records.length} 条关联记录。`);
    } else {
      resetToMockData();
    }
  } catch (error) {
    if (uploadedFile && await connectC1AfterFailure(error)) {
      try {
        const retryResult = await fetchC1Search();
        applyC1Result(retryResult);
        showToast(`CampusVision C1 返回 ${records.length} 条关联记录。`);
      } catch (retryError) {
        resetToMockData();
        showToast(`${retryError.message}，已回退本地模拟。`);
      }
    } else {
      resetToMockData();
      showToast(`${error.message}，已回退本地模拟。`);
    }
  } finally {
    elements.startSearchBtn.disabled = false;
    elements.startSearchBtn.innerHTML = '<svg class="ui-icon search-action-icon" aria-hidden="true"><use href="#icon-search"></use></svg>开始检索';
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
  elements.newSearchBtn?.addEventListener("click", resetSearchInput);
  elements.routeNewSearchBtn?.addEventListener("click", resetSearchInput);
  document.querySelector("#openRouteBtn").addEventListener("click", () => { switchScreen("route"); showToast("已打开人物路线图。"); });
  document.querySelector("#backToResultBtn").addEventListener("click", () => switchScreen("result"));
  document.querySelector("#showAllBtn").addEventListener("click", () => {
    elements.resultRecordList?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "start" });
    elements.resultRecordList?.querySelector(".record-card.is-active")?.focus();
    showToast(`已定位到 ${records.length} 条检索记录。`);
  });
  document.querySelector("#fullRouteBtn").addEventListener("click", () => {
    document.querySelector(".timeline-table")?.scrollIntoView({ behavior: "smooth", block: "start" });
    showToast(`已定位到 ${routePoints.length} 个轨迹点的时间线。`);
  });
  document.querySelector("#playBtn").addEventListener("click", () => showToast("关键帧时间线已定位到当前记录。"));
  document.querySelector("#exportFrameBtn").addEventListener("click", () => {
    const record = records[selectedRecordIndex];
    downloadText(`GKGuard-${record.title}.json`, JSON.stringify(record, null, 2));
    showToast("记录数据已导出。");
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
initDesktopUpdateEntry();
