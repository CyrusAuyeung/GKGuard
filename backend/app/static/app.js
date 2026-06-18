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
  routeOverviewPointCount: document.querySelector("#routeOverviewPointCount"),
  routeOverviewStart: document.querySelector("#routeOverviewStart"),
  routeOverviewEnd: document.querySelector("#routeOverviewEnd"),
  routeOverviewDuration: document.querySelector("#routeOverviewDuration"),
  routeCurrentRecord: document.querySelector("#routeCurrentRecord"),
  routeCurrentTime: document.querySelector("#routeCurrentTime"),
  routeCurrentLocation: document.querySelector("#routeCurrentLocation"),
  routeCurrentSimilarity: document.querySelector("#routeCurrentSimilarity"),
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
  toastTitle: document.querySelector("#toastTitle"),
  toastMessage: document.querySelector("#toastMessage"),
  toastIconUse: document.querySelector("#toastIconUse"),
  mediaViewer: document.querySelector("#mediaViewer"),
  mediaViewerClose: document.querySelector("#mediaViewerClose"),
  mediaViewerTitle: document.querySelector("#mediaViewerTitle"),
  mediaViewerSubtitle: document.querySelector("#mediaViewerSubtitle"),
  mediaViewerFrame: document.querySelector("#mediaViewerFrame"),
  mediaViewerTime: document.querySelector("#mediaViewerTime"),
  mediaViewerLocation: document.querySelector("#mediaViewerLocation"),
  mediaViewerCamera: document.querySelector("#mediaViewerCamera"),
  mediaViewerSimilarity: document.querySelector("#mediaViewerSimilarity"),
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
let queryFaces = [];
let selectedQueryFaceIndex = null;
let selectedQueryFaceImageUrl = "";
let queryFaceDetectionComplete = false;
let queryFaceDetectionPromise = null;
let searchInProgress = false;
let lastC1Notice = "";
let activeSource = "mock";
let toastTimer = null;
let lastFocusedElement = null;

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

  hideToast();

  const resetScroll = () => {
    window.scrollTo(0, 0);
    document.scrollingElement?.scrollTo(0, 0);
  };
  resetScroll();
  window.requestAnimationFrame(resetScroll);
  window.setTimeout(resetScroll, 80);
}

const feedbackConfig = {
  info: { title: "状态提示", icon: "#icon-info", timeout: 2600 },
  success: { title: "操作完成", icon: "#icon-info", timeout: 2600 },
  warning: { title: "需要注意", icon: "#icon-info", timeout: 3600 },
  error: { title: "操作失败", icon: "#icon-info", timeout: 4600 },
  loading: { title: "处理中", icon: "#icon-update", timeout: 0 },
};

function hideToast() {
  if (!elements.toast) return;
  window.clearTimeout(toastTimer);
  elements.toast.className = "toast toast-info";
  elements.toast.classList.remove("is-visible");
  elements.toast.hidden = true;
  elements.toast.setAttribute("role", "status");
  elements.toast.setAttribute("aria-live", "polite");
  if (elements.toastTitle) elements.toastTitle.textContent = "状态提示";
  if (elements.toastMessage) elements.toastMessage.textContent = "";
  if (elements.toastIconUse) elements.toastIconUse.setAttribute("href", "#icon-info");
}

function showToast(message, options = {}) {
  if (!elements.toast) return;
  const normalizedMessage = String(message ?? "").trim();
  if (!normalizedMessage) {
    hideToast();
    return;
  }
  const tone = feedbackConfig[options.tone] ? options.tone : "info";
  const config = feedbackConfig[tone];
  elements.toast.hidden = false;
  elements.toast.className = `toast toast-${tone}${tone === "loading" ? " is-loading" : ""}`;
  elements.toast.setAttribute("role", tone === "error" ? "alert" : "status");
  elements.toast.setAttribute("aria-live", tone === "error" ? "assertive" : "polite");
  if (elements.toastTitle) elements.toastTitle.textContent = options.title || config.title;
  if (elements.toastMessage) elements.toastMessage.textContent = normalizedMessage;
  if (elements.toastIconUse) elements.toastIconUse.setAttribute("href", options.icon || config.icon);
  elements.toast.classList.add("is-visible");
  window.clearTimeout(toastTimer);
  const timeout = Number.isFinite(options.timeout) ? options.timeout : config.timeout;
  if (timeout > 0) {
    toastTimer = window.setTimeout(hideToast, timeout);
  }
}

function setButtonBusy(button, busy, busyLabel, idleLabel) {
  if (!button) return;
  button.disabled = busy;
  button.dataset.state = busy ? "busy" : "idle";
  button.setAttribute("aria-busy", busy ? "true" : "false");
  button.innerHTML = `<svg class="ui-icon search-action-icon" aria-hidden="true"><use href="#icon-search"></use></svg>${busy ? busyLabel : idleLabel}`;
}

