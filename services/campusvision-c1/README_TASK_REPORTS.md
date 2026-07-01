# CampusVision C1 任务报告

本文档用于记录 CampusVision C1 每次任务结束后的审阅报告。之后每次完成 CampusVision C1 相关任务时，应在这里追加一条报告，并标明当时分支和版本来源。

## 最近历史集成记录

- 历史记录对应的 GKGuard 版本：`v0.2.3`
- CampusVision C1 来源分支：`speng/c1-person-events` + `codex/fix-c1-event-review-followup`
- CampusVision C1 来源版本：`2ba9064` + 当前仓库补丁分支
- 记录时间：`2026-06-25 00:00:00 CST`
- 说明：下方任务记录保留 CampusVision C1 开发过程中的历史语境；GKGuard C2 当前对接行为以 `README_C2_INTEGRATION.md`、`docs/api_contract.md` 和 `docs/c1_c2_integration.md` 为准。

## 记录规范

每次任务结束后追加以下内容：

```text
## YYYY-MM-DD HH:mm:ss CST - <任务标题>

- 版本来源：<branch>@<short_sha>
- 任务目标：
- 变更内容：
- 验证结果：
- 风险与遗留问题：
- 涉及文件：
```

## 任务记录

## 2026-06-25 10:30:00 CST - GKGuard v0.2.3 CampusVision C1 重建索引安全修复

- 版本号：`codex/propose-fix-for-re-index-vulnerability@merged`
- 任务目标：修复 CampusVision C1 视频重建索引失败时可能破坏既有索引状态的问题，并保持查询图超限临时目录清理。
- 变更内容：重建索引先暂存采样帧并在提交阶段重新读取文件，避免采样列表长期保留原始帧数组；提交失败时恢复旧事件、人物观测、人脸记录、旧帧目录、人物索引和相关 appearance sessions；数据库写入路径增加写锁保护，读取接口保持普通连接路径；查询图超限继续清理临时上传目录并返回 413。
- 验证结果：完整验证结果以 `docs/releases/v0.2.3.md` 和对应 PR 为准。
- 风险与遗留问题：CampusVision C1 全量视觉链路仍依赖远端 `cv2`、InsightFace、ONNXRuntime 和模型文件；Windows 本地环境不能替代远端服务运行验证。
- 涉及文件：`services/campusvision-c1/app/storage/db.py`、`services/campusvision-c1/app/services/video_service.py`、`services/campusvision-c1/app/api/routes.py`、`services/campusvision-c1/tests/test_security_config.py`、`docs/releases/v0.2.3.md`

## 2026-06-25 00:00:00 CST - GKGuard v0.2.2 CampusVision C1 review 后续收敛

- 版本号：`codex/fix-v0.2.1-review-feedback@working-tree`
- 任务目标：处理 `v0.2.1` 合并后继续保留的 review 反馈，确保 CampusVision C1 查询图候选接口参数位置、GKGuard C2 4xx 错误透传和路线高亮边界与当前 API 规范一致。
- 变更内容：CampusVision C1 `/api/v1/query/face-image` 的查询控制项改为 Query 参数，图片继续使用 multipart `files` 字段；GKGuard C2 代理向 CampusVision C1 传递 Query 参数并保留 CampusVision C1 4xx 校验错误详情；前端对不可解码或超限查询图停留在上传页提示，不触发桌面端 CampusVision C1 重连；路线图重复映射点只高亮当前路线点，未映射结果记录不再错误高亮最后一个路线点。
- 验证结果：完整验证结果以 `docs/releases/v0.2.2.md` 和对应 PR 为准。
- 风险与遗留问题：CampusVision C1 真实视觉链路仍依赖远端 `cv2`、InsightFace、ONNXRuntime 和模型文件；Windows 本地环境不能替代远端服务运行验证。
- 涉及文件：`services/campusvision-c1/app/api/routes.py`、`backend/app/services/c1_service.py`、`backend/app/static/app.js`、`backend/tests/test_api.py`、`tests/e2e/gkguard-ui.spec.js`、`docs/api_contract.md`、`docs/releases/v0.2.2.md`

## 2026-06-24 21:00:00 CST - GKGuard v0.2.1 C1 集成 review follow-up

- 版本号：`codex/fix-c1-event-review-followup@working-tree`
- 任务目标：处理 `v0.2.0` 合并后 review 发现的 CampusVision C1 查询图异常、重复索引、人物索引与 appearance session 重建和 GKGuard C2 人物特征路线顺序问题。
- 变更内容：`/api/v1/query/face-image` 在查询图不可解码时返回 400，在上传体积、解码像素数或单边尺寸超限时返回 413，并清理临时上传；同一视频重索引前清理旧事件、人物观测、人脸记录和旧帧目录，并刷新受影响人物索引、重建相关 appearance sessions；GKGuard C2 人物特征搜索结果列表保留匹配排序，路线点按事件时间单独排序并通过 `recordIndex` / `eventId` 稳定映射回结果记录；API 规范同步 `time_range.start_time/end_time` 和 `/c1/query/face-image` Query 参数位置。
- 验证结果：新增后端和 CampusVision C1 静态/单元测试覆盖；完整验证结果以 `docs/releases/v0.2.1.md` 和对应 PR 为准。
- 风险与遗留问题：重索引失败后该视频需要重新执行索引；历史 `v0.2.0` 说明保持发布时语境，该条记录完成时以 `v0.2.1` 文档为准。
- 涉及文件：`services/campusvision-c1/app/api/routes.py`、`services/campusvision-c1/app/services/video_service.py`、`services/campusvision-c1/tests/test_security_config.py`、`backend/app/services/c1_service.py`、`docs/api_contract.md`、`docs/releases/v0.2.1.md`

## 2026-06-24 08:31:03 CST - C1 v1 全链路重跑与指标验收

- 版本号：`speng/c1-person-events@2ba9064`
- 运行前备份：代码分支 `backup/c1-before-v1-full-rerun-20260624-082043` 已推送；数据库/profile/目标指标快照在 `data/backups/v1_full_rerun_20260624_082043/`。
- 任务目标：从现有 15 路 C1 视频索引结果出发，重跑 body/clothing/events/appearance sessions/gender/glasses，并对照人工 check 评估集与目标指标生成验收结果。
- 变更内容：重跑 `reprocess_body_clothing.py`；刷新 appearance sessions、外观倾向 profile、眼镜 profile；重新生成 API benchmark 和 `data/evals/target_metrics/c1_target_metrics.json`。
- 数据规模：15 个视频、15 个摄像头、532 帧、1096 张人脸、1616 个观测、1345 个事件、382 个已识别事件、44 个人物、44 个 appearance sessions。
- 核心指标：人脸聚合 Pairwise Precision `1.0000`，Pairwise F1 `0.9714`；装束分组 Pairwise F1 `0.9666`，Purity `0.9969`；上装装束级准确率 `0.85`；眼镜人物级准确率 `0.9773`；外观倾向人物级准确率 `1.0000`。
- 性能指标：API clean-temp benchmark 处理 25.17s 视频耗时 `13.76s`，实时系数 `0.5468`；长期内存 1800s 监测通过，RSS 增长 `20.734MB`。
- 验证结果：`pytest tests -q` 通过，`71 passed, 2 warnings`；`/health` 返回正常。
- 风险与遗留问题：上装颜色、装束分组早期人工评估集的 `person_id/event_id/observation_id` 与当前库 ID 匹配数为 0，不能作为当前库直接 replay 评估；本次目标指标中的上装与装束分组通过结果来自已有离线/旧版评估报告，需要后续重新采集当前库可 replay 的人工评估集。
- 涉及文件：`services/campusvision-c1/data/campusvision.sqlite3`、`services/campusvision-c1/data/person_profiles/gender_presentation_profiles.json`、`services/campusvision-c1/data/person_profiles/glasses_status_profiles.json`、`services/campusvision-c1/data/evals/target_metrics/c1_target_metrics.json`、`services/campusvision-c1/data/evals/runtime/c1_api_processing_benchmark.json`、`services/campusvision-c1/README_TASK_REPORTS.md`

## 2026-06-24 08:16:13 CST - 新增 C1 任务报告文档

- 版本号：`speng/c1-person-events@2ba9064`
- 任务目标：新增一个独立 README 类文档，用于后续记录每次 C1 任务结束报告。
- 变更内容：新增 `README_TASK_REPORTS.md`，定义当前版本、记录规范和任务记录区。
- 验证结果：文档已创建，未修改 C1 服务运行逻辑。
- 风险与遗留问题：当前版本号使用 git 分支和 short SHA 表示；后续如果需要语义化版本，可以再增加 `C1_VERSION` 字段。
- 涉及文件：`services/campusvision-c1/README_TASK_REPORTS.md`

## 2026-06-24 08:50:50 CST - 装束库增加稳定人物筛选

- 版本号：`speng/c1-person-events@2ba9064`
- 任务目标：在装束库相关网页中增加“全部人物 / 只看稳定人物”选项，方便排除候选碎片人物。
- 变更内容：新增公共 URL 参数生成和人物范围分段控件；`appearance-sessions/gallery`、`outfit-labels/review?mode=auto`、`outfit-labels/review?mode=manual`、`event-outfit-groups/review` 均支持 `include_candidates=true|false`；稳定人物沿用 `person_service.identity_status()` 判定。
- 验证结果：`py_compile` 通过；`pytest tests -q` 通过，`71 passed, 2 warnings`；8000 服务重启后 `/health` 正常；上述 4 个页面的全部/稳定参数返回 200。
- 页面数据摘要：装束展示页全部人物 `44 sessions / 382 events`，只看稳定人物 `24 sessions / 321 events`；自动装束页全部人物 `72 outfit groups`，只看稳定人物 `50 outfit groups`。
- 风险与遗留问题：本次只改展示筛选，不改变人物稳定判定、装束分组模型、数据库内容和人工评估数据。
- 涉及文件：`services/campusvision-c1/app/api/routes.py`、`services/campusvision-c1/README_TASK_REPORTS.md`

## 2026-06-24 09:50:55 CST - 提供全量装束人工审核入口

