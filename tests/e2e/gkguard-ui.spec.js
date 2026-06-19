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

test.describe("GKGuard C2 demo UI", () => {
  test("mock search, route navigation, and reset remain responsive", async ({ page }) => {
    const problems = collectBrowserProblems(page);

    await page.goto("/demo?desktop=1&e2e=mock-flow");
    await expect(page.getByRole("heading", { name: "人脸检索" })).toBeVisible();
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
});
