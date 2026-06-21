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
  openQueryFaceModalBtn: document.querySelector("#openQueryFaceModalBtn"),
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
  queryFaceModal: document.querySelector("#queryFaceModal"),
  queryFaceModalClose: document.querySelector("#queryFaceModalClose"),
  queryFaceModalFrame: document.querySelector("#queryFaceModalFrame"),
  queryFaceModalStatus: document.querySelector("#queryFaceModalStatus"),
  queryFaceModalConfirm: document.querySelector("#queryFaceModalConfirm"),
  queryFaceModalCancel: document.querySelector("#queryFaceModalCancel"),
  queryFaceZoomIn: document.querySelector("#queryFaceZoomIn"),
  queryFaceZoomOut: document.querySelector("#queryFaceZoomOut"),
  queryFaceZoomReset: document.querySelector("#queryFaceZoomReset"),
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
let activeSearchController = null;
let searchRunId = 0;
let pendingAutoSearchTimer = null;
let queryFaceModalZoom = 1;
let queryFaceModalBaseScale = 1;
let lastC1Notice = "";
let activeSource = "mock";
let toastTimer = null;
let lastFocusedElement = null;
const CONFIDENT_QUERY_FACE_SCORE = 0.65;
const MIN_VISIBLE_QUERY_FACE_SCORE = 0.45;
const FACE_HIT_PADDING_PX = 8;
const QUERY_FACE_MODAL_MIN_ZOOM = 0.5;
const QUERY_FACE_MODAL_MAX_ZOOM = 3;
const TARGET_PORTRAIT_CROP_PADDING_X = 0.45;
const TARGET_PORTRAIT_CROP_PADDING_TOP = 0.65;
const TARGET_PORTRAIT_CROP_PADDING_BOTTOM = 0.45;
const C1_QUERY_FACE_TIMEOUT_MS = 15000;
const C1_SEARCH_TIMEOUT_MS = 25000;
const SEARCH_WATCHDOG_TIMEOUT_MS = 30000;

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

function finiteNumber(value) {
  if (value === "" || value === null || value === undefined) return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function faceDetectionScore(face) {
  return finiteNumber(face?.score ?? face?.bbox?.score);
}

function visibleQueryFaces() {
  if (!queryFaces.length) return [];
  return queryFaces.filter((face) => {
    const score = faceDetectionScore(face);
    return score === null || score >= MIN_VISIBLE_QUERY_FACE_SCORE;
  });
}

function selectableQueryFaces() {
  return visibleQueryFaces();
}

function queryFaceConfidenceClass(face) {
  const score = faceDetectionScore(face);
  if (score !== null && score < CONFIDENT_QUERY_FACE_SCORE) return "is-low-confidence";
  return "";
}

function queryFaceConfidenceLabel(face) {
  const score = faceDetectionScore(face);
  if (score === null) return "检测置信度 --";
  return score < CONFIDENT_QUERY_FACE_SCORE ? `低置信 ${formatPercent(score)}` : `检测 ${formatPercent(score)}`;
}

function localizedC1Notice(message) {
  const text = String(message || "").trim();
  if (!text) return "";
  if (/No person matched the requested minimum score/i.test(text)) {
    return "未找到达到相似度阈值的人员。请更换目标人脸、检查人物库或确认 CampusVision C1 数据。";
  }
  if (/No face\/target embedding extracted/i.test(text)) {
    return "未能从查询图片中提取可检索的人脸特征。请上传更清晰的正脸照片。";
  }
  if (/Selected query face was not found/i.test(text)) {
    return "选中的查询人脸已失效，请重新选择目标人脸后检索。";
  }
  if (/Low-confidence person match/i.test(text)) {
    return "当前为低置信匹配，请结合关键帧人工确认。";
  }
  return text;
}

async function fetchWithTimeout(url, options = {}, timeoutMs = C1_SEARCH_TIMEOUT_MS) {
  const { signal, ...fetchOptions } = options;
  const controller = new AbortController();
  const abortFromOuterSignal = () => controller.abort(signal?.reason);
  if (signal?.aborted) controller.abort(signal.reason);
  signal?.addEventListener("abort", abortFromOuterSignal, { once: true });
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...fetchOptions, signal: controller.signal });
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error("CampusVision C1 响应超时，请检查服务状态或稍后重试");
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
    signal?.removeEventListener("abort", abortFromOuterSignal);
  }
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
  const portraitUrl = selectedQueryFaceImageUrl || matchedPersonImageUrl || uploadedImageUrl;
  if (portraitUrl) return `<img src="${portraitUrl}" alt="目标人物照片" />`;
  return '<span class="portrait-art" aria-hidden="true"></span>';
}

function initialFaceBoxStyle(box) {
  const leftPct = finiteNumber(box?.leftPct);
  const topPct = finiteNumber(box?.topPct);
  const widthPct = finiteNumber(box?.widthPct);
  const heightPct = finiteNumber(box?.heightPct);
  if ([leftPct, topPct, widthPct, heightPct].every((value) => value !== null)) {
    return `left:${leftPct}%; top:${topPct}%; width:${widthPct}%; height:${heightPct}%`;
  }
  const x1 = finiteNumber(box?.x1);
  const y1 = finiteNumber(box?.y1);
  const width = finiteNumber(box?.width);
  const height = finiteNumber(box?.height);
  if ([x1, y1, width, height].every((value) => value !== null && value >= 0 && value <= 1)) {
    return `left:${x1 * 100}%; top:${y1 * 100}%; width:${width * 100}%; height:${height * 100}%`;
  }
  return "";
}