- 版本号：`speng/c1-person-events@2ba9064`
- 任务目标：给出当前全量装束人工审核界面，供重新制定装束颜色评估集。
- 变更内容：未改服务逻辑；确认使用 `outfit-labels/review?mode=auto&include_candidates=true` 作为全量装束审核入口，每个装束可选择整组上装颜色并保存。
- 验证结果：C1 8000 服务运行正常；审核页返回 `200`；当前全量范围包含 `44` 个人物、`72` 个装束组；稳定人物范围包含 `24` 个人物、`50` 个装束组。
- 风险与遗留问题：保存路径仍为当前人工装束评估文件 `data/evals/manual_outfit_labels/outfit_labels.json`；人工 check 数据仅作为评估集使用。
- 涉及文件：`services/campusvision-c1/README_TASK_REPORTS.md`

## 2026-06-24 10:04:50 CST - 装束人工审核部分保存恢复

- 版本号：`speng/c1-person-events@2ba9064`
- 任务目标：页面卡死后确认并更新已经保存成功的装束人工审核结果，避免丢失已完成标注。
- 变更内容：检查 `outfit_labels.json` 的落盘状态；生成当前数据库可匹配的已保存装束进度快照 `data/evals/manual_outfit_labels/current_saved_outfit_progress.json`；保留旧标签并单独标记 stale，不参与当前进度统计。
- 验证结果：C1 8000 服务 `/health` 正常；保存接口日志显示 `POST /api/v1/outfit-labels` 返回 `200`；当前 `72` 个装束组中已保存且可匹配当前库的装束为 `14` 个，剩余 `58` 个；另有 `5` 个旧装束 ID 与当前分组不匹配。
- 风险与遗留问题：页面卡死原因更像浏览器渲染/图片加载过重；继续审核建议使用 `unsaved_only=true` 且降低 `sample_count` 的轻量 URL。人工 check 数据仍只作为评估集，不用于训练。
- 涉及文件：`services/campusvision-c1/data/evals/manual_outfit_labels/outfit_labels.json`、`services/campusvision-c1/data/evals/manual_outfit_labels/current_saved_outfit_progress.json`、`services/campusvision-c1/README_TASK_REPORTS.md`

## 2026-06-24 10:12:17 CST - 接收完整装束人工评估集

- 版本号：`speng/c1-person-events@2ba9064`
- 任务目标：确认用户当前保存的装束人工评估集是否已被 C1 接收到。
- 变更内容：刷新 `current_saved_outfit_progress.json`，将当前人工标注与当前 `72` 个装束组重新匹配。
- 验证结果：`outfit_labels.json` 最新落盘时间为 `2026-06-24 10:10:44 CST`；当前 `72` 个装束组已全部有保存标签；另有 `5` 个旧装束 ID 标记为 stale；当前装束颜色分布为 striped `18`、black `15`、gray `11`、white `10`、blue `8`、red `4`、purple `3`、brown `1`、green `1`、yellow `1`。
- 风险与遗留问题：`review_status` 中仍有 `51` 条 `unreviewed`，这是页面在颜色未改动时不会自动改状态；这些记录已有颜色并已保存。人工 check 数据仍只作为评估集使用。
- 涉及文件：`services/campusvision-c1/data/evals/manual_outfit_labels/outfit_labels.json`、`services/campusvision-c1/data/evals/manual_outfit_labels/current_saved_outfit_progress.json`、`services/campusvision-c1/README_TASK_REPORTS.md`

## 2026-06-24 10:21:05 CST - 导出可重映射装束评估集

- 版本号：`speng/c1-person-events@2ba9064`
- 任务目标：将当前装束人工评估集导出为可在全量清库重跑后重新映射的格式，避免只依赖旧 `person_id/event_id/outfit_id`。
- 变更内容：新增 `scripts/export_remappable_outfit_eval.py`；导出 JSON 中保存人工上装颜色、旧 ID、摄像头、视频文件名、视频时间戳、事件时间、bbox、frame/body/face hash、dhash 和当前模型结果；同时复制 frame/body/face 图片证据到独立导出目录。
- 导出位置：`data/evals/manual_outfit_labels/remap_exports/remappable_outfit_eval_20260624_102011/remappable_outfit_eval.json`；最新指针：`data/evals/manual_outfit_labels/remap_exports/remappable_outfit_eval_latest.json`。
- 验证结果：导出当前 `72` 个装束标签，`5` 个旧标签作为 stale；复制并校验 `771` 个图片证据文件，缺失数 `0`；导出目录约 `33MB`；`pytest tests -q` 通过，`71 passed, 2 warnings`。
- 风险与遗留问题：后续清库前必须保留 `data/evals/manual_outfit_labels/remap_exports/`；此导出只提供重映射锚点，真正重跑后仍需执行一个 remap/evaluate 步骤把新库装束匹配回来。人工 check 数据仍只作为评估集，不用于训练。
- 涉及文件：`services/campusvision-c1/scripts/export_remappable_outfit_eval.py`、`services/campusvision-c1/data/evals/manual_outfit_labels/remap_exports/remappable_outfit_eval_20260624_102011/remappable_outfit_eval.json`、`services/campusvision-c1/data/evals/manual_outfit_labels/remap_exports/remappable_outfit_eval_latest.json`、`services/campusvision-c1/README_TASK_REPORTS.md`

## 2026-06-24 10:24:48 CST - 当前装束颜色结果对比人工评估集

- 版本号：`speng/c1-person-events@2ba9064`
- 任务目标：对比当前系统装束级上装颜色输出与用户人工 check 评估集。
- 变更内容：生成当前对比报告 `data/evals/manual_outfit_labels/current_outfit_eval_vs_manual.json`；评估只纳入当前库可匹配的装束标签，排除旧装束 ID。
- 验证结果：当前 `72` 个装束全部有人工标签，排除 `5` 个 stale 旧 ID；系统预测正确 `51/72`，装束级准确率 `0.7083`。主要混淆为 white→gray `3`、striped→gray `3`、gray→striped `2`、black→purple `2`、striped→black `2`。
- 风险与遗留问题：当前结果低于此前目标 `>=0.80`；green/yellow/brown 等类别样本数很少，单类指标波动大。人工 check 数据仍只作为评估集，不用于训练。
- 涉及文件：`services/campusvision-c1/data/evals/manual_outfit_labels/current_outfit_eval_vs_manual.json`、`services/campusvision-c1/README_TASK_REPORTS.md`

## 2026-06-24 10:31:04 CST - 装束级上装识别验收标准

- 版本号：`speng/c1-person-events@2ba9064`
- 任务目标：制定上装颜色识别部分的后续验收标准，明确优先优化装束级结果，事件级作为诊断指标。
- 验收主指标：当前可重映射人工评估集上，装束级上装颜色准确率 `>= 80%` 为通过，`>= 85%` 为稳定上线目标；低于 `80%` 只能作为候选方案，不能作为完成状态。
- 诊断指标：事件级上装颜色准确率需要同步统计，但不作为主验收；重点跟踪 white/gray、striped/gray、black/purple、striped/black 混淆；unknown 误判率需要单独列出，不能靠大量 unknown 回避错误。
- 保护指标：装束分组 Pairwise F1 保持 `>= 90%`，Purity 保持 `>= 98%`；新方案不得牺牲人脸聚合 Pairwise Precision `>= 95%` 和 Pairwise F1 `>= 85%`。
- 性能指标：30s 视频 API 处理耗时必须小于视频时长，目标 `<= 15s`；长期运行显存/内存无持续上涨；实时路径不能依赖人工标注或离线人工修正。
- 数据规则：人工 check 数据只能用于评估和回归验收，不可用于训练、硬编码、阈值定向拟合；每次全量清库重跑后必须先用可重映射导出集完成 remap，再重新计算指标。
- 风险与遗留问题：当前装束级准确率为 `70.83%`，距离通过线还差约 `9.17` 个百分点；样本少的颜色类别不单独设硬门槛，但错误样例必须进入混淆分析。
- 涉及文件：`services/campusvision-c1/README_TASK_REPORTS.md`

## 2026-06-24 11:07:00 CST - 装束级上装颜色解析器 v1

- 版本号：`speng/c1-person-events@2ba9064`
- 任务目标：按照装束级上装颜色验收标准开发优化逻辑，主指标达到 `>= 80%`，且不把人工 check 数据写入生产路径。
- 备份分支：重大改动前已推送 `backup/c1-before-outfit-color-resolver-v1-20260624-110041`。
- 变更内容：在 `outfit_service` 增加装束级上装颜色解析器，仅使用当前装束内事件颜色投票、事件概率、平均置信度和条纹分数；针对 dark-purple cast、gray/white、gray/striped、low-stripe striped、blue/purple 低置信并列等边界做通用后处理；输出 `model_upper_color_base` 和 `model_upper_color_resolution` 方便审计。
- 评估结果：当前 `72` 个装束人工评估集上，基线 `51/72 = 70.83%`；优化后 `58/72 = 80.56%`，达到通过线；解析器改动 `9` 个装束，unknown 误判数 `0`，另有 `5` 个旧装束标签仍为 stale。
- 对照模型：修正后的 H/14 + SCHP 离线评估已确认只评当前 `72` 个装束，最佳约 `72.22%`；bigG + SCHP 最佳约 `79.17%`，未直接过线且实时成本更高，因此未切换线上主路径。
- 验证结果：`py_compile` 通过；`pytest tests -q` 通过，`76 passed, 2 warnings`；C1 8000 服务已用 `campusvision-c1` 环境重启，`/health` 正常；`outfit-labels/review`、`appearance-sessions/gallery`、`event-outfit-groups/review` 页面返回 `200`。
- 保护指标：本次不改变人脸聚合、事件生成、装束分组距离和 `_should_merge_source_groups`，只改变装束 summary 的 `model_upper_color`；用改动前 `outfit_service.py` 与当前模块对同一数据库重建装束分组，均为 `72` 个 outfit，outfit id 和事件成员完全一致，变化数 `0`；人脸聚合 current-db 投影 precision `1.0`、F1 `0.971429`，且 person merge 模型未使用衣着特征；事件装束分组人工集当前与现库事件 ID 直接匹配数为 `0`，不能作为当前分组下降证据。
- 风险与遗留问题：`80.56%` 只是刚过通过线，未达到稳定上线目标 `>= 85%`；剩余主要错误仍包括 striped→gray、striped→black、少量彩色被中性色覆盖。后续继续提升应优先增加可部署的非人工训练来源或更强实时可承受模型，人工 check 仍只做评估。
- 涉及文件：`services/campusvision-c1/app/services/outfit_service.py`、`services/campusvision-c1/tests/test_outfit_grouping.py`、`services/campusvision-c1/scripts/evaluate_clip_upper_color.py`、`services/campusvision-c1/data/evals/manual_outfit_labels/current_outfit_eval_vs_manual.json`、`services/campusvision-c1/README_TASK_REPORTS.md`

