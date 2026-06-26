# v1.0.0 — Agent Skill MVP

## Highlights

- **Buyer APIs**: brands, template, create order, status, confirm receipt
- **Seller APIs**: pending list, accept, start-recharge, deliver
- **Full order state machine** with pay/fulfillment timeouts and auto-confirm
- **9 automated E2E tests** in `test_skill.py`
- **Three integration paths**: OpenAPI (Dify/Coze), MCP Server, Cursor SKILL.md
- **Channel adapter stubs**: WeChat, Alipay, Meituan
- **Open-source packaging**: MIT LICENSE, Dockerfile, CI, CONTRIBUTING.md

## Quick Start

```bash
git clone https://github.com/Xxxjane/recharge-agent-skill.git
cd recharge-agent-skill
pip install -r requirements.txt
uvicorn src.app:app --host 127.0.0.1 --port 8000
python test_skill.py
```

## Limitations

Mock payment, in-memory storage, adapter stubs only. See README.