function targetPortraitMarkup() {
  const portraitUrl = selectedQueryFaceImageUrl || uploadedImageUrl || matchedPersonImageUrl;
  if (portraitUrl) return `<img src="${portraitUrl}" alt="目标人物照片" />`;
  return '<span class="portrait-art" aria-hidden="true"></span>';
}

function faceBoxMarkup(face, options = {}) {
  const box = face?.bbox;
  if (!box) return "";
  const selected = Number(face.index) === Number(selectedQueryFaceIndex);
  const classes = [
    "face-box",
    selected ? "is-selected" : "",
    options.compact ? "is-compact" : "",
  ].filter(Boolean).join(" ");
  const label = options.label || formatPercent(face.score ?? box.score);
  return `
    <span class="${classes}" role="button" tabindex="0" data-query-face-box data-query-face-index="${escapeHtml(face.index)}"
      data-x1="${escapeHtml(box.x1)}" data-y1="${escapeHtml(box.y1)}"
      data-width="${escapeHtml(box.width)}" data-height="${escapeHtml(box.height)}"
      style="left:${box.leftPct}%; top:${box.topPct}%; width:${box.widthPct}%; height:${box.heightPct}%"
      aria-label="选择第 ${Number(face.index) + 1} 张人脸，检测置信度 ${escapeHtml(label)}">
      <span>${escapeHtml(label)}</span>
    </span>
  `;
}

function uploadPortraitMarkup() {
  if (!uploadedImageUrl) return '<span class="portrait-art" aria-hidden="true"></span>';
  const boxes = queryFaces.map((face) => faceBoxMarkup(face)).join("");
  return `
    <img src="${uploadedImageUrl}" alt="上传的查询图片" />
    <span class="query-face-layer" aria-label="查询图人脸选择">${boxes}</span>
  `;
}

function recordThumbMarkup(record) {
  const thumbUrl = record.thumbnailUrl || record.faceUrl || record.frameUrl;
  if (thumbUrl) {
    return `<span class="mini-face has-thumb"><img src="${escapeHtml(thumbUrl)}" alt="${escapeHtml(record.title)} 缩略图" /></span>`;
  }
  return '<span class="mini-face" aria-hidden="true"></span>';
}

function frameFaceBoxMarkup(record) {
  const box = record?.faceBox;
  if (!box) return "";
  return `
    <span class="face-box result-face-box" data-frame-face-box
      data-x1="${escapeHtml(box.x1)}" data-y1="${escapeHtml(box.y1)}"
      data-width="${escapeHtml(box.width)}" data-height="${escapeHtml(box.height)}">
      <span>${escapeHtml(formatPercent(record.similarity))}</span>
    </span>
  `;
}

function frameImageMarkup(record, imageClass) {
  return `
    <span class="frame-image-wrap">
      <img class="${imageClass}" src="${escapeHtml(record.frameUrl)}" alt="${escapeHtml(record.title)} 监控关键帧" />
      <span class="frame-face-layer" aria-label="目标人脸位置">${frameFaceBoxMarkup(record)}</span>
    </span>
  `;
}

function positionFrameFaceBoxes(root = document) {
  root.querySelectorAll(".frame-image-wrap, .portrait-frame").forEach((wrap) => {
    const image = wrap.querySelector("img");
    if (!image) return;
    const update = () => {
      if (!image.naturalWidth || !image.naturalHeight) return;
      const imageStyle = window.getComputedStyle(image);
      const paddingLeft = Number.parseFloat(imageStyle.paddingLeft) || 0;
      const paddingRight = Number.parseFloat(imageStyle.paddingRight) || 0;
      const paddingTop = Number.parseFloat(imageStyle.paddingTop) || 0;
      const paddingBottom = Number.parseFloat(imageStyle.paddingBottom) || 0;
      const width = Math.max(0, (image.clientWidth || wrap.clientWidth) - paddingLeft - paddingRight);
      const height = Math.max(0, (image.clientHeight || wrap.clientHeight) - paddingTop - paddingBottom);
      if (!width || !height) return;
      const imageRatio = image.naturalWidth / image.naturalHeight;
      const boxRatio = width / height;
      const renderedWidth = boxRatio > imageRatio ? height * imageRatio : width;
      const renderedHeight = boxRatio > imageRatio ? height : width / imageRatio;
      const wrapRect = wrap.getBoundingClientRect();
      const imageRect = image.getBoundingClientRect();
      const offsetX = imageRect.left - wrapRect.left + paddingLeft + (width - renderedWidth) / 2;
      const offsetY = imageRect.top - wrapRect.top + paddingTop + (height - renderedHeight) / 2;

      wrap.querySelectorAll("[data-frame-face-box], [data-query-face-box]").forEach((box) => {
        const x1 = Number(box.dataset.x1);
        const y1 = Number(box.dataset.y1);
        const boxWidth = Number(box.dataset.width);
        const boxHeight = Number(box.dataset.height);
        if (![x1, y1, boxWidth, boxHeight].every(Number.isFinite)) return;
        const left = offsetX + (x1 / image.naturalWidth) * renderedWidth;
        const top = offsetY + (y1 / image.naturalHeight) * renderedHeight;
        box.style.left = `${left}px`;
        box.style.top = `${top}px`;
        box.style.width = `${(boxWidth / image.naturalWidth) * renderedWidth}px`;
        box.style.height = `${(boxHeight / image.naturalHeight) * renderedHeight}px`;
        box.classList.toggle("is-label-inside", top < 30);
      });
    };
    if (image.complete) update();
    image.addEventListener("load", update, { once: true });
    window.requestAnimationFrame(update);
  });
}