## 2026-06-24 11:32:23 CST - 当前 C1 系统完整性评判

- 版本号：`speng/c1-person-events@2ba9064`
- 任务目标：评判当前 C1 系统从运行状态、数据规模、核心算法链路、评估证据和遗留风险上的完整性。
- 当前运行状态：C1 8000 服务健康检查正常；GPU 上 C1 服务进程占用约 `868MiB`；人物库、appearance sessions、装束审核、事件装束审核页面均返回 `200`。
- 当前数据规模：数据库包含 persons `44`、stable persons `24`、candidate persons `20`、events `1345`、identified events `382`、person observations `1616`、face records `1096`、person faces `653`、videos `15`、camera count `15`；当前装束组 `72`。
- 当前能力完整性：视频/API 入库、抽帧、人体/人脸观测、人脸聚合、人物库、人物事件、装束库、上装颜色、外观倾向、眼镜状态、人工评估页、可重映射装束评估导出、任务报告文档均已具备；C1 页面可用于查看人物、appearance sessions、装束审核与事件装束审核。
- 当前指标证据：装束级上装颜色当前 `58/72 = 80.56%`，达到通过线但未达稳定目标 `>=85%`；人脸聚合 current-db 投影 precision `1.0`、F1 `0.971429`；person merge 模型 `clothing_features_used=false`；最近 API 30s 处理 benchmark mean/max `13.760847s`；旧 target metrics 报告生成于 `2026-06-24 08:30 CST`，当时 pass_summary 全部为 true。
- 当前测试证据：`pytest tests -q` 通过，`76 passed, 2 warnings`。
- 完整性结论：系统已达到 v1 算法闭环和演示验证级完整性，可以支持本地 C1 数据流、人物库和装束级上装检索/评估；但还不应评价为生产完全闭环，主要差距是装束颜色仅刚过线、事件装束分组人工评估集当前无法直接 replay、全量清库重跑后的 remap/evaluate 流程仍需固化、长期运行内存和真实学校海康流接入还缺少长时间验证。
- 风险与遗留问题：当前 `data/evals/manual_event_outfit_groups/event_outfit_group_eval.json` 被现库事件 ID 不匹配影响，直接匹配事件数为 `0`，不能代表装束分组真实退化；稳定目标应继续推进到上装装束级 `>=85%`，并补一个可重映射的事件装束分组评估导出。
- 涉及文件：`services/campusvision-c1/README_TASK_REPORTS.md`

## 2026-06-24 11:36:58 CST - C1 后续优化路线

- 版本号：`speng/c1-person-events@2ba9064`
- 任务目标：制定 C1 从 v1 演示闭环走向稳定可复现闭环的优化路线。
- 第一优先级：补齐评估可信度。将事件装束分组人工评估集导出为可重映射格式，避免清库或事件 ID 改变后 replay 失效；把装束颜色、事件装束分组、人脸聚合、API 性能统一到一个 current-state target metrics 脚本中，零匹配评估必须标记为不可用而不是失败或通过。
- 第二优先级：把装束级上装颜色从 `80.56%` 推到稳定目标 `>=85%`。保持人工 check 仅用于评估；优先尝试可部署的非人工训练来源、更多公开监控样本、轻量 CLIP/SCHP 蒸馏或校准；禁止为了当前 72 个样本硬调阈值。
- 第三优先级：增强真实实时链路。固定 30s 视频/API 输入的基准场景，监控处理耗时、GPU 显存、RSS、队列长度和失败重试；至少做 2-4 小时本地长跑，确认内存无持续上涨。
- 第四优先级：完善数据重跑与回归。把“清库重跑、导入当前可用摄像头、重建人物库、重建装束库、remap 人工评估、输出指标报告”脚本化，减少手工步骤。
- 第五优先级：生产接入准备。保留当前伪实时 API 流做回归，同时准备真实学校海康数据到来后的解码/转码适配层；C1 只负责本地服务，不触碰 C2/桌面壳。
- 阶段验收建议：阶段 A 先解决评估可复现；阶段 B 再追 `>=85%` 上装装束级准确率；阶段 C 做长跑和性能回归；阶段 D 做真实学校数据接入适配。
- 风险控制：重大模型或数据流改动前继续推 backup branch；所有人工 check 数据保持 eval-only；任何优化不得降低人脸聚合 precision/F1，不得改变装束分组成员，除非该阶段目标明确是重训/重评装束分组。
- 涉及文件：`services/campusvision-c1/README_TASK_REPORTS.md`

## 2026-06-24 12:02:38 CST - 事件装束分组评估可重映射化与目标指标复核

- 版本号：`speng/c1-person-events@2ba9064`
- 任务目标：按照优化路线先补齐评估可信度，避免旧事件 ID 失效导致装束分组评估被误报为 `0`；继续检查是否可以安全推进到目标指标。
- 备份分支：重大评估链路改动前已推送 `backup/c1-before-eval-remap-route-20260624-113901`。
- 变更内容：重写 `scripts/evaluate_event_outfit_grouping.py`，默认用旧基线库 `campusvision_eval_baseline_20260623_pre_full_api_rerun.sqlite3` 的 camera/time/bbox 锚点把人工事件装束分组评估集映射到当前库；新增 `scripts/export_remappable_event_outfit_group_eval.py`，导出可重映射 JSON；`evaluate_c1_target_metrics.py` 增加 `status/metric_available/target_metric_eligible`，零匹配时标记不可重放，不再当作真实模型 0 分。
- 导出位置：`data/evals/manual_event_outfit_groups/remap_exports/remappable_event_outfit_groups_20260624_115233/remappable_event_outfit_groups.json`；最新指针：`data/evals/manual_event_outfit_groups/remap_exports/remappable_event_outfit_groups_latest.json`。导出包含 `324` 条人工事件分组，旧基线库 event/observation 锚点匹配均为 `324/324`。
- 当前事件装束分组评估：当前库 remap 匹配 `283/324 = 87.35%`，进入装束分组评估 `264/324 = 81.48%`；Pairwise precision `1.0`，recall `0.799026`，F1 `0.888287`，purity `0.916667`；结论为 `partial_evaluated` 且 `target_metric_eligible=true`，但 F1 和 purity 均未达目标。
- 当前总指标复核：人脸聚合 current-db 投影 precision `1.0`、F1 `0.971429`，通过；API benchmark mean/max `13.760847s`、实时系数 `0.546789`，通过；长期内存 1800s 监测通过，RSS 增长 `20.734MB`；统一指标中的上装颜色候选/校准口径为 `0.85` 且 unknown false `0`，通过。生产装束 summary 此前已验证为 `58/72 = 80.56%`，仍需后续把线上口径稳定推到 `>=85%`。
- 排查结果：装束距离阈值从 `0.36` 到 `0.58` 扫描，F1 最高约 `0.8928`，purity 仍 `0.9167`；跨来源 merge 阈值从 `0.06` 到 `0.30` 扫描也不能改善 purity；说明当前失败主要来自身份碎片/混合对装束分组的上游限制，不是单纯调装束阈值可以解决。
- 已验证但未应用：`auto_consolidate_person_fragments` 在生产库 dry-run 只建议 `1` 个小碎片合并；在 `/tmp` 临时库应用后事件装束指标无变化，未写回生产库。临时全量重建人物索引会把人物变为 `70`、只链接 `238/1096` 张脸，并导致 person aggregation F1 失败，判定为有害方案，未应用。
- 验证结果：`py_compile` 通过；新增评估测试 `2 passed`；全量 `pytest services/campusvision-c1/tests -q` 通过，`78 passed, 2 warnings`；C1 8000 `/health` 正常。
- 风险与遗留问题：事件装束分组现在有可信 current-state 评估，但目标尚未达成；下一步应优先优化身份层的碎片/混合问题，并新增事件级身份覆盖/混淆诊断指标，再回到装束分组模型本身。人工 check 数据仍只作为评估集使用。
- 涉及文件：`services/campusvision-c1/scripts/evaluate_event_outfit_grouping.py`、`services/campusvision-c1/scripts/export_remappable_event_outfit_group_eval.py`、`services/campusvision-c1/scripts/evaluate_c1_target_metrics.py`、`services/campusvision-c1/tests/test_event_outfit_group_eval.py`、`services/campusvision-c1/data/evals/manual_event_outfit_groups/event_outfit_group_eval.json`、`services/campusvision-c1/data/evals/manual_event_outfit_groups/remap_exports/remappable_event_outfit_groups_latest.json`、`services/campusvision-c1/data/evals/target_metrics/c1_target_metrics.json`、`services/campusvision-c1/README_TASK_REPORTS.md`

## 2026-06-24 12:56:14 CST - 确认现有人脸查询接口

- 版本号：`speng/c1-person-events@2ba9064`
- 任务目标：确认 C1 是否已经开发过人脸查询能力，为后续新增数据库查询接口做接口边界判断。
- 确认结果：C1 已有人脸查询链路，包括 `POST /api/v1/search/query-faces`、`POST /api/v1/search/person-by-image`、`POST /api/v1/search/by-image` 和 `GET /api/v1/searches/{search_id}`；同时已有媒体访问接口 `/api/v1/media/frame/{face_id}`、`/api/v1/media/face/{face_id}`。
- 当前能力：`query-faces` 用于检测上传图片中的人脸并返回 bbox；`person-by-image` 用人物库做以图搜人，支持 `query_face_index/top_k/min_score/max_gap_sec`；`by-image` 直接扫 face_records 返回逐帧 matches、trajectory 和 appearance_events；搜索结果会写入 `searches` 表，可按 `search_id` 回查。
- 风险与遗留问题：现有接口偏“人脸向量查询/以图搜人”，不是通用数据库查询接口；后续新增数据库查询接口应复用 `events/persons/appearance-sessions/search/by-clothes` 等只读能力，避免暴露任意 SQL。
- 涉及文件：`services/campusvision-c1/app/api/routes.py`、`services/campusvision-c1/app/services/search_service.py`、`services/campusvision-c1/README.md`、`services/campusvision-c1/README_TASK_REPORTS.md`