function faceBoxMarkup(face, options = {}) {
  const box = face?.bbox;
  if (!box) return "";
  const selected = Number(face.index) === Number(selectedQueryFaceIndex);
  const classes = [
    "face-box",
    "is-pending",
    selected ? "is-selected" : "",
    queryFaceConfidenceClass(face),
    options.compact ? "is-compact" : "",
    options.modal ? "is-modal-face" : "",
  ].filter(Boolean).join(" ");
  const label = options.label || formatPercent(face.score ?? box.score);
  const ariaLabel = queryFaceConfidenceLabel(face);
  const style = initialFaceBoxStyle(box);
  return `
    <span class="${classes}" role="button" tabindex="0" data-query-face-box data-query-face-index="${escapeHtml(face.index)}"
      data-x1="${escapeHtml(box.x1)}" data-y1="${escapeHtml(box.y1)}"
      data-width="${escapeHtml(box.width)}" data-height="${escapeHtml(box.height)}"
      data-image-width="${escapeHtml(face.imageWidth ?? "")}" data-image-height="${escapeHtml(face.imageHeight ?? "")}"
      data-left-pct="${escapeHtml(box.leftPct ?? "")}" data-top-pct="${escapeHtml(box.topPct ?? "")}"
      data-width-pct="${escapeHtml(box.widthPct ?? "")}" data-height-pct="${escapeHtml(box.heightPct ?? "")}"
      ${style ? `style="${style}"` : ""}
      aria-label="选择第 ${Number(face.index) + 1} 张人脸，${escapeHtml(ariaLabel)}">
      <span>${escapeHtml(label)}</span>
    </span>
  `;
}

