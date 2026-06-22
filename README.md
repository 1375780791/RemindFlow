# RemindFlow Server

RemindFlow 是一个自用的个人周期提醒系统后端，计划使用 FastAPI、SQLite、APScheduler 和 SMTP 邮件发送实现。

核心原则：

> 待办规则保持稳定，提醒周期按规则生成；完成只关闭当前周期，不改动下一周期的计算基准。

例如每月 3 号充话费，提前 2 天提醒：如果 1 号点击“本轮完成”，则 2 号和 3 号不再提醒，但下个月仍然以 3 号为基准继续生成提醒窗口。

## 技术栈

- FastAPI：后端 Web 框架
- SQLite：轻量本地数据库
- SQLModel：数据库模型与 ORM
- APScheduler：每日定时扫描提醒任务
- SMTP：邮件提醒发送
- OpenAI SDK：接入 OpenAI 协议兼容的大模型服务
- lunardate：阳历 / 农历日期转换
- JWT：登录状态认证
- Docker / Docker Compose：便于 NAS 或其他服务器部署

## 当前目录结构

```text
.
├── .env.example
├── .gitignore
├── Dockerfile
├── README.md
├── app
│   ├── __init__.py
│   ├── api
│   │   ├── __init__.py
│   │   ├── deps.py
│   │   ├── router.py
│   │   └── routes
│   │       ├── __init__.py
│   │       ├── auth.py
│   │       ├── health.py
│   │       └── todos.py
│   ├── core
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── security.py
│   ├── db
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── session.py
│   ├── main.py
│   ├── models
│   │   ├── __init__.py
│   │   └── user.py
│   ├── schemas
│   │   ├── __init__.py
│   │   └── auth.py
│   ├── services
│   │   ├── __init__.py
│   │   ├── calendar.py
│   │   ├── email_sender.py
│   │   └── reminder_engine.py
│   ├── static
│   │   └── .gitkeep
│   ├── tasks
│   │   ├── __init__.py
│   │   └── scheduler.py
│   └── templates
│       └── .gitkeep
├── data
│   └── .gitkeep
├── docker-compose.yml
├── requirements.txt
└── tests
    └── __init__.py
```

## 模块说明

- `app/main.py`：FastAPI 应用入口，负责挂载静态资源、注册路由、初始化数据库和启动定时任务。
- `app/api/deps.py`：API 依赖注入，目前包含数据库会话和当前登录用户解析。
- `app/api/router.py`：统一注册 API 路由。
- `app/api/routes/auth.py`：注册、登录、当前用户等认证接口。
- `app/api/routes/health.py`：健康检查接口。
- `app/api/routes/todos.py`：待办事项接口，目前包含创建、列表和详情查询。
- `app/core/config.py`：集中读取 `.env` 配置，避免路径、邮箱、时区等信息写死在代码中。
- `app/core/security.py`：密码哈希、密码校验、JWT 创建和解析。
- `app/db/session.py`：SQLite 数据库引擎、表初始化和数据库会话。
- `app/models/`：数据库模型目录，目前包含 `users`、`todos`、`reminder_cycles` 和 `email_logs`。
- `app/schemas/`：请求和响应数据结构目录，目前包含认证和待办相关 schema。
- `app/services/calendar.py`：阳历 / 农历转换逻辑。
- `app/services/reminder_engine.py`：提醒周期生成、提醒窗口判断、本轮完成状态判断等核心业务逻辑。
- `app/services/email_sender.py`：SMTP 邮件发送逻辑。
- `app/services/llm.py`：OpenAI 协议兼容的大模型客户端封装。
- `app/tasks/scheduler.py`：APScheduler 定时任务入口，后续会每日扫描需要提醒的周期。
- `app/templates/`：前端 HTML 模板目录。
- `app/static/`：前端静态资源目录。
- `data/`：SQLite 数据库文件目录，Docker 部署时建议挂载到宿主机。
- `tests/`：测试目录。

## 本地开发

创建虚拟环境：

```bash
python -m venv .venv
source .venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

复制配置文件：

```bash
cp .env.example .env
```

启动服务：

```bash
uv run uvicorn app.main:app --reload
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

预期返回：

```json
{"status":"ok"}
```




## 配置说明

`.env.example` 中包含当前支持的配置项：

```env
APP_NAME=RemindFlow
DATABASE_URL=sqlite:///data/remindflow.db
SECRET_KEY=change-this-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=43200

SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM=
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_TIMEOUT_SECONDS=10
REGISTRATION_EMAIL_VERIFICATION_REQUIRED=true
EMAIL_VERIFICATION_CODE_EXPIRES_MINUTES=10
EMAIL_VERIFICATION_CODE_COOLDOWN_SECONDS=60
EMAIL_VERIFICATION_MAX_ATTEMPTS=5

SCHEDULER_TIMEZONE=Asia/Shanghai
REMINDER_SCAN_HOUR=8
REMINDER_SCAN_MINUTE=0

OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
OPENAI_TIMEOUT_SECONDS=30
OPENAI_TEMPERATURE=0.2
OPENAI_MAX_TOKENS=1024
LLM_DEBUG_LOG_ENABLED=false
LLM_DEBUG_LOG_PATH=logs/llm_debug.log
```