function emptyStateMarkup(title, detail) {
  return `
    <div class="empty-state" role="status">
      <strong>${escapeHtml(title)}</strong>
      <span>${escapeHtml(detail)}</span>
    </div>
  `;
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
  if (elements.uploadPreview) elements.uploadPreview.innerHTML = uploadPortraitMarkup();
  [elements.resultPortrait, elements.routePortrait].forEach((target) => {
    if (!target) return;
    target.innerHTML = targetPortraitMarkup();
  });
  window.requestAnimationFrame(() => positionFrameFaceBoxes());
}

function loadBrowserImage(src) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.addEventListener("load", () => resolve(image), { once: true });
    image.addEventListener("error", reject, { once: true });
    image.src = src;
  });
}

async function cropUploadedFace(face) {
  if (!uploadedImageUrl || !face?.bbox) return "";
  const image = await loadBrowserImage(uploadedImageUrl);
  const box = face.bbox;
  const padX = Math.max(8, Number(box.width || 0) * 0.18);
  const padY = Math.max(8, Number(box.height || 0) * 0.22);
  const x = Math.max(0, Number(box.x1 || 0) - padX);
  const y = Math.max(0, Number(box.y1 || 0) - padY);
  const width = Math.min(image.naturalWidth - x, Number(box.width || 0) + padX * 2);
  const height = Math.min(image.naturalHeight - y, Number(box.height || 0) + padY * 2);
  if (width <= 0 || height <= 0) return "";

  const canvas = document.createElement("canvas");
  canvas.width = Math.round(width);
  canvas.height = Math.round(height);
  const context = canvas.getContext("2d");
  context.drawImage(image, x, y, width, height, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.92);
}

function clearQueryFaces() {
  queryFaces = [];
  selectedQueryFaceIndex = null;
  selectedQueryFaceImageUrl = "";
  queryFaceDetectionComplete = false;
  queryFaceDetectionPromise = null;
}

async function selectQueryFace(index, options = {}) {
  const face = queryFaces.find((item) => Number(item.index) === Number(index));
  if (!face) return false;
  selectedQueryFaceIndex = Number(face.index);
  selectedQueryFaceImageUrl = await cropUploadedFace(face).catch(() => "");
  syncPortraits();
  if (!options.silent) {
    showToast(`已选择第 ${selectedQueryFaceIndex + 1} 张人脸作为检索目标。`, { tone: "success", title: "目标已确认" });
  }
  return true;
}

function setSearchIdleLabel(label = "开始检索") {
  if (!elements.startSearchBtn || elements.startSearchBtn.dataset.state === "busy") return;
  elements.startSearchBtn.innerHTML = `<svg class="ui-icon search-action-icon" aria-hidden="true"><use href="#icon-search"></use></svg>${label}`;
}

async function fetchQueryFaces() {
  if (!uploadedFile) throw new Error("请先上传目标人脸图片");
  const formData = new FormData();
  formData.append("file", uploadedFile, uploadedFile.name || "query.jpg");
  const response = await fetch("/c1/query-faces", {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail?.detail?.message || `C1 人脸检测返回 ${response.status}`);
  }
  return response.json();
}

async function prepareQueryFaces(options = {}) {
  if (!uploadedFile) return "no-upload";
  if (queryFaceDetectionPromise) return queryFaceDetectionPromise;

  queryFaceDetectionPromise = (async () => {
    try {
      if (!queryFaceDetectionComplete) {
        const result = await fetchQueryFaces();
        queryFaces = Array.isArray(result.queryFaces) ? result.queryFaces : [];
        queryFaceDetectionComplete = true;
      }

      if (!queryFaces.length) {
        selectedQueryFaceIndex = null;
        selectedQueryFaceImageUrl = "";
        syncPortraits();
        showToast("未检测到人脸，请上传清晰正脸照片。", { tone: "warning", title: "未检测到人脸", timeout: 4200 });
        setSearchIdleLabel("重新上传后检索");
        return "no-face";
      }

      if (queryFaces.length === 1) {
        await selectQueryFace(queryFaces[0].index, { silent: true });
        if (options.autoSearchSingle) {
          showToast("已自动选中唯一人脸，正在检索。", { tone: "loading", title: "单人目标已确认" });
          window.setTimeout(() => startSearch(), 120);
        } else {
          showToast("已自动选中唯一人脸。", { tone: "success", title: "目标已确认" });
        }
        setSearchIdleLabel("开始检索");
        return "ready";
      }

      syncPortraits();
      setSearchIdleLabel(selectedQueryFaceIndex === null ? "选择人脸后检索" : "确认选择并检索");
      if (selectedQueryFaceIndex === null) {
        showToast("检测到多张人脸，请在原图上选择检索目标。", { tone: "warning", title: "请选择目标人脸", timeout: 5200 });
        return "needs-selection";
      }
      return "ready";
    } finally {
      queryFaceDetectionPromise = null;
    }
  })();

  return queryFaceDetectionPromise;
}

