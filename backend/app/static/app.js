const profileContent = document.querySelector("#profileContent");
const routeMap = document.querySelector("#routeMap");
const routeSummary = document.querySelector("#routeSummary");
const timelineList = document.querySelector("#timelineList");
const timelineCount = document.querySelector("#timelineCount");
const captureGrid = document.querySelector("#captureGrid");
const captureCount = document.querySelector("#captureCount");
const eventTable = document.querySelector("#eventTable");
const bridgeMode = document.querySelector("#bridgeMode");
const bridgeTopics = document.querySelector("#bridgeTopics");
const resultContent = document.querySelector("#resultContent");
const resultStatus = document.querySelector("#resultStatus");
const resultSummary = document.querySelector("#resultSummary");
const globalSearch = document.querySelector("#globalSearch");
const studentIdInput = document.querySelector("#studentId");
const naturalQueryInput = document.querySelector("#naturalQuery");
const imageFileInput = document.querySelector("#imageFile");

let activePersonId = "P001";
let activeTimeline = null;
let activeProfile = null;
let activeReport = null;

const identityLabels = {
  student: "学生",
  faculty: "教职工",
  staff: "工作人员",
  visitor: "访客",
};

const statusLabels = {
  open: "待处理",
  closed: "已闭环",
  completed: "已完成",
  created: "已创建",
  confirmed_safe: "确认安全",
  pending_confirmation: "待确认",
  dispatched: "已派发",
  arrived_mock: "已到达（模拟）",
  mock_ready: "模拟就绪",
  high: "高",
  medium: "中",
  low: "低",
  person: "人员",
  vehicle: "车辆",
  after_hours: "夜间/非工作时段",
  today: "今天",
  red: "红色",
  white: "白色",
  black: "黑色",
  silver: "银色",
  blue: "蓝色",
  gray: "灰色",
  Parking: "停车场",
  missing_person_review: "失联复核",
  vehicle_after_hours: "车辆夜间异常",
};

const actionLabels = {
  image_search: "图片检索",
  event_report_generated: "生成案件报告",
  report_generated: "生成案件报告",
  event_disposition_archived: "归档处置结果",
  disposition_archived: "归档处置结果",
  case_package_exported: "导出证据包",
};

const locationLabels = {
  "Clinic Door": "医务室门口",
  "Main Gate North": "校园北门",
  "Library West": "图书馆西侧",
  "Canteen Entrance": "食堂入口",
  "Dorm East Gate": "宿舍东门",
  "Parking Lot East": "东侧停车场",
  "Lab Building South": "实验楼南侧",
  "Sports Field": "运动场",
};

const displayPlaceLabels = {
  "Clinic Door": "C2 教学楼南门",
  "Main Gate North": "校门口（进校）",
  "Library West": "图书馆一楼大厅",
  "Canteen Entrance": "宿舍区主干道",
  "Dorm East Gate": "C2 教学楼南门",
  "Parking Lot East": "东侧停车场",
  "Lab Building South": "体育馆东门",
};

const deviceLabels = {
  "Clinic Door Camera": "C2-NM-02 门口摄像机",
  "Main Gate North Camera": "GATE-01 人脸抓拍机",
  "Library West Camera": "LIB-01 大厅摄像机",
  "Canteen Entrance Camera": "Dorm-RD-03 道路摄像机",
  "Dorm East Gate Camera": "C2-NM-02 门口摄像机",
  "Parking Lot East Camera": "PARK-E1 车辆摄像机",
  "Lab Building South Camera": "GYM-02 东门摄像机",
};

const cameraLabels = {
  "Clinic Door Camera": "医务室门口摄像头",
  "Main Gate North Camera": "校园北门摄像头",
  "Library West Camera": "图书馆西侧摄像头",
  "Canteen Entrance Camera": "食堂入口摄像头",
  "Dorm East Gate Camera": "宿舍东门摄像头",
  "Parking Lot East Camera": "东侧停车场摄像头",
  "Lab Building South Camera": "实验楼南侧摄像头",
};

const departmentLabels = {
  "Computer Science": "计算机科学系",
  "Information Systems": "信息系统系",
  Security: "安保处",
};

const personNameLabels = {
  "Student Alpha": "演示学生 Alpha",
};

const filterLabels = {
  location: "地点",
  color: "颜色",
  object_type: "对象类型",
  time_hint: "时间范围",
};

const campusBuildings = [
  { name: "北门", left: 6, top: 16, width: 18, height: 16 },
  { name: "图书馆", left: 26, top: 24, width: 18, height: 18 },
  { name: "食堂", left: 42, top: 54, width: 18, height: 15 },
  { name: "宿舍区", left: 63, top: 36, width: 20, height: 18 },
  { name: "医务室", left: 11, top: 63, width: 18, height: 15 },
  { name: "实验楼", left: 72, top: 66, width: 18, height: 14 },
];

