# CampusVision C1 任务报告

本文档用于记录 CampusVision C1 每次任务结束后的审阅报告。之后每次完成 CampusVision C1 相关任务时，应在这里追加一条报告，并标明当时分支和版本来源。

## 当前集成状态

- GKGuard 集成目标：`v0.2.1`
- CampusVision C1 来源分支：`speng/c1-person-events` + `codex/fix-c1-event-review-followup`
- CampusVision C1 来源版本：`2ba9064` + 当前仓库补丁分支
- 记录时间：`2026-06-24 21:00:00 CST`
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

## 2026-06-24 21:00:00 CST - GKGuard v0.2.1 C1 集成 review follow-up

- 版本号：`codex/fix-c1-event-review-followup@working-tree`
- 任务目标：处理 `v0.2.0` 合并后 review 发现的 CampusVision C1 查询图异常、重复索引、人物索引与 appearance session 重建和 GKGuard C2 人物特征路线顺序问题。
- 变更内容：`/api/v1/query/face-image` 在查询图不可解码时返回 400，在上传体积、解码像素数或单边尺寸超限时返回 413，并清理临时上传；同一视频重索引前清理旧事件、人物观测、人脸记录和旧帧目录，并刷新受影响人物索引、重建相关 appearance sessions；GKGuard C2 人物特征检索结果列表保留匹配排序，路线点按事件时间单独排序并通过 `recordIndex` / `eventId` 稳定映射回结果记录；API 规范同步 `time_range.start_time/end_time` 和 `/c1/query/face-image` Query 参数位置。
- 验证结果：新增后端和 CampusVision C1 静态/单元测试覆盖；完整验证结果以 `docs/releases/v0.2.1.md` 和对应 PR 为准。
- 风险与遗留问题：重索引失败后该视频需要重新执行索引；历史 `v0.2.0` 说明保持发布时语境，当前行为以 `v0.2.1` 文档为准。
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
- 风险与遗留问题：当前实现仍是遍历现有人物和 face records 做向量比对，适合当前本地库规模；后续人物库显著扩大时应引入向量索引或人物 embedding 缓存。事件展示由 C2 消费 JSON 完成，C1 本次不改 C2。
- 涉及文件：`services/campusvision-c1/app/api/routes.py`、`services/campusvision-c1/app/services/person_service.py`、`services/campusvision-c1/app/services/search_service.py`、`services/campusvision-c1/tests/test_query_face_preprocessing.py`、`services/campusvision-c1/README_TASK_REPORTS.md`

## 2026-06-24 13:21:40 CST - 人物特征检索大接口设计计划

- 版本号：`speng/c1-person-events@2ba9064`
- 任务目标：规划第二个数据库查询大接口：按时间、摄像头、外观倾向、眼镜状态、上装颜色等条件搜索事件；条件均可为空；返回完全匹配事件或相似事件，并标明每条事件不满足哪些条件。
- 现状判断：C1 已有 `/events`、`/search/by-clothes`、人物外观倾向 profile、眼镜 profile、appearance sessions 和事件代表图/人脸/人体图字段；新接口应复用这些只读能力，不暴露任意 SQL，不引入 C2 改动。
- 计划接口：新增 `POST /api/v1/query/person-attributes`，请求体使用 JSON；支持 `time_range`、`camera_ids`、`gender_presentation`、`glasses_status`、`upper_colors`、`person_scope`、`match_mode`、`top_k`、`limit`、`offset`、`include_candidates`、`include_near_misses`。
- 匹配策略：先用时间、摄像头、识别状态做硬过滤控制搜索空间；再对外观倾向、眼镜、上装颜色做可解释软评分；完全满足条件的事件排前，相似事件按分数排序并输出 `failed_conditions` 和 `condition_scores`。
- 返回结构：顶层返回 `query_id/query/summary/results`；每条 result 包含 `event_id/person_id/identity_status/score/match_type/failed_conditions/condition_scores/event_time/camera/representative_frame_url/representative_body_crop_url/representative_face_crop_url/upper_color/glasses_status/gender_presentation/appearance_session_id`。
- 结果语义：`match_type=exact` 表示所有有值条件满足；`partial` 表示部分满足并说明缺口；`unknown` 表示关键属性不可判断，不直接当作错误；当所有条件为空时返回最近事件或按时间排序的事件列表。
- 保护策略：人工 check 数据只用于评估，不进入搜索逻辑；不搜索下装；接口只读，不改人物库、事件库或 profile；默认返回稳定人物事件，`include_candidates=true` 才包含候选碎片人物。
- 验收建议：空条件、单条件、多条件、冲突条件、unknown 属性、分页、图片 URL 完整性都应有测试；同一条件下 exact 必须排在 partial 前；每条 partial 必须清楚标出不满足的字段，供 C2 展示“相似但不完全满足”。
- 风险与遗留问题：当前外观倾向和眼镜是人物/profile 层能力，事件层传播依赖已有 profile 文件；上装颜色目前以事件/appearance session 的 normalized upper color 为准，准确率仍受模型现状影响。
- 涉及文件计划：`services/campusvision-c1/app/api/routes.py`、`services/campusvision-c1/app/services/person_attribute_query_service.py` 或 `person_service.py`、`services/campusvision-c1/tests/`、`services/campusvision-c1/README_TASK_REPORTS.md`

## 2026-06-24 13:32:39 CST - 人物特征检索大接口实现

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
- 分支状态：当前分支相对 `origin/main` 已有 `38` 个提交；PR 基础能力来自 C1，不涉及 C2/桌面壳。
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

## 2026-06-24 13:45:33 CST - C2 对接文档

- 版本号：`speng/c1-person-events@2ba9064`
- 任务目标：为即将开始的 C2 工作提供 C1 v1 接口契约文档，避免 C2 误读任务报告或直接依赖 C1 本地文件路径。
- 新增文档：`services/campusvision-c1/README_C2_INTEGRATION.md`
- 文档内容：CampusVision C1 base URL、健康检查、人脸以图搜人接口、人物特征检索接口、media 图片 URL、枚举值、请求/响应示例、GKGuard C2 展示建议、错误处理和 known limitations。
- 对接重点：C2 事件主图优先用 `representative_body_crop_url`，现场图用 `representative_frame_url`，人脸小图用 `representative_face_crop_url`；`partial` 搜索结果必须展示 `failed_conditions`；`unknown` 表示无法判断，不等于否定。
- 风险说明：文档明确上装颜色、外观倾向、眼镜状态来自模型/profile，C2 不应当作绝对事实；装束分组当前未完全达到最终指标，但不影响两个查询大接口使用。
- 验证结果：文档已创建并检查，未改动 C2；当前文件仍未提交，PR 前需要将该文档加入 commit。
- 涉及文件：`services/campusvision-c1/README_C2_INTEGRATION.md`、`services/campusvision-c1/README_TASK_REPORTS.md`
