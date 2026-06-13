# CampusVision C1：校园智能视频检索与轨迹分析接口版

C1 是暑期项目第一阶段的最小可运行版本，目标是打通：

> 上传/接入视频 → 抽帧 → 人脸/目标向量入库 → 上传目标照片 → 返回出现时间、地点、截图、相似度 → 生成轨迹时间线

你后续只需要把自己的照片和视频放进来，通过接口调用即可。

---

## 1. 适配你的环境

你目前已有一个 `torch126` conda 环境，并且里面装了 PyTorch。这个环境**用得上**：

- C1 的真实人脸识别后端可以使用 PyTorch；
- 不建议直接在原环境上继续装依赖，避免污染；
- 推荐克隆一个新环境，例如 `campusvision-c1`。

### 推荐安装方式

在 Ubuntu 22.04 LTS 上执行：

```bash
cd campusvision-c1
bash scripts/bootstrap_from_torch126.sh
```

脚本默认执行：

```bash
conda create -n campusvision-c1 --clone torch126
conda activate campusvision-c1
pip install -r requirements.txt
```

如果你的原环境名不是 `torch126`，可以这样：

```bash
bash scripts/bootstrap_from_torch126.sh 你的原环境名 campusvision-c1
```

---

## 2. 启动服务

```bash
conda activate campusvision-c1
cd campusvision-c1

cp .env.example .env
bash scripts/run_dev.sh
```

默认服务地址：

```text
http://127.0.0.1:8000
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

---

## 3. 识别引擎说明

C1 正式版只支持 InsightFace/ArcFace 人脸引擎。这样可以保证视频库和查询图片始终处在同一个 512 维 ArcFace embedding 空间，避免混用不同模型向量导致相似度不可解释。

安装依赖：

```bash
pip install -r requirements.txt
```

`.env` 中保持：

```bash
FACE_ENGINE=insightface
```

该模式使用 InsightFace/ArcFace 的 `buffalo_l` 模型，适合监控视频里的小脸、侧脸和跨光照检索。首次运行会下载模型文件；如果服务器无法联网，可以提前准备 InsightFace 模型缓存。

---

## 4. 快速接口流程

### 4.1 创建摄像头点位

```bash
curl -X POST http://127.0.0.1:8000/api/v1/cameras \
  -H "Content-Type: application/json" \
  -d '{
    "camera_id": "cam_dorm_gate_01",
    "name": "宿舍区东门摄像头01",
    "location": "宿舍区东门",
    "lat": 31.0001,
    "lng": 121.0001
  }'
```

### 4.2 上传视频

```bash
curl -X POST http://127.0.0.1:8000/api/v1/videos/upload \
  -F "file=@/path/to/demo.mp4" \
  -F "camera_id=cam_dorm_gate_01" \
  -F "recorded_at=2026-07-01T09:00:00" \
  -F "frame_interval_sec=1.0"
```

返回 `video_id`。

### 4.3 对视频建索引

```bash
curl -X POST http://127.0.0.1:8000/api/v1/videos/{video_id}/index
```

### 4.4 以图搜人

逐帧检索会直接在已入库的人脸记录中查找相似帧，适合调试和对比原始命中。

```bash
curl -X POST http://127.0.0.1:8000/api/v1/search/by-image \
  -F "files=@/path/to/person_1.jpg" \
  -F "files=@/path/to/person_2.jpg" \
  -F "top_k=20" \
  -F "max_gap_sec=3.0"
```

`min_score` 可不传，服务会使用 InsightFace 默认阈值 `0.30`。

返回内容包含：

- `matches`：逐帧命中记录，按相似度从高到低排序；
- 相似度；
- 摄像头；
- 地点；
- 视频时间戳；
- `time_display`：例如 `00:00:01.999` 的视频内时间；
- 画面截图 URL；
- `trajectory`：按时间排序的轨迹时间线；
- `appearance_events`：按 `video_id`、`camera_id` 和连续时间窗口合并后的出现事件，保留最佳截图和命中数量。

### 4.5 构建人物库

人物库会从已经建好的逐帧人脸记录中聚类生成，一个 `person` 对应一组视觉上相似的人脸。重建人物库不会改写原始 `face_records`。

```bash
curl -X POST http://127.0.0.1:8000/api/v1/persons/rebuild-index \
  -F "min_faces=2" \
  -F "min_face_area=2500" \
  -F "min_detection_score=0.85"
```

默认不需要提前知道视频里有几个人。服务会先用严格质量过滤生成高置信人物簇，再从未入库的人脸中恢复持续出现的弱稳定簇，用于召回后方小脸、低头人等检测分偏低但多次出现的人物。过小、过短、与已有簇过近或簇内质量不足的候选仍会统计为 `noise_faces`，避免把所有检测框都硬塞进人物库。

查看人物库：

```bash
curl http://127.0.0.1:8000/api/v1/persons
```

浏览器打开下面地址可以查看人物库可视化页面，每个 `person` 会显示一张裁剪出来的代表人脸和相关信息：

```text
http://127.0.0.1:8000/api/v1/persons/gallery
```

基于人物库搜索：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/search/person-by-image \
  -F "files=@/path/to/person_1.jpg" \
  -F "top_k=5" \
  -F "max_gap_sec=3.0"
```

返回内容包含 `persons`，每个候选人物里会带 `score`、代表截图、关联逐帧 `matches`、`trajectory` 和 `appearance_events`。

### 4.6 查看截图

搜索结果中的 `frame_url` 类似：

```text
/api/v1/media/frame/{face_id}
```

浏览器打开即可查看命中帧。

人物库中的 `representative_face_crop_url` 类似：

```text
/api/v1/media/face/{face_id}
```

浏览器打开即可查看按人脸框裁剪出来的小图。

---

## 5. 目录结构

```text
campusvision-c1/
  app/
    api/                 FastAPI 路由
    core/                配置
    services/            视频索引、搜索服务
    storage/             SQLite 存储
    vision/              人脸识别/抽帧/向量逻辑
  data/
    uploads/             上传视频和查询图片
    frames/              抽帧截图
    campusvision.sqlite3 本地数据库，运行后生成
  docs/
    C1_API.md            接口说明
    C1_DESIGN.md         架构说明
  scripts/
    bootstrap_from_torch126.sh
    run_dev.sh
    check_env.py
    smoke_test.sh
```

---

## 6. C1 的边界

C1 重点是“视频文件人物检索闭环”，当前正式版使用 InsightFace/ArcFace 作为唯一人脸识别后端。

当前重点：

- 视频上传；
- 摄像头点位；
- 抽帧；
- 人脸/目标入库；
- 以图搜图；
- 时间线轨迹；
- 接口文档。

后续 C2/C3 可以继续扩展：

- 人体 ReID；
- 多摄像头跨镜追踪；
- 行为共现关系；
- 车辆检索；
- 轨迹地图前端；
- 接入海康/大华 SDK 或 RTSP 流。

---

## 7. 常见问题

### Q：为什么要克隆 torch126？

因为你的 `torch126` 已经有 PyTorch，后续真实识别模型可以直接复用。克隆后安装 Web/API 依赖，不破坏原始环境。

### Q：视频和图片放哪里？

通过接口上传即可。系统会自动保存到：

```text
data/uploads/videos/
data/uploads/query_images/
data/frames/
```

### Q：能不能直接对接监控流？

C1 先做“上传视频文件”。RTSP/SDK 接入建议放到 C2。