function escapeHtml(value) {
  return String(value ?? "-")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function label(value) {
  return statusLabels[value] || identityLabels[value] || value || "-";
}

function displayLocation(value) {
  return locationLabels[value] || value || "-";
}

function displayCamera(value) {
  return cameraLabels[value] || value || "-";
}

function displayPlace(value) {
  return displayPlaceLabels[value] || displayLocation(value);
}

function displayDevice(value) {
  return deviceLabels[value] || displayCamera(value);
}

function displayDepartment(value) {
  return departmentLabels[value] || value || "-";
}

function displayPersonName(value) {
  return personNameLabels[value] || value || "-";
}

function displayFilterValue(key, value) {
  if (key === "location") return displayLocation(value);
  return label(value);
}

function formatTime(value) {
  if (!value) return "-";
  return String(value).replace("T", " ");
}

function formatTimeShort(value) {
  if (!value) return "-";
  const timePart = String(value).split("T")[1] || String(value);
  return timePart.slice(0, 5);
}

function formatDateShort(value) {
  if (!value) return "-";
  return String(value).slice(5, 10).replace("-", "/");
}

function formatPercent(value) {
  if (value === null || value === undefined) return "-";
  return `${Math.round(Number(value) * 100)}%`;
}

function resultField(labelText, value) {
  return `<div><span class="field-label">${escapeHtml(labelText)}</span><span class="field-value">${escapeHtml(value)}</span></div>`;
}

function listItems(items, renderItem) {
  if (!items || !items.length) return '<p class="empty-state">暂无记录。</p>';
  return `<ul class="result-list">${items.map((item, index) => `<li>${renderItem(item, index)}</li>`).join("")}</ul>`;
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    throw new Error(typeof payload === "string" ? payload : JSON.stringify(payload));
  }
  return payload;
}

function summarizePayload(payload) {
  if (payload.shell_notice) return payload.message;
  if (payload.integration_id === "ue-campuscar") return `UE/CampusCar 联调契约已加载，模式：${payload.mode || "mock"}。`;
  if (payload.flow_id) return `完整演示流程已完成，共执行 ${payload.steps.length} 个环节。`;
  if (payload.package_id) return `证据包 ${payload.package_id} 已生成，包含 ${payload.timeline_points.length} 个轨迹点和 ${payload.evidence_snapshots.length} 条证据。`;
  if (payload.disposition_id) return `处置结果 ${payload.disposition_id} 已归档，状态从 ${label(payload.status_before)} 更新为 ${label(payload.status_after)}。`;
  if (payload.report_id) return `案件报告 ${payload.report_id} 已生成，包含 ${payload.key_findings.length} 条关键发现。`;
  if (payload.task_id) return `巡检车复核任务 ${payload.task_id} 已创建，目标地点：${displayLocation(payload.location)}。`;
  if (payload.query_filename) return `图片线索 ${payload.query_filename} 匹配到 ${payload.matches.length} 条相似记录。`;
  if (payload.items) return `已加载 ${payload.count ?? payload.items.length} 条审计或列表记录。`;
  if (payload.filters) return `已从自然语言线索中解析出 ${Object.keys(payload.filters).length} 个筛选条件。`;
  if (payload.profile && payload.timeline) return `已加载 ${displayPersonName(payload.profile.person.name)} 的画像和 ${payload.timeline.summary.point_count} 个轨迹点。`;
  if (payload.error) return payload.error;
  if (payload.message) return payload.message;
  return "处理结果已更新。";
}

function translateFinding(text) {
  const value = String(text || "");
  const summary = value.match(/Found (\d+) appearance records across (\d+) cameras\. Last seen at (.+) at (.+)\./);
  if (summary) return `共发现 ${summary[1]} 条出现记录，覆盖 ${summary[2]} 个摄像头；最后一次出现地点为 ${displayLocation(summary[3])}，时间为 ${formatTime(summary[4])}。`;
  const first = value.match(/First related record: (.+)\./);
  if (first) return `首条关联记录时间：${formatTime(first[1])}。`;
  const last = value.match(/Last related record: (.+) at (.+)\./);
  if (last) return `最后关联记录：${formatTime(last[1])}，地点：${displayLocation(last[2])}。`;
  const count = value.match(/Related snapshot count: (\d+)\./);
  if (count) return `关联抓拍数量：${count[1]}。`;
  return value;
}