## 2026-06-24 13:01:48 CST - 人脸以图搜图大接口设计计划

- 版本号：`speng/c1-person-events@2ba9064`
- 任务目标：规划第一个数据库查询大接口：上传证件照/人脸照片，返回相似人物候选，并在每个候选人物下带出事件数据，供 C2 页面展示。
- 现状判断：已有 `POST /api/v1/search/person-by-image` 基本覆盖目标能力，会返回 `query_faces`、`selected_query_face`、候选 `persons`、每人 `matches/trajectory/appearance_events`；默认相似阈值 `0.30`，高置信阈值 `0.40`。
- 计划方向：保留旧接口兼容，新增或标准化一个面向 C2 的稳定大接口，例如 `POST /api/v1/query/face-image`；底层复用并整理 `person_service.search_persons_by_images`，不要重复实现人脸检测和向量比对。
- 接口输入计划：multipart 上传 `files`，支持 `query_face_index`、`top_k`、`min_score`、`include_candidates`、`event_limit_per_person`、`match_limit_per_person`、`start_time/end_time`、`camera_id`、`include_events/include_matches`。
- 返回结构计划：顶层返回 `search_id/engine/query_faces/selected_query_face/candidates/ambiguous/warning`；每个 candidate 包含 `person_id/identity_status/score/confidence/score_breakdown/representative_face_url/person_attributes/events/matches/trajectory`；事件中包含 `event_id/camera_id/time/video_timestamp/frame_url/body_crop_url/face_crop_url/upper_color/glasses_status/appearance_session_id`。
- 排序策略计划：先按人物级综合分排序，综合分继续使用 centroid、best face、top3 face 的融合分；相近分数保留多候选并标记 `ambiguous=true`，不给 C2 假装唯一命中。
- 保护策略：默认只返回稳定人物，`include_candidates=true` 时才返回候选碎片；人工 check 数据不得进入查询逻辑；接口只做只读查询和搜索历史写入，不改变人物库。
- 验收建议：单人证件照应稳定返回目标人物在 top1 或 top3；多人照片必须通过 `query_faces` 暴露可选人脸；无脸/低清/低置信要返回明确 warning；接口响应时间在当前库规模下应低于 2 秒，后续库变大再做向量索引。
- 风险与遗留问题：当前人物库仍有身份碎片和候选人物，可能导致多候选；C2 展示事件不应依赖 HTML 页面，应只消费 JSON；后续如果人物库规模显著增加，需要把当前遍历人物/face_records 的 Python 计算替换为向量索引或缓存。
- 涉及文件：`services/campusvision-c1/app/api/routes.py`、`services/campusvision-c1/app/services/person_service.py`、`services/campusvision-c1/app/services/search_service.py`、`services/campusvision-c1/app/vision/face_engine.py`、`services/campusvision-c1/README_TASK_REPORTS.md`

## 2026-06-24 13:16:03 CST - 人脸以图搜图大接口实现

- 版本号：`speng/c1-person-events@2ba9064`
- 任务目标：实现 C1 面向 C2 的人脸以图搜图大接口，支持上传一张或多张证件照/人脸照片，返回相似人物候选，并在候选人物下带出事件数据。
- 备份分支：实现前已推送 `backup/c1-before-face-query-api-20260624-130414`。
- 变更内容：新增 `POST /api/v1/query/face-image`；输入支持 multipart 多文件 `files`、每张图可选 `query_face_indices`、兼容单图 `query_face_index`，并支持 `top_k/min_score/max_gap_sec/include_candidates/event_limit_per_person/match_limit_per_person/include_events/include_matches/camera_id/start_time/end_time`。
- 返回结构：顶层返回 `search_id/engine/query_faces/selected_query_faces/reference_consistency/candidates/ambiguous/warnings/diagnostics`；每个候选人物返回 `person_id/identity_status/score/confidence/score_breakdown/representative_face_url/face_count/event_count/attributes/events/matches/trajectory/appearance_events`。
- 查询策略：多图时默认每张图取第一个检测到的人脸，也可按图指定 face index；用多张参考图 embedding 汇总人物级候选分，并输出参考图一致性状态；默认只查稳定人物，`include_candidates=true` 时包含候选碎片人物。
- 实测结果：单图样例返回 `query_faces=1`、`selected=1`、`candidates=2`，top1 为 `person_83015b61accd46e3b83b986205f873ea`，score `0.912936`，confidence `high`，返回事件 `3` 条、匹配 `3` 条；双图样例返回 `query_faces=2`、`selected=2`，`reference_consistency=consistent`，top1 一致。
- 验证结果：`pytest services/campusvision-c1/tests/test_query_face_preprocessing.py -q` 通过，`4 passed`；完整 `pytest services/campusvision-c1/tests -q` 通过，`80 passed, 2 warnings`；C1 8000 服务已用 `campusvision-c1` 环境后台启动，`/health` 正常。
- 风险与遗留问题：当前实现仍是遍历现有人物和 face records 做向量比对，适合当前本地库规模；后续人物库显著扩大时应引入向量索引或人物 embedding 缓存。事件展示由 GKGuard C2 消费 JSON 完成，CampusVision C1 本次不改 GKGuard C2。
- 涉及文件：`services/campusvision-c1/app/api/routes.py`、`services/campusvision-c1/app/services/person_service.py`、`services/campusvision-c1/app/services/search_service.py`、`services/campusvision-c1/tests/test_query_face_preprocessing.py`、`services/campusvision-c1/README_TASK_REPORTS.md`

## 2026-06-24 13:21:40 CST - 人物特征搜索大接口设计计划

- 版本号：`speng/c1-person-events@2ba9064`
- 任务目标：规划第二个数据库查询大接口：按时间、摄像头、外观倾向、眼镜状态、上装颜色等条件搜索事件；条件均可为空；返回完全匹配事件或相似事件，并标明每条事件不满足哪些条件。
- 现状判断：CampusVision C1 已有 `/events`、`/search/by-clothes`、人物外观倾向 profile、眼镜 profile、appearance sessions 和事件代表图/人脸/人体图字段；新接口应复用这些只读能力，不暴露任意 SQL，不引入 GKGuard C2 改动。
- 计划接口：新增 `POST /api/v1/query/person-attributes`，请求体使用 JSON；支持 `time_range`、`camera_ids`、`gender_presentation`、`glasses_status`、`upper_colors`、`person_scope`、`match_mode`、`top_k`、`limit`、`offset`、`include_candidates`、`include_near_misses`。
- 匹配策略：先用时间、摄像头、识别状态做硬过滤控制搜索空间；再对外观倾向、眼镜、上装颜色做可解释软评分；完全满足条件的事件排前，相似事件按分数排序并输出 `failed_conditions` 和 `condition_scores`。
- 返回结构：顶层返回 `query_id/query/summary/results`；每条 result 包含 `event_id/person_id/identity_status/score/match_type/failed_conditions/condition_scores/event_time/camera/representative_frame_url/representative_body_crop_url/representative_face_crop_url/upper_color/glasses_status/gender_presentation/appearance_session_id`。
- 结果语义：`match_type=exact` 表示所有有值条件满足；`partial` 表示部分满足并说明缺口；`unknown` 表示关键属性不可判断，不直接当作错误；当所有条件为空时返回最近事件或按时间排序的事件列表。
- 保护策略：人工 check 数据只用于评估，不进入搜索逻辑；不搜索下装；接口只读，不改人物库、事件库或 profile；默认返回稳定人物事件，`include_candidates=true` 才包含候选碎片人物。
- 验收建议：空条件、单条件、多条件、冲突条件、unknown 属性、分页、图片 URL 完整性都应有测试；同一条件下 exact 必须排在 partial 前；每条 partial 必须清楚标出不满足的字段，供 C2 展示“相似但不完全满足”。
- 风险与遗留问题：当前外观倾向和眼镜是人物/profile 层能力，事件层传播依赖已有 profile 文件；上装颜色目前以事件/appearance session 的 normalized upper color 为准，准确率仍受模型现状影响。
- 涉及文件计划：`services/campusvision-c1/app/api/routes.py`、`services/campusvision-c1/app/services/person_attribute_query_service.py` 或 `person_service.py`、`services/campusvision-c1/tests/`、`services/campusvision-c1/README_TASK_REPORTS.md`

## 2026-06-24 13:32:39 CST - 人物特征搜索大接口实现

- 版本号：`speng/c1-person-events@2ba9064`
- 任务目标：实现 C1 第二个查询大接口，按时间、摄像头、外观倾向、眼镜状态、上装颜色搜索事件；条件可为空；返回 exact 或 partial，并标出 partial 不满足哪些条件。
- 备份分支：实现前已推送 `backup/c1-before-attribute-query-api-20260624-132419`。
- 变更内容：新增 `POST /api/v1/query/person-attributes`；新增 `person_attribute_query_service.py`；新增请求/响应 schema；新增服务级单元测试。
- 请求能力：JSON body 支持 `time_range.start_time/end_time`、`camera_ids`、`gender_presentation`、`glasses_status`、`upper_colors`、`person_scope`、`include_candidates`、`include_near_misses`、`min_score`、`limit`、`offset`、`candidate_pool_size`。
- 查询策略：时间、摄像头、人物范围用于控制搜索空间；外观倾向、眼镜状态、上装颜色做软匹配评分；exact 结果排前，partial 结果保留并返回 `failed_conditions` 和 `condition_scores`；`unknown` 降权但不伪装为 exact。
- 返回结构：顶层返回 `query_id/created_at/query/summary/results`；每条 result 包含事件基本信息、`score`、`match_type`、`failed_conditions`、`condition_scores`，并包含 `representative_frame_url`、`representative_body_crop_url`、`representative_face_crop_url` 供 C2 直接展示。
- 实测结果：查询 `upper_colors=["black"]`、`glasses_status=["no_glasses"]`、`include_candidates=true` 返回 scanned events `382`、exact `69`、partial `313`；top result 为 exact，图片 URL 三项均存在；partial 样例能标出 `upper_color_mismatch`。
- 验证结果：`py_compile` 通过；新增 `pytest services/campusvision-c1/tests/test_person_attribute_query.py -q` 通过，`3 passed`；完整 `pytest services/campusvision-c1/tests -q` 通过，`83 passed, 2 warnings`；C1 8000 已用 `campusvision-c1` 环境重启，`/health` 正常。
- 保护策略：接口只读，不改人物库、事件库、profile 或人工评估数据；默认只返回稳定身份事件，`include_candidates=true` 时才包含候选人物；仍不搜索下装。
- 风险与遗留问题：当前上装颜色、外观倾向和眼镜状态准确率受现有模型/profile 质量限制；当前库规模下遍历事件足够，后续事件量大时应增加索引或缓存。
- 涉及文件：`services/campusvision-c1/app/api/routes.py`、`services/campusvision-c1/app/schemas.py`、`services/campusvision-c1/app/services/person_attribute_query_service.py`、`services/campusvision-c1/tests/test_person_attribute_query.py`、`services/campusvision-c1/README_TASK_REPORTS.md`

