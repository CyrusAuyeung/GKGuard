const { test, expect } = require("@playwright/test");

const PNG_BUFFER = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "base64",
);

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
              faceBox: { x1: 22, y1: 20, x2: 66, y2: 72, width: 44, height: 52 },
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
          faceCount: 2,
          queryFaces: [
            {
              index: 0,
              score: 0.91,
              bbox: {
                x1: 0.05,
                y1: 0.16,
                x2: 0.32,
                y2: 0.7,
                width: 0.27,
                height: 0.54,
                leftPct: 5,
                topPct: 16,
                widthPct: 27,
                heightPct: 54,
              },
            },
            {
              index: 1,
              score: 0.89,
              bbox: {
                x1: 0.58,
                y1: 0.18,
                x2: 0.9,
                y2: 0.72,
                width: 0.32,
                height: 0.54,
                leftPct: 58,
                topPct: 18,
                widthPct: 32,
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
          searchId: "e2e-c1-multi",
          queryFaces: [
            { index: 0, score: 0.91, bbox: { x1: 0.05, y1: 0.16, x2: 0.32, y2: 0.7, width: 0.27, height: 0.54 } },
            { index: 1, score: 0.89, bbox: { x1: 0.58, y1: 0.18, x2: 0.9, y2: 0.72, width: 0.32, height: 0.54 } },
          ],
          selectedQueryFace: { index: 1, score: 0.89, bbox: { x1: 0.58, y1: 0.18, x2: 0.9, y2: 0.72, width: 0.32, height: 0.54 } },
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
      name: "query-multi.png",
      mimeType: "image/png",
      buffer: PNG_BUFFER,
    });

    await expect(page.locator("[data-query-face-index]")).toHaveCount(2);
    await expect(page.locator("#searchView")).toHaveClass(/is-active/);
    await clickQueryFaceByIndex(page, 1);
    await expect(page.locator('[data-query-face-index="1"]')).toHaveClass(/is-selected/);

    await page.getByRole("button", { name: /确认选择并检索/ }).click();
    await expect(page.locator("#resultView")).toHaveClass(/is-active/);
    expect(searchUrl).toContain("query_face_index=1");
    await expect(page.locator("#resultPortrait img")).toBeVisible();
    await expect(page.locator("#resultPortrait img")).toHaveAttribute("src", /^data:image\/jpeg/);
    await expect(page.locator("#recordScene .result-face-box")).toContainText("88%");
    await expectDesktopRecordListOnLeft(page);
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