function translateRecommendation(text) {
  const value = String(text || "");
  if (value === "Review the timeline points and source camera snapshots.") return "复核轨迹点和来源摄像头抓拍。";
  const fieldReview = value.match(/Prioritize field review around (.+)\./);
  if (fieldReview) return `优先在 ${displayLocation(fieldReview[1])} 附近进行现场复核。`;
  if (value === "Create or continue a campusCar field-review task before closing the event.") return "闭环前创建或继续巡检车现场复核任务。";
  if (value === "Escalate to the duty officer if the subject is not confirmed on site.") return "若现场未确认目标对象，应升级给值班负责人。";
  return value;
}

function renderProfileResult(payload) {
  const person = payload.profile.person;
  const summary = payload.timeline.summary;
  return `
    <section class="result-card">
      <h3>人员画像已加载</h3>
      <div class="result-grid">
        ${resultField("姓名", displayPersonName(person.name))}
        ${resultField("学工号", person.student_id)}
        ${resultField("身份", label(person.identity_type))}
        ${resultField("院系/部门", displayDepartment(person.department))}
        ${resultField("轨迹点", `${summary.point_count} 个`)}
        ${resultField("覆盖摄像头", `${summary.camera_count} 个`)}
        ${resultField("最后位置", displayLocation(summary.last_location))}
        ${resultField("最后时间", formatTime(summary.last_seen))}
      </div>
    </section>
  `;
}

function renderParseResult(payload) {
  const entries = Object.entries(payload.filters || {});
  return `
    <section class="result-card">
      <h3>自然语言线索解析</h3>
      <p>原始线索：${escapeHtml(payload.query)}</p>
      <div class="result-grid">
        ${resultField("解析置信度", formatPercent(payload.confidence))}
        ${resultField("命中关键词", payload.matched_terms?.join("、") || "无")}
        ${resultField("筛选条件", entries.length ? `${entries.length} 个` : "暂未识别")}
        ${resultField("解析方式", "规则解析，可替换为大模型")}
      </div>
      ${listItems(entries, ([key, value]) => `${escapeHtml(filterLabels[key] || key)}：${escapeHtml(displayFilterValue(key, value))}`)}
    </section>
  `;
}

function renderImageResult(payload) {
  const minSimilarity = payload.matches.length ? Math.min(...payload.matches.map((match) => match.similarity)) : null;
  return `
    <section class="result-card">
      <h3>图片匹配结果</h3>
      <div class="result-grid">
        ${resultField("查询图片", payload.query_filename)}
        ${resultField("候选结果", `${payload.matches.length} 条`)}
        ${resultField("提示对象", payload.query_hint_person_id || "未命中")}
        ${resultField("最低相似度", formatPercent(minSimilarity))}
      </div>
      ${listItems(payload.matches, (match, index) => `
        <strong>匹配 ${index + 1}：${escapeHtml(displayLocation(match.location))}</strong><br />
        时间：${escapeHtml(formatTime(match.time))}；摄像头：${escapeHtml(displayCamera(match.camera_name))}；相似度：${escapeHtml(formatPercent(match.similarity))}
      `)}
    </section>
  `;
}

function renderTaskResult(payload) {
  const contract = payload.bridge_contract || {};
  return `
    <section class="result-card">
      <h3>巡检车复核任务</h3>
      <div class="result-grid">
        ${resultField("任务编号", payload.task_id)}
        ${resultField("关联事件", payload.event_id)}
        ${resultField("目标地点", displayLocation(payload.location))}
        ${resultField("任务状态", label(payload.status))}
        ${resultField("指令话题", contract.command_topic || "-")}
        ${resultField("状态话题", contract.status_topic || "-")}
      </div>
      <p>建议由巡检车前往目标地点补充现场复核图片，并通过 UE/ROS2 适配器回传给安保端闭环。</p>
    </section>
  `;
}

function renderBridgeStatusResult(payload) {
  return `
    <section class="result-card">
      <h3>UE/CampusCar 联调契约</h3>
      <div class="result-grid">
        ${resultField("集成编号", payload.integration_id)}
        ${resultField("状态", label(payload.status))}
        ${resultField("rosbridge", payload.rosbridge_url)}
        ${resultField("UE测试程序", payload.external_test_app)}
        ${resultField("指令话题", payload.command_topic)}
        ${resultField("位姿话题", payload.position_topic)}
        ${resultField("状态话题", payload.status_topic)}
        ${resultField("HLS", payload.video_hls_url)}
      </div>
      ${listItems(payload.notes, (item) => escapeHtml(item))}
    </section>
  `;
}