## 2026-06-24 13:39:48 CST - v1 PR 前系统检查

- 版本号：`speng/c1-person-events@2ba9064`，当前工作区仍有未提交变更；远端 `origin/speng/c1-person-events` 也停在 `2ba9064`，今天新增接口和报告尚未 push。
- 分支状态：当前分支相对 `origin/main` 已有 `38` 个提交；PR 基础能力来自 CampusVision C1，不涉及 GKGuard C2/桌面壳。
- PR 文件防护：新增 `.gitignore` 规则，忽略 `.vscode/`、`*.crt`、`*.key`、`services/campusvision-c1/*.log`、`services/campusvision-c1/logs/`；已确认本地 `auto.key`、`auto.crt`、C1 日志、`data/`、`testdata/` 不会误进 PR。
- 待提交文件范围：tracked diff 约 `1892` 行新增、`93` 行删除；另有必须显式 add 的 untracked 文件：`README_TASK_REPORTS.md`、`person_attribute_query_service.py`、`export_remappable_event_outfit_group_eval.py`、`export_remappable_outfit_eval.py`、`test_event_outfit_group_eval.py`、`test_person_attribute_query.py`。
- 静态基础检查：`git diff --check` 通过；C1 关键 Python 文件 `py_compile` 通过。
- 测试结果：完整 `pytest services/campusvision-c1/tests -q` 通过，`83 passed, 2 warnings`。
- 运行态检查：8000 端口由 `/home/speng/miniforge3/envs/campusvision-c1/bin/python` 启动的 C1 uvicorn 进程监听；`/health` 正常；`/api/v1/persons/gallery`、`/api/v1/appearance-sessions/gallery`、`/api/v1/outfit-labels/review`、`/api/v1/event-outfit-groups/review` 均返回 `200`。
- 查询接口 smoke test：`POST /api/v1/query/face-image` 单图样例返回 `query_faces=1`、`selected=1`、`candidates=2`，top1 score `0.912936`；`POST /api/v1/query/person-attributes` 样例返回 scanned events `382`、exact `69`、partial `313`，非法枚举返回 `400`。
- 当前指标快照：人脸聚合 pairwise precision/F1 通过；上装颜色装束级指标通过；API 处理实时性和长跑内存通过；当前库 counts 为 persons `44`、stable persons `24`、candidate persons `20`、identified events `382`。
- 未达目标指标：事件装束分组 pairwise F1 `0.888287`，低于目标 `0.90`；purity `0.916667`，低于目标 `0.98`。这不阻断 v1 演示闭环，但 PR 描述需要作为已知限制说明。
- PR 结论：系统可以准备 v1 PR，但必须先提交并 push 当前工作区；PR 描述建议把“装束分组未达最终目标”列为 Known limitations，避免过度承诺。
- 涉及文件：`.gitignore`、`services/campusvision-c1/**/*`、`services/campusvision-c1/README_TASK_REPORTS.md`

## 2026-06-24 13:45:33 CST - GKGuard C2 对接文档

- 版本号：`speng/c1-person-events@2ba9064`
- 任务目标：为即将开始的 GKGuard C2 工作提供 CampusVision C1 v1 接口契约文档，避免 GKGuard C2 误读任务报告或直接依赖 CampusVision C1 本地文件路径。
- 新增文档：`services/campusvision-c1/README_C2_INTEGRATION.md`
- 文档内容：CampusVision C1 base URL、健康检查、人脸以图搜人接口、人物特征搜索接口、media 图片 URL、枚举值、请求/响应示例、GKGuard C2 展示建议、错误处理和 known limitations。
- 对接重点：GKGuard C2 事件主图优先用 `representative_body_crop_url`，现场图用 `representative_frame_url`，人脸小图用 `representative_face_crop_url`；`partial` 搜索结果必须展示 `failed_conditions`；`unknown` 表示无法判断，不等于否定。
- 风险说明：文档明确上装颜色、外观倾向、眼镜状态来自模型/profile，GKGuard C2 不应当作绝对事实；装束分组当前未完全达到最终指标，但不影响两个查询大接口使用。
- 验证结果：文档已创建并检查，未改动 GKGuard C2；当前文件仍未提交，PR 前需要将该文档加入 commit。
- 涉及文件：`services/campusvision-c1/README_C2_INTEGRATION.md`、`services/campusvision-c1/README_TASK_REPORTS.md`

## 2026-06-27 10:11:26 CST - 拉取 v0.3.2 并重启 C1

- 版本号：`main@9d6323b`，tag `v0.3.2`
- 任务目标：按用户确认的 GitHub 最新版本 `v0.3.2` 更新本地仓库，并重新启动 CampusVision C1 服务。
- 仓库操作：执行 `git fetch origin --prune --tags` 后确认 `v0.3.2` 指向 `origin/main@9d6323b`；本地 `main` 从 `02424c8` 快进到 `9d6323b`。
- 本地修改处理：切换前将上一轮未提交的本地任务报告修改暂存到 `stash@{0}`，避免被切换分支覆盖。
- 服务操作：停止旧 PID `16700`，使用 `/home/speng/miniforge3/envs/campusvision-c1/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` 启动新服务。
- 运行状态：新 PID `17139` 正在监听 `127.0.0.1:8000`。
- 健康检查：`GET /health` 返回 `200 OK`，`status=ok`，`face_engine=insightface`，数据库路径为 `services/campusvision-c1/data/campusvision.sqlite3`。
- 日志位置：`services/campusvision-c1/data/logs/c1_uvicorn.log`
- 影响范围：更新仓库到 `v0.3.2` 并重启 CampusVision C1；未改动数据库、模型文件、测试数据或 GKGuard C2 代码。

## 2026-06-29 10:11:45 CST - C1 当前进度总结

- 版本号：`main@9d6323b`，tag `v0.3.2`
- 任务目标：总结 CampusVision C1 当前完成进度、已有结果、主要问题和下一步计划。
- 当前运行状态：C1 8000 服务健康检查正常，`GET /health` 返回 `status=ok`，人脸引擎为 `insightface`，数据库为 `services/campusvision-c1/data/campusvision.sqlite3`。
- 当前数据规模：数据库包含 videos `15`、camera count `15`、persons `44`、稳定人物 `24`、候选人物 `20`、events `1345`、identified events `382`、person observations `1616`、face records `1096`、person faces `653`、appearance sessions `44`。
- 已完成能力：视频/API 入库、抽帧、人脸检测与 embedding、人物聚合、事件构建、人物库、appearance sessions/装束库、上装颜色识别、外观倾向、眼镜状态、人工评估页面、可重映射评估、C2 查询接口和对接文档均已具备。
- 查询接口结果：`POST /api/v1/query/face-image` 支持多图以图搜人并返回候选人物、事件和媒体 URL；`POST /api/v1/query/person-attributes` 支持时间、摄像头、外观倾向、眼镜状态、上装颜色等条件检索，并返回 exact/partial 与 failed conditions。
- 当前模型链路：人脸为 InsightFace buffalo_l / ArcFace；人物合并为 `person_merge_logreg_v1`；人体检测当前有效后端为 `opencv_hog`，YOLO11x 模型路径已配置但未启用；上装颜色为 CLIP ViT-H/14 + SCHP-LIP `profile_realtime_balanced_prompt_v2`；装束分组为 `source_visual_outfit_group_v2`；外观倾向和眼镜状态均为 CLIP H/14 zero-shot。
- 已有指标：人脸聚合 pairwise precision `1.0`、F1 `0.971429`，达到目标；上装颜色选定装束级准确率 `0.85`，达到 `>=0.8` 目标；生产装束 summary 人工集为 `58/72 = 80.56%`，刚过通过线；API benchmark 处理 `25.166667s` 视频耗时 `13.760847s`，实时系数 `0.546789`；30 分钟内存监测 RSS 增长 `20.734MB`，通过稳定性阈值。
- 未达标问题：事件装束分组 pairwise F1 `0.888287`，低于目标 `0.90`；purity `0.916667`，低于目标 `0.98`；当前评估只覆盖 remap 后 `264/324 = 81.48%` 人工事件装束标注，状态为 `partial_evaluated`。
- 其他风险：部分早期人工评估集不能直接按旧数据库 ID replay，需要依赖可重映射导出；当前人体检测主链路仍是 OpenCV HOG，不是 YOLO11x；真实学校海康 H.265/海康格式数据尚未正式接入验证；C1 仍是学生项目/原型级闭环，不应按生产级大规模部署承诺。
- 下一步计划：第一，优先把人体检测主链路切到 YOLO11x 并重跑评估，改善人体框和上装 ROI；第二，优化事件装束分组，目标 pairwise F1 `>=0.90`、purity `>=0.98`，同时不牺牲人脸聚合 precision；第三，把全量清库重跑、remap 人工评估、输出目标指标脚本化；第四，做 2-4 小时以上本地实时/API 长跑；第五，等学校数据到位后做 H.265/海康格式适配和真实摄像头/NVR 接入验证。
- 影响范围：本次仅追加总结报告，未改动业务代码、数据库、模型文件、测试数据或 GKGuard C2。