说明：

- `DATABASE_URL` 默认把 SQLite 数据库放在 `data/remindflow.db`。
- `SECRET_KEY` 用于签发 JWT，正式部署时需要换成随机长字符串。
- `ACCESS_TOKEN_EXPIRE_MINUTES` 控制登录有效期，默认 `43200` 分钟，也就是 30 天。
- `SMTP_*` 用于配置邮件发送服务器，`SMTP_PASSWORD` 通常填写邮箱服务商生成的授权码或应用专用密码，不建议填写登录密码。
- 如果邮箱服务商使用 587 端口，一般设置 `SMTP_USE_TLS=true`、`SMTP_USE_SSL=false`。
- 如果邮箱服务商使用 465 端口，一般设置 `SMTP_USE_TLS=false`、`SMTP_USE_SSL=true`。
- `REGISTRATION_EMAIL_VERIFICATION_REQUIRED` 控制注册时是否必须填写邮箱验证码。
- `EMAIL_VERIFICATION_CODE_EXPIRES_MINUTES` 控制验证码有效期。
- `EMAIL_VERIFICATION_CODE_COOLDOWN_SECONDS` 控制同一邮箱两次发送验证码的最小间隔。
- `EMAIL_VERIFICATION_MAX_ATTEMPTS` 控制同一个验证码最多允许输错几次。
- `SCHEDULER_TIMEZONE` 默认使用 `Asia/Shanghai`。
- `REMINDER_SCAN_HOUR` 和 `REMINDER_SCAN_MINUTE` 控制每日扫描提醒任务的执行时间。
- `OPENAI_API_KEY` 用于配置 OpenAI 或兼容服务的 API Key。
- `OPENAI_BASE_URL` 用于配置 OpenAI 协议兼容网关，默认是官方接口地址，也可以改成第三方服务的 `/v1` 地址。
- `OPENAI_MODEL` 是默认调用模型。
- `OPENAI_TIMEOUT_SECONDS` 控制 LLM 请求超时时间。
- `OPENAI_TEMPERATURE` 控制默认生成随机性。
- `OPENAI_MAX_TOKENS` 控制默认最大输出长度。
- `LLM_DEBUG_LOG_ENABLED` 控制是否记录 LLM 调试日志。
- `LLM_DEBUG_LOG_PATH` 控制 LLM 调试日志文件路径，默认写入 `logs/llm_debug.log`。

## 大模型接入

后端已封装 OpenAI 协议兼容客户端，入口在 `app/services/llm.py`。

```python
from app.services.llm import create_chat_completion

response = await create_chat_completion(
    [
        {"role": "system", "content": "你是 RemindFlow 的提醒助手。"},
        {"role": "user", "content": "帮我整理明天要提醒的事项。"},
    ]
)
```

如果使用第三方 OpenAI 兼容服务，只需要在 `.env` 中替换：

```env
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://your-provider.example.com/v1
OPENAI_MODEL=your-model-name
```

自然语言解析待办事项：

```bash
curl -X POST http://127.0.0.1:8000/todos/parse-text \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"text":"周五提醒我交话费"}'
```

接口只返回解析草稿，不会写入数据库。前端确认后仍然通过创建待办接口保存。

测试大模型联通性：

```bash
curl -X POST http://127.0.0.1:8000/llm/test-connection \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"provider_type":"openai_compatible","base_url":"https://api.openai.com/v1","model":"gpt-4o-mini"}'
```

前端页面入口在“模型配置”，路径是 `/llm-settings`。

## 登录接口

当前已实现邮箱注册和 JWT 登录。邮箱就是用户名，并且必须唯一。

注册：

```bash
curl -X POST http://127.0.0.1:8000/auth/send-verification-code \
  -H "Content-Type: application/json" \
  -d '{"email":"me@example.com"}'

curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"me@example.com","password":"password123","verification_code":"123456"}'
```

登录：

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"me@example.com","password":"password123"}'
```

查询当前用户：

```bash
curl http://127.0.0.1:8000/auth/me \
  -H "Authorization: Bearer <access_token>"