function renderReportResult(payload) {
  return `
    <section class="result-card">
      <h3>案件报告</h3>
      <div class="result-grid">
        ${resultField("报告编号", payload.report_id)}
        ${resultField("事件编号", payload.event_id)}
        ${resultField("事件状态", label(payload.status))}
        ${resultField("严重等级", label(payload.severity))}
      </div>
      <h3>关键发现</h3>
      ${listItems(payload.key_findings, (item) => escapeHtml(translateFinding(item)))}
      <h3>建议动作</h3>
      ${listItems(payload.recommended_actions, (item) => escapeHtml(translateRecommendation(item)))}
    </section>
  `;
}

function renderDispositionResult(payload) {
  return `
    <section class="result-card">
      <h3>处置结果已归档</h3>
      <div class="result-grid">
        ${resultField("归档编号", payload.disposition_id)}
        ${resultField("事件编号", payload.event_id)}
        ${resultField("原状态", label(payload.status_before))}
        ${resultField("新状态", label(payload.status_after))}
        ${resultField("处理人", payload.handler)}
        ${resultField("处置结论", label(payload.result))}
      </div>
      <p>${escapeHtml(payload.notes || "处置记录已保存。")}</p>
    </section>
  `;
}

function renderAuditResult(payload) {
  return `
    <section class="result-card">
      <h3>审计日志</h3>
      <p>最近 ${payload.items.length} 条操作记录，便于演示追溯。</p>
      ${listItems(payload.items, (item) => `
        <strong>${escapeHtml(actionLabels[item.action] || item.action)}</strong><br />
        时间：${escapeHtml(formatTime(item.timestamp))}；目标：${escapeHtml(item.target?.event_id || item.target_id || "-")}
      `)}
    </section>
  `;
}

function renderPackageResult(payload) {
  return `
    <section class="result-card">
      <h3>证据包已生成</h3>
      <div class="result-grid">
        ${resultField("证据包编号", payload.package_id)}
        ${resultField("事件编号", payload.event_id)}
        ${resultField("轨迹点", `${payload.timeline_points.length} 个`)}
        ${resultField("证据抓拍", `${payload.evidence_snapshots.length} 条`)}
      </div>
      <p>证据包已整合案件报告、轨迹点、抓拍证据和审计记录，可交给 C1 或前端进一步展示。</p>
    </section>
  `;
}

function renderFlowResult(payload) {
  const report = payload.report || {};
  const disposition = payload.disposition || {};
  const casePackage = payload.case_package || {};
  return `
    <section class="result-card">
      <h3>完整演示流程已完成</h3>
      <div class="result-grid">
        ${resultField("流程编号", payload.flow_id)}
        ${resultField("完成环节", `${payload.steps.length} 个`)}
        ${resultField("报告编号", report.report_id || "-")}
        ${resultField("证据包", casePackage.package_id || "-")}
        ${resultField("处置状态", label(disposition.status_after))}
        ${resultField("最后位置", displayLocation(payload.profile?.timeline?.summary?.last_location))}
      </div>
      <h3>已执行动作</h3>
      ${listItems([
        "加载人员画像和轨迹",
        "解析自然语言线索",
        "执行图片相似检索",
        "创建巡检车复核任务",
        "读取 UE/CampusCar 联调契约",
        "生成案件报告",
        "归档处置结果",
        "导出证据包",
        "读取审计日志",
      ], (item) => escapeHtml(item))}
    </section>
  `;
}

function renderGenericResult(payload) {
  if (payload.error) {
    return `<section class="result-card"><h3>发生错误</h3><p>${escapeHtml(payload.error)}</p></section>`;
  }
  if (payload.message) {
    return `<section class="result-card"><h3>提示</h3><p>${escapeHtml(payload.message)}</p></section>`;
  }
  return `<section class="result-card"><h3>处理完成</h3><p>结果已更新，但当前类型暂无专用展示模板。</p></section>`;
}

function renderShellNotice(payload) {
  return `
    <section class="result-card">
      <h3>${escapeHtml(payload.message)}</h3>
      ${payload.details?.length ? listItems(payload.details, (item) => escapeHtml(item)) : ""}
    </section>
  `;
}

function renderResult(payload) {
  if (payload.shell_notice) return renderShellNotice(payload);
  if (payload.integration_id === "ue-campuscar") return renderBridgeStatusResult(payload);
  if (payload.flow_id) return renderFlowResult(payload);
  if (payload.package_id) return renderPackageResult(payload);
  if (payload.disposition_id) return renderDispositionResult(payload);
  if (payload.report_id) return renderReportResult(payload);
  if (payload.task_id) return renderTaskResult(payload);
  if (payload.query_filename) return renderImageResult(payload);
  if (payload.items) return renderAuditResult(payload);
  if (payload.filters) return renderParseResult(payload);
  if (payload.profile && payload.timeline) return renderProfileResult(payload);
  return renderGenericResult(payload);
}