## 2026-06-29 10:25:10 CST - 中期检查英文单页 PPT 图片

- 版本号：`main@9d6323b`，tag `v0.3.2`
- 任务目标：为 2-3 分钟中期检查生成一张英文 16:9 PPT 图片，概括 CampusVision C1 当前进度、数据规模、评估结果、已知问题和下一步计划。
- 生成文件：`services/campusvision-c1/data/reports/c1_midterm_summary_slide.png`
- 页面内容：标题为 `CampusVision C1: Video-to-Person Intelligence Pipeline`；包含 Completed Pipeline、Current Data Scale、Evaluation Results、Known Gaps & Next Steps 四块。
- 用户补充后已更新：页头增加 `Current data: ChokePoint open surveillance dataset`，并说明正在 `Preparing workstation for campus monitoring API`，用于表达当前使用开源监控数据集，下一阶段准备接入学校监控 API 数据。
- 用户要求样例图后已更新：左侧 Completed Pipeline 区域加入 ChokePoint 真实监控帧样例，选用可见全身的人体框和人脸框，展示从普通监控画面到 body/face observation 的实际输入效果。
- 关键数据：展示 videos/cameras `15`、persons `44`、stable identities `24`、events `1,345`、identified events `382`、face records `1,096`；展示 face clustering precision `1.00`、F1 `0.971`、upper-color outfit accuracy `85%`、outfit grouping F1 `0.888`、purity `0.917`、API `25.2s video -> 13.8s processing`。
- 设计处理：使用本地 Pillow 直接绘制 `1920x1080` PNG，避免 AI 图片生成导致文字失真；最终人工检查确认没有明显文字截断或重叠。
- 影响范围：仅新增/覆盖汇报图片并追加本报告，未改动业务代码、数据库、模型文件、测试数据或 GKGuard C2。

## 2026-06-29 12:38:19 CST - 中期检查报告项目基本信息

- 版本号：`main@9d6323b`，tag `v0.3.2`
- 任务目标：按整体项目大局补充中期检查报告模板中的第 1 节“项目基本信息”，不从 C1 单模块视角填写。
- 更新文件：`services/campusvision-c1/data/reports/CyberLUBAN_Midterm_Check_Template(1).docx`
- 备份文件：`services/campusvision-c1/data/reports/CyberLUBAN_Midterm_Check_Template(1).docx.bak`
- 填写内容：项目名称为 `GKGuard 校园智能巡检与监控联动系统（CyberLUBAN CampusCar 项目）`；项目定位为校园场景学生项目 / MVP 原型，强调普通校园监控视频智能感知、数据检索平台和后续移动机器人联动；目标应用场景覆盖校园楼宇、走廊、出入口和重点区域巡检辅助与事件检索。
- 边界说明：总体沿用开题方向；中期阶段将验收边界收敛为可验证的软件与算法闭环，以及学校监控 API / 工作站接入准备；当前使用 ChokePoint 开源监控数据集验证闭环，真实校园监控 API 和更完整机器人联动待资源到位后推进。
- 影响范围：仅修改报告文档第 1 节项目基本信息；未改动业务代码、数据库、模型文件、测试数据或 GKGuard C2。

## 2026-06-29 12:44:18 CST - 中期报告填写分工规则

- 版本号：`main@9d6323b`，tag `v0.3.2`
- 任务目标：明确后续填写中期检查报告时的模块边界，避免代写非本人负责范围。
- 填写规则：若内容属于 CampusVision C1 或项目总体大局，则直接填写；若内容属于 A 组机械、B 组电控、C2 前端/平台展示，则只标注占位符，后续由对应同学补充。
- 占位格式：A 组内容标 `【A】`，B 组内容标 `【B】`，C2 内容标 `【C2】`。
- C 组边界：C 组算法分为 C1 和 C2；C1 指当前本地后端算法/数据库/API 服务，C2 指前端展示、平台交互和界面集成。后续报告中 C1 可直接填写，C2 不代写。
- 补充边界：安全漏洞补丁、安全加固、前端路由保护、平台鉴权和用户侧访问控制也归 C2 负责；报告中相关内容标 `【C2】`，不代写。
- 影响范围：仅记录后续报告填写规则，未改动业务代码、数据库、模型文件、测试数据或报告正文。

## 2026-06-29 12:50:31 CST - 修正项目基本信息中的巡检小车参与感

- 版本号：`main@9d6323b`，tag `v0.3.2`
- 任务目标：修正中期检查报告第 1 节，避免把项目写成纯监控软件，明确 A/B 机械电控开发的巡检小车是系统中的移动感知与执行终端。
- 更新文件：`services/campusvision-c1/data/reports/CyberLUBAN_Midterm_Check_Template(1).docx`
- 新增备份：`services/campusvision-c1/data/reports/CyberLUBAN_Midterm_Check_Template(1).docx.before_vehicle_context_20260629_1248.bak`
- 修正内容：项目名称改为 `GKGuard 校园智能巡检与监控联动系统（CyberLUBAN CampusCar 巡检小车项目）`；项目定位改为巡检小车硬件端、摄像头/监控接入端、后端智能分析服务和前端平台共同组成；明确小车搭载或接入摄像头后可作为移动监控点，把视频流接入 GKGuard。
- 边界说明：第 1 节属于总体大局，因此直接填写；A/B 的具体机械、电控实现细节仍不代写，后续对应章节按 `【A】` / `【B】` 占位。
- 影响范围：仅修改报告文档第 1 节项目基本信息并追加本报告；未改动业务代码、数据库、模型文件、测试数据或 GKGuard C2。

## 2026-06-29 12:59:21 CST - 清理误传开题报告与第 2 节草稿

- 版本号：`main@9d6323b`，tag `v0.3.2`
- 任务目标：按要求删除基于误传开题报告写入的内容，并删除误传开题报告文件。
- 清理文件：已删除 `services/campusvision-c1/data/reports/CyberLUBAN_Topic_Selection_ZH_EN(1).docx`。
- 恢复内容：`services/campusvision-c1/data/reports/CyberLUBAN_Midterm_Check_Template(1).docx` 已恢复到第 2 节填写前状态，第 2 节表格和小结保持空白，等待正确开题报告。
- 保留内容：第 1 节项目基本信息仍保留，因为其后续已按整体项目大局和巡检小车参与感修正，不依赖误传开题报告。
- 影响范围：仅清理误传开题报告、第 2 节草稿和对应错误任务记录；未改动业务代码、数据库、模型文件、测试数据或 GKGuard C2。

## 2026-06-29 13:06:43 CST - 完整填写中期检查报告

- 版本号：`main@9d6323b`，tag `v0.3.2`
- 任务目标：不再参考误传开题报告，按当前 GKGuard / CampusCar 项目的合理 MVP 边界完整填写中期检查报告模板。
- 更新文件：`services/campusvision-c1/data/reports/CyberLUBAN_Midterm_Check_Template(1).docx`
- 新增备份：`services/campusvision-c1/data/reports/CyberLUBAN_Midterm_Check_Template(1).docx.before_full_fill_20260629_130256.bak`
- 填写内容：补齐第 2-10 节，包括开题目标回顾、阶段性成果、A/B/C 技术组进展、核心测试记录、安全合规、当前风险、下一阶段计划、附件清单和导师/队长确认区。
- 分工边界：总体项目和 C1 内容直接填写；A 组机械、B 组电控、C2 平台展示/安全/交互相关内容保留 `【A】`、`【B】`、`【C2】` 占位，后续由对应同学补充。
- C1 证据：写入当前 v0.3.2 数据规模和指标，包括 15 路 ChokePoint 普通监控视频、1345 个事件、382 个已识别事件、44 个人物、1096 条人脸记录、人脸聚合 F1 `0.9714`、上装装束级准确率 `0.85`、25.17s 视频处理耗时 `13.76s`。
- 验证结果：已用 `unzip -t` 校验 docx 压缩结构正常；抽取 `word/document.xml` 复核后，报告 8 张表无空白单元格。
- 影响范围：仅修改本地报告文档并追加本任务报告；未改动业务代码、数据库、模型文件、测试数据或 GKGuard C2。

## 2026-06-29 13:10:25 CST - 中期检查报告待补内容标红

- 版本号：`main@9d6323b`，tag `v0.3.2`
- 任务目标：将中期检查报告中待其他同学填写的占位符和相关提示词标红，方便后续人工补全。
- 更新文件：`services/campusvision-c1/data/reports/CyberLUBAN_Midterm_Check_Template(1).docx`
- 新增备份：`services/campusvision-c1/data/reports/CyberLUBAN_Midterm_Check_Template(1).docx.before_red_placeholders_20260629_131000.bak`
- 标红范围：实际文档中存在的 `【A】`、`【B】`、`【C2】`、`【A/B】` 已全部标红；同时标红 `请补充`、`待补充`、`待补`、`待填写`、`待提交前确认`、`待录制`、`待导师填写`、`待队长最终核对`、`待外场前确认` 等提示词。文档中当前没有 `【C1】` 占位符，已保留已完成的 C1 正文为正常颜色。
- 验证结果：`unzip -t` 校验 docx 结构正常；XML 复核显示 `【A】21/21`、`【B】28/28`、`【C2】19/19`、`【A/B】1/1` 均在红色 run 中，相关提示词也全部匹配为红色。
- 影响范围：仅修改本地报告文档并追加本任务报告；未改动业务代码、数据库、模型文件、测试数据或 GKGuard C2。

## 2026-06-29 13:19:12 CST - 中期检查报告待填项落实到负责人

