# C1 架构说明

## 目标

C1 只做第一阶段最小闭环：

```text
视频文件 → 抽帧 → 识别/向量化 → 本地索引 → 上传目标图 → 相似度检索 → 轨迹时间线
```

## 模块

### API 层

FastAPI 提供接口：

- 摄像头管理；
- 视频上传；
- 视频建索引；
- 以图搜图；
- 命中帧访问。

### 存储层

使用 SQLite，便于本地开发和演示。主要表：

- `cameras`
- `videos`
- `face_records`
- `searches`

### 视觉层

`app/vision/face_engine.py` 定义统一接口，并在正式版中固定加载 InsightFace/ArcFace：

```python
class FaceEngine:
    def detect_faces(self, image_bgr): ...
    def embed_faces(self, image_bgr, boxes): ...
```

当前提供：

- `InsightFaceEngine`：使用 InsightFace `buffalo_l` 模型做人脸检测和 512 维 ArcFace embedding。

正式版不再保留 hash/FaceNet 多后端切换，避免不同模型 embedding 混入同一人物库。后续如果接入校方已有算法服务、海康/大华智能分析接口、人体 ReID 或车辆 ReID，应作为新的明确能力设计，并为向量版本和索引重建提供迁移方案。

### 轨迹生成

搜索结果按时间排序后，映射到摄像头点位，生成：

- 时间；
- 摄像头；
- 地点；
- 经纬度；
- 截图；
- 相似度。

C1 不做复杂轨迹修正，只输出时间线和点位序列。

## 为什么先不做 RTSP

RTSP/SDK 接入依赖现场网络、摄像头权限、厂商协议、码流稳定性。C1 先用视频文件建立闭环，后续 C2 再接实时流更稳。

## 为什么固定 InsightFace

人物库检索依赖稳定的向量空间。固定 InsightFace 后，视频索引、人物聚类和查询图片都使用同一种 512 维 ArcFace embedding，阈值和分数解释更稳定，也能避免旧测试引擎生成的向量被误用于正式检索。
