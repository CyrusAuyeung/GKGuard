const serviceStatus = document.querySelector("#serviceStatus");
const currentPerson = document.querySelector("#currentPerson");
const profileContent = document.querySelector("#profileContent");
const routeMap = document.querySelector("#routeMap");
const timelineList = document.querySelector("#timelineList");
const timelineCount = document.querySelector("#timelineCount");
const resultJson = document.querySelector("#resultJson");

let activePersonId = "P001";
let activeTimeline = null;

function showJson(payload) {
  resultJson.textContent = JSON.stringify(payload, null, 2);
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

function renderProfile(profile) {
  const person = profile.person;
  activePersonId = person.person_id;
  currentPerson.textContent = person.person_id;
  profileContent.classList.remove("empty-state");
  profileContent.innerHTML = `
    <div class="profile-grid">
      <div class="metric"><span>Name</span><strong>${person.name}</strong></div>
      <div class="metric"><span>ID</span><strong>${person.student_id}</strong></div>
      <div class="metric"><span>Role</span><strong>${person.identity_type}</strong></div>
      <div class="metric"><span>Department</span><strong>${person.department}</strong></div>
      <div class="metric"><span>Snapshots</span><strong>${profile.snapshots.length}</strong></div>
      <div class="metric"><span>Alerts</span><strong>${profile.alerts.length}</strong></div>
    </div>
  `;
}

function normalize(points, key) {
  const values = points.map((point) => point[key]);
  const min = Math.min(...values);
  const max = Math.max(...values);
  return points.map((point) => {
    if (max === min) return 50;
    return 10 + ((point[key] - min) / (max - min)) * 80;
  });
}

function renderMap(points) {
  routeMap.innerHTML = "";
  if (!points.length) return;

  const xs = normalize(points, "lng");
  const ys = normalize(points, "lat").map((value) => 100 - value);

  for (let index = 0; index < points.length - 1; index += 1) {
    const x1 = xs[index];
    const y1 = ys[index];
    const x2 = xs[index + 1];
    const y2 = ys[index + 1];
    const dx = x2 - x1;
    const dy = y2 - y1;
    const line = document.createElement("span");
    line.className = "map-line";
    line.style.left = `${x1}%`;
    line.style.top = `${y1}%`;
    line.style.width = `${Math.hypot(dx, dy)}%`;
    line.style.transform = `rotate(${Math.atan2(dy, dx)}rad)`;
    routeMap.appendChild(line);
  }

  points.forEach((point, index) => {
    const marker = document.createElement("span");
    marker.className = "map-point";
    marker.dataset.index = String(index + 1);
    marker.title = `${point.location} ${point.time}`;
    marker.style.left = `${xs[index]}%`;
    marker.style.top = `${ys[index]}%`;
    routeMap.appendChild(marker);
  });
}

function renderTimeline(timeline) {
  activeTimeline = timeline;
  const points = timeline.points || [];
  timelineCount.textContent = `${points.length} points`;
  timelineList.innerHTML = "";
  points.forEach((point) => {
    const item = document.createElement("li");
    item.className = "timeline-item";
    item.innerHTML = `<strong>${point.location}</strong><span>${point.time} · ${point.camera_name} · similarity ${point.similarity}</span>`;
    timelineList.appendChild(item);
  });
  renderMap(points);
}

async function loadProfileByStudentId() {
  const studentId = document.querySelector("#studentId").value.trim();
  const persons = await api(`/search/persons?student_id=${encodeURIComponent(studentId)}`);
  if (!persons.items.length) {
    showJson({ message: "No person found", student_id: studentId });
    return;
  }
  const personId = persons.items[0].person_id;
  const profile = await api(`/search/persons/${personId}/profile`);
  const timeline = await api(`/persons/${personId}/timeline?min_similarity=0.9`);
  renderProfile(profile);
  renderTimeline(timeline);
  showJson({ profile, timeline });
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
  showJson(result);
}

async function parseQuery() {
  const query = document.querySelector("#naturalQuery").value.trim();
  const result = await api("/ai/parse-query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  showJson(result);
}

async function dispatchCar() {
  const targetLocation = activeTimeline?.summary?.last_location || "Dorm East Gate";
  const result = await api("/car-tasks/mock-dispatch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event_id: "ALT-001", target_location: targetLocation, reason: "field review" }),
  });
  showJson(result);
}

async function checkHealth() {
  try {
    const result = await api("/health");
    serviceStatus.textContent = result.status;
  } catch (error) {
    serviceStatus.textContent = "Offline";
    serviceStatus.classList.add("muted");
  }
}

document.querySelector("#personSearchBtn").addEventListener("click", () => loadProfileByStudentId().catch((error) => showJson({ error: error.message })));
document.querySelector("#imageSearchBtn").addEventListener("click", () => runImageSearch().catch((error) => showJson({ error: error.message })));
document.querySelector("#parseBtn").addEventListener("click", () => parseQuery().catch((error) => showJson({ error: error.message })));
document.querySelector("#dispatchBtn").addEventListener("click", () => dispatchCar().catch((error) => showJson({ error: error.message })));

checkHealth();
loadProfileByStudentId().catch((error) => showJson({ error: error.message }));
