## 中文

## 变更摘要

- 

## 影响范围

- [ ] C2 后端 / FastAPI
- [ ] C2 前端 / 静态页面
- [ ] Electron 桌面端
- [ ] C1 适配或 CampusVision C1
- [ ] CampusCar / UE 占位合同
- [ ] 文档 / Release notes
- [ ] GitHub Actions / 发布流程

## 验证

- [ ] `node --check desktop/main.js`
- [ ] `python -m pytest backend`
- [ ] 手动打开 `/demo`
- [ ] 检查 `/c1/status`
- [ ] 文档-only，代码测试不适用

## 安全与数据检查

- [ ] 未提交真实视频、真实图片、人脸裁剪图或抽帧图。
- [ ] 未提交 `.env`、密码、token、私钥或服务器凭据。
- [ ] 未提交真实姓名、学号/工号、手机号、车牌、轨迹或案件材料。
- [ ] 如涉及 C1/SSH，已说明网络前提和密码处理方式。

## English

## Summary

- 

## Scope

- [ ] C2 backend / FastAPI
- [ ] C2 frontend / static UI
- [ ] Electron desktop app
- [ ] C1 adapter or CampusVision C1
- [ ] CampusCar / UE placeholder contract
- [ ] Docs / Release notes
- [ ] GitHub Actions / release flow

## Validation

- [ ] `node --check desktop/main.js`
- [ ] `python -m pytest backend`
- [ ] Manually opened `/demo`
- [ ] Checked `/c1/status`
- [ ] Documentation-only, code tests not applicable

## Security And Data Check

- [ ] No real videos, real images, face crops, or extracted frames are committed.
- [ ] No `.env`, passwords, tokens, private keys, or server credentials are committed.
- [ ] No real names, student/staff IDs, phone numbers, license plates, trajectories, or case material are committed.
- [ ] If C1/SSH is involved, network prerequisites and password handling are documented.
