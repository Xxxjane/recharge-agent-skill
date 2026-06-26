# Contributing

感谢关注 **recharge-agent-skill**！欢迎 Issue 与 Pull Request。

## 开发环境

```bash
git clone https://github.com/Xxxjane/recharge-agent-skill.git
cd recharge-agent-skill
pip install -r requirements.txt
cp .env.example .env
uvicorn src.app:app --host 127.0.0.1 --port 8000
python test_skill.py
```

## 修改 API 时的同步清单

若改动 [`src/schemas/openapi.yaml`](src/schemas/openapi.yaml)，请同步更新：

1. [`src/app.py`](src/app.py) — Mock 实现与校验逻辑
2. [`src/prompt/system_prompt.md`](src/prompt/system_prompt.md) / [`seller_prompt.md`](src/prompt/seller_prompt.md)
3. [`integration/dify/tool_config.json`](integration/dify/tool_config.json)
4. [`integration/coze/metadata.json`](integration/coze/metadata.json)
5. [`recharge_mcp/server.py`](recharge_mcp/server.py) — MCP tools
6. [`test_skill.py`](test_skill.py) — 补充或更新测试用例

## PR 要求

- `python test_skill.py` 全部通过
- OpenAPI YAML 可正常解析（CI 会自动检查）
- 不提交 `.env`、密钥、内网地址

## 业务背景

业务规则参考 [`docs/PRD_Reference.md`](docs/PRD_Reference.md)。本仓库为学习与开源参考实现，非 Jiigo / 彩贝壳官方仓库。
