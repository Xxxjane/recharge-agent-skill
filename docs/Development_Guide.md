开发一个标准 Skill 并发布到 GitHub，标准的工程化流程如下：

```text
[步骤1: 契约设计] ➔ [步骤2: 本地Mock与逻辑实现] ➔ [步骤3: Prompt约束] ➔ [步骤4: Agent平台集成调试] ➔ [步骤5: GitHub开源整理]
```

---

## 步骤 1：契约设计 (Design API Contract)

不要急着写代码，先用 OpenAPI 3.0 (Swagger/YAML) 规范定义好你的“工具箱门面”。

- **输出文件：** `openapi.yaml`
- **核心动作：** 定义好 paths（接口路径）、parameters（参数描述）和 components.schemas（数据结构对象）。把 PRD 里的“红灯泡校验”和“Quantity限制为1”在 YAML 里用限制条件写清楚。

---

## 步骤 2：本地 Mock 与逻辑实现 (Backend & Mock implementation)

在本地用 Python (FastAPI/Flask) 或 Node.js (Express) 快速搭一个 Mock 服务器。

**核心代码实现：**

- 实现静态品牌数据和动态级联模板的返回。
- 编写账号格式校验逻辑（验证 inputRegex 是否能完美卡死不合规输入）。
- 实现 15 分钟倒计时的定时任务（若超时未发货，将订单状态置为 REFUNDED 并在内存中退款）。

**开源加分项：** 提供一个单文件版的 Mock Server（例如一个简单的 server.js 或 app.py），让下载你开源项目的人不需要连数据库就能直接跑起来测试。

---

## 步骤 3：Prompt 行为约束编写 (System Instruction Prompting)

大模型只看 API 还是容易在交互中失控，你需要为它量身定制一套“操作指南”。

**编写 Prompt：**

- 约束大模型必须先调 getBrandTemplate，再调 createRechargeOrder，不得跳步骤。
- 强制让它在输出下单链接前，用高亮 Markdown 输出 【红色电灯泡二次确认框】。

---

## 步骤 4：Agent 平台集成与链路调试 (Sandbox Integration)

将你写好的 API YAML 导入到主流的 AI 平台中进行“沙箱测试”。

**测试平台：**

- **Dify：** 导入 OpenAPI，测试 Dify 的工具调用（Tool Call）是否能准确识别你的参数，并观察 System Prompt 约束效果。
- **Coze (扣子)：** 导入并配置插件，测试卡片渲染（利用 Coze 的消息卡片直接展示充值截图）。
- **MCP + Cursor：** 见 `integration/mcp/README.md` 与 `examples/cursor-mcp.md`

**测试用例（必测）：**

- 输入错误的手机号，测试大模型是否会友好拦截并拒绝下单。
- 尝试输入购买数量 2，测试大模型是否能用你的话术友好拒绝并提示“一次只能买1份”。
- 模拟卖家超时，测试大模型是否能准确播报“已超时并全额退款”。

---

## 步骤 5：GitHub 开源规范化整理 (GitHub Open Source Packaging)

当你本地和平台都调通后，就要进行高质量的开源包装了，这决定了你能否在社区拿到 Star：

**撰写优秀的 README.md（门面）：**

- 加入一目了然的架构闭环图。
- 提供一键导入 Dify/Coze 插件的 DSL 配置文件（放在 integration/ 目录下）。

**加入 CI/CD 自动化：**

- 在 .github/workflows 中增加 Swagger/OpenAPI 自动化语法 lint 检查，保证任何人修改 API 都会自动校验规范性。

**完善部署文档：**

- 写一份 Deployment_Guide.md，教小白开发者怎么用 Docker 一键在 Vercel 或 Railway 部署你的 Mock 后端。