function renderBridgeStatus(payload) {
  if (!bridgeMode || !bridgeTopics) return;
  bridgeMode.textContent = `${payload.mode || "mock"} / ${payload.rosbridge_url || "ws://127.0.0.1:9090"}`;
  bridgeTopics.innerHTML = `
    <div><dt>指令</dt><dd>${escapeHtml(payload.command_topic)}</dd></div>
    <div><dt>位姿</dt><dd>${escapeHtml(payload.position_topic)}</dd></div>
    <div><dt>状态</dt><dd>${escapeHtml(payload.status_topic)}</dd></div>
  `;
}

function plainTextResult(payload) {
  const temporary = document.createElement("div");
  temporary.innerHTML = renderResult(payload);
  return temporary.textContent.replace(/\s+/g, " ").trim();
}

function showResult(payload) {
  resultSummary.textContent = summarizePayload(payload);
  resultStatus.textContent = payload.error ? "错误" : "已更新";
  resultContent.textContent = plainTextResult(payload) || summarizePayload(payload);
}

function showShellNotice(title, message, details = []) {
  showResult({
    shell_notice: true,
    message: `${title}：${message}`,
    details,
  });
}

async function runAction(labelText, action) {
  resultStatus.textContent = "处理中";
  resultSummary.textContent = `${labelText}正在执行。`;
  resultContent.textContent = "正在调用接口并整理中文结果...";
  try {
    const payload = await action();
    showResult(payload);
  } catch (error) {
    showResult({ error: error.message });
  }
}

function renderProfile(profile) {
  const person = profile.person;
  activePersonId = person.person_id;
  activeProfile = profile;
  profileContent.innerHTML = `
    <div class="target-photo" aria-hidden="true"></div>
    <div class="target-fields">
      <div><span>姓名</span><strong>${escapeHtml(displayPersonName(person.name))}</strong></div>
      <div><span>学工号</span><strong>${escapeHtml(person.student_id)}</strong></div>
      <div><span>性别</span><strong>男</strong></div>
      <div><span>年龄</span><strong>22</strong></div>
      <div><span>身份</span><strong>${escapeHtml(label(person.identity_type))}</strong></div>
      <div><span>院系</span><strong>${escapeHtml(displayDepartment(person.department))}</strong></div>
      <div><span>最近出现</span><strong>${escapeHtml(formatTime(profile.snapshots.at(-1)?.time))}</strong></div>
      <div><span>最后位置</span><strong>${escapeHtml(displayPlace(profile.snapshots.at(-1)?.location))}</strong></div>
    </div>
    <div class="target-actions"><button id="profileImageBtn" type="button">以图搜图</button><button id="watchBtn" type="button">加入关注</button></div>
    <div class="similarity-row"><span>相似度阈值</span><div class="similarity-track"><i></i></div><strong>80%</strong></div>
  `;
  document.querySelector("#profileImageBtn")?.addEventListener("click", () => runAction("目标图片检索", runImageSearch));
  document.querySelector("#watchBtn")?.addEventListener("click", () => {
    showShellNotice("关注名单已更新", `${displayPersonName(person.name)} 已加入本地关注队列`, [
      "后续接入真实账号服务时，可替换为 POST /watchlist 或人员标签接口。",
      `当前对象：${person.person_id} / ${person.student_id}`,
    ]);
  });
}

function normalizeAxis(points, key, reverse = false) {
  const values = points.map((point) => Number(point[key]));
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  return points.map((point) => {
    const rawValue = maxValue === minValue ? 50 : 12 + ((Number(point[key]) - minValue) / (maxValue - minValue)) * 76;
    return reverse ? 100 - rawValue : rawValue;
  });
}

