## 中文

## 变更摘要

- 请概述本次变更。

## 影响范围

- [ ] GKGuard C2 后端 / FastAPI
- [ ] GKGuard C2 前端 / 静态页面
- [ ] Electron 桌面端
- [ ] GKGuard C2 本地代理或 CampusVision C1 服务
- [ ] CampusCar / UE 占位接口规范
- [ ] 文档 / 发布说明
- [ ] GitHub Actions / CI 或发布流程

## 验证

- [ ] PR 标题使用 `type(scope): summary`，且未包含 `[codex]`、`[copilot]`、`[ai]` 或 `AI:` 等工具来源前缀
- [ ] 如使用 AI agent 协助，已阅读并遵守 `AGENTS.md`
- [ ] 如包含 AI agent 代码审查输出，review 结论、风险、建议和 inline comment 已中英双语，中文在前、English 在后，并用换行分隔中英文段落
- [ ] 合并前已确认 PR 正文 reaction、Issue 评论、审查线程和审查状态；没有把“未发现评论”当作可合并状态，没有 PR 正文 👀 或等价“正在 review”信号，且已有 PR 正文 👍、approval 或明确无阻断结论
- [ ] GitHub Actions CI 通过
- [ ] `node --check backend/app/static/app.js`
- [ ] `node --check desktop/main.js`
- [ ] `node --check desktop/preload.js`
- [ ] `python -m pytest backend`
- [ ] `python -m py_compile backend/desktop_server.py`
- [ ] `npm run test:e2e`
- [ ] `npm audit --audit-level=low`
- [ ] 手动打开 `/demo`
- [ ] 检查 `/c1/status`
- [ ] 文档-only，代码测试不适用
- [ ] 已按需设置标签并加入 GKGuard Roadmap Project
- [ ] Project item 已在 GKGuard Roadmap 或 Project 主列表可见，并补齐 Status、Area、Type、Priority、Blocked、Start date、End date、Timeline order 和必要的 Target version

## 安全与数据检查

- [ ] 未提交真实视频、真实图片、人脸裁剪图或抽帧图。
- [ ] 未提交 `.env`、密码、token、私钥或服务器凭据。
- [ ] 未提交真实姓名、学号/工号、手机号、车牌、轨迹或案件材料。
- [ ] 如涉及 CampusVision C1 服务或 SSH，已说明网络前提和密码处理方式。

## English

## Summary

- Please summarize this change.

## Scope

- [ ] GKGuard C2 backend / FastAPI
- [ ] GKGuard C2 frontend / static UI
- [ ] Electron desktop app
- [ ] GKGuard C2 local proxy or CampusVision C1 service
- [ ] CampusCar / UE placeholder interface specification
- [ ] Docs / Release notes
- [ ] GitHub Actions / CI or release flow

## Validation

- [ ] PR title uses `type(scope): summary` and does not include tool-source prefixes such as `[codex]`, `[copilot]`, `[ai]`, or `AI:`
- [ ] If AI-agent assistance was used, `AGENTS.md` has been read and followed
- [ ] If AI-agent code review output is included, the review conclusion, risks, suggestions, and inline comments are bilingual Chinese/English, with Chinese first, English second, and line breaks separating the language paragraphs
- [ ] Before merge, PR-body reactions, issue comments, review threads, and review state have been checked; "no comments found" has not been treated as mergeable, there is no PR-body 👀 or equivalent "review in progress" signal, and there is a PR-body 👍, approval, or explicit no-blocker conclusion
- [ ] GitHub Actions CI passed
- [ ] `node --check backend/app/static/app.js`
- [ ] `node --check desktop/main.js`
- [ ] `node --check desktop/preload.js`
- [ ] `python -m pytest backend`
- [ ] `python -m py_compile backend/desktop_server.py`
- [ ] `npm run test:e2e`
- [ ] `npm audit --audit-level=low`
- [ ] Manually opened `/demo`
- [ ] Checked `/c1/status`
- [ ] Documentation-only, code tests not applicable
- [ ] Labels are set and the PR is added to the GKGuard Roadmap Project when applicable
- [ ] Project item is visible in GKGuard Roadmap or the Project main item list, and fields are filled: Status, Area, Type, Priority, Blocked, Start date, End date, Timeline order, and required Target version

## Security And Data Check

- [ ] No real videos, real images, face crops, or extracted frames are committed.
- [ ] No `.env`, passwords, tokens, private keys, or server credentials are committed.
- [ ] No real names, student/staff IDs, phone numbers, license plates, trajectories, or case material are committed.
- [ ] If the CampusVision C1 service or SSH is involved, network prerequisites and password handling are documented.