function loadImage(file) {
  if (!file) return;
  if (!file.type.startsWith("image/")) {
    showToast("请选择 JPG 或 PNG 图片。", { tone: "warning", title: "图片格式不支持" });
    return;
  }
  const reader = new FileReader();
  reader.addEventListener("load", () => {
    uploadedFile = file;
    uploadedImageUrl = String(reader.result || "");
    matchedPersonImageUrl = "";
    clearQueryFaces();
    elements.uploadHint.textContent = `${file.name} 已就绪`;
    syncPortraits();
    showToast("目标照片已加载，正在检测人脸。", { tone: "loading", title: "图片已就绪" });
    prepareQueryFaces({ autoSearchSingle: true }).catch((error) => {
      showToast(`${error.message}。点击开始检索时将尝试连接 CampusVision C1。`, { tone: "warning", title: "人脸检测暂不可用", timeout: 5200 });
      setSearchIdleLabel("开始检索");
    });
  });
  reader.readAsDataURL(file);
}

function resetToMockData() {
  records.splice(0, records.length, ...mockRecords.map((record) => ({ ...record })));
  routePoints.splice(0, routePoints.length, ...mockRoutePoints.map((point) => ({ ...point })));
  activeSource = "mock";
  lastC1Notice = "";
}

function resetSearchInput() {
  uploadedFile = null;
  uploadedImageUrl = "";
  matchedPersonImageUrl = "";
  clearQueryFaces();
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
  showToast("已返回上传页，可选择新的目标照片。", { tone: "info", title: "已重置检索" });
}

