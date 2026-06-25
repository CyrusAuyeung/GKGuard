const { test, expect } = require("@playwright/test");

const PNG_BUFFER = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "base64",
);
const COLOR_QUERY_IMAGE = Buffer.from(`
  <svg xmlns="http://www.w3.org/2000/svg" width="100" height="50" viewBox="0 0 100 50">
    <rect width="50" height="50" fill="#e11d48"/>
    <rect x="50" width="50" height="50" fill="#2563eb"/>
  </svg>
`);
const PORTRAIT_QUERY_IMAGE = Buffer.from(`
  <svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 300 300">
    <rect width="300" height="300" fill="#e0f2fe"/>
    <rect x="105" y="58" width="90" height="54" rx="22" fill="#1f2937"/>
    <ellipse cx="150" cy="142" rx="54" ry="62" fill="#f7c9a9"/>
    <circle cx="132" cy="132" r="7" fill="#111827"/>
    <circle cx="168" cy="132" r="7" fill="#111827"/>
    <rect x="128" y="180" width="44" height="8" rx="4" fill="#9f1239"/>
    <rect x="104" y="206" width="92" height="56" rx="20" fill="#2563eb"/>
  </svg>
`);

async function expectNoHorizontalOverflow(page) {
  const overflow = await page.evaluate(() => {
    const doc = document.documentElement;
    return Math.ceil(doc.scrollWidth - window.innerWidth);
  });
  expect(overflow).toBeLessThanOrEqual(1);
}

function collectBrowserProblems(page) {
  const problems = [];
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      problems.push(`${message.type()}: ${message.text()}`);
    }
  });
  page.on("pageerror", (error) => {
    problems.push(`pageerror: ${error.message}`);
  });
  return problems;
}

async function expectHealthyPage(page, problems) {
  await expect(page).toHaveTitle(/GKGuard/);
  await expect(page.locator(".screen.is-active")).toBeVisible();
  await expect(page.locator("#toast")).toBeHidden();
  await expectNoHorizontalOverflow(page);
  expect(problems).toEqual([]);
}

async function expectDesktopRecordListOnLeft(page) {
  const viewport = page.viewportSize();
  if (!viewport || viewport.width < 981) return;
  const recordBox = await page.locator(".record-panel").boundingBox();
  const detailBox = await page.locator(".detail-panel").boundingBox();
  const targetBox = await page.locator(".target-panel").boundingBox();
  expect(recordBox).not.toBeNull();
  expect(detailBox).not.toBeNull();
  expect(targetBox).not.toBeNull();
  expect(recordBox.x + recordBox.width).toBeLessThanOrEqual(detailBox.x);
  expect(recordBox.y).toBeGreaterThanOrEqual(targetBox.y);
}

async function clickQueryFaceByIndex(page, index) {
  const locator = page.locator(`[data-query-face-index="${index}"]`);
  const box = await locator.boundingBox();
  expect(box).not.toBeNull();
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
}

async function expectResultFaceBoxAwayFromOrigin(page, selector = "#recordScene .result-face-box") {
  const box = await page.locator(selector).boundingBox();
  const scene = await page.locator("#recordScene").boundingBox();
  expect(box).not.toBeNull();
  expect(scene).not.toBeNull();
  expect(box.x - scene.x).toBeGreaterThan(80);
  expect(box.y - scene.y).toBeGreaterThan(40);
}

async function expectResultFaceLabelOutsideBox(page, selector = "#recordScene .result-face-box") {
  const placement = await page.locator(selector).evaluate((box) => {
    const label = box.querySelector(".face-score-label");
    const boxRect = box.getBoundingClientRect();
    const labelRect = label.getBoundingClientRect();
    return {
      above: labelRect.bottom <= boxRect.top,
      below: labelRect.top >= boxRect.bottom,
    };
  });
  expect(placement.above || placement.below).toBe(true);
}

async function expectResultPortraitCenterBlue(page) {
  const sample = await page.locator("#resultPortrait img").evaluate(async (image) => {
    if (!image.complete) {
      await new Promise((resolve, reject) => {
        image.onload = resolve;
        image.onerror = reject;
      });
    }
    const canvas = document.createElement("canvas");
    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;
    const context = canvas.getContext("2d");
    context.drawImage(image, 0, 0);
    const [r, g, b] = context.getImageData(Math.floor(canvas.width / 2), Math.floor(canvas.height / 2), 1, 1).data;
    return { r, g, b, width: image.naturalWidth, height: image.naturalHeight };
  });
  expect(sample.width).toBeGreaterThan(10);
  expect(sample.height).toBeGreaterThan(10);
  expect(sample.b).toBeGreaterThan(140);
  expect(sample.r).toBeLessThan(140);
}

async function expectResultPortraitFitsFrame(page) {
  const metrics = await page.locator("#resultPortrait").evaluate((frame) => {
    const image = frame.querySelector("img");
    if (!image) return null;
    const frameRect = frame.getBoundingClientRect();
    const imageRect = image.getBoundingClientRect();
    const style = window.getComputedStyle(image);
    return {
      frameWidth: frameRect.width,
      frameHeight: frameRect.height,
      imageWidth: imageRect.width,
      imageHeight: imageRect.height,
      naturalWidth: image.naturalWidth,
      naturalHeight: image.naturalHeight,
      horizontalFit: imageRect.left >= frameRect.left && imageRect.right <= frameRect.right,
      verticalFit: imageRect.top >= frameRect.top && imageRect.bottom <= frameRect.bottom,
      objectFit: style.objectFit,
    };
  });
  expect(metrics).not.toBeNull();
  expect(metrics.objectFit).toBe("contain");
  expect(metrics.imageWidth).toBeLessThanOrEqual(metrics.frameWidth);
  expect(metrics.imageHeight).toBeLessThanOrEqual(metrics.frameHeight);
  expect(metrics.imageWidth).toBeGreaterThanOrEqual(metrics.frameWidth - 18);
  expect(metrics.imageHeight).toBeGreaterThanOrEqual(metrics.frameHeight - 18);
  expect(metrics.horizontalFit).toBe(true);
  expect(metrics.verticalFit).toBe(true);
}

async function expectTargetSummaryDoesNotOverlapPortrait(page) {
  const metrics = await page.locator(".target-panel").evaluate((panel) => {
    const portrait = panel.querySelector("#resultPortrait");
    const summary = panel.querySelector(".result-summary");
    if (!portrait || !summary) return null;
    const portraitRect = portrait.getBoundingClientRect();
    const summaryRect = summary.getBoundingClientRect();
    return {
      portraitRight: portraitRect.right,
      summaryLeft: summaryRect.left,
      separatedHorizontally: portraitRect.right <= summaryRect.left,
      separatedVertically: portraitRect.bottom <= summaryRect.top || summaryRect.bottom <= portraitRect.top,
    };
  });
  expect(metrics).not.toBeNull();
  expect(metrics.separatedHorizontally || metrics.separatedVertically).toBe(true);
  if (metrics.separatedHorizontally) {
    expect(metrics.summaryLeft - metrics.portraitRight).toBeGreaterThanOrEqual(12);
  }
}

async function expectResultPortraitCropLargerThan(page, minNaturalWidth, minNaturalHeight) {
  const size = await page.locator("#resultPortrait img").evaluate((image) => ({
    naturalWidth: image.naturalWidth,
    naturalHeight: image.naturalHeight,
  }));
  expect(size.naturalWidth).toBeGreaterThan(minNaturalWidth);
  expect(size.naturalHeight).toBeGreaterThan(minNaturalHeight);
}

async function expectResultPortraitCropNearSquare(page) {
  const ratio = await page.locator("#resultPortrait img").evaluate((image) => (
    image.naturalWidth / image.naturalHeight
  ));
  expect(ratio).toBeGreaterThan(0.95);
  expect(ratio).toBeLessThan(1.05);
}