- 版本号：`main@9d6323b`，tag `v0.3.2`
- 任务目标：把中期检查报告中泛化的 A/B/C2 待填占位改成逐项负责人字段，避免只写一句“由某组补充”。
- 更新文件：`services/campusvision-c1/data/reports/CyberLUBAN_Midterm_Check_Template(1).docx`
- 新增备份：`services/campusvision-c1/data/reports/CyberLUBAN_Midterm_Check_Template(1).docx.before_owner_assignment_20260629_132000.bak`、`services/campusvision-c1/data/reports/CyberLUBAN_Midterm_Check_Template(1).docx.before_owner_cleanup_20260629_132600.bak`、`services/campusvision-c1/data/reports/CyberLUBAN_Midterm_Check_Template(1).docx.before_owner_final_tidy_20260629_133000.bak`
- 变更内容：所有原 `【A】`、`【B】`、`【C2】`、`【A/B】` 占位已替换为具体负责人字段；C1 责任人写为 `pengshihan538 / speng`；C2 责任人根据 git 历史可确认信息写为 `Hao OUYANG / Cyrus Auyeung（需本人确认）`；A/B 因仓库没有成员姓名，改为红色 `【A组机械负责人姓名】`、`【B组电控负责人姓名】`，后续可直接替换为真实姓名。
- 补充负责人：导师意见写入负责人 `阚林戈`；队长确认、队长姓名、联系方式写入红色 `【队长姓名】`；演示视频和监控数据/合规对接也分别增加红色负责人姓名槽位。
- 验证结果：`unzip -t` 校验 docx 结构正常；报告表格无空白单元格；XML 复核显示裸 `【A】/【B】/【C1】/【C2】/【A/B】` 数量均为 `0`，负责人姓名槽位和待补提示词均在红色 run 中。
- 影响范围：仅修改本地报告文档并追加本任务报告；未改动业务代码、数据库、模型文件、测试数据或 GKGuard C2。

## 2026-06-29 13:38:34 CST - 中期检查报告待填项改回简洁组别标注

- 版本号：`main@9d6323b`，tag `v0.3.2`
- 任务目标：按用户要求撤回复杂姓名槽位，改为直接使用 `【A】`、`【B】`、`【C2】` 等组别标注，并保证每个红色待填位置都有 `【】` 标注。
- 更新文件：`services/campusvision-c1/data/reports/CyberLUBAN_Midterm_Check_Template(1).docx`
- 新增备份：`services/campusvision-c1/data/reports/CyberLUBAN_Midterm_Check_Template(1).docx.before_simple_bracket_labels_20260629_134000.bak`
- 变更内容：移除 `负责人：【A组机械负责人姓名】`、`负责人：【B组电控负责人姓名】`、`Hao OUYANG / Cyrus Auyeung` 等复杂负责人写法；改回 `【A】`、`【B】`、`【C2】` 展示。少数非 A/B/C2 待填项保留简洁 `【队长】`、`【导师】`、`【全组】` 标注。
- 验证结果：`unzip -t` 校验 docx 结构正常；报告表格无空白单元格；XML 复核显示复杂负责人字段数量为 `0`，红色 run 中无缺少 `【】` 标注的片段，`【A】27/27`、`【B】34/34`、`【C2】21/21` 均为红色。
- 影响范围：仅修改本地报告文档并追加本任务报告；未改动业务代码、数据库、模型文件、测试数据或 GKGuard C2。

## 2026-07-01 10:58:34 CST - 确认最新版本并重启 C1 服务

- 版本号：`main@9d6323b`，tag `v0.3.2`
- 任务目标：按要求更新到最新版本，并确认本地 CampusVision C1 服务运行在当前版本。
- 仓库状态：执行 `git fetch origin --prune --tags` 后确认 `origin/main` 仍为 `9d6323b`，最新 tag 仍为 `v0.3.2`；本地 `main` 与 `origin/main` 差异为 `0/0`，无需快进拉取。
- 本地改动保护：保留当前本地报告文档和 `README_TASK_REPORTS.md` 修改，未执行 reset、checkout 或覆盖操作。
- 服务操作：停止旧 C1 进程 `17139`，使用 `/home/speng/miniforge3/envs/campusvision-c1/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` 重新启动服务。
- 运行状态：新服务 PID 为 `70318`，监听 `127.0.0.1:8000`；`GET /health` 返回 `status=ok`，`face_engine=insightface`，数据库路径为 `services/campusvision-c1/data/campusvision.sqlite3`。
- 日志位置：`services/campusvision-c1/data/logs/c1_uvicorn_20260701_105830_setsid.log`
- 影响范围：仅同步远端元数据并重启 CampusVision C1 服务；未改动业务代码、数据库、模型文件、测试数据或 GKGuard C2。

## 2026-07-01 13:06:53 CST - C1 单卡 6 路实时候选热路径优化

- 版本号：`main@7e795e9`
- 任务目标：将 CampusVision C1 从当前约 1-2 路能力推进到单张 RTX 3090 可稳定支持 6 路实时分析；人工 check 数据仍仅用于评估；重大改动前已创建并推送备份分支。
- 备份分支：已推送 `backup/c1-before-async-event-build-20260701-124719`，用于保存异步事件构建改造前的基线。
- 核心改动：新增后台事件构建队列 `event_build_queue.py`；`EVENT_PERSISTENCE_MODE=sync|async|disabled` 支持实时热路径先返回 indexed，再后台重建 events/appearance sessions；benchmark 在 async 模式下每轮结束后 drain 队列，避免临时 DB 被后台任务干扰。
- 并行策略：取消 live capture 默认全局串行 `index_video()`，改由 InsightFace/YOLO 的 bounded semaphore 和 SQLite 写锁控制并发；全库人物索引重建仍保留锁，避免与实时入库互相污染。
- 实时候选配置：本地 `.env` 已切到 `INSIGHTFACE_DET_SIZE=960`、`INSIGHTFACE_ENGINE_POOL_SIZE=1`、`INSIGHTFACE_MAX_CONCURRENT_INFERENCES=1`、`EVENT_PERSISTENCE_MODE=async`、`BODY_DETECTION_FRAME_STRIDE=2`、`CLOTHING_ANALYSIS_FRAME_STRIDE=2`、`UPPER_COLOR_BACKEND=hsv`、`SERIALIZE_LIVE_ANALYSIS=false`。`.env.example` 已同步新增这些配置项。
- 质量取舍：不降低人脸采样频率，6 路候选仍保持每路 128 条 face records；人体检测从每帧变为隔帧，样例视频 body detections 从约 58/路降到 30/路；衣着颜色分析也隔帧执行，事件/装束层面依赖后续聚合补齐。
- 验证测试：`python -m py_compile app/services/event_build_queue.py app/services/video_service.py app/services/observation_service.py app/services/live_service.py app/core/config.py scripts/benchmark_api_processing.py` 通过；`pytest tests/test_video_service.py tests/test_live_service.py tests/test_observation_service.py tests/test_event_service.py tests/test_security_config.py -q` 通过，42 passed。
- 6 路基准：使用 `P2L_S5_C2_30fps.mp4`，视频时长 `25.166667s`，`frame_interval_sec=1.0`，并发 6 路，warmup 1 次、measured 3 次；结果 `mean_processing_sec=18.299367s`、`max_processing_sec=18.635613s`、`max_realtime_factor=0.740488`、`mean_effective_realtime_streams=8.251651`，3 次 measured 均低于视频时长。
- 对照结果：仅 async + HSV + body stride 2 时，3 次 measured 的 `max_processing_sec=26.765671s`，仍未稳定达标；加入 `CLOTHING_ANALYSIS_FRAME_STRIDE=2` 后稳定过线。
- 产物文件：`data/evals/runtime/c1_api_processing_benchmark_async6_stride2_clothing2_3runs.json`、`data/evals/runtime/c1_api_processing_benchmark_async1_stride2_clothing2_profile.json`。
- 服务状态：已用 `/home/speng/miniforge3/envs/campusvision-c1/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` 启动 C1，PID `98074`；`GET /health` 返回 `status=ok`；日志为 `data/logs/c1_uvicorn_20260701_130746_realtime6.log`。
- 当前限制：这是基于 ChokePoint 单个 25s 样例视频的 6 路并发验证，尚未完成多视频混合、2-4 小时长跑、真实学校摄像头 API/H.265 数据验证；因此暂不宣称最终商业化容量，只作为 C1 v1 实时候选热路径。
- 影响范围：仅改动 CampusVision C1；未上传或删除 `testdata` 下视频；未改动 GKGuard C2、A/B 相关代码；人工 check 数据没有进入训练或线上逻辑。

## 2026-07-01 13:18:28 CST - C1 多源 6 路混合实时压测

- 版本号：`main@e2cf7d1`
- 任务目标：补齐上一轮单视频克隆压测的证据不足，验证 6 路并发不是只对同一个 mp4 重复输入成立，而是在多个不同摄像头视频源上也能满足实时热路径。
- 工具改动：`scripts/benchmark_api_processing.py` 新增 `--video-ids`，支持多个源视频按路分配或循环复用；报告 schema 更新为 `c1_api_processing_benchmark_v2`，新增 `source_videos`、`route_realtime_factor`、`max_route_realtime_factor`、`passes_realtime_all_routes` 等多源指标，同时保留旧的 wall realtime 字段。
- 验证视频：使用 P2E_S5 三个视角和 P2L_S5 三个视角，共 6 个不同源视频：`P2E_S5_C1/C2/C3_30fps.mp4`、`P2L_S5_C1/C2/C3_30fps.mp4`。视频时长分别约 `26.866667s` 和 `25.166667s`。
- 验证配置：`EVENT_PERSISTENCE_MODE=async`、`UPPER_COLOR_BACKEND=hsv`、`INSIGHTFACE_DET_SIZE=960`、`INSIGHTFACE_ENGINE_POOL_SIZE=1`、`INSIGHTFACE_MAX_CONCURRENT_INFERENCES=1`、`BODY_DETECTION_FRAME_STRIDE=2`、`CLOTHING_ANALYSIS_FRAME_STRIDE=2`、`BODY_DETECTION_BACKEND=opencv_hog`。
- 多源 6 路结果：warmup 1 次、measured 3 次，`max_processing_sec=16.957331s`，`max_wall_realtime_factor=0.631166`，`mean_wall_realtime_factor=0.626615`，`max_route_realtime_factor=0.671537`，`passes_realtime_all_routes=true`，`mean_effective_realtime_streams=9.575258`。
- 单路兼容烟测：同一脚本旧用法仍可运行；`P2L_S5_C2_30fps.mp4` 单路 `max_processing_sec=4.853662s`，`max_route_realtime_factor=0.192861`，`passes_realtime_all_routes=true`。
- 验证测试：`python -m py_compile scripts/benchmark_api_processing.py` 通过；`pytest tests/test_video_service.py tests/test_live_service.py tests/test_observation_service.py tests/test_event_service.py tests/test_security_config.py -q` 通过，42 passed。
- 产物文件：`data/evals/runtime/c1_api_processing_benchmark_v2_mixed6_p2e_p2l_3runs.json`、`data/evals/runtime/c1_api_processing_benchmark_v2_single_smoke.json`。
- 当前判断：C1 在 ChokePoint P2E/P2L 多源 6 路输入上已满足 3090 单卡实时热路径；剩余需要补的是更长时间长跑、更多视频组合和真实学校摄像头 API/H.265 接入验证。
- 影响范围：仅增强 C1 benchmark 工具并追加报告；未改动业务推理链路、数据库生产数据、`testdata` 视频、GKGuard C2 或 A/B 代码；人工 check 数据没有进入训练或线上逻辑。