function renderMap(points) {
  routeMap.innerHTML = "";
  campusBuildings.forEach((building) => {
    const element = document.createElement("span");
    element.className = "campus-building";
    element.textContent = building.name;
    element.style.left = `${building.left}%`;
    element.style.top = `${building.top}%`;
    element.style.width = `${building.width}%`;
    element.style.height = `${building.height}%`;
    routeMap.appendChild(element);
  });
  const lake = document.createElement("span");
  lake.className = "lake";
  routeMap.appendChild(lake);

  if (!points.length) {
    routeSummary.textContent = "当前筛选条件下暂无轨迹点。";
    return;
  }

  const xPositions = normalizeAxis(points, "lng");
  const yPositions = normalizeAxis(points, "lat", true);
  const polylinePoints = points.map((point, index) => `${xPositions[index]},${yPositions[index]}`).join(" ");
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "route-svg");
  svg.setAttribute("viewBox", "0 0 100 100");
  svg.setAttribute("preserveAspectRatio", "none");
  svg.innerHTML = `
    <polyline points="${polylinePoints}" fill="none" stroke="rgba(23,105,245,0.18)" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" />
    <polyline points="${polylinePoints}" fill="none" stroke="#1769f5" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="4 3" />
  `;
  routeMap.appendChild(svg);

  points.forEach((point, index) => {
    const marker = document.createElement("span");
    marker.className = `route-marker ${index === 0 ? "start" : ""} ${index === points.length - 1 ? "end" : ""}`;
    marker.textContent = String(index + 1);
    marker.title = `${displayLocation(point.location)} ${formatTime(point.time)}`;
    marker.style.left = `${xPositions[index]}%`;
    marker.style.top = `${yPositions[index]}%`;
    routeMap.appendChild(marker);
  });
}

function renderTimeline(timeline) {
  activeTimeline = timeline;
  const points = timeline.points || [];
  const summary = timeline.summary || {};
  timelineCount.textContent = `${points.length} 条记录`;
  routeSummary.textContent = `${displayPlace(summary.first_seen ? points[0]?.location : "-")} 至 ${displayPlace(summary.last_location)}，覆盖 ${summary.camera_count || 0} 个摄像头。`;
  timelineList.innerHTML = "";
  points.slice().reverse().forEach((point, index) => {
    const item = document.createElement("li");
    item.className = "appearance-item";
    item.innerHTML = `
      <span>${escapeHtml(formatTimeShort(point.time))}</span>
      <div>
        <strong>${escapeHtml(displayPlace(point.location))}</strong>
        <small>${escapeHtml(displayDevice(point.camera_name))}</small>
      </div>
      <div class="appearance-thumb" aria-hidden="true"></div>
      <b class="score">${escapeHtml(formatPercent(point.similarity))}</b>
    `;
    timelineList.appendChild(item);
  });
  renderMap(points);
}

function renderCaptures(records) {
  const items = records.slice().reverse();
  captureCount.textContent = String(records.length);
  captureGrid.innerHTML = items.map((record, index) => `
    <article class="capture-item">
      <div class="capture-thumb" data-index="${items.length - index}"></div>
      <div class="capture-body">
        <strong>${escapeHtml(displayPlace(record.location))}</strong>
        <span>${escapeHtml(formatTime(record.time))}</span>
        <span>${escapeHtml(displayDevice(record.camera_name))}</span>
        <span>相似度 <b>${escapeHtml(formatPercent(record.mock_similarity || record.similarity))}</b></span>
      </div>
    </article>
  `).join("");
}

function renderEvents(report, profile) {
  activeReport = report;
  const alerts = profile.alerts || [];
  const rows = [
    ...alerts.map((alert) => ({ type: label(alert.alert_type), time: "05-14 16:24", place: displayPlace(alert.location), status: "待复核", className: "wait", action: "处理" })),
    { type: "校园巡逻任务", time: "05-14 16:20", place: "图书馆周边", status: "巡逻中", className: "doing", action: "查看" },
    { type: "异常通道预警", time: "05-14 16:12", place: "体育馆东侧", status: "已确认", className: "done", action: "查看" },
    { type: "陌生人进校", time: "05-14 15:58", place: "校门口", status: "已处置", className: "done", action: "查看" },
  ];
  eventTable.innerHTML = `
    <div class="review-head"><span>任务类型</span><span>关联时间</span><span>地点</span><span>状态</span><span>操作</span></div>
    ${rows.map((row) => `
      <div class="review-row">
        <strong>${escapeHtml(row.type)}</strong>
        <span>${escapeHtml(row.time)}</span>
        <span>${escapeHtml(row.place)}</span>
        <span class="pill ${escapeHtml(row.className)}">${escapeHtml(row.status)}</span>
        <button class="row-action" type="button" data-action="${escapeHtml(row.action)}" data-type="${escapeHtml(row.type)}">${escapeHtml(row.action)}</button>
      </div>
    `).join("")}
  `;
  eventTable.querySelectorAll(".row-action").forEach((button) => {
    button.addEventListener("click", () => {
      const action = button.dataset.action || "查看";
      if (action === "处理") {
        runAction("巡检车复核", dispatchCar);
        return;
      }
      showShellNotice("事件详情已就绪", `${button.dataset.type} 的详情面板可接入真实事件服务`, [
        "预留接口：GET /events/{event_id}、GET /car-tasks/{task_id}",
        `当前报告：${activeReport?.report_id || "待生成"}`,
      ]);
    });
  });
}