test.describe("GKGuard C2 demo UI", () => {
  test("mock search, route navigation, and reset remain responsive", async ({ page }) => {
    const problems = collectBrowserProblems(page);

    await page.goto("/demo?desktop=1&e2e=mock-flow");
    await expect(page.getByRole("heading", { name: "智能检索" })).toBeVisible();
    await expectHealthyPage(page, problems);

    await page.getByRole("button", { name: /开始检索/ }).click();
    await expect(page.locator("#resultView")).toHaveClass(/is-active/);
    await expect(page.locator("#resultRecordList .record-card")).toHaveCount(5);
    await expect(page.locator("#resultCountBadge")).toHaveText("5 条");
    await expect(page.locator("#toast")).toContainText("已加载 5 条本地模拟记录");
    await expectDesktopRecordListOnLeft(page);
    await expectNoHorizontalOverflow(page);

    await page.getByRole("button", { name: /查看人物路线图/ }).click();
    await expect(page.locator("#routeView")).toHaveClass(/is-active/);
    await expect(page.locator("#routeCurrentRecord")).toContainText("记录1");
    await expect(page.locator("#routeRecordList .record-card")).toHaveCount(5);

    await page.locator("#routeRecordList .record-card").nth(2).click();
    await expect(page.locator("#routeCurrentRecord")).toContainText("记录3");
    await expect(page.locator("#routeCurrentLocation")).toContainText("体育馆东门");

    await page.getByRole("button", { name: /定位时间线/ }).click();
    await expect(page.locator("#routeTimelineRows .timeline-row").first()).toBeVisible();
    await expectNoHorizontalOverflow(page);

    await page.getByRole("button", { name: /返回检索结果/ }).click();
    await expect(page.locator("#resultView")).toHaveClass(/is-active/);

    await page.getByRole("button", { name: /重新上传/ }).first().click();
    await expect(page.locator("#searchView")).toHaveClass(/is-active/);
    await expect(page.locator("#toast")).toContainText("已返回上传页");
    await expectNoHorizontalOverflow(page);
    expect(problems).toEqual([]);
  });

  test("target portrait and source summary stay separated at medium width", async ({ page }) => {
    const problems = collectBrowserProblems(page);

    await page.setViewportSize({ width: 820, height: 920 });
    await page.goto("/demo?desktop=1&e2e=mock-flow");
    await page.getByRole("button", { name: /开始检索/ }).click();
    await expect(page.locator("#resultView")).toHaveClass(/is-active/);
    await expectTargetSummaryDoesNotOverlapPortrait(page);
    await expectNoHorizontalOverflow(page);
    expect(problems).toEqual([]);
  });

  test("CampusVision C1 media result opens the keyframe viewer", async ({ page }) => {
    const problems = collectBrowserProblems(page);
    let searchUrl = "";

    await page.route("**/c1/query-faces", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          source: "c1",
          engine: "e2e-face",
          faceCount: 1,
          queryFaces: [
            {
              index: 0,
              score: 0.96,
              bbox: {
                x1: 0.08,
                y1: 0.1,
                x2: 0.48,
                y2: 0.64,
                width: 0.4,
                height: 0.54,
                leftPct: 8,
                topPct: 10,
                widthPct: 40,
                heightPct: 54,
              },
            },
          ],
        }),
      });
    });

    await page.route("**/c1/search/person-by-image?**", async (route) => {
      searchUrl = route.request().url();
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          source: "c1",
          searchId: "e2e-c1",
          queryFaces: [
            {
              index: 0,
              score: 0.96,
              bbox: { x1: 0.08, y1: 0.1, x2: 0.48, y2: 0.64, width: 0.4, height: 0.54 },
            },
          ],
          selectedQueryFace: {
            index: 0,
            score: 0.96,
            bbox: { x1: 0.08, y1: 0.1, x2: 0.48, y2: 0.64, width: 0.4, height: 0.54 },
          },
          records: [
            {
              id: 1,
              title: "记录1",
              time: "10:12:30",
              fullTime: "2026-06-17 10:12:30",
              location: "教学楼南门",
              camera: "C1-E2E-01 南门摄像机",
              cameraId: "C1-E2E-01",
              similarity: 0.99,
              note: "E2E 关键帧检索结果",
              sceneClass: "scene-1",
              progress: 62,
              frameUrl: "/static/icons/app-mark.png",
              faceUrl: "/static/icons/app-mark.png",
              faceBox: { x1: 180, y1: 150, x2: 290, y2: 276, width: 110, height: 126 },
            },
          ],
          routePoints: [
            { id: 1, time: "10:12:30", location: "教学楼南门", x: 84, y: 24, kind: "start" },
          ],
          person: {
            personId: "P-E2E",
            confidence: "high",
            representativeFaceUrl: "/static/icons/app-mark.png",
          },
        }),
      });
    });

    await page.goto("/demo?desktop=1&e2e=c1-media");
    await expectHealthyPage(page, problems);
    await page.locator("#faceFile").setInputFiles({
      name: "query.png",
      mimeType: "image/png",
      buffer: PNG_BUFFER,
    });

    await expect(page.locator("#resultView")).toHaveClass(/is-active/);
    expect(searchUrl).toContain("query_face_index=0");
    await expect(page.locator("#resultSourceBadge")).toHaveText("CampusVision C1");
    await expect(page.locator("#resultPortrait img")).toHaveAttribute("src", /^data:image\/jpeg/);
    await expect(page.locator("#recordScene.has-frame .scene-frame")).toBeVisible();
    await expect(page.locator("#recordScene .result-face-box")).toContainText("99%");
    await expect(page.locator("#recordScene .result-face-box")).not.toHaveClass(/is-pending/);
    await expectResultFaceBoxAwayFromOrigin(page);
    await expectResultFaceLabelOutsideBox(page);
    await expectDesktopRecordListOnLeft(page);

    await page.locator("#recordScene").click();
    await expect(page.locator("#mediaViewer")).toBeVisible();
    await expect(page.locator("#mediaViewerTitle")).toContainText("记录1");
    await expect(page.locator("#mediaViewer img")).toBeVisible();
    await expect(page.locator("#mediaViewer .result-face-box")).toContainText("99%");

    await page.keyboard.press("Escape");
    await expect(page.locator("#mediaViewer")).toBeHidden();
    await expectNoHorizontalOverflow(page);
    expect(problems).toEqual([]);
  });

  test("unmapped extra route points do not all highlight the last record", async ({ page }) => {
    const problems = collectBrowserProblems(page);
    const records = Array.from({ length: 5 }, (_, index) => ({
      id: index + 1,
      title: `记录${index + 1}`,
      time: `10:1${index}:00`,
      fullTime: `2026-06-17 10:1${index}:00`,
      location: `路线区域${index + 1}`,
      camera: "C1-E2E-01 南门摄像机",
      cameraId: "C1-E2E-01",
      similarity: 0.9 - index * 0.04,
      note: "E2E 无映射路线点",
      sceneClass: `scene-${(index % 5) + 1}`,
      progress: 20 + index * 10,
      frameUrl: "/static/icons/app-mark.png",
      faceUrl: "/static/icons/app-mark.png",
      thumbnailUrl: "/static/icons/app-mark.png",
      faceBox: { x1: 0.2, y1: 0.2, width: 0.34, height: 0.42 },
    }));
    const routePoints = Array.from({ length: 8 }, (_, index) => ({
      id: index + 1,
      time: `10:1${index}:30`,
      location: `路线点${index + 1}`,
      x: 18 + index * 9,
      y: 74 - index * 5,
      kind: index === 0 ? "start" : index === 7 ? "end" : "",
    }));

    await page.route("**/c1/query-faces", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          source: "c1",
          engine: "e2e-face",
          faceCount: 1,
          queryFaces: [{ index: 0, score: 0.96, bbox: { x1: 0.08, y1: 0.1, x2: 0.48, y2: 0.64, width: 0.4, height: 0.54 } }],
        }),
      });
    });

    await page.route("**/c1/search/person-by-image?**", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          source: "c1",
          searchId: "e2e-unmapped-route",
          queryFaces: [{ index: 0, score: 0.96, bbox: { x1: 0.08, y1: 0.1, x2: 0.48, y2: 0.64, width: 0.4, height: 0.54 } }],
          selectedQueryFace: { index: 0, score: 0.96, bbox: { x1: 0.08, y1: 0.1, x2: 0.48, y2: 0.64, width: 0.4, height: 0.54 } },
          records,
          routePoints,
          person: { personId: "P-E2E", confidence: "high", representativeFaceUrl: "/static/icons/app-mark.png" },
        }),
      });
    });

    await page.goto("/demo?desktop=1&e2e=unmapped-route-points");
    await expectHealthyPage(page, problems);
    await page.locator("#faceFile").setInputFiles({
      name: "query.png",
      mimeType: "image/png",
      buffer: PNG_BUFFER,
    });

    await expect(page.locator("#resultView")).toHaveClass(/is-active/);
    await page.getByRole("button", { name: /查看人物路线图/ }).click();
    await expect(page.locator("#routeView")).toHaveClass(/is-active/);
    await page.locator("#routeRecordList .record-card").nth(4).click();
    await expect(page.locator("#routeCurrentRecord")).toContainText("记录5");
    await expect(page.locator("#campusRouteMap .map-point.is-active")).toHaveCount(1);
    await expect(page.locator("#campusRouteMap .map-point.is-active")).toHaveAttribute("data-route-index", "4");
    await expect(page.locator("#routeTimelineRows .timeline-row.is-active")).toHaveCount(1);
    await expect(page.locator("#routeTimelineRows .timeline-row.is-active")).toHaveAttribute("data-route-index", "4");
    await page.locator("#campusRouteMap [data-route-index='6']").click();
    await expect(page.locator("#routeCurrentRecord")).toContainText("记录5");
    await expect(page.locator("#campusRouteMap .map-point.is-active")).toHaveCount(1);
    await expect(page.locator("#campusRouteMap .map-point.is-active")).toHaveAttribute("data-route-index", "6");
    expect(problems).toEqual([]);
  });

  test("duplicate mapped route points keep only the selected marker active", async ({ page }) => {
    const problems = collectBrowserProblems(page);
    const records = [
      {
        id: 1,
        title: "记录1",
        time: "10:00:00",
        fullTime: "2026-06-17 10:00:00",
        location: "一号入口",
        camera: "C1-E2E-01",
        cameraId: "C1-E2E-01",
        similarity: 0.91,
        note: "重复映射测试",
        sceneClass: "scene-1",
        progress: 28,
        frameUrl: "/static/icons/app-mark.png",
        faceUrl: "/static/icons/app-mark.png",
        thumbnailUrl: "/static/icons/app-mark.png",
        faceBox: { x1: 0.2, y1: 0.2, width: 0.34, height: 0.42 },
        eventId: "same-person-a",
      },
      {
        id: 2,
        title: "记录2",
        time: "10:02:00",
        fullTime: "2026-06-17 10:02:00",
        location: "二号入口",
        camera: "C1-E2E-02",
        cameraId: "C1-E2E-02",
        similarity: 0.86,
        note: "重复映射测试",
        sceneClass: "scene-2",
        progress: 52,
        frameUrl: "/static/icons/app-mark.png",
        faceUrl: "/static/icons/app-mark.png",
        thumbnailUrl: "/static/icons/app-mark.png",
        faceBox: { x1: 0.2, y1: 0.2, width: 0.34, height: 0.42 },
        eventId: "same-person-b",
      },
    ];
    const routePoints = [
      { id: 1, time: "10:00:00", location: "一号入口", x: 30, y: 60, kind: "start", recordIndex: 0, eventId: "same-person-a" },
      { id: 2, time: "10:00:20", location: "一号入口补点", x: 42, y: 48, recordIndex: 0, eventId: "same-person-a-extra" },
      { id: 3, time: "10:02:00", location: "二号入口", x: 62, y: 36, kind: "end", recordIndex: 1, eventId: "same-person-b" },
    ];

    await page.route("**/c1/query-faces", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          source: "c1",
          engine: "e2e-face",
          faceCount: 1,
          queryFaces: [{ index: 0, score: 0.96, bbox: { x1: 0.08, y1: 0.1, x2: 0.48, y2: 0.64, width: 0.4, height: 0.54 } }],
        }),
      });
    });

    await page.route("**/c1/search/person-by-image?**", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          source: "c1",
          searchId: "e2e-duplicate-route-points",
          queryFaces: [{ index: 0, score: 0.96, bbox: { x1: 0.08, y1: 0.1, x2: 0.48, y2: 0.64, width: 0.4, height: 0.54 } }],
          selectedQueryFace: { index: 0, score: 0.96, bbox: { x1: 0.08, y1: 0.1, x2: 0.48, y2: 0.64, width: 0.4, height: 0.54 } },
          records,
          routePoints,
          person: { personId: "P-E2E", confidence: "high", representativeFaceUrl: "/static/icons/app-mark.png" },
        }),
      });
    });

    await page.goto("/demo?desktop=1&e2e=duplicate-route-points");
    await expectHealthyPage(page, problems);
    await page.locator("#faceFile").setInputFiles({
      name: "query.png",
      mimeType: "image/png",
      buffer: PNG_BUFFER,
    });

    await expect(page.locator("#resultView")).toHaveClass(/is-active/);
    await page.getByRole("button", { name: /查看人物路线图/ }).click();
    await expect(page.locator("#routeView")).toHaveClass(/is-active/);
    await expect(page.locator("#campusRouteMap .map-point.is-active")).toHaveCount(1);
    await expect(page.locator("#campusRouteMap .map-point.is-active")).toHaveAttribute("data-route-index", "0");

    await page.locator("#campusRouteMap [data-route-index='1']").click();
    await expect(page.locator("#routeCurrentRecord")).toContainText("记录1");
    await expect(page.locator("#campusRouteMap .map-point.is-active")).toHaveCount(1);
    await expect(page.locator("#campusRouteMap .map-point.is-active")).toHaveAttribute("data-route-index", "1");
    await expect(page.locator("#routeTimelineRows .timeline-row.is-active")).toHaveCount(1);
    await expect(page.locator("#routeTimelineRows .timeline-row.is-active")).toHaveAttribute("data-route-index", "1");
    expect(problems).toEqual([]);
  });

  test("records without a matching route point do not highlight the final marker", async ({ page }) => {
    const problems = collectBrowserProblems(page);
    const records = Array.from({ length: 5 }, (_, index) => ({
      id: index + 1,
      title: `记录${index + 1}`,
      time: `10:2${index}:00`,
      fullTime: `2026-06-17 10:2${index}:00`,
      location: `记录区域${index + 1}`,
      camera: "C1-E2E-02",
      cameraId: "C1-E2E-02",
      similarity: 0.88 - index * 0.03,
      note: "缺少路线点映射测试",
      sceneClass: `scene-${(index % 5) + 1}`,
      progress: 24 + index * 10,
      frameUrl: "/static/icons/app-mark.png",
      faceUrl: "/static/icons/app-mark.png",
      thumbnailUrl: "/static/icons/app-mark.png",
      faceBox: { x1: 0.2, y1: 0.2, width: 0.34, height: 0.42 },
    }));
    const routePoints = Array.from({ length: 3 }, (_, index) => ({
      id: index + 1,
      time: `10:2${index}:30`,
      location: `路线点${index + 1}`,
      x: 28 + index * 14,
      y: 66 - index * 8,
      kind: index === 0 ? "start" : index === 2 ? "end" : "",
    }));

    await page.route("**/c1/query-faces", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          source: "c1",
          engine: "e2e-face",
          faceCount: 1,
          queryFaces: [{ index: 0, score: 0.96, bbox: { x1: 0.08, y1: 0.1, x2: 0.48, y2: 0.64, width: 0.4, height: 0.54 } }],
        }),
      });
    });

    await page.route("**/c1/search/person-by-image?**", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          source: "c1",
          searchId: "e2e-record-without-route-point",
          queryFaces: [{ index: 0, score: 0.96, bbox: { x1: 0.08, y1: 0.1, x2: 0.48, y2: 0.64, width: 0.4, height: 0.54 } }],
          selectedQueryFace: { index: 0, score: 0.96, bbox: { x1: 0.08, y1: 0.1, x2: 0.48, y2: 0.64, width: 0.4, height: 0.54 } },
          records,
          routePoints,
          person: { personId: "P-E2E", confidence: "high", representativeFaceUrl: "/static/icons/app-mark.png" },
        }),
      });
    });

    await page.goto("/demo?desktop=1&e2e=record-without-route-point");
    await expectHealthyPage(page, problems);
    await page.locator("#faceFile").setInputFiles({
      name: "query.png",
      mimeType: "image/png",
      buffer: PNG_BUFFER,
    });

    await expect(page.locator("#resultView")).toHaveClass(/is-active/);
    await page.getByRole("button", { name: /查看人物路线图/ }).click();
    await expect(page.locator("#routeView")).toHaveClass(/is-active/);
    await page.locator("#routeRecordList .record-card").nth(4).click();
    await expect(page.locator("#routeCurrentRecord")).toContainText("记录5");
    await expect(page.locator("#campusRouteMap .map-point.is-active")).toHaveCount(0);
    await expect(page.locator("#routeTimelineRows .timeline-row.is-active")).toHaveCount(0);
    expect(problems).toEqual([]);
  });

  test("CampusVision C1 attribute search renders event results", async ({ page }) => {
    const problems = collectBrowserProblems(page);
    let requestPayload = null;

    await page.route("**/c1/query/person-attributes", async (route) => {
      requestPayload = route.request().postDataJSON();
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          source: "c1",
          mode: "person-attributes",
          searchId: "e2e-attribute",
          warning: null,
          person: {
            confidence: "attribute",
            representativeFaceUrl: "/static/icons/app-mark.png",
          },
          records: [
            {
              id: 1,
              title: "记录1",
              time: "11:20:30",
              fullTime: "2026-06-18 11:20:30",
              location: "图书馆大厅",
              camera: "C1-ATTR-01 图书馆摄像机",
              cameraId: "C1-ATTR-01",
              similarity: 0.82,
              note: "上衣颜色：blue；眼镜状态：佩戴眼镜",
              sceneClass: "scene-1",
              progress: 48,
              frameUrl: "/static/icons/app-mark.png",
              faceUrl: "/static/icons/app-mark.png",
              thumbnailUrl: "/static/icons/app-mark.png",
              personBox: { x1: 0.2, y1: 0.2, width: 0.34, height: 0.42 },
              eventId: "later-high-score",
              attributes: {
                upperColor: "blue",
                glassesStatus: "glasses",
                genderPresentation: "masculine",
                bodyVisibility: "upper",
              },
            },
            {
              id: 2,
              title: "记录2",
              time: "08:15:00",
              fullTime: "2026-06-18 08:15:00",
              location: "教学楼入口",
              camera: "C1-ATTR-02 教学楼摄像机",
              cameraId: "C1-ATTR-02",
              similarity: 0.48,
              note: "上衣颜色：blue；眼镜状态：佩戴眼镜",
              sceneClass: "scene-2",
              progress: 22,
              frameUrl: "/static/icons/app-mark.png",
              faceUrl: "/static/icons/app-mark.png",
              thumbnailUrl: "/static/icons/app-mark.png",
              faceBox: { x1: 0.18, y1: 0.18, width: 0.32, height: 0.4 },
              eventId: "earlier-low-score",
              attributes: {
                upperColor: "blue",
                glassesStatus: "glasses",
                genderPresentation: "masculine",
                bodyVisibility: "upper",
              },
            },
          ],
          routePoints: [
            { id: 1, time: "08:15:00", location: "教学楼入口", x: 36, y: 58, kind: "start", recordIndex: 1, eventId: "earlier-low-score" },
            { id: 2, time: "11:20:30", location: "图书馆大厅", x: 52, y: 33, kind: "end", recordIndex: 0, eventId: "later-high-score" },
          ],
          raw: {},
        }),
      });
    });

    await page.goto("/demo?desktop=1&e2e=attribute-search");
    await expectHealthyPage(page, problems);
    await expect(page.locator(".search-mode-tabs")).toHaveCount(0);
    const defaultRange = await page.evaluate(() => {
      const pad = (value) => String(value).padStart(2, "0");
      const today = new Date();
      const day = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;
      return { start: `${day}T00:00`, end: `${day}T23:59` };
    });
    await expect(page.locator("#startTime")).toHaveValue(defaultRange.start);
    await expect(page.locator("#endTime")).toHaveValue(defaultRange.end);
    await expect(page.locator("#attributeStartTime")).toHaveValue(defaultRange.start);
    await expect(page.locator("#attributeEndTime")).toHaveValue(defaultRange.end);
    await page.locator("#endTime").evaluate((input) => {
      input.value = "202500-01-31T06:52";
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await expect(page.locator("#endTime")).toHaveValue("2025-01-31T06:52");
    await page.getByRole("button", { name: "人物特征搜索" }).click();
    await page.locator("#upperColorFilter").selectOption("blue");
    await page.locator("#glassesStatusFilter").selectOption("glasses");
    await page.locator("#genderPresentationFilter").selectOption("masculine");
    await page.locator("#attributeCameraFilter").fill("C1-ATTR-01");
    await page.locator("#attributePersonScope").selectOption("all");
    await page.locator("#attributeMinScore").fill("0.4");
    await page.locator("#attributeLimit").fill("8");
    await page.locator("#startAttributeSearchBtn").click();

    await expect(page.locator("#resultView")).toHaveClass(/is-active/);
    expect(requestPayload.upper_colors).toEqual(["blue"]);
    expect(requestPayload.glasses_status).toEqual(["glasses"]);
    expect(requestPayload.gender_presentation).toEqual(["masculine"]);
    expect(requestPayload.camera_ids).toEqual(["C1-ATTR-01"]);
    expect(requestPayload.person_scope).toBe("all");
    expect(requestPayload.include_candidates).toBe(true);
    expect(requestPayload.candidate_pool_size).toBe(5000);
    expect(requestPayload.time_range).toBeNull();
    expect(requestPayload.min_score).toBe(0.4);
    expect(requestPayload.limit).toBe(8);
    await expect(page.locator("#resultViewTitle")).toHaveText("人物特征搜索结果");
    await expect(page.locator("#resultSourceBadge")).toHaveText("CampusVision C1 · 特征搜索");
    await expect(page.locator("#recordTitle")).toHaveText("记录1");
    await expect(page.locator("#recordInfo")).toContainText("上衣颜色");
    await expect(page.locator("#recordInfo")).toContainText("佩戴眼镜");
    await expect(page.locator("#recordScene.has-frame .scene-frame")).toBeVisible();
    await expect(page.locator("#recordScene .result-face-box")).toBeVisible();
    await page.locator("#openCandidatesBtn").click();
    await expect(page.locator("#candidateDrawer")).toHaveClass(/is-visible/);
    await expect(page.locator("#candidateList .candidate-card")).toHaveCount(3);
    await page.locator("#candidateDrawerClose").click();
    await page.locator("#openEventDetailBtn").click();
    await expect(page.locator("#eventDetailDrawer")).toHaveClass(/is-visible/);
    await expect(page.locator("#eventDetailDrawer .event-detail-row").first()).toContainText("出现时间：");
    await page.getByRole("button", { name: "在主视图定位现场图" }).click();
    await expect(page.locator("#eventDetailDrawer")).toBeHidden();
    await page.getByRole("button", { name: /查看人物路线图/ }).click();
    await expect(page.locator("#routeView")).toHaveClass(/is-active/);
    await page.locator("#routeTimelineRows .timeline-row").first().click();
    await expect(page.locator("#routeCurrentRecord")).toContainText("记录2");
    await expect(page.locator("#routeCurrentLocation")).toContainText("教学楼入口");
    await expectNoHorizontalOverflow(page);
    expect(problems).toEqual([]);
  });

  test("attribute route defaults to a plotted record when top score is not routed", async ({ page }) => {
    const problems = collectBrowserProblems(page);
    const records = Array.from({ length: 10 }, (_, index) => ({
      id: index + 1,
      title: `记录${index + 1}`,
      time: `09:${String(index).padStart(2, "0")}:00`,
      fullTime: `2026-06-18 09:${String(index).padStart(2, "0")}:00`,
      location: `摄像头区域${index + 1}`,
      camera: "C1-ATTR-01 图书馆摄像机",
      cameraId: "C1-ATTR-01",
      similarity: 0.95 - index * 0.04,
      note: "上衣颜色：blue",
      sceneClass: `scene-${(index % 5) + 1}`,
      progress: 18 + index * 6,
      frameUrl: "/static/icons/app-mark.png",
      faceUrl: "/static/icons/app-mark.png",
      thumbnailUrl: "/static/icons/app-mark.png",
      faceBox: { x1: 0.2, y1: 0.2, width: 0.34, height: 0.42 },
      eventId: `event-${index + 1}`,
      attributes: { upperColor: "blue", glassesStatus: "unknown" },
    }));

    await page.route("**/c1/query/person-attributes", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          source: "c1",
          mode: "person-attributes",
          searchId: "e2e-attribute-route-gap",
          warning: null,
          person: { confidence: "attribute", representativeFaceUrl: "/static/icons/app-mark.png" },
          records,
          routePoints: [
            { id: 1, time: "09:09:00", location: "摄像头区域10", x: 22, y: 68, kind: "start", recordIndex: 9, eventId: "event-10" },
            { id: 2, time: "09:08:00", location: "摄像头区域9", x: 36, y: 52, recordIndex: 8, eventId: "event-9" },
            { id: 3, time: "09:07:00", location: "摄像头区域8", x: 48, y: 44, kind: "end", recordIndex: 7, eventId: "event-8" },
          ],
          raw: {},
        }),
      });
    });

    await page.goto("/demo?desktop=1&e2e=attribute-route-gap");
    await expectHealthyPage(page, problems);
    await page.getByRole("button", { name: "人物特征搜索" }).click();
    await page.locator("#upperColorFilter").selectOption("blue");
    await page.locator("#startAttributeSearchBtn").click();

    await expect(page.locator("#resultView")).toHaveClass(/is-active/);
    await expect(page.locator("#recordTitle")).toHaveText("记录10");
    await page.locator("#resultRecordList .record-card").first().click();
    await expect(page.locator("#recordTitle")).toHaveText("记录1");
    await page.locator("#openEventDetailBtn").click();
    await expect(page.locator("#eventDetailDrawer")).toHaveClass(/is-visible/);
    await page.getByRole("button", { name: "在主视图定位现场图" }).click();
    await expect(page.locator("#eventDetailDrawer")).toBeHidden();
    await expect(page.locator("#recordTitle")).toHaveText("记录1");
    await page.getByRole("button", { name: /查看人物路线图/ }).click();
    await expect(page.locator("#routeView")).toHaveClass(/is-active/);
    await expect(page.locator("#routeCurrentRecord")).toContainText("记录1");
    await expect(page.locator("#routeTimelineRows .timeline-row.is-active")).toHaveCount(0);
    await expectNoHorizontalOverflow(page);
    expect(problems).toEqual([]);
  });

  test("record switching keeps the current keyframe until the next keyframe is ready", async ({ page }) => {
    const problems = collectBrowserProblems(page);
    let releaseSecondFrame;
    const secondFrameGate = new Promise((resolve) => { releaseSecondFrame = resolve; });

    await page.route("**/c1/query-faces", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          source: "c1",
          engine: "e2e-face",
          faceCount: 1,
          queryFaces: [
            { index: 0, score: 0.96, bbox: { x1: 0.08, y1: 0.1, x2: 0.48, y2: 0.64, width: 0.4, height: 0.54 } },
          ],
        }),
      });
    });

    await page.route("**/c1/search/person-by-image?**", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          source: "c1",
          searchId: "e2e-frame-switch",
          selectedQueryFace: { index: 0, score: 0.96, bbox: { x1: 0.08, y1: 0.1, x2: 0.48, y2: 0.64, width: 0.4, height: 0.54 } },
          records: [
            {
              id: 1,
              title: "记录1",
              time: "10:12:30",
              fullTime: "2026-06-17 10:12:30",
              location: "教学楼南门",
              camera: "C1-E2E-01 南门摄像机",
              cameraId: "C1-E2E-01",
              similarity: 0.99,
              note: "E2E 第一张关键帧",
              sceneClass: "scene-1",
              progress: 32,
              frameUrl: "/e2e/frame-one.svg",
              faceUrl: "/static/icons/app-mark.png",
              faceBox: { x1: 90, y1: 70, x2: 160, y2: 150, width: 70, height: 80 },
            },
            {
              id: 2,
              title: "记录2",
              time: "10:14:30",
              fullTime: "2026-06-17 10:14:30",
              location: "图书馆入口",
              camera: "C1-E2E-02 图书馆摄像机",
              cameraId: "C1-E2E-02",
              similarity: 0.94,
              note: "E2E 延迟关键帧",
              sceneClass: "scene-2",
              progress: 54,
              frameUrl: "/e2e/frame-two.svg",
              faceUrl: "/static/icons/app-mark.png",
              faceBox: { x1: 220, y1: 90, x2: 290, y2: 170, width: 70, height: 80 },
            },
          ],
          routePoints: [],
        }),
      });
    });

    await page.route("**/e2e/frame-one.svg", async (route) => {
      await route.fulfill({
        contentType: "image/svg+xml",
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="240"><rect width="400" height="240" fill="#2563eb"/><text x="160" y="126" fill="white" font-size="28">one</text></svg>',
      });
    });

    await page.route("**/e2e/frame-two.svg", async (route) => {
      await secondFrameGate;
      await route.fulfill({
        contentType: "image/svg+xml",
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="240"><rect width="400" height="240" fill="#16a34a"/><text x="160" y="126" fill="white" font-size="28">two</text></svg>',
      });
    });

    await page.goto("/demo?desktop=1&e2e=frame-switch");
    await expectHealthyPage(page, problems);
    await page.locator("#faceFile").setInputFiles({
      name: "query.png",
      mimeType: "image/png",
      buffer: PNG_BUFFER,
    });

    await expect(page.locator("#resultView")).toHaveClass(/is-active/);
    await expect(page.locator("#recordScene .scene-frame")).toHaveAttribute("src", /frame-one\.svg$/);

    await page.locator("#resultRecordList .record-card").nth(1).click();
    await expect(page.locator("#recordTitle")).toHaveText("记录2");
    await expect(page.locator("#recordScene")).toHaveClass(/is-frame-loading/);
    await expect(page.locator("#recordScene .scene-frame")).toHaveAttribute("src", /frame-one\.svg$/);

    await page.locator("#resultRecordList .record-card").nth(0).click();
    await expect(page.locator("#recordTitle")).toHaveText("记录1");
    await expect(page.locator("#recordScene")).not.toHaveClass(/is-frame-loading/);
    await expect(page.locator("#recordScene .scene-frame")).toHaveAttribute("src", /frame-one\.svg$/);

    releaseSecondFrame();
    await page.waitForTimeout(150);
    await expect(page.locator("#recordTitle")).toHaveText("记录1");
    await expect(page.locator("#recordScene .scene-frame")).toHaveAttribute("src", /frame-one\.svg$/);
    await expect(page.locator("#recordScene .result-face-box")).toContainText("99%");

    await page.locator("#resultRecordList .record-card").nth(1).click();
    await expect(page.locator("#recordTitle")).toHaveText("记录2");
    await expect(page.locator("#recordScene .scene-frame")).toHaveAttribute("src", /frame-two\.svg$/);
    await expect(page.locator("#recordScene")).not.toHaveClass(/is-frame-loading/);
    await expect(page.locator("#recordScene .result-face-box")).toContainText("94%");
    expect(problems).toEqual([]);
  });

  test("single low-confidence query face portrait crop is padded and fills the target frame", async ({ page }) => {
    const problems = collectBrowserProblems(page);
    let searchUrl = "";

    await page.route("**/c1/query-faces", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          source: "c1",
          engine: "e2e-face",
          faceCount: 1,
          queryFaces: [
            {
              index: 0,
              score: 0.51,
              imageWidth: 300,
              imageHeight: 300,
              bbox: {
                x1: 115,
                y1: 104,
                x2: 185,
                y2: 188,
                width: 70,
                height: 84,
              },
            },
          ],
        }),
      });
    });

    await page.route("**/c1/search/person-by-image?**", async (route) => {
      searchUrl = route.request().url();
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          source: "c1",
          searchId: "e2e-single-low-confidence",
          warning: "Low confidence match, manual confirmation recommended.",
          selectedQueryFace: { index: 0, score: 0.51, imageWidth: 300, imageHeight: 300, bbox: { x1: 115, y1: 104, x2: 185, y2: 188, width: 70, height: 84 } },
          records: [
            {
              id: 1,
              title: "记录1",
              time: "11:08:12",
              fullTime: "2026-06-17 11:08:12",
              location: "图书馆入口",
              camera: "C1-E2E-03 图书馆摄像机",
              cameraId: "C1-E2E-03",
              similarity: 0.51,
              note: "E2E 单人低置信检索结果",
              sceneClass: "scene-2",
              progress: 48,
              frameUrl: "/static/icons/app-mark.png",
              faceUrl: "/static/icons/app-mark.png",
              faceBox: { x1: 26, y1: 22, x2: 72, y2: 78, width: 46, height: 56 },
            },
          ],
          routePoints: [
            { id: 1, time: "11:08:12", location: "图书馆入口", x: 52, y: 38, kind: "start" },
          ],
          person: {
            personId: "P-E2E-low",
            confidence: "low",
            representativeFaceUrl: "/static/icons/app-mark.png",
          },
        }),
      });
    });

    await page.goto("/demo?desktop=1&e2e=c1-single-low-confidence");
    await expectHealthyPage(page, problems);
    await page.locator("#faceFile").setInputFiles({
      name: "query-single-low.svg",
      mimeType: "image/svg+xml",
      buffer: PORTRAIT_QUERY_IMAGE,
    });

    await expect(page.locator("#resultView")).toHaveClass(/is-active/);
    expect(searchUrl).toContain("query_face_index=0");
    await expect(page.locator("#toast")).toContainText("需要人工确认");
    await expect(page.locator("#resultPortrait img")).toBeVisible();
    await expectResultPortraitFitsFrame(page);
    await expectResultPortraitCropLargerThan(page, 70, 84);
    await expectResultPortraitCropNearSquare(page);
    await expectNoHorizontalOverflow(page);
    expect(problems).toEqual([]);
  });

  test("multiple query faces require selecting a boxed face before C1 search", async ({ page }) => {
    const problems = collectBrowserProblems(page);
    let searchUrl = "";

    await page.route("**/c1/query-faces", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          source: "c1",
          engine: "e2e-face",
          faceCount: 3,
          queryFaces: [
            {
              index: 0,
              score: 0.52,
              imageWidth: 1000,
              imageHeight: 500,
              bbox: {
                x1: 30,
                y1: 40,
                x2: 180,
                y2: 150,
                width: 150,
                height: 110,
              },
            },
            {
              index: 1,
              score: 0.91,
              imageWidth: 1000,
              imageHeight: 500,
              bbox: {
                x1: 80,
                y1: 160,
                x2: 340,
                y2: 420,
                width: 260,
                height: 260,
              },
            },
            {
              index: 2,
              score: 0.89,
              imageWidth: 1000,
              imageHeight: 500,
              bbox: {
                x1: 580,
                y1: 90,
                x2: 900,
                y2: 360,
                width: 320,
                height: 270,
              },
            },
          ],
        }),
      });
    });

    await page.route("**/c1/search/person-by-image?**", async (route) => {
      searchUrl = route.request().url();
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          source: "c1",
          searchId: "e2e-c1-multi",
          queryFaces: [
            { index: 0, score: 0.52, imageWidth: 1000, imageHeight: 500, bbox: { x1: 30, y1: 40, x2: 180, y2: 150, width: 150, height: 110 } },
            { index: 1, score: 0.91, imageWidth: 1000, imageHeight: 500, bbox: { x1: 80, y1: 160, x2: 340, y2: 420, width: 260, height: 260 } },
            { index: 2, score: 0.89, imageWidth: 1000, imageHeight: 500, bbox: { x1: 580, y1: 90, x2: 900, y2: 360, width: 320, height: 270 } },
          ],
          selectedQueryFace: { index: 2, score: 0.89, imageWidth: 1000, imageHeight: 500, bbox: { x1: 580, y1: 90, x2: 900, y2: 360, width: 320, height: 270 } },
          records: [
            {
              id: 1,
              title: "记录1",
              time: "11:08:12",
              fullTime: "2026-06-17 11:08:12",
              location: "图书馆入口",
              camera: "C1-E2E-02 图书馆摄像机",
              cameraId: "C1-E2E-02",
              similarity: 0.88,
              note: "E2E 多人查询图检索结果",
              sceneClass: "scene-2",
              progress: 48,
              frameUrl: "/static/icons/app-mark.png",
              faceUrl: "/static/icons/app-mark.png",
              faceBox: { x1: 26, y1: 22, x2: 72, y2: 78, width: 46, height: 56 },
            },
          ],
          routePoints: [
            { id: 1, time: "11:08:12", location: "图书馆入口", x: 52, y: 38, kind: "start" },
          ],
          person: {
            personId: "P-E2E-2",
            confidence: "medium",
            representativeFaceUrl: "/static/icons/app-mark.png",
          },
        }),
      });
    });

    await page.goto("/demo?desktop=1&e2e=c1-multi-face");
    await expectHealthyPage(page, problems);
    await page.locator("#faceFile").setInputFiles({
      name: "query-multi.svg",
      mimeType: "image/svg+xml",
      buffer: COLOR_QUERY_IMAGE,
    });

    await expect(page.locator("#queryFaceModal")).toBeVisible();
    await expect(page.locator("#uploadDrop [data-query-face-index]")).toHaveCount(3);
    await expect(page.locator('#uploadDrop [data-query-face-index="0"]')).toHaveClass(/is-low-confidence/);
    await expect(page.locator("#queryFaceModalFrame [data-query-face-index]")).toHaveCount(3);
    await expect(page.locator("#searchView")).toHaveClass(/is-active/);
    await page.locator("#queryFaceModalCancel").click();
    await expect(page.locator("#queryFaceModal")).toBeHidden();
    await expect(page.locator("#openQueryFaceModalBtn")).toBeVisible();
    const chooserPromise = page.waitForEvent("filechooser");
    await page.locator(".upload-action").click();
    await chooserPromise;
    await expect(page.locator("#queryFaceModal")).toBeHidden();
    await page.locator("#openQueryFaceModalBtn").click();
    await expect(page.locator("#queryFaceModal")).toBeVisible();
    const fitMetrics = await page.locator("#queryFaceModalFrame").evaluate((frame) => {
      const wrap = frame.querySelector(".face-select-image-wrap");
      return {
        frameWidth: frame.clientWidth,
        frameHeight: frame.clientHeight,
        wrapWidth: wrap?.getBoundingClientRect().width || 0,
        wrapHeight: wrap?.getBoundingClientRect().height || 0,
        scrollWidth: frame.scrollWidth,
        scrollHeight: frame.scrollHeight,
      };
    });
    expect(fitMetrics.wrapWidth).toBeLessThanOrEqual(fitMetrics.frameWidth);
    expect(fitMetrics.wrapHeight).toBeLessThanOrEqual(fitMetrics.frameHeight);
    expect(fitMetrics.scrollWidth).toBeLessThanOrEqual(fitMetrics.frameWidth + 2);
    expect(fitMetrics.scrollHeight).toBeLessThanOrEqual(fitMetrics.frameHeight + 2);
    await page.locator("#queryFaceZoomOut").click();
    const smallerWidth = await page.locator("#queryFaceModalFrame .face-select-image-wrap").evaluate((wrap) => wrap.getBoundingClientRect().width);
    expect(smallerWidth).toBeLessThan(fitMetrics.wrapWidth);
    await page.locator("#queryFaceZoomReset").click();
    const resetMetrics = await page.locator("#queryFaceModalFrame").evaluate((frame) => {
      const wrap = frame.querySelector(".face-select-image-wrap");
      return {
        frameWidth: frame.clientWidth,
        frameHeight: frame.clientHeight,
        wrapWidth: wrap?.getBoundingClientRect().width || 0,
        wrapHeight: wrap?.getBoundingClientRect().height || 0,
        scrollWidth: frame.scrollWidth,
        scrollHeight: frame.scrollHeight,
      };
    });
    expect(Math.abs(resetMetrics.wrapWidth - fitMetrics.wrapWidth)).toBeLessThanOrEqual(2);
    expect(resetMetrics.wrapWidth).toBeLessThanOrEqual(resetMetrics.frameWidth);
    expect(resetMetrics.wrapHeight).toBeLessThanOrEqual(resetMetrics.frameHeight);
    expect(resetMetrics.scrollWidth).toBeLessThanOrEqual(resetMetrics.frameWidth + 2);
    expect(resetMetrics.scrollHeight).toBeLessThanOrEqual(resetMetrics.frameHeight + 2);
    const modalFace = page.locator('#queryFaceModalFrame [data-query-face-index="2"]');
    const modalFaceBox = await modalFace.boundingBox();
    expect(modalFaceBox).not.toBeNull();
    await page.mouse.click(modalFaceBox.x + modalFaceBox.width / 2, modalFaceBox.y + modalFaceBox.height / 2);
    await expect(modalFace).toHaveClass(/is-selected/);

    await page.locator("#queryFaceModalConfirm").click();
    await expect(page.locator("#resultView")).toHaveClass(/is-active/);
    await expect(page.locator("#queryFaceModal")).toBeHidden();
    expect(searchUrl).toContain("query_face_index=2");
    await expect(page.locator("#resultPortrait img")).toBeVisible();
    await expect(page.locator("#resultPortrait img")).toHaveAttribute("src", /^data:image\/jpeg/);
    await expectResultPortraitCenterBlue(page);
    await expectResultPortraitFitsFrame(page);
    await expectResultPortraitCropLargerThan(page, 32, 27);
    await expect(page.locator("#recordScene .result-face-box")).toContainText("88%");
    await expectDesktopRecordListOnLeft(page);
    await expectNoHorizontalOverflow(page);
    expect(problems).toEqual([]);
  });

  test("C1 no-match response returns to an idle upload state", async ({ page }) => {
    const problems = collectBrowserProblems(page);
    let searchCalls = 0;

    await page.route("**/c1/query-faces", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          source: "c1",
          engine: "e2e-face",
          faceCount: 1,
          queryFaces: [
            {
              index: 0,
              score: 0.91,
              bbox: {
                x1: 0.18,
                y1: 0.18,
                x2: 0.52,
                y2: 0.62,
                width: 0.34,
                height: 0.44,
                leftPct: 18,
                topPct: 18,
                widthPct: 34,
                heightPct: 44,
              },
            },
          ],
        }),
      });
    });

    await page.route("**/c1/search/person-by-image?**", async (route) => {
      searchCalls += 1;
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          source: "c1",
          searchId: "e2e-no-match",
          warning: "No person matched the requested minimum score.",
          queryFaces: [
            { index: 0, score: 0.91, bbox: { x1: 0.18, y1: 0.18, x2: 0.52, y2: 0.62, width: 0.34, height: 0.44 } },
          ],
          selectedQueryFace: { index: 0, score: 0.91, bbox: { x1: 0.18, y1: 0.18, x2: 0.52, y2: 0.62, width: 0.34, height: 0.44 } },
          records: [],
          routePoints: [],
          person: {},
        }),
      });
    });

    await page.goto("/demo?desktop=1&e2e=c1-no-match");
    await expectHealthyPage(page, problems);
    await page.locator("#faceFile").setInputFiles({
      name: "query-no-match.png",
      mimeType: "image/png",
      buffer: PNG_BUFFER,
    });

    await expect(page.locator("#searchView")).toHaveClass(/is-active/);
    await expect(page.locator("#resultView")).not.toHaveClass(/is-active/);
    await expect(page.locator("#toast")).toContainText("未找到达到相似度阈值的人员");
    await expect(page.locator("#toast")).not.toContainText("No person matched");
    await expect(page.getByRole("button", { name: /开始检索/ })).toBeEnabled();
    expect(searchCalls).toBe(1);
    await expectNoHorizontalOverflow(page);
    expect(problems).toEqual([]);
  });

  test("C1 search timeout returns to an idle upload state", async ({ page }) => {
    const problems = collectBrowserProblems(page);
    let searchCalls = 0;

    await page.route("**/static/app.js?**", async (route) => {
      const response = await route.fetch();
      const body = (await response.text())
        .replace("const C1_QUERY_FACE_TIMEOUT_MS = 15000;", "const C1_QUERY_FACE_TIMEOUT_MS = 600;")
        .replace("const C1_SEARCH_TIMEOUT_MS = 25000;", "const C1_SEARCH_TIMEOUT_MS = 600;")
        .replace("const SEARCH_WATCHDOG_TIMEOUT_MS = 30000;", "const SEARCH_WATCHDOG_TIMEOUT_MS = 900;");
      await route.fulfill({ response, body });
    });

    await page.route("**/c1/query-faces", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          source: "c1",
          engine: "e2e-face",
          faceCount: 1,
          queryFaces: [
            {
              index: 0,
              score: 0.93,
              bbox: {
                x1: 0.18,
                y1: 0.18,
                x2: 0.52,
                y2: 0.62,
                width: 0.34,
                height: 0.44,
                leftPct: 18,
                topPct: 18,
                widthPct: 34,
                heightPct: 44,
              },
            },
          ],
        }),
      });
    });

    await page.route("**/c1/search/person-by-image?**", async (route) => {
      searchCalls += 1;
      await new Promise((resolve) => setTimeout(resolve, 1600));
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ records: [] }),
      }).catch(() => {});
    });

    await page.goto("/demo?desktop=1&e2e=c1-timeout");
    await expectHealthyPage(page, problems);
    await page.locator("#faceFile").setInputFiles({
      name: "query-timeout.png",
      mimeType: "image/png",
      buffer: PNG_BUFFER,
    });

    await expect(page.locator("#searchView")).toHaveClass(/is-active/, { timeout: 5000 });
    await expect(page.locator("#resultView")).not.toHaveClass(/is-active/);
    await expect(page.locator("#toast")).toContainText("响应超时", { timeout: 5000 });
    await expect(page.getByRole("button", { name: /开始检索|重新检测人脸/ })).toBeEnabled();
    expect(searchCalls).toBe(1);
    await expectNoHorizontalOverflow(page);
    expect(problems).toEqual([]);
  });

  test("query face detection failure does not show false search results", async ({ page }) => {
    const problems = collectBrowserProblems(page);
    let searchCalls = 0;

    await page.route("**/c1/query-faces", async (route) => {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: { message: "query face detection unavailable" } }),
      });
    });

    await page.route("**/c1/search/person-by-image?**", async (route) => {
      searchCalls += 1;
      await route.abort();
    });

    await page.goto("/demo?desktop=1&e2e=query-face-failure");
    await expectHealthyPage(page, problems);
    await page.locator("#faceFile").setInputFiles({
      name: "query-failure.png",
      mimeType: "image/png",
      buffer: PNG_BUFFER,
    });

    await expect(page.locator("#searchView")).toHaveClass(/is-active/);
    await expect(page.locator("#toast")).toContainText("人脸检测暂不可用");
    await page.getByRole("button", { name: /重新检测人脸|开始检索/ }).click();
    await expect(page.locator("#searchView")).toHaveClass(/is-active/);
    await expect(page.locator("#resultView")).not.toHaveClass(/is-active/);
    await expect(page.locator("#toast")).toContainText("未执行检索");
    expect(searchCalls).toBe(0);
    await expectNoHorizontalOverflow(page);
    expect(problems.filter((problem) => !problem.includes("status of 503"))).toEqual([]);
  });

  test("bad query image response does not trigger desktop C1 reconnect", async ({ page }) => {
    const problems = collectBrowserProblems(page);
    let searchCalls = 0;

    await page.addInitScript(() => {
      window.__connectC1Calls = 0;
      window.gkguardDesktop = {
        getAppInfo: async () => ({ version: "0.2.3" }),
        checkForUpdates: async () => ({ updateAvailable: false, currentVersion: "0.2.3" }),
        downloadUpdate: async () => ({ embedded: true }),
        installUpdate: async () => ({}),
        onUpdateEvent: () => () => {},
        onSshConnectProgress: () => () => {},
        submitSshPassword: () => {},
        cancelSshPassword: () => {},
        connectC1: async () => {
          window.__connectC1Calls += 1;
          return { connected: true, prompted: true };
        },
      };
    });

    await page.route("**/c1/query-faces", async (route) => {
      await route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({
          detail: {
            code: "C1_VALIDATION_ERROR",
            message: "Uploaded query image could not be decoded.",
          },
        }),
      });
    });

    await page.route("**/c1/search/person-by-image?**", async (route) => {
      searchCalls += 1;
      await route.abort();
    });

    await page.goto("/demo?desktop=1&e2e=query-face-bad-image");
    await expectHealthyPage(page, problems);
    await page.locator("#faceFile").setInputFiles({
      name: "query-bad.png",
      mimeType: "image/png",
      buffer: PNG_BUFFER,
    });

    await expect(page.locator("#searchView")).toHaveClass(/is-active/);
    await expect(page.locator("#resultView")).not.toHaveClass(/is-active/);
    await expect(page.locator("#toast")).toContainText("上传图片无法解码");
    await page.getByRole("button", { name: /重新检测人脸|开始检索/ }).click();
    await expect(page.locator("#searchView")).toHaveClass(/is-active/);
    await expect(page.locator("#resultView")).not.toHaveClass(/is-active/);
    await expect(page.locator("#toast")).toContainText("未执行检索");
    const connectCalls = await page.evaluate(() => window.__connectC1Calls || 0);
    expect(connectCalls).toBe(0);
    expect(searchCalls).toBe(0);
    await expectNoHorizontalOverflow(page);
    expect(problems.filter((problem) => !problem.includes("status of 400"))).toEqual([]);
  });

  test("person image search validation error does not trigger desktop C1 reconnect", async ({ page }) => {
    const problems = collectBrowserProblems(page);

    await page.addInitScript(() => {
      window.__connectC1Calls = 0;
      window.gkguardDesktop = {
        getAppInfo: async () => ({ version: "0.2.3" }),
        checkForUpdates: async () => ({ updateAvailable: false, currentVersion: "0.2.3" }),
        downloadUpdate: async () => ({ embedded: true }),
        installUpdate: async () => ({}),
        onUpdateEvent: () => () => {},
        onSshConnectProgress: () => () => {},
        submitSshPassword: () => {},
        cancelSshPassword: () => {},
        connectC1: async () => {
          window.__connectC1Calls += 1;
          return { connected: true, prompted: true };
        },
      };
    });

    await page.route("**/c1/query-faces", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          source: "c1",
          engine: "e2e-face",
          faceCount: 1,
          queryFaces: [{ index: 0, score: 0.96, bbox: { x1: 0.08, y1: 0.1, x2: 0.48, y2: 0.64, width: 0.4, height: 0.54 } }],
        }),
      });
    });

    await page.route("**/c1/search/person-by-image?**", async (route) => {
      await route.fulfill({
        status: 413,
        contentType: "application/json",
        body: JSON.stringify({
          detail: {
            code: "C1_PAYLOAD_TOO_LARGE",
            message: "Query image payload too large.",
          },
        }),
      });
    });

    await page.goto("/demo?desktop=1&e2e=search-validation-error");
    await expectHealthyPage(page, problems);
    await page.locator("#faceFile").setInputFiles({
      name: "query-too-large.png",
      mimeType: "image/png",
      buffer: PNG_BUFFER,
    });

    await expect(page.locator("#searchView")).toHaveClass(/is-active/);
    await expect(page.locator("#resultView")).not.toHaveClass(/is-active/);
    await expect(page.locator("#toast")).toContainText("上传图片过大");
    const connectCalls = await page.evaluate(() => window.__connectC1Calls || 0);
    expect(connectCalls).toBe(0);
    await expectNoHorizontalOverflow(page);
    expect(problems.filter((problem) => !problem.includes("status of 413"))).toEqual([]);
  });

  test("attribute search validation error does not trigger desktop C1 reconnect", async ({ page }) => {
    const problems = collectBrowserProblems(page);

    await page.addInitScript(() => {
      window.__connectC1Calls = 0;
      window.gkguardDesktop = {
        getAppInfo: async () => ({ version: "0.2.3" }),
        checkForUpdates: async () => ({ updateAvailable: false, currentVersion: "0.2.3" }),
        downloadUpdate: async () => ({ embedded: true }),
        installUpdate: async () => ({}),
        onUpdateEvent: () => () => {},
        onSshConnectProgress: () => () => {},
        submitSshPassword: () => {},
        cancelSshPassword: () => {},
        connectC1: async () => {
          window.__connectC1Calls += 1;
          return { connected: true, prompted: true };
        },
      };
    });

    await page.route("**/c1/query/person-attributes", async (route) => {
      await route.fulfill({
        status: 400,
        contentType: "application/json",
        body: JSON.stringify({
          detail: {
            code: "C1_VALIDATION_ERROR",
            message: "No event matched the requested attributes.",
          },
        }),
      });
    });

    await page.goto("/demo?desktop=1&e2e=attribute-validation-error");
    await expectHealthyPage(page, problems);
    await page.getByRole("button", { name: "人物特征搜索" }).click();
    await page.locator("#upperColorFilter").selectOption("blue");
    await page.locator("#startAttributeSearchBtn").click();

    await expect(page.locator("#searchView")).toHaveClass(/is-active/);
    await expect(page.locator("#resultView")).not.toHaveClass(/is-active/);
    await expect(page.locator("#toast")).toContainText("未找到符合人物特征条件");
    const connectCalls = await page.evaluate(() => window.__connectC1Calls || 0);
    expect(connectCalls).toBe(0);
    await expectNoHorizontalOverflow(page);
    expect(problems.filter((problem) => !problem.includes("status of 400"))).toEqual([]);
  });
});
