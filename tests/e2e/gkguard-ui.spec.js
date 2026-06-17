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

    await page.route("**/c1/search/person-by-image?**", async (route) => {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          source: "c1",
          searchId: "e2e-c1",
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

    await page.getByRole("button", { name: /开始检索/ }).click();
    await expect(page.locator("#resultView")).toHaveClass(/is-active/);
    await expect(page.locator("#resultSourceBadge")).toHaveText("CampusVision C1");
    await expect(page.locator("#recordScene.has-frame .scene-frame")).toBeVisible();

    await page.locator("#recordScene").click();
    await expect(page.locator("#mediaViewer")).toBeVisible();
    await expect(page.locator("#mediaViewerTitle")).toContainText("记录1");
    await expect(page.locator("#mediaViewer img")).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(page.locator("#mediaViewer")).toBeHidden();
    await expectNoHorizontalOverflow(page);
    expect(problems).toEqual([]);
  });
});