async function loadProfileByStudentId() {
  const keyword = globalSearch.value.trim() || studentIdInput.value.trim() || "S2026001";
  studentIdInput.value = keyword;
  const query = keyword.toUpperCase().startsWith("S") ? `student_id=${encodeURIComponent(keyword)}` : `keyword=${encodeURIComponent(keyword)}`;
  const persons = await api(`/search/persons?${query}`);
  if (!persons.items.length) {
    const emptyResult = { message: "未找到该检索条件对应的人员。", keyword };
    showResult(emptyResult);
    return emptyResult;
  }
  const personId = persons.items[0].person_id;
  const [profile, timeline, records, report] = await Promise.all([
    api(`/search/persons/${personId}/profile`),
    api(`/persons/${personId}/timeline?min_similarity=0.9`),
    api(`/search/records?person_id=${personId}&min_similarity=0.9`),
    api("/events/ALT-001/report"),
  ]);
  renderProfile(profile);
  renderTimeline(timeline);
  renderCaptures(records.items || []);
  renderEvents(report, profile);
  const result = { profile, timeline };
  showResult(result);
  return result;
}

function selectNavigation(targetId, selectedLink) {
  document.querySelectorAll(".app-sidebar a").forEach((link) => {
    link.classList.toggle("active", selectedLink ? link === selectedLink : link.getAttribute("href") === `#${targetId}`);
  });
  const target = document.getElementById(targetId);
  if (target) {
    target.scrollIntoView({ block: "nearest", inline: "nearest" });
  }
  const moduleName = selectedLink?.dataset.module || targetId;
  const details = selectedLink?.dataset.details?.split("|") || [
    "左侧导航已完成状态切换。",
    "后续可将该入口替换为独立页面、路由或权限控制模块。",
  ];
  showShellNotice("模块已切换", `当前进入 ${moduleName} 模块`, details);
}

function bindNavigation() {
  document.querySelectorAll(".app-sidebar a").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      selectNavigation(link.getAttribute("href").replace("#", "") || "overview", link);
    });
  });
}

function bindShellControls() {
  document.querySelector("#noticeBtn")?.addEventListener("click", () => {
    showShellNotice("通知中心", "当前有 12 条待处理提醒", [
      "失联复核 1 条，巡逻任务 6 条，系统同步提醒 5 条。",
      "后续接入通知服务时，可替换为 GET /notifications。",
    ]);
  });
  document.querySelector("#helpBtn")?.addEventListener("click", () => {
    showShellNotice("帮助中心", "已准备好演示说明和接口接入说明入口", [
      "全局搜索：人员、图片、车辆线索统一入口。",
      "事件处置：可接 CampusCar、报告、审计和归档服务。",
    ]);
  });
  document.querySelector("#userMenuBtn")?.addEventListener("click", () => {
    showShellNotice("用户菜单", "管理员工作台占位已启用", [
      "后续可接入登录、角色权限、操作审计和账号设置。",
      "当前角色：security_admin / 演示模式。",
    ]);
  });
  document.querySelector("#calendarBtn")?.addEventListener("click", () => {
    showShellNotice("日期筛选", "已切换到 2025-05-14 的演示数据窗口", [
      "后续接入真实数据时，可将该控件连接到时间范围查询参数。",
    ]);
  });
  document.querySelector("#timelineFilterBtn")?.addEventListener("click", () => {
    showShellNotice("时间线筛选", "当前展示相似度不低于 90% 的轨迹点", [
      "可扩展筛选项：时间范围、摄像头、相似度阈值、校区区域。",
    ]);
  });
  document.querySelector("#refreshBtn")?.addEventListener("click", () => runAction("刷新数据", loadProfileByStudentId));
  document.querySelector("#mapMode")?.addEventListener("change", (event) => {
    showShellNotice("地图模式", `已切换为 ${event.target.value}`, [
      "地图容器、轨迹点和图例已保留，可替换为真实 GIS/摄像头底图组件。",
    ]);
  });
  imageFileInput?.addEventListener("change", () => runAction("图片匹配", runImageSearch));
}

async function runImageSearch() {
  const fileInput = document.querySelector("#imageFile");
  const form = new FormData();
  if (fileInput.files.length) {
    form.append("file", fileInput.files[0]);
  } else {
    form.append("file", new Blob(["p001 target demo image"], { type: "image/jpeg" }), "p001_target.jpg");
  }
  const result = await api("/search/image?top_k=5&min_similarity=0.8", { method: "POST", body: form });
  if (result.query_hint_person_id) {
    const timeline = await api(`/persons/${result.query_hint_person_id}/timeline?min_similarity=0.9`);
    renderTimeline(timeline);
  }
  showResult(result);
  return result;
}