function applyC1Result(result) {
  if (!result?.records?.length) {
    throw new Error(result?.warning || "C1 没有返回匹配记录");
  }
  lastC1Notice = result.warning || (result.ambiguous ? "候选人物分数接近，请人工确认。" : "");
  if (!lastC1Notice && result.person?.confidence === "low") {
    lastC1Notice = "当前为低置信匹配，请结合关键帧人工确认。";
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
  if (result.selectedQueryFace && selectedQueryFaceIndex === null) {
    selectedQueryFaceIndex = Number(result.selectedQueryFace.index);
  }

  activeSource = "c1";
}

async function fetchC1Search() {
  if (!uploadedFile) throw new Error("请先上传目标人脸图片");
  const formData = new FormData();
  formData.append("file", uploadedFile, uploadedFile.name || "query.jpg");
  const params = new URLSearchParams({ top_k: "5", max_gap_sec: "3" });
  if (selectedQueryFaceIndex !== null) params.set("query_face_index", String(selectedQueryFaceIndex));
  const response = await fetch(`/c1/search/person-by-image?${params.toString()}`, {
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

  showToast("CampusVision C1 暂不可用，请在软件内输入服务器密码。", { tone: "warning", title: "需要连接 CampusVision C1", timeout: 0 });
  const result = await desktopBridge.connectC1(error?.message || "CampusVision C1 服务当前不可用").catch(() => null);
  if (result?.connected) {
    showToast(result.prompted ? "CampusVision C1 已连接，正在重新检索。" : "CampusVision C1 已可用，正在重新检索。", { tone: "success", title: "连接已恢复" });
    return true;
  }
  showToast("仍未检测到 CampusVision C1，将使用本地模拟。请确认服务器密码和校园网连接。", { tone: "warning", title: "已切换本地模拟", timeout: 4600 });
  return false;
}

function renderRecordLists() {
  if (!records.length) {
    const html = emptyStateMarkup("暂无检索记录", "请重新上传图片或检查 CampusVision C1 服务状态。");
    elements.resultRecordList.innerHTML = html;
    elements.routeRecordList.innerHTML = html;
    if (elements.resultSourceBadge) elements.resultSourceBadge.textContent = sourceLabel();
    if (elements.resultCountBadge) elements.resultCountBadge.textContent = "0 条";
    return;
  }

  const html = records.map((record, index) => `
    <button class="record-card ${index === selectedRecordIndex ? "is-active" : ""}" type="button" data-index="${index}" aria-pressed="${index === selectedRecordIndex ? "true" : "false"}">
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
      renderRouteMap();
      renderRouteTimeline();
    });
  });
}

function setUpdateStatus(label, disabled = false, state = "idle") {
  if (!elements.checkUpdateBtn || !elements.updateStatus) return;
  elements.updateStatus.textContent = label;
  elements.checkUpdateBtn.disabled = disabled;
  elements.checkUpdateBtn.dataset.state = state;
  elements.checkUpdateBtn.setAttribute("aria-busy", state === "busy" ? "true" : "false");
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
      setUpdateStatus(`下载中 ${event.percent}%`, true, "busy");
    }
    if (event?.type === "update-downloaded") {
      updateStage = "downloaded";
      setUpdateStatus("重启安装", false, "success");
      showToast("新版已在应用内下载完成，点击即可重启安装。", { tone: "success", title: "更新已下载" });
    }
    if (event?.type === "error") {
      updateStage = "idle";
      setUpdateStatus("检查更新", false, "danger");
      showToast(`更新失败：${event.message}`, { tone: "error", title: "更新失败" });
    }
  });

  elements.checkUpdateBtn.addEventListener("click", async () => {
    if (updateStage === "downloaded") {
      setUpdateStatus("正在重启...", true, "busy");
      showToast("正在重启并安装新版。", { tone: "loading", title: "准备安装" });
      try {
        await desktopBridge.installUpdate?.();
      } catch (error) {
        setUpdateStatus("重启安装", false, "danger");
        showToast(`重启安装失败：${error.message}`, { tone: "error", title: "安装失败" });
      }
      return;
    }

    if (latestUpdate?.updateAvailable && updateStage === "available") {
      setUpdateStatus("开始下载...", true, "busy");
      try {
        const downloadResult = await desktopBridge.downloadUpdate();
        if (downloadResult?.embedded === false) {
          updateStage = "idle";
          setUpdateStatus("检查更新");
          elements.checkUpdateBtn.disabled = false;
          showToast("已打开 GitHub Release。正式安装版会在应用内更新。", { tone: "info", title: "已打开发布页" });
          return;
        }
        if (updateStage !== "downloaded") {
          updateStage = "downloading";
          setUpdateStatus("下载中...", true, "busy");
        }
        showToast("新版正在应用内下载。", { tone: "loading", title: "下载更新中" });
      } catch (error) {
        updateStage = "available";
        setUpdateStatus(latestUpdate?.latestVersion ? `应用内更新 ${latestUpdate.latestVersion}` : "重新下载", false, "danger");
        showToast(`下载更新失败：${error.message}`, { tone: "error", title: "下载失败" });
      }
      return;
    }

    setUpdateStatus("检查中...", true, "busy");
    showToast("正在检查 GitHub Release 最新版本。", { tone: "loading", title: "检查更新中" });
    try {
      latestUpdate = await desktopBridge.checkForUpdates();
      if (latestUpdate.updateAvailable) {
        updateStage = latestUpdate.downloaded ? "downloaded" : "available";
        setUpdateStatus(updateStage === "downloaded" ? "重启安装" : `应用内更新 ${latestUpdate.latestVersion}`, false, updateStage === "downloaded" ? "success" : "available");
        showToast(updateStage === "downloaded" ? "新版已下载完成，点击即可重启安装。" : `发现新版 ${latestUpdate.latestVersion}，再次点击将在应用内下载。`, { tone: "success", title: updateStage === "downloaded" ? "更新已下载" : "发现新版" });
      } else {
        updateStage = "idle";
        setUpdateStatus("已是最新版", true, "success");
        showToast(`当前已是最新版本 ${latestUpdate.currentVersion}。`, { tone: "success", title: "无需更新" });
        window.setTimeout(() => setUpdateStatus(`检查更新 v${latestUpdate.currentVersion}`), 2400);
      }
    } catch (error) {
      setUpdateStatus("检查更新", false, "danger");
      showToast(`检查更新失败：${error.message}`, { tone: "error", title: "检查更新失败" });
    } finally {
      if (updateStage !== "downloading" && (!latestUpdate || latestUpdate.updateAvailable)) {
        elements.checkUpdateBtn.disabled = false;
      }
    }
  });
}

function renderSelectedRecord() {
  const record = records[selectedRecordIndex];
  if (!record) {
    elements.recordTitle.textContent = "暂无记录";
    elements.recordScene.className = "camera-scene is-empty";
    elements.recordScene.innerHTML = '<span class="scene-time">--</span><div class="empty-state"><strong>暂无关键帧</strong><span>当前没有可展示的检索结果。</span></div>';
    elements.timeBubble.textContent = "--:--:--";
    elements.trackProgress.style.left = "0%";
    elements.timeBubble.style.left = "0%";
    elements.recordInfo.innerHTML = emptyStateMarkup("暂无相关信息", "请重新检索或检查 CampusVision C1 返回内容。");
    renderRouteCurrentSummary();
    return;
  }
  elements.recordTitle.textContent = record.title;
  elements.recordScene.className = `camera-scene ${record.frameUrl ? "has-frame" : record.sceneClass}`;
  elements.recordScene.querySelectorAll(".scene-frame, .frame-image-wrap").forEach((node) => node.remove());
  if (record.frameUrl) {
    elements.recordScene.insertAdjacentHTML("afterbegin", frameImageMarkup(record, "scene-frame"));
    positionFrameFaceBoxes(elements.recordScene);
  }
  elements.recordScene.querySelector(".scene-time").innerHTML = record.fullTime.replace(" ", "&nbsp;&nbsp;");
  elements.recordScene.setAttribute("tabindex", "0");
  elements.recordScene.setAttribute("role", "button");
  elements.recordScene.setAttribute("aria-label", `${record.title} 关键帧预览`);
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
  renderRouteCurrentSummary();
}

function renderRouteCurrentSummary() {
  const record = records[selectedRecordIndex] || records[0];
  if (!record) {
    if (elements.routeCurrentRecord) elements.routeCurrentRecord.textContent = "--";
    if (elements.routeCurrentTime) elements.routeCurrentTime.textContent = "--";
    if (elements.routeCurrentLocation) elements.routeCurrentLocation.textContent = "--";
    if (elements.routeCurrentSimilarity) elements.routeCurrentSimilarity.textContent = "--";
    return;
  }
  if (elements.routeCurrentRecord) {
    elements.routeCurrentRecord.textContent = `${record.title} · ${record.cameraId || record.camera || "--"}`;
  }
  if (elements.routeCurrentTime) elements.routeCurrentTime.textContent = record.time || "--";
  if (elements.routeCurrentLocation) elements.routeCurrentLocation.textContent = record.location || "--";
  if (elements.routeCurrentSimilarity) elements.routeCurrentSimilarity.textContent = formatPercent(record.similarity);
}

function selectRouteRecord(index, shouldAnnounce = true) {
  if (!records.length) return;
  selectedRecordIndex = Math.max(0, Math.min(Number(index) || 0, records.length - 1));
  renderRecordLists();
  renderSelectedRecord();
  renderRouteMap();
  renderRouteTimeline();
  if (shouldAnnounce) {
    const record = records[selectedRecordIndex];
    showToast(`已定位到 ${record.title}：${record.location}`, { tone: "info", title: "已定位轨迹点" });
  }
}

function bindRoutePointInteractions() {
  document.querySelectorAll("[data-route-index]").forEach((button) => {
    button.addEventListener("click", () => selectRouteRecord(button.dataset.routeIndex));
  });
}

function renderRouteMap() {
  if (!routePoints.length) {
    elements.campusRouteMap.innerHTML = emptyStateMarkup("暂无路线", "当前检索结果没有可用轨迹点。");
    return;
  }
  const linePoints = routePoints.map((point) => `${point.x},${point.y}`).join(" ");
  const mapLabelClass = (point) => [
    "map-label",
    point.x >= 74 ? "is-near-right" : "",
    point.x <= 18 ? "is-near-left" : "",
    point.y >= 76 ? "is-near-bottom" : "",
    point.y <= 16 ? "is-near-top" : "",
  ].filter(Boolean).join(" ");
  elements.campusRouteMap.innerHTML = `
    ${buildings.map((building) => `<span class="map-building" style="left:${building.x}%;top:${building.y}%;width:${building.w}%;height:${building.h}%">${escapeHtml(building.name)}</span>`).join("")}
    <svg class="route-line" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <polyline points="${linePoints}" fill="none" stroke="rgba(36,111,245,.16)" stroke-width="5.8" stroke-linecap="round" stroke-linejoin="round"></polyline>
      <polyline points="${linePoints}" fill="none" stroke="#246ff5" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"></polyline>
    </svg>
    ${routePoints.map((point, index) => `
      <button class="map-point ${point.kind || ""} ${index === selectedRecordIndex ? "is-active" : ""}" type="button" data-route-index="${index}" style="left:${point.x}%;top:${point.y}%" aria-label="定位到${escapeHtml(point.location)}">${point.kind === "start" ? "起" : point.kind === "end" ? "终" : point.id}</button>
      <span class="${mapLabelClass(point)}" style="left:${point.x}%;top:${point.y}%">${escapeHtml(point.location)}</span>
    `).join("")}
    <div class="map-legend">
      <span><i class="start-dot">起</i>起点</span>
      <span><i class="end-dot">终</i>终点</span>
      <span><i>1</i>轨迹点</span>
      <span><i class="camera-dot"></i>摄像头</span>
    </div>
  `;
  bindRoutePointInteractions();
}

function renderRouteTimeline() {
  elements.routeTimelineRows.innerHTML = routePoints.length ? routePoints.map((point, index) => `
    <button class="timeline-row ${index === selectedRecordIndex ? "is-active" : ""}" type="button" data-route-index="${index}">
      <b>${point.id}</b>
      <span>${escapeHtml(point.time)}</span>
      <strong>${escapeHtml(point.location)}</strong>
    </button>
  `).join("") : emptyStateMarkup("暂无时间线", "当前检索结果没有可用轨迹点。");
  bindRoutePointInteractions();

  const startPoint = routePoints[0];
  const endPoint = routePoints[routePoints.length - 1];
  const cameras = new Set(records.map((record) => record.cameraId || record.camera).filter(Boolean));
  const sortedSeconds = routePoints.map((point) => parseTimeSeconds(point.time)).filter((value) => value !== null).sort((left, right) => left - right);
  const duration = sortedSeconds.length > 1 ? sortedSeconds[sortedSeconds.length - 1] - sortedSeconds[0] : null;
  const durationLabel = formatDuration(duration);
  elements.routePointCount.textContent = String(routePoints.length);
  elements.routeStart.textContent = startPoint?.location || "--";
  elements.routeEnd.textContent = endPoint?.location || "--";
  elements.routeOverviewPointCount.textContent = String(routePoints.length);
  elements.routeOverviewStart.textContent = startPoint?.location || "--";
  elements.routeOverviewEnd.textContent = endPoint?.location || "--";
  elements.routeOverviewDuration.textContent = durationLabel;
  elements.summaryDuration.textContent = durationLabel;
  elements.summaryCameraCount.textContent = `${Math.max(cameras.size, 1)}路`;
  elements.summaryFrameCount.textContent = String(records.length);
  elements.summaryFinalSimilarity.textContent = formatPercent(records[0]?.similarity);
}

function openMediaViewer(record = records[selectedRecordIndex]) {
  if (!record || !elements.mediaViewer) return;
  lastFocusedElement = document.activeElement;
  elements.mediaViewerTitle.textContent = `${record.title} 关键帧`;
  elements.mediaViewerSubtitle.textContent = sourceLabel();
  elements.mediaViewerTime.textContent = record.fullTime || record.time || "--";
  elements.mediaViewerLocation.textContent = record.location || "--";
  elements.mediaViewerCamera.textContent = record.camera || record.cameraId || "--";
  elements.mediaViewerSimilarity.textContent = formatPercent(record.similarity);
  if (record.frameUrl) {
    elements.mediaViewerFrame.innerHTML = frameImageMarkup(record, "media-frame-image");
  } else {
    elements.mediaViewerFrame.innerHTML = `
      <div class="camera-scene media-viewer-mock ${escapeHtml(record.sceneClass || "scene-1")}">
        <span class="scene-time">${escapeHtml(record.fullTime || record.time || "--")}</span>
        <span class="building-door"></span>
        <span class="scene-tree tree-left"></span>
        <span class="scene-tree tree-right"></span>
        <span class="walking-person"></span>
        <span class="camera-sign">C2<br />模拟</span>
      </div>
    `;
  }
  elements.mediaViewer.hidden = false;
  elements.mediaViewer.classList.add("is-visible");
  positionFrameFaceBoxes(elements.mediaViewerFrame);
  elements.mediaViewerClose?.focus();
}

function closeMediaViewer() {
  if (!elements.mediaViewer) return;
  elements.mediaViewer.classList.remove("is-visible");
  elements.mediaViewer.hidden = true;
  elements.mediaViewerFrame.innerHTML = "";
  lastFocusedElement?.focus?.();
}

async function startSearch() {
  if (searchInProgress) return;
  searchInProgress = true;
  setButtonBusy(elements.startSearchBtn, true, "检索中...", "开始检索");
  showToast(uploadedFile ? "正在调用 CampusVision C1 检索服务。" : "未上传图片，使用本地模拟数据。", { tone: "loading", title: uploadedFile ? "检索中" : "准备本地模拟" });
  let resultToast = null;
  let shouldShowResults = false;

  async function runC1SearchFlow() {
    const faceState = await prepareQueryFaces({ autoSearchSingle: false });
    if (faceState === "needs-selection" || faceState === "no-face") return faceState;
    const result = await fetchC1Search();
    applyC1Result(result);
    return "searched";
  }

  try {
    if (uploadedFile) {
      const flowState = await runC1SearchFlow();
      if (flowState !== "searched") return;
      shouldShowResults = true;
      resultToast = lastC1Notice
        ? { message: `${lastC1Notice} 已返回 ${records.length} 条候选记录。`, options: { tone: "warning", title: "需要人工确认", timeout: 5600 } }
        : { message: `CampusVision C1 返回 ${records.length} 条关联记录。目标人脸已确认。`, options: { tone: "success", title: "检索完成" } };
    } else {
      resetToMockData();
      shouldShowResults = true;
      resultToast = { message: `已加载 ${records.length} 条本地模拟记录。`, options: { tone: "info", title: "本地模拟已就绪" } };
    }
  } catch (error) {
    if (uploadedFile && await connectC1AfterFailure(error)) {
      try {
        queryFaceDetectionComplete = false;
        const retryState = await runC1SearchFlow();
        if (retryState !== "searched") return;
        shouldShowResults = true;
        resultToast = lastC1Notice
          ? { message: `${lastC1Notice} 已返回 ${records.length} 条候选记录。`, options: { tone: "warning", title: "需要人工确认", timeout: 5600 } }
          : { message: `CampusVision C1 返回 ${records.length} 条关联记录。`, options: { tone: "success", title: "重试检索完成" } };
      } catch (retryError) {
        resetToMockData();
        shouldShowResults = true;
        resultToast = { message: `${retryError.message}，已回退本地模拟。`, options: { tone: "warning", title: "已使用本地模拟", timeout: 4600 } };
      }
    } else {
      resetToMockData();
      shouldShowResults = true;
      resultToast = { message: `${error.message}，已回退本地模拟。`, options: { tone: "warning", title: "已使用本地模拟", timeout: 4600 } };
    }
  } finally {
    setButtonBusy(elements.startSearchBtn, false, "检索中...", "开始检索");
    searchInProgress = false;
    if (queryFaces.length > 1 && selectedQueryFaceIndex === null) {
      setSearchIdleLabel("选择人脸后检索");
    }
    if (queryFaces.length > 1 && selectedQueryFaceIndex !== null) {
      setSearchIdleLabel("确认选择并检索");
    }
    if (shouldShowResults) {
      selectedRecordIndex = 0;
      renderRecordLists();
      renderSelectedRecord();
      renderRouteMap();
      renderRouteTimeline();
      switchScreen("result");
    }
    if (resultToast) {
      showToast(resultToast.message, resultToast.options);
    }
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
  elements.uploadDrop.addEventListener("click", async (event) => {
    const faceTarget = event.target.closest("[data-query-face-index]");
    if (faceTarget) {
      event.preventDefault();
      await selectQueryFace(faceTarget.dataset.queryFaceIndex);
      setSearchIdleLabel("确认选择并检索");
      return;
    }
    elements.faceFile.click();
  });
  elements.uploadDrop.addEventListener("keydown", async (event) => {
    const faceTarget = event.target.closest("[data-query-face-index]");
    if (faceTarget && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      await selectQueryFace(faceTarget.dataset.queryFaceIndex);
      setSearchIdleLabel("确认选择并检索");
      return;
    }
    if ((event.key === "Enter" || event.key === " ") && event.target === elements.uploadDrop) {
      event.preventDefault();
      elements.faceFile.click();
    }
  });
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
  document.querySelector("#openRouteBtn").addEventListener("click", () => { switchScreen("route"); showToast("已打开人物路线图。", { tone: "info", title: "已切换视图" }); });
  document.querySelector("#backToResultBtn").addEventListener("click", () => switchScreen("result"));
  document.querySelector("#showAllBtn").addEventListener("click", () => {
    elements.resultRecordList?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "start" });
    elements.resultRecordList?.querySelector(".record-card.is-active")?.focus();
    showToast(`已定位到 ${records.length} 条检索记录。`, { tone: "info", title: "已定位记录列表" });
  });
  document.querySelector("#fullRouteBtn").addEventListener("click", () => {
    document.querySelector(".timeline-table")?.scrollIntoView({ behavior: "smooth", block: "start" });
    showToast(`已定位到 ${routePoints.length} 个轨迹点的时间线。`, { tone: "info", title: "已定位时间线" });
  });
  document.querySelector("#playBtn").addEventListener("click", () => showToast("关键帧时间线已定位到当前记录。", { tone: "info", title: "时间线已定位" }));
  elements.recordScene.addEventListener("click", () => openMediaViewer());
  elements.recordScene.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openMediaViewer();
    }
  });
  elements.mediaViewerClose?.addEventListener("click", closeMediaViewer);
  elements.mediaViewer?.addEventListener("click", (event) => {
    if (event.target === elements.mediaViewer) closeMediaViewer();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && elements.mediaViewer?.classList.contains("is-visible")) {
      closeMediaViewer();
    }
  });
  window.addEventListener("resize", () => positionFrameFaceBoxes());
  document.querySelector("#exportFrameBtn").addEventListener("click", () => {
    const record = records[selectedRecordIndex];
    downloadText(`GKGuard-${record.title}.json`, JSON.stringify(record, null, 2));
    showToast("记录数据已导出。", { tone: "success", title: "导出完成" });
  });
  document.querySelector("#exportRouteBtn").addEventListener("click", () => {
    downloadText("GKGuard-route.json", JSON.stringify({ routePoints, records }, null, 2));
    showToast("路线图数据已导出。", { tone: "success", title: "导出完成" });
  });
}

syncPortraits();
renderRecordLists();
renderSelectedRecord();
renderRouteMap();
renderRouteTimeline();
bindEvents();
initDesktopUpdateEntry();
hideToast();
