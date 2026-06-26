# GitHub 仓库展示配置指南

Push 代码后，在 GitHub 网页完成以下配置（需仓库管理员权限）。

## About（仓库首页右侧齿轮）

| 字段 | 建议值 |
|------|--------|
| Description | 虚拟商品代充值 AI Agent Skill — OpenAPI + MCP + Prompt |
| Website | （可选）部署后的 API 地址 |
| Topics | `ai-agent`, `mcp`, `openapi`, `fastapi`, `dify`, `coze`, `virtual-goods`, `skill`, `cursor`, `agent-skill` |

## 创建 Release

1. 打开 https://github.com/Xxxjane/recharge-agent-skill/releases/new
2. Choose tag: `v1.0.0`（若已 push tag）
3. Title: `v1.0.0 — Agent Skill MVP`
4. 粘贴 [RELEASE_v1.0.0.md](RELEASE_v1.0.0.md) 内容

## 验证清单

- [ ] README 与 CI Badge 正常显示
- [ ] Actions 最新 run 为绿色
- [ ] Topics 已添加，便于搜索
- [ ] Release v1.0.0 已发布