async function parseQuery() {
  const query = naturalQueryInput.value.trim() || "夜间停车场附近的红色车辆";
  const result = await api("/ai/parse-query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  showResult(result);
  return result;
}

async function dispatchCar() {
  const targetLocation = activeTimeline?.summary?.last_location || "Dorm East Gate";
  const result = await api("/car-tasks/mock-dispatch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      event_id: "ALT-001",
      target_location: targetLocation,
      reason: "field review",
      robot_id: "CAR-DEMO-01",
      robot_type: "campusCar",
      speed_mps: 0.8,
      command_topic: "/U2RTopic_Command",
      position_topic: "/R2UTopic_Pos",
      status_topic: "/R2UTopic_Text",
    }),
  });
  showResult(result);
  return result;
}

async function loadBridgeStatus({ show = true } = {}) {
  const result = await api("/car-tasks/ue-bridge-status");
  renderBridgeStatus(result);
  if (show) showResult(result);
  return result;
}

async function generateReport() {
  const result = await api("/events/ALT-001/report");
  showResult(result);
  return result;
}

async function archiveDisposition() {
  const result = await api("/events/ALT-001/disposition", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      result: "confirmed_safe",
      handler: "security_desk_demo",
      notes: "演示闭环：轨迹和巡检车复核均显示目标已返回宿舍东门。",
    }),
  });
  showResult(result);
  return result;
}

async function viewAuditLogs() {
  const result = await api("/audit/logs?limit=10");
  showResult(result);
  return result;
}

async function exportCasePackage() {
  const result = await api("/events/ALT-001/case-package");
  showResult(result);
  return result;
}

async function runFullDemoFlow() {
  const profile = await loadProfileByStudentId();
  const parsedQuery = await parseQuery();
  const imageSearch = await runImageSearch();
  const carDispatch = await dispatchCar();
  const bridgeStatus = await loadBridgeStatus({ show: false });
  const report = await generateReport();
  const disposition = await archiveDisposition();
  const casePackage = await exportCasePackage();
  const auditLogs = await viewAuditLogs();
  const result = {
    flow_id: "FLOW-ALT-001",
    steps: [
      "profile_loaded",
      "query_parsed",
      "image_matched",
      "campuscar_review_created",
      "ue_bridge_contract_loaded",
      "case_report_generated",
      "disposition_archived",
      "case_package_exported",
      "audit_logs_loaded",
    ],
    profile,
    parsed_query: parsedQuery,
    image_search: imageSearch,
    car_dispatch: carDispatch,
    bridge_status: bridgeStatus,
    report,
    disposition,
    case_package: casePackage,
    audit_logs: auditLogs,
  };
  showResult(result);
  return result;
}

async function checkHealth() {
  try {
    const result = await api("/health");
    resultStatus.textContent = result.status === "ok" ? "在线" : result.status;
  } catch (error) {
    resultStatus.textContent = "离线";
    resultStatus.classList.add("muted");
  }
}

document.querySelector("#personSearchBtn").addEventListener("click", () => runAction("人员检索", loadProfileByStudentId));
document.querySelector("#imageSearchBtn").addEventListener("click", () => runAction("图片匹配", runImageSearch));
document.querySelector("#parseBtn").addEventListener("click", () => runAction("线索解析", parseQuery));
document.querySelector("#fullFlowBtn").addEventListener("click", () => runAction("完整演示流程", runFullDemoFlow));
document.querySelector("#dispatchBtn").addEventListener("click", () => runAction("巡检车复核", dispatchCar));
document.querySelector("#reportBtn").addEventListener("click", () => runAction("案件报告", generateReport));
document.querySelector("#archiveBtn").addEventListener("click", () => runAction("处置归档", archiveDisposition));
document.querySelector("#auditBtn").addEventListener("click", () => runAction("审计日志", viewAuditLogs));
document.querySelector("#packageBtn").addEventListener("click", () => runAction("证据包导出", exportCasePackage));
document.querySelector("#bridgeStatusBtn").addEventListener("click", () => runAction("UE联调契约", loadBridgeStatus));
globalSearch.addEventListener("keydown", (event) => {
  if (event.key === "Enter") runAction("人员检索", loadProfileByStudentId);
});

bindNavigation();
bindShellControls();
checkHealth();
loadBridgeStatus({ show: false }).catch(() => {
  if (bridgeMode) bridgeMode.textContent = "mock / 契约接口待启动";
});
loadProfileByStudentId().catch((error) => showResult({ error: error.message }));