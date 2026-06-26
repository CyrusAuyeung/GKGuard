# GKGuard Icon Prompts

> 用途：本文件保留图标资产的生成方向，供后续重生成品牌图标、启动图标或功能图标时参考。当前 `v0.3.2` 前端功能小图标以页面内 SVG sprite 为准，品牌、启动和桌面端打包图标使用仓库中的 PNG/ICO/ICNS 资产。
>
> Purpose: This file preserves icon-generation guidance for future brand, loading, or functional icon refreshes. As of `v0.3.2`, small UI icons are implemented through the embedded SVG sprite, while brand/loading/desktop packaging icons use repository PNG/ICO/ICNS assets.

## 通用风格 / Shared Style

请所有图标保持同一套视觉语言，不限定输出格式。若生成的是功能小图标，后续接入前应优先提炼为单色或双色矢量符号，避免按钮中出现白底贴图感。

- 画布：正方形图标，透明背景，适合后续导出为常见图片或图标格式。
- 风格：现代安防系统、AI 人脸以图搜人、校园监控控制台，专业、克制、清晰。
- 形态：简洁、扁平、线性或轻微填充均可，但不要做成复杂插画。
- 颜色：优先单色或双色；可使用深蓝、科技蓝、低饱和灰蓝作为主色，不要花哨渐变。
- 构图：居中，留出安全边距，小尺寸按钮内仍然清楚。
- 约束：不要文字、不要背景场景、不要 3D 拟物、不要过多阴影，不要输出带实色背景的按钮贴片。

Shared style requirements:

- Canvas: square icon, transparent background, suitable for export to common image or icon formats.
- Style: modern campus security AI dashboard, professional, restrained, and clear.
- Shape: simple, flat, line-based, or lightly filled; avoid complex illustration.
- Color: prefer monochrome or two-color designs using deep blue, technology blue, or muted blue-gray.
- Composition: centered, with safe padding and legible at small button sizes.
- Constraints: no text, no full background scene, no 3D realism, no excessive shadow, and no solid-background sticker look.

Shared prompt prefix:

```text
Create a clean square icon asset with transparent background. Style: modern campus security AI dashboard, professional, restrained, high-legibility at small UI sizes. Use a simple flat or line-based design, centered composition, safe padding, no text labels, no full background scene, no 3D realism, and no decorative clutter. The icon may be delivered in any common image or icon format.
```

## 1. 应用主标识 / App Mark

用途：桌面启动页、窗口图标、未来安装包图标基础。

```text
Create a GKGuard app mark: a shield combined with a subtle camera aperture and face recognition focus brackets. It should feel like campus safety and AI search, not military or aggressive. Include a simple shield outline, one small lens/aperture detail, and four minimal scan corner brackets. Keep it recognizable at small icon sizes.
```

建议命名：`app-mark`

## 2. 人脸以图搜人 / Face Search

用途：搜索页、结果页、路线页标题左侧 `face-icon`。

```text
Create a face recognition icon: a calm human face silhouette inside four scan corner brackets. The face should be minimal and neutral, with a head-and-shoulders shape rather than cartoon details. Keep the scan brackets precise and the person shape balanced.
```

建议命名：`face-search`

## 3. 开始检索 / Search Action

用途：“开始检索”主按钮 `search-action-icon`。

```text
Create an AI search icon: a magnifying glass combined with a small face scan target inside the lens. Make the handle clear, the lens round, and include two tiny scan corner hints inside the lens without overcrowding.
```

建议命名：`search-action`

## 4. 上传照片 / Upload Face

用途：上传区域“点击上传或拖拽图片到此处”前的小图标。

```text
Create an upload face image icon: a simple portrait photo frame with an upward upload arrow entering the frame. The portrait should read as a face/photo target, and the arrow should be clean and centered.
```

建议命名：`upload-face`

## 5. 重新上传 / Back To Upload

用途：“重新上传”按钮，可以替换当前返回箭头样式。

```text
Create a return-to-upload icon: a left-turn arrow leading back into a small image frame with a face silhouette. Keep it simple, with the arrow clearly indicating returning to the upload step.
```

建议命名：`back-to-upload`

## 6. 返回结果 / Back To Results

用途：“返回检索结果”按钮。

```text
Create a back-to-results icon: a left arrow beside a compact results list with two short horizontal rows. It should communicate returning from route map to result list, not generic browser back.
```

建议命名：`back-to-results`

## 7. 路线图 / Route Map

用途：“查看人物路线图”“定位时间线”按钮 `route-small-icon`。

```text
Create a route map icon: three location dots connected by a smooth path line, with the final dot slightly emphasized. The path should feel like a campus route trace, clean and easy to read in a small button.
```

建议命名：`route-map`

## 8. 导出 / Export Download

用途：“导出记录”“导出路线图”按钮 `download-icon`。

```text
Create an export download icon: a downward arrow entering a tray, with a subtle document/image outline behind it. Make it read as exporting evidence or report material from the app.
```

建议命名：`export-download`

## 9. 检查更新 / Update Check

用途：右上角“检查更新”按钮 `update-icon`。

```text
Create an update check icon: circular refresh arrows with a small check mark integrated near the lower right. It should communicate checking or installing app updates, not general sync noise.
```

建议命名：`update-check`

## 10. 信息提示 / Info Notice

用途：检索源说明、轨迹摘要提示中的信息图标。

```text
Create an information notice icon: a clean circle with a lowercase i, balanced for UI banners. Keep it quiet and professional, matching a dashboard info message.
```

建议命名：`info-notice`

## 11. 启动加载 / Boot Loading Mark

用途：桌面启动页 `loading.html` 当前的 G 字母方块替换。

```text
Create a compact boot/loading brand icon for GKGuard: combine a shield, camera aperture, and small scanning corner hints into a square-friendly mark. It should work inside a 38px rounded square and remain recognizable.
```

建议命名：`boot-mark`

## 12. 服务器连接 / CampusVision C1 Connection

用途：CampusVision C1 密码窗口标题或未来连接状态图标。

```text
Create a server connection icon: a small server stack connected by a secure tunnel line to a shield or lock. It should communicate secure SSH connection to a CampusVision C1 server, without looking like a generic cloud icon.
```

建议命名：`server-connection`