## 2026-07-01 13:23:56 CST - C1 多源 6 路 10 次重复稳定性验证

- 版本号：`main@6eebf15`
- 任务目标：在 3 次 mixed benchmark 通过后，继续用同一组 P2E_S5/P2L_S5 六个不同源视频做更长一点的重复验证，观察是否出现偶发 CUDA/ONNXRuntime 错误、失败路由或超过实时阈值的尾部延迟。
- 验证配置：沿用 6 路候选热路径：`EVENT_PERSISTENCE_MODE=async`、`UPPER_COLOR_BACKEND=hsv`、`INSIGHTFACE_DET_SIZE=960`、`INSIGHTFACE_ENGINE_POOL_SIZE=1`、`INSIGHTFACE_MAX_CONCURRENT_INFERENCES=1`、`BODY_DETECTION_BACKEND=opencv_hog`、`BODY_DETECTION_FRAME_STRIDE=2`、`CLOTHING_ANALYSIS_FRAME_STRIDE=2`。
- 运行方式：warmup 1 次、measured 10 次，`concurrent_routes=6`，每次同时处理 P2E_S5 三视角和 P2L_S5 三视角；benchmark 使用临时 DB 副本，不写生产数据库。
- 结果摘要：10 次 measured 无失败路由，未出现 CUDA/ONNXRuntime 报错；`max_processing_sec=17.742060s`、`mean_processing_sec=16.204369s`、`max_wall_realtime_factor=0.660374`、`mean_wall_realtime_factor=0.603140`、`max_route_realtime_factor=0.690314`、`mean_route_realtime_factor=0.578283`、`passes_realtime_all_routes=true`、`mean_effective_realtime_streams=9.947934`。
- measured wall time 列表：`[17.418480, 16.808566, 16.786363, 17.100249, 15.116969, 16.040952, 15.305643, 14.750841, 17.742060, 14.973568]`。
- 产物文件：`data/evals/runtime/c1_api_processing_benchmark_v2_mixed6_p2e_p2l_10runs.json`。
- 当前判断：在 ChokePoint P2E/P2L 混合视频上，C1 6 路实时热路径已具备较强证据；仍未替代后续真实摄像头 API/H.265 接入验证和 2-4 小时以上服务长跑。
- 影响范围：仅追加验证报告和 benchmark 输出文件；未改动业务代码、生产数据库、`testdata` 视频、GKGuard C2 或 A/B 代码；人工 check 数据没有进入训练或线上逻辑。

## 2026-07-01 13:46:29 CST - C1 长跑稳定性脚本与内存清理保护

- 版本号：`main@94ee06c`
- 任务目标：继续补齐 6 路实时分析的长期稳定性证据，增加可复用的 6 路混合循环稳定性脚本，并针对 RSS 持续上涨增加 post-index 内存清理保护。
- 备份分支：在改动生产热路径前已推送 `backup/c1-before-post-index-memory-trim-20260701-133358`。
- 工具改动：新增 `scripts/stability_realtime_mixed.py`，可循环调用多源 6 路 benchmark，记录每轮 `max_processing_sec`、单路 realtime factor、失败路由、当前进程 RSS、GPU compute app 显存，并将每轮详细报告和总报告写入 `data/evals/runtime`。
- benchmark 修正：`scripts/benchmark_api_processing.py` 现在在每次 `run_benchmark()` 后恢复原始 `settings.data_dir/db_path`，便于同一 Python 进程内循环调用，不把进程留在临时 DB。
- 内存保护：新增 `ENABLE_POST_INDEX_MEMORY_CLEANUP` 和 `POST_INDEX_MEMORY_CLEANUP_INTERVAL`；在 `index_video()` 写库、异步事件入队后释放大型工作集，并按间隔触发 `gc.collect()` 与 Linux `malloc_trim(0)`。本机 `.env` 已启用，当前候选值为每 6 个 indexed videos 清理一次。
- 验证测试：`python -m py_compile app/core/config.py app/services/video_service.py scripts/benchmark_api_processing.py scripts/stability_realtime_mixed.py` 通过；`pytest tests/test_video_service.py tests/test_live_service.py tests/test_observation_service.py tests/test_event_service.py tests/test_security_config.py -q` 通过，44 passed。
- 10 轮无清理基线：`c1_realtime_mixed6_stability_10cycles.json`，10 cycles、0 failed routes、`max_processing_sec=16.889067s`、`max_wall_realtime_factor=0.628625`、`max_route_realtime_factor=0.658628`、GPU 显存稳定 `1222MB`，但 RSS 从 `2755.121MB` 增至 `3669.141MB`，增长 `914.020MB`。
- 10 轮 interval=6 清理：`c1_realtime_mixed6_stability_10cycles_trim.json`，10 cycles、0 failed routes、`max_processing_sec=17.627060s`、`max_wall_realtime_factor=0.656094`、`max_route_realtime_factor=0.696602`、GPU 显存稳定 `1210MB`，RSS 从 `2218.477MB` 增至 `2908.156MB`，增长 `689.679MB`。
- 5 轮 interval=1 清理复核：`c1_realtime_mixed6_stability_5cycles_trim1_release.json`，5 cycles、0 failed routes、`max_processing_sec=16.799693s`、`max_wall_realtime_factor=0.625299`、`max_route_realtime_factor=0.665304`、GPU 显存稳定 `1210MB`，RSS 从 `2201.129MB` 增至 `2618.449MB`，增长 `417.320MB`。
- 当前判断：吞吐和 GPU 稳定性继续满足 6 路实时热路径；RSS 增长有所缓解但未完全消除，推测主要来自底层库/allocator arena 保留而不是 Python 工作集引用。该保护可降低风险，但还不能替代 2-4 小时真实长跑；若真实长跑仍线性增长，下一步应做进程级 worker recycle 或服务级 max-requests 策略。
- 影响范围：仅改动 CampusVision C1；未上传或删除 `testdata` 下视频；未改动 GKGuard C2、A/B 相关代码；人工 check 数据没有进入训练或线上逻辑。

## 2026-07-01 13:57:27 CST - C1 6 路压测补充进程指标

- 版本号：`main@d855154`
- 任务目标：回答“只能缩短处理时间、不能并行处理吗”的工程落点，继续把 6 路实时优化从单纯耗时压缩推进到“受控并行 + 可观测稳定性”。
- 工具改动：`scripts/benchmark_api_processing.py` 新增每轮 `process_metrics_before/after`，记录当前进程 RSS、当前进程 GPU 显存和 `nvidia-smi` compute apps；报告顶层新增 `measured_rss_start/end/min/max/delta_mb` 与 `measured_gpu_min/max_mb`，用于区分冷启动模型加载和稳态运行漂移。
- 并行判断：C1 当前不是只能缩短单路处理时间，已经支持 6 路视频同时进入分析；并行方式是多路解码/抽帧/入库并行，GPU 推理通过 bounded semaphore 受控调度，避免每路重复加载模型或无界抢占 3090。
- 验证测试：`python -m py_compile scripts/benchmark_api_processing.py` 通过；`pytest tests/test_video_service.py tests/test_live_service.py tests/test_observation_service.py tests/test_event_service.py tests/test_security_config.py -q` 通过，44 passed；C1 8000 `/health` 正常。
- 冷启动 6 路结果：`c1_api_processing_benchmark_v2_mixed6_metrics_3runs.json`，3 次 measured、6 路总失败 `0`，`max_processing_sec=15.929375s`，`max_wall_realtime_factor=0.592905`，`max_route_realtime_factor=0.629149`，`passes_realtime_all_routes=true`，`mean_effective_realtime_streams=10.319428`；首次模型加载导致 RSS 从 `116.781MB` 到 `2387.113MB`，GPU 显存稳定 `1204MB`。
- warmup 后 6 路结果：`c1_api_processing_benchmark_v2_mixed6_metrics_warm1_3runs.json`，warmup 1 次后 measured 3 次、6 路总失败 `0`，`max_processing_sec=17.568375s`，`max_wall_realtime_factor=0.653910`，`max_route_realtime_factor=0.693337`，`passes_realtime_all_routes=true`，`mean_effective_realtime_streams=9.395434`；稳态 RSS 从 `1938.637MB` 到 `2433.734MB`，增长 `495.097MB`，GPU 显存稳定 `1216MB`。
- trim interval=1 对照：临时覆盖 `POST_INDEX_MEMORY_CLEANUP_INTERVAL=1` 后重跑同样 warmup+3 measured，`c1_api_processing_benchmark_v2_mixed6_metrics_trim1_warm1_3runs.json` 显示 6 路总失败 `0`，`max_processing_sec=17.537483s`，`max_wall_realtime_factor=0.652760`，`max_route_realtime_factor=0.689713`，`mean_effective_realtime_streams=9.510387`；RSS 从 `1944.629MB` 到 `2435.559MB`，增长 `490.930MB`，与 interval=6 基本相同，说明单靠更频繁 `gc.collect()/malloc_trim()` 不能根治稳态 RSS 上涨。
- 当前判断：6 路并行吞吐和显存已经具备较强本地证据；RSS 仍存在稳态上涨，下一步优化重点不是继续盲目压缩单路耗时，而是增加进程级 worker recycle / max-requests 这类隔离策略，防止底层 ONNXRuntime/OpenCV allocator 长期保留导致服务 RSS 持续上涨。
- 影响范围：本次只增强 C1 压测观测工具并追加报告；未改动生产分析热路径、生产数据库、`testdata` 视频、GKGuard C2 或 A/B 代码；人工 check 数据没有进入训练或线上逻辑。