```

修改当前用户密码：

```bash
curl -X POST http://127.0.0.1:8000/auth/change-password \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{"old_password":"password123","new_password":"newpassword123"}'
```

说明：

- `users.id` 是从 1 开始的整数自增主键。
- 密码不会明文保存，会写入哈希后的 `password_hash`。
- 当前密码使用 bcrypt 哈希，并在依赖中固定 `bcrypt==4.0.1`，避免新版 bcrypt 与 passlib 的兼容问题。
- bcrypt 本身限制密码不能超过 72 字节；如果使用中文或特殊字符，一个字符可能占多个字节。
- 登录成功后返回 `access_token`。
- 后续需要保护的接口可以通过 `CurrentUserDep` 获取当前用户。

## 待办事项表

当前已新增 `todos` 表，用来保存每个用户创建的待办提醒规则。

字段说明：

- `id`：待办事项 ID，从 1 开始自增。
- `user_id`：所属用户 ID，每个用户只能访问自己的待办。
- `description`：任务描述，例如“充话费”。
- `recipient_email`：提醒邮件发送到的邮箱。
- `calendar_type`：日期类型，`solar` 表示阳历，`lunar` 表示农历。
- `task_date`：任务日期。阳历任务直接使用该日期；农历任务可保存首次对应的阳历日期，后续仍按农历规则计算。
- `lunar_month`：农历月份，仅农历任务需要。
- `lunar_day`：农历日期，仅农历任务需要。
- `lunar_is_leap_month`：是否为农历闰月。
- `remind_days_before`：提前提醒天数，例如 `2` 表示目标日前 2 天、前 1 天和当天都属于提醒窗口。
- `recurrence_type`：循环类型，支持 `none`、`daily`、`monthly`、`yearly`、`interval_days`。
- `interval_days`：按固定天数间隔循环时使用，例如每 30 天提醒一次。
- `repeat_count`：循环次数，不填表示暂不限制次数。
- `is_active`：是否启用。
- `created_at` / `updated_at`：创建和更新时间。

创建待办：

```bash
curl -X POST http://127.0.0.1:8000/todos/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{
    "description": "充话费",
    "recipient_email": "me@example.com",
    "calendar_type": "solar",
    "task_date": "2026-06-03",
    "remind_days_before": 2,
    "recurrence_type": "interval_days",
    "interval_days": 30
  }'
```

创建农历待办：

```bash
curl -X POST http://127.0.0.1:8000/todos/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{
    "description": "农历生日",
    "recipient_email": "me@example.com",
    "calendar_type": "lunar",
    "task_date": "2026-06-03",
    "lunar_month": 4,
    "lunar_day": 18,
    "lunar_is_leap_month": false,
    "remind_days_before": 3,
    "recurrence_type": "yearly"
  }'
```

如果创建农历待办时没有传 `lunar_month` 和 `lunar_day`，后端会根据 `task_date` 自动换算出对应的农历规则并保存。

如果同时传了 `task_date` 和农历月日，后端会校验二者是否匹配，避免“执行日期”和“原始农历规则”对不上。

获取待办列表：

```bash
curl http://127.0.0.1:8000/todos/ \
  -H "Authorization: Bearer <access_token>"
```

获取待办详情：

```bash
curl http://127.0.0.1:8000/todos/1 \
  -H "Authorization: Bearer <access_token>"
```

编辑待办：

```bash
curl -X PATCH http://127.0.0.1:8000/todos/1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <access_token>" \
  -d '{
    "description": "新的任务描述",
    "recipient_email": "new@example.com",
    "task_date": "2026-06-10",
    "remind_days_before": 1,
    "repeat_count": 2
  }'
```

说明：修改日期、提醒天数、循环规则等提醒配置后，后端会重建尚未发送、尚未完成的提醒周期；已经发送过邮件或已经完成的周期会作为历史保留。

标记本轮提醒完成：

```bash
curl -X POST http://127.0.0.1:8000/todos/1/cycles/1/complete \
  -H "Authorization: Bearer <access_token>"
```

说明：只有该提醒周期已经有成功邮件发送日志时，才能标记为完成。完成后只停止当前周期后续提醒，不影响下一轮周期。

查询邮件发送日志：

```bash
curl "http://127.0.0.1:8000/todos/1/email-logs?limit=100&offset=0" \
  -H "Authorization: Bearer <access_token>"
```

也可以按提醒周期筛选：

```bash
curl "http://127.0.0.1:8000/todos/1/email-logs?cycle_id=1" \
  -H "Authorization: Bearer <access_token>"
```

发送测试邮件：

```bash
curl -X POST http://127.0.0.1:8000/todos/1/test-email \
  -H "Authorization: Bearer <access_token>"
```

说明：测试邮件会调用 SMTP 发送能力，但不会写入正式 `email_logs`，也不会让该周期变成“已经提醒过”。

## Docker 部署

首次部署前，先准备 `.env`：

```bash
cp .env.example .env
```

启动：

```bash
docker compose up -d
```

停止：

```bash
docker compose down
```

当前 `docker-compose.yml` 会把本地 `./data` 挂载到容器内 `/app/data`，这样 SQLite 数据库可以保留在宿主机，方便 NAS 部署和未来迁移。

## 后续开发顺序

建议按以下顺序继续实现：

1. 增加长期循环任务的未来周期自动补齐逻辑。
2. 引入数据库迁移机制，支持已有 SQLite 数据库平滑升级。

## 关键业务规则

- 阳历规则直接按阳历日期计算提醒周期。
- 农历规则保存用户设置的农历月日，每一轮执行前通过 `lunardate` 转换成当年的阳历日期。
- 提前提醒形成一个提醒窗口，例如目标日提前 2 天，会在目标日前 2 天、前 1 天、当天尝试提醒。
- 用户点击“本轮完成”后，当前周期后续日期不再提醒。
- “本轮完成”不修改待办原始规则，也不影响下一轮周期基准日。