function uploadPortraitMarkup() {
  if (!uploadedImageUrl) return '<span class="portrait-art" aria-hidden="true"></span>';
  const boxes = selectableQueryFaces().map((face) => faceBoxMarkup(face)).join("");
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
  const style = initialFaceBoxStyle(box);
  return `
    <span class="face-box result-face-box is-pending" data-frame-face-box
      data-x1="${escapeHtml(box.x1)}" data-y1="${escapeHtml(box.y1)}"
      data-width="${escapeHtml(box.width)}" data-height="${escapeHtml(box.height)}"
      data-left-pct="${escapeHtml(box.leftPct ?? "")}" data-top-pct="${escapeHtml(box.topPct ?? "")}"
      data-width-pct="${escapeHtml(box.widthPct ?? "")}" data-height-pct="${escapeHtml(box.heightPct ?? "")}"
      ${style ? `style="${style}"` : ""}>
      <span class="face-score-label">${escapeHtml(formatPercent(record.similarity))}</span>
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

function imageContentRect(wrap, image) {
  if (!image.naturalWidth || !image.naturalHeight) return null;
  const imageStyle = window.getComputedStyle(image);
  const paddingLeft = Number.parseFloat(imageStyle.paddingLeft) || 0;
  const paddingRight = Number.parseFloat(imageStyle.paddingRight) || 0;
  const paddingTop = Number.parseFloat(imageStyle.paddingTop) || 0;
  const paddingBottom = Number.parseFloat(imageStyle.paddingBottom) || 0;
  const wrapRect = wrap.getBoundingClientRect();
  const imageRect = image.getBoundingClientRect();
  const contentWidth = Math.max(0, imageRect.width - paddingLeft - paddingRight);
  const contentHeight = Math.max(0, imageRect.height - paddingTop - paddingBottom);
  if (!contentWidth || !contentHeight) return null;

  const scale = imageStyle.objectFit === "cover"
    ? Math.max(contentWidth / image.naturalWidth, contentHeight / image.naturalHeight)
    : Math.min(contentWidth / image.naturalWidth, contentHeight / image.naturalHeight);
  const renderedWidth = image.naturalWidth * scale;
  const renderedHeight = image.naturalHeight * scale;
  return {
    left: imageRect.left - wrapRect.left + paddingLeft + (contentWidth - renderedWidth) / 2,
    top: imageRect.top - wrapRect.top + paddingTop + (contentHeight - renderedHeight) / 2,
    width: renderedWidth,
    height: renderedHeight,
    naturalWidth: image.naturalWidth,
    naturalHeight: image.naturalHeight,
  };
}

function faceBoxRect(box, content) {
  const x1 = finiteNumber(box.dataset.x1);
  const y1 = finiteNumber(box.dataset.y1);
  const boxWidth = finiteNumber(box.dataset.width);
  const boxHeight = finiteNumber(box.dataset.height);
  const sourceWidth = finiteNumber(box.dataset.imageWidth) || content.naturalWidth;
  const sourceHeight = finiteNumber(box.dataset.imageHeight) || content.naturalHeight;
  const leftPct = finiteNumber(box.dataset.leftPct);
  const topPct = finiteNumber(box.dataset.topPct);
  const widthPct = finiteNumber(box.dataset.widthPct);
  const heightPct = finiteNumber(box.dataset.heightPct);
  const hasPctBox = [leftPct, topPct, widthPct, heightPct].every((value) => value !== null);
  const hasPixelBox = [x1, y1, boxWidth, boxHeight].every((value) => value !== null);
  const hasNormalizedBox = hasPixelBox && [x1, y1, boxWidth, boxHeight].every((value) => value >= 0 && value <= 1);
  if (!hasPctBox && !hasPixelBox) return null;

  const left = hasPctBox
    ? content.left + (leftPct / 100) * content.width
    : content.left + (hasNormalizedBox ? x1 : x1 / sourceWidth) * content.width;
  const top = hasPctBox
    ? content.top + (topPct / 100) * content.height
    : content.top + (hasNormalizedBox ? y1 : y1 / sourceHeight) * content.height;
  const width = hasPctBox
    ? (widthPct / 100) * content.width
    : (hasNormalizedBox ? boxWidth : boxWidth / sourceWidth) * content.width;
  const height = hasPctBox
    ? (heightPct / 100) * content.height
    : (hasNormalizedBox ? boxHeight : boxHeight / sourceHeight) * content.height;
  if (![left, top, width, height].every(Number.isFinite) || width <= 0 || height <= 0) {
    return null;
  }
  return { left, top, width, height };
}

function positionFrameFaceBoxes(root = document) {
  root.querySelectorAll(".frame-image-wrap, .portrait-frame, .face-select-image-wrap").forEach((wrap) => {
    const image = wrap.querySelector("img");
    if (!image) return;
    const update = () => {
      const content = imageContentRect(wrap, image);
      if (!content) return;

      wrap.querySelectorAll("[data-frame-face-box], [data-query-face-box]").forEach((box) => {
        const rect = faceBoxRect(box, content);
        if (!rect) {
          box.classList.add("is-pending");
          return;
        }
        box.style.left = `${rect.left}px`;
        box.style.top = `${rect.top}px`;
        box.style.width = `${rect.width}px`;
        box.style.height = `${rect.height}px`;
        const isResultBox = box.classList.contains("result-face-box");
        box.classList.toggle("is-label-inside", !isResultBox && rect.top < 30);
        box.classList.toggle("is-label-below", isResultBox && rect.top < 32);
        box.classList.remove("is-pending");
        box.classList.add("is-positioned");
      });
    };
    if (image.complete) update();
    image.addEventListener("load", update, { once: true });
    if (image.decode) image.decode().then(update).catch(() => {});
    window.requestAnimationFrame(update);
    window.requestAnimationFrame(() => window.requestAnimationFrame(update));
    window.setTimeout(update, 80);
    window.setTimeout(update, 280);
    if (window.ResizeObserver && !wrap.dataset.faceBoxObserverBound) {
      wrap.dataset.faceBoxObserverBound = "1";
      const observer = new ResizeObserver(update);
      observer.observe(wrap);
      observer.observe(image);
    }
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

function syncUploadPreviewAction() {
  if (!elements.openQueryFaceModalBtn) return;
  const canOpenModal = Boolean(uploadedImageUrl && visibleQueryFaces().length > 1);
  elements.openQueryFaceModalBtn.hidden = !canOpenModal;
  elements.openQueryFaceModalBtn.textContent = selectedQueryFaceIndex === null ? "放大选择目标人脸" : "重新放大选择";
  elements.openQueryFaceModalBtn.setAttribute(
    "aria-label",
    selectedQueryFaceIndex === null ? "打开大图选择目标人脸" : "重新打开大图选择目标人脸",
  );
}

function syncPortraits() {
  if (elements.uploadPreview) elements.uploadPreview.innerHTML = uploadPortraitMarkup();
  syncUploadPreviewAction();
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

async function cropUploadedFace(face, sourceBox = null) {
  if (!uploadedImageUrl || !face?.bbox) return "";
  const image = await loadBrowserImage(uploadedImageUrl);
  const cropRect = selectedQueryFaceCropRect(face, image, sourceBox);
  if (!cropRect) return "";

  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(cropRect.width));
  canvas.height = Math.max(1, Math.round(cropRect.height));
  const context = canvas.getContext("2d");
  context.drawImage(image, cropRect.x, cropRect.y, cropRect.width, cropRect.height, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.92);
}

function selectedQueryFaceCropRect(face, image, sourceBox = null) {
  const baseRect = cropRectFromSelectedFaceElement(image, sourceBox) || cropRectFromFacePayload(face, image);
  return expandQueryFacePortraitCropRect(baseRect, image);
}

function cropRectFromSelectedFaceElement(image, sourceBox = null) {
  const selectedBox = sourceBox || document.querySelector("[data-query-face-index].is-selected");
  const wrap = selectedBox?.closest(".face-select-image-wrap, .portrait-frame");
  const renderedImage = wrap?.querySelector("img");
  if (!selectedBox || !wrap || !renderedImage) return null;

  const content = imageContentRect(wrap, renderedImage);
  if (!content) return null;

  const wrapRect = wrap.getBoundingClientRect();
  const boxRect = selectedBox.getBoundingClientRect();
  const contentLeft = wrapRect.left + content.left;
  const contentTop = wrapRect.top + content.top;
  const rawX = ((boxRect.left - contentLeft) / content.width) * image.naturalWidth;
  const rawY = ((boxRect.top - contentTop) / content.height) * image.naturalHeight;
  const rawWidth = (boxRect.width / content.width) * image.naturalWidth;
  const rawHeight = (boxRect.height / content.height) * image.naturalHeight;
  return clampCropRect(rawX, rawY, rawWidth, rawHeight, image);
}

function cropRectFromFacePayload(face, image) {
  const box = face.bbox;
  const leftPct = Number(box.leftPct);
  const topPct = Number(box.topPct);
  const widthPct = Number(box.widthPct);
  const heightPct = Number(box.heightPct);
  const hasPctBox = [leftPct, topPct, widthPct, heightPct].every(Number.isFinite);
  const sourceWidth = finiteNumber(face.imageWidth) || image.naturalWidth;
  const sourceHeight = finiteNumber(face.imageHeight) || image.naturalHeight;
  const x1 = finiteNumber(box.x1) ?? 0;
  const y1 = finiteNumber(box.y1) ?? 0;
  const x2 = finiteNumber(box.x2);
  const y2 = finiteNumber(box.y2);
  const boxWidth = finiteNumber(box.width);
  const boxHeight = finiteNumber(box.height);
  const hasNormalizedBox = !hasPctBox && [x1, y1, boxWidth, boxHeight].every((value) => value !== null && value >= 0 && value <= 1);
  const hasNormalizedCorners = !hasPctBox && x2 !== null && y2 !== null && [x1, y1, x2, y2].every((value) => value >= 0 && value <= 1);
  const rawX = hasPctBox
    ? (leftPct / 100) * image.naturalWidth
    : hasNormalizedBox || hasNormalizedCorners
      ? x1 * image.naturalWidth
      : (x1 / sourceWidth) * image.naturalWidth;
  const rawY = hasPctBox
    ? (topPct / 100) * image.naturalHeight
    : hasNormalizedBox || hasNormalizedCorners
      ? y1 * image.naturalHeight
      : (y1 / sourceHeight) * image.naturalHeight;
  const rawWidth = hasPctBox
    ? (widthPct / 100) * image.naturalWidth
    : hasNormalizedBox
      ? boxWidth * image.naturalWidth
      : hasNormalizedCorners
        ? Math.max(0, (x2 - x1) * image.naturalWidth)
        : ((boxWidth ?? Math.max(0, (x2 ?? x1) - x1)) / sourceWidth) * image.naturalWidth;
  const rawHeight = hasPctBox
    ? (heightPct / 100) * image.naturalHeight
    : hasNormalizedBox
      ? boxHeight * image.naturalHeight
      : hasNormalizedCorners
        ? Math.max(0, (y2 - y1) * image.naturalHeight)
        : ((boxHeight ?? Math.max(0, (y2 ?? y1) - y1)) / sourceHeight) * image.naturalHeight;
  return clampCropRect(rawX, rawY, rawWidth, rawHeight, image);
}

function expandQueryFacePortraitCropRect(rect, image) {
  if (!rect) return null;
  const paddedX = rect.x - rect.width * TARGET_PORTRAIT_CROP_PADDING_X;
  const paddedY = rect.y - rect.height * TARGET_PORTRAIT_CROP_PADDING_TOP;
  const paddedWidth = rect.width * (1 + TARGET_PORTRAIT_CROP_PADDING_X * 2);
  const paddedHeight = rect.height * (1 + TARGET_PORTRAIT_CROP_PADDING_TOP + TARGET_PORTRAIT_CROP_PADDING_BOTTOM);
  const squareSide = Math.max(paddedWidth, paddedHeight);
  if (squareSide <= image.naturalWidth && squareSide <= image.naturalHeight) {
    const centerX = paddedX + paddedWidth / 2;
    const centerY = paddedY + paddedHeight / 2;
    return clampCropRect(centerX - squareSide / 2, centerY - squareSide / 2, squareSide, squareSide, image);
  }
  return clampCropRect(paddedX, paddedY, paddedWidth, paddedHeight, image);
}

function clampCropRect(rawX, rawY, rawWidth, rawHeight, image) {
  if (![rawX, rawY, rawWidth, rawHeight].every(Number.isFinite) || rawWidth <= 0 || rawHeight <= 0) return null;
  const width = Math.min(image.naturalWidth, rawWidth);
  const height = Math.min(image.naturalHeight, rawHeight);
  const x = Math.min(Math.max(0, rawX), Math.max(0, image.naturalWidth - width));
  const y = Math.min(Math.max(0, rawY), Math.max(0, image.naturalHeight - height));
  if (width <= 0 || height <= 0) return null;
  return { x, y, width, height };
}

function clearQueryFaces() {
  queryFaces = [];
  selectedQueryFaceIndex = null;
  selectedQueryFaceImageUrl = "";
  queryFaceDetectionComplete = false;
  queryFaceDetectionPromise = null;
  closeQueryFaceModal();
}

async function selectQueryFace(index, options = {}) {
  const face = queryFaces.find((item) => Number(item.index) === Number(index));
  if (!face) return false;
  selectedQueryFaceIndex = Number(face.index);
  updateQueryFaceSelectionState();
  selectedQueryFaceImageUrl = await cropUploadedFace(face, options.sourceBox).catch(() => "");
  syncPortraits();
  updateQueryFaceSelectionState();
  if (!options.silent) {
    showToast(`已选择第 ${selectedQueryFaceIndex + 1} 张人脸作为检索目标。`, { tone: "success", title: "目标已确认" });
  }
  return true;
}

function updateQueryFaceSelectionState() {
  document.querySelectorAll("[data-query-face-index]").forEach((box) => {
    box.classList.toggle("is-selected", Number(box.dataset.queryFaceIndex) === Number(selectedQueryFaceIndex));
  });
  if (elements.queryFaceModalStatus) {
    elements.queryFaceModalStatus.textContent = selectedQueryFaceIndex === null
      ? `检测到 ${visibleQueryFaces().length} 张可选人脸，请点击目标人物。`
      : `已选择第 ${selectedQueryFaceIndex + 1} 张人脸。`;
  }
  if (elements.queryFaceModalConfirm) {
    elements.queryFaceModalConfirm.disabled = selectedQueryFaceIndex === null;
  }
}

function queryFaceHitFromPoint(event, root = elements.uploadDrop) {
  const boxes = Array.from(root.querySelectorAll("[data-query-face-index]"));
  const hits = boxes
    .map((box) => {
      const rect = box.getBoundingClientRect();
      const contains = event.clientX >= rect.left - FACE_HIT_PADDING_PX
        && event.clientX <= rect.right + FACE_HIT_PADDING_PX
        && event.clientY >= rect.top - FACE_HIT_PADDING_PX
        && event.clientY <= rect.bottom + FACE_HIT_PADDING_PX;
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;
      return {
        box,
        index: box.dataset.queryFaceIndex,
        contains,
        area: rect.width * rect.height,
        distance: Math.hypot(event.clientX - centerX, event.clientY - centerY),
      };
    })
    .filter((item) => item.contains);
  if (hits.length) {
    hits.sort((left, right) => left.area - right.area || left.distance - right.distance);
    return hits[0];
  }
  const target = event.target.closest("[data-query-face-index]");
  return target ? { box: target, index: target.dataset.queryFaceIndex } : null;
}

function queryFaceIndexFromPoint(event, root = elements.uploadDrop) {
  return queryFaceHitFromPoint(event, root)?.index;
}

function closeQueryFaceModal() {
  if (!elements.queryFaceModal) return;
  elements.queryFaceModal.classList.remove("is-visible");
  elements.queryFaceModal.hidden = true;
  if (elements.queryFaceModalFrame) elements.queryFaceModalFrame.innerHTML = "";
  lastFocusedElement?.focus?.();
}

function calculateQueryFaceModalBaseScale(image) {
  const frame = elements.queryFaceModalFrame;
  if (!frame || !image?.naturalWidth || !image?.naturalHeight) return 1;
  const availableWidth = Math.max(1, frame.clientWidth - 24);
  const availableHeight = Math.max(1, frame.clientHeight - 18);
  return Math.min(availableWidth / image.naturalWidth, availableHeight / image.naturalHeight);
}

function setQueryFaceModalZoom(nextZoom) {
  queryFaceModalZoom = Math.max(QUERY_FACE_MODAL_MIN_ZOOM, Math.min(QUERY_FACE_MODAL_MAX_ZOOM, Number(nextZoom) || 1));
  const stage = elements.queryFaceModalFrame?.querySelector(".face-select-image-wrap");
  const image = stage?.querySelector("img");
  if (!stage || !image) return;
  const naturalWidth = image.naturalWidth || 900;
  queryFaceModalBaseScale = calculateQueryFaceModalBaseScale(image);
  stage.style.width = `${Math.max(1, Math.round(naturalWidth * queryFaceModalBaseScale * queryFaceModalZoom))}px`;
  positionFrameFaceBoxes(elements.queryFaceModalFrame);
}

function renderQueryFaceModalFrame() {
  if (!elements.queryFaceModalFrame || !uploadedImageUrl) return;
  const boxes = visibleQueryFaces().map((face) => faceBoxMarkup(face, { modal: true })).join("");
  elements.queryFaceModalFrame.innerHTML = `
    <span class="face-select-image-wrap">
      <img src="${escapeHtml(uploadedImageUrl)}" alt="放大选择目标人脸" />
      <span class="query-face-layer" aria-label="放大查询图人脸选择">${boxes}</span>
    </span>
  `;
  queryFaceModalZoom = 1;
  queryFaceModalBaseScale = 1;
  const image = elements.queryFaceModalFrame.querySelector("img");
  const applyInitialZoom = () => {
    setQueryFaceModalZoom(1);
    updateQueryFaceSelectionState();
  };
  if (image?.complete) applyInitialZoom();
  image?.addEventListener("load", applyInitialZoom, { once: true });
  positionFrameFaceBoxes(elements.queryFaceModalFrame);
  updateQueryFaceSelectionState();
}

function openQueryFaceModal() {
  if (!elements.queryFaceModal || !uploadedImageUrl || visibleQueryFaces().length < 2) return;
  lastFocusedElement = document.activeElement;
  elements.queryFaceModal.hidden = false;
  elements.queryFaceModal.classList.add("is-visible");
  renderQueryFaceModalFrame();
  updateQueryFaceSelectionState();
  elements.queryFaceModalFrame?.focus?.();
}

function scheduleAutoSearch() {
  window.clearTimeout(pendingAutoSearchTimer);
  pendingAutoSearchTimer = window.setTimeout(() => {
    pendingAutoSearchTimer = null;
    if (uploadedFile && selectedQueryFaceIndex !== null && !searchInProgress) {
      startSearch();
    }
  }, 120);
}

function cancelActiveSearch() {
  window.clearTimeout(pendingAutoSearchTimer);
  pendingAutoSearchTimer = null;
  if (activeSearchController) {
    activeSearchController.abort();
    activeSearchController = null;
  }
  searchRunId += 1;
  searchInProgress = false;
}

function openFaceFilePicker() {
  if (!elements.faceFile) return;
  elements.faceFile.value = "";
  elements.faceFile.click();
}

function setSearchIdleLabel(label = "开始检索") {
  if (!elements.startSearchBtn || elements.startSearchBtn.dataset.state === "busy") return;
  elements.startSearchBtn.innerHTML = `<svg class="ui-icon search-action-icon" aria-hidden="true"><use href="#icon-search"></use></svg>${label}`;
}

async function fetchQueryFaces(signal) {
  if (!uploadedFile) throw new Error("请先上传目标人脸图片");
  const formData = new FormData();
  formData.append("file", uploadedFile, uploadedFile.name || "query.jpg");
  const response = await fetchWithTimeout("/c1/query-faces", {
    method: "POST",
    body: formData,
    signal,
  }, C1_QUERY_FACE_TIMEOUT_MS);
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail?.detail?.message || `C1 人脸检测返回 ${response.status}`);
  }
  return response.json();
}

async function prepareQueryFaces(options = {}) {
  if (!uploadedFile) return "no-upload";
  if (queryFaceDetectionPromise) return queryFaceDetectionPromise;
  const { signal } = options;

  queryFaceDetectionPromise = (async () => {
    try {
      if (!queryFaceDetectionComplete) {
        const result = await fetchQueryFaces(signal);
        queryFaces = Array.isArray(result.queryFaces) ? result.queryFaces : [];
        queryFaceDetectionComplete = true;
      }

      if (!queryFaces.length) {
        selectedQueryFaceIndex = null;
        selectedQueryFaceImageUrl = "";
        syncPortraits();
        showToast("未检测到人脸，请重新检测或上传更清晰的正脸照片。", { tone: "warning", title: "未检测到人脸", timeout: 5200 });
        setSearchIdleLabel("重新检测人脸");
        return "no-face";
      }

      const candidates = selectableQueryFaces();
      if (!candidates.length) {
        selectedQueryFaceIndex = null;
        selectedQueryFaceImageUrl = "";
        syncPortraits();
        showToast("检测到的人脸置信度过低，请重新检测或上传更清晰的照片。", { tone: "warning", title: "人脸置信度过低", timeout: 5600 });
        setSearchIdleLabel("重新检测人脸");
        return "no-face";
      }

      if (candidates.length === 1) {
        await selectQueryFace(candidates[0].index, { silent: true });
        if (options.autoSearchSingle) {
          const score = faceDetectionScore(candidates[0]);
          const message = score !== null && score < CONFIDENT_QUERY_FACE_SCORE
            ? "已自动选中唯一低置信人脸，正在检索，请结合结果人工确认。"
            : "已自动选中唯一人脸，正在检索。";
          showToast(message, { tone: score !== null && score < CONFIDENT_QUERY_FACE_SCORE ? "warning" : "loading", title: "单人目标已确认" });
          scheduleAutoSearch();
        } else {
          showToast("已自动选中唯一人脸。", { tone: "success", title: "目标已确认" });
        }
        setSearchIdleLabel("开始检索");
        return "ready";
      }

      syncPortraits();
      setSearchIdleLabel(selectedQueryFaceIndex === null ? "选择人脸后检索" : "确认选择并检索");
      if (selectedQueryFaceIndex === null) {
        const hiddenCount = Math.max(0, queryFaces.length - visibleQueryFaces().length);
        openQueryFaceModal();
        const message = hiddenCount
          ? `检测到多张人脸，已隐藏 ${hiddenCount} 个极低置信框，请在放大图中选择检索目标。`
          : "检测到多张人脸，请在放大图中选择检索目标。";
        showToast(message, { tone: "warning", title: "请选择目标人脸", timeout: 5200 });
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
  cancelActiveSearch();
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
      showToast(`${error.message}。请重试检测或检查 CampusVision C1 连接。`, { tone: "warning", title: "人脸检测暂不可用", timeout: 5200 });
      setSearchIdleLabel("重新检测人脸");
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
  cancelActiveSearch();
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

async function applyC1Result(result) {
  if (Array.isArray(result?.queryFaces) && result.queryFaces.length) {
    queryFaces = result.queryFaces;
    queryFaceDetectionComplete = true;
  }
  if (result?.selectedQueryFace && !queryFaces.some((face) => Number(face.index) === Number(result.selectedQueryFace.index))) {
    queryFaces.push(result.selectedQueryFace);
  }
  if (result?.selectedQueryFace) {
    selectedQueryFaceIndex = Number(result.selectedQueryFace.index);
  }
  if (selectedQueryFaceIndex !== null && !selectedQueryFaceImageUrl) {
    await selectQueryFace(selectedQueryFaceIndex, { silent: true });
  }

  if (!result?.records?.length) {
    records.splice(0, records.length);
    routePoints.splice(0, routePoints.length);
    lastC1Notice = localizedC1Notice(result?.warning) || "未找到达到相似度阈值的人员。请更换目标人脸、检查人物库或确认 CampusVision C1 数据。";
    activeSource = "c1";
    syncPortraits();
    return false;
  }
  lastC1Notice = localizedC1Notice(result.warning) || (result.ambiguous ? "候选人物分数接近，请人工确认。" : "");
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
  }
  syncPortraits();

  activeSource = "c1";
  return true;
}

async function fetchC1Search(signal) {
  if (!uploadedFile) throw new Error("请先上传目标人脸图片");
  const formData = new FormData();
  formData.append("file", uploadedFile, uploadedFile.name || "query.jpg");
  const params = new URLSearchParams({ top_k: "5", max_gap_sec: "3" });
  if (selectedQueryFaceIndex !== null) params.set("query_face_index", String(selectedQueryFaceIndex));
  const response = await fetchWithTimeout(`/c1/search/person-by-image?${params.toString()}`, {
    method: "POST",
    body: formData,
    signal,
  }, C1_SEARCH_TIMEOUT_MS);
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
  const result = await Promise.race([
    desktopBridge.connectC1(error?.message || "CampusVision C1 服务当前不可用").catch(() => null),
    new Promise((resolve) => window.setTimeout(() => resolve({ connected: false, timeout: true }), SEARCH_WATCHDOG_TIMEOUT_MS)),
  ]);
  if (result?.timeout) {
    showToast("CampusVision C1 连接等待超时，请重试或手动检查 SSH 隧道。", { tone: "error", title: "连接超时", timeout: 6200 });
    return false;
  }
  if (result?.connected) {
    showToast(result.prompted ? "CampusVision C1 已连接，正在重新检索。" : "CampusVision C1 已可用，正在重新检索。", { tone: "success", title: "连接已恢复" });
    return true;
  }
  showToast("仍未检测到 CampusVision C1。已上传图片的真实检索不会回退本地模拟，请确认服务器密码和校园网连接后重试。", { tone: "warning", title: "连接未恢复", timeout: 5200 });
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
          showToast("已打开当前平台安装文件下载地址。", { tone: "info", title: "已打开下载页" });
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
        const manualDownload = latestUpdate.embedded === false;
        setUpdateStatus(updateStage === "downloaded" ? "重启安装" : `${manualDownload ? "下载新版" : "应用内更新"} ${latestUpdate.latestVersion}`, false, updateStage === "downloaded" ? "success" : "available");
        showToast(
          updateStage === "downloaded"
            ? "新版已下载完成，点击即可重启安装。"
            : `发现新版 ${latestUpdate.latestVersion}，再次点击将${manualDownload ? "打开当前平台安装文件" : "在应用内下载"}。`,
          { tone: "success", title: updateStage === "downloaded" ? "更新已下载" : "发现新版" },
        );
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
  if (searchInProgress) {
    showToast("当前检索仍在进行，请等待完成或重新上传以取消。", { tone: "info", title: "检索中" });
    return;
  }
  if (uploadedFile && queryFaceDetectionComplete && !queryFaces.length) {
    queryFaceDetectionComplete = false;
  }

  const runId = searchRunId + 1;
  searchRunId = runId;
  const controller = new AbortController();
  activeSearchController = controller;
  searchInProgress = true;
  setButtonBusy(elements.startSearchBtn, true, "检索中...", "开始检索");
  showToast(uploadedFile ? "正在调用 CampusVision C1 检索服务。" : "未上传图片，使用本地模拟数据。", { tone: "loading", title: uploadedFile ? "检索中" : "准备本地模拟" });
  let resultToast = null;
  let shouldShowResults = false;
  const watchdog = window.setTimeout(() => {
    controller.abort(new Error("CampusVision C1 检索超时"));
  }, SEARCH_WATCHDOG_TIMEOUT_MS);

  async function runC1SearchFlow() {
    const faceState = await prepareQueryFaces({ autoSearchSingle: false, signal: controller.signal });
    if (faceState === "needs-selection" || faceState === "no-face") return faceState;
    const result = await fetchC1Search(controller.signal);
    if (runId !== searchRunId) return "stale";
    const hasResults = await applyC1Result(result);
    return hasResults ? "searched" : "no-match";
  }

  try {
    if (uploadedFile) {
      const flowState = await runC1SearchFlow();
      if (flowState === "no-match") {
        resultToast = { message: lastC1Notice, options: { tone: "warning", title: "未找到匹配人员", timeout: 6200 } };
        return;
      }
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
    if (runId !== searchRunId) return;
    if (uploadedFile && await connectC1AfterFailure(error)) {
      try {
        queryFaceDetectionComplete = false;
        const retryState = await runC1SearchFlow();
        if (retryState === "no-match") {
          resultToast = { message: lastC1Notice, options: { tone: "warning", title: "未找到匹配人员", timeout: 6200 } };
          return;
        }
        if (retryState !== "searched") return;
        shouldShowResults = true;
        resultToast = lastC1Notice
          ? { message: `${lastC1Notice} 已返回 ${records.length} 条候选记录。`, options: { tone: "warning", title: "需要人工确认", timeout: 5600 } }
          : { message: `CampusVision C1 返回 ${records.length} 条关联记录。`, options: { tone: "success", title: "重试检索完成" } };
      } catch (retryError) {
        const message = localizedC1Notice(retryError.message) || retryError.message;
        resultToast = { message: `${message}。未执行检索，请重新检测人脸或检查 CampusVision C1。`, options: { tone: "error", title: "检索未完成", timeout: 6200 } };
      }
    } else if (uploadedFile) {
      const message = localizedC1Notice(error.message) || error.message;
      resultToast = { message: `${message}。未执行检索，请重新检测人脸或检查 CampusVision C1。`, options: { tone: "error", title: "检索未完成", timeout: 6200 } };
    } else {
      resetToMockData();
      shouldShowResults = true;
      resultToast = { message: `${error.message}，已回退本地模拟。`, options: { tone: "warning", title: "已使用本地模拟", timeout: 4600 } };
    }
  } finally {
    window.clearTimeout(watchdog);
    if (activeSearchController === controller) activeSearchController = null;
    if (runId === searchRunId) {
      setButtonBusy(elements.startSearchBtn, false, "检索中...", "开始检索");
      searchInProgress = false;
      const candidateCount = selectableQueryFaces().length;
      if (uploadedFile && queryFaceDetectionComplete && !queryFaces.length) {
        setSearchIdleLabel("重新检测人脸");
      }
      if (candidateCount > 1 && selectedQueryFaceIndex === null) {
        setSearchIdleLabel("选择人脸后检索");
      }
      if (candidateCount > 1 && selectedQueryFaceIndex !== null) {
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
    if (event.target.closest("#openQueryFaceModalBtn")) return;
    const faceHit = queryFaceHitFromPoint(event);
    if (faceHit?.index !== undefined) {
      event.preventDefault();
      await selectQueryFace(faceHit.index, { sourceBox: faceHit.box });
      setSearchIdleLabel("确认选择并检索");
      return;
    }
    openFaceFilePicker();
  });
  elements.uploadDrop.addEventListener("keydown", async (event) => {
    const faceTarget = event.target.closest("[data-query-face-index]");
    if (faceTarget && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      await selectQueryFace(faceTarget.dataset.queryFaceIndex, { sourceBox: faceTarget });
      setSearchIdleLabel("确认选择并检索");
      return;
    }
    if ((event.key === "Enter" || event.key === " ") && event.target === elements.uploadDrop) {
      event.preventDefault();
      openFaceFilePicker();
    }
  });
  elements.faceFile.addEventListener("change", (event) => loadImage(event.target.files?.[0]));
  elements.openQueryFaceModalBtn?.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    openQueryFaceModal();
  });
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
  elements.queryFaceModalFrame?.addEventListener("click", async (event) => {
    const faceHit = queryFaceHitFromPoint(event, elements.queryFaceModalFrame);
    if (faceHit?.index === undefined) return;
    event.preventDefault();
    await selectQueryFace(faceHit.index, { silent: true, sourceBox: faceHit.box });
    setSearchIdleLabel("确认选择并检索");
  });
  elements.queryFaceModalFrame?.addEventListener("keydown", async (event) => {
    const faceTarget = event.target.closest("[data-query-face-index]");
    if (faceTarget && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      await selectQueryFace(faceTarget.dataset.queryFaceIndex, { silent: true, sourceBox: faceTarget });
      setSearchIdleLabel("确认选择并检索");
    }
  });
  elements.queryFaceModalConfirm?.addEventListener("click", () => {
    if (selectedQueryFaceIndex === null) {
      showToast("请先在放大图中选择目标人脸。", { tone: "warning", title: "未选择目标" });
      return;
    }
    closeQueryFaceModal();
    startSearch();
  });
  elements.queryFaceModalCancel?.addEventListener("click", closeQueryFaceModal);
  elements.queryFaceModalClose?.addEventListener("click", closeQueryFaceModal);
  elements.queryFaceModal?.addEventListener("click", (event) => {
    if (event.target === elements.queryFaceModal) closeQueryFaceModal();
  });
  elements.queryFaceZoomIn?.addEventListener("click", () => setQueryFaceModalZoom(queryFaceModalZoom + 0.25));
  elements.queryFaceZoomOut?.addEventListener("click", () => setQueryFaceModalZoom(queryFaceModalZoom - 0.25));
  elements.queryFaceZoomReset?.addEventListener("click", () => setQueryFaceModalZoom(1));
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
    if (event.key === "Escape" && elements.queryFaceModal?.classList.contains("is-visible")) {
      closeQueryFaceModal();
    }
  });
  window.addEventListener("resize", () => {
    if (elements.queryFaceModal?.classList.contains("is-visible")) {
      setQueryFaceModalZoom(queryFaceModalZoom);
      return;
    }
    positionFrameFaceBoxes();
  });
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
