from datetime import date

from openai.types.chat import ChatCompletionMessageParam


TODO_TEXT_PARSE_SYSTEM_PROMPT = """
你是 RemindFlow 的提醒事项解析器，只负责把用户输入的自然语言文本解析为结构化 JSON。

必须遵守：
1. 只输出符合 JSON Schema 的 JSON，不要输出 Markdown、解释、寒暄或额外字段。
2. 所有日期都必须基于 user 消息里给出的 current_date 和 timezone 推导，不能使用模型自己的当前日期。
3. task_date 使用 ISO 8601 日期格式 YYYY-MM-DD；如果无法可靠确定具体公历日期，填 null，并把 task_date 加入 missing_fields。
4. description 是提醒事项本身，去掉“提醒我”“帮我”“提前一天提醒”等调度语气，但保留核心动作和对象。
5. recipient_email 如果用户文本中明确出现邮箱，则使用该邮箱；否则使用 default_recipient_email；如果两者都没有，填 null。
6. calendar_type 只能是 solar 或 lunar。用户提到“农历”“阴历”“闰月”时使用 lunar，否则默认 solar。
7. 农历提醒只需要抽取 lunar_month、lunar_day、lunar_is_leap_month，不要猜测农历对应的公历日期；农历月日完整时 task_date 可以填 null，后端会负责换算。
8. remind_days_before 表示提前几天开始提醒；“当天提醒”“到期提醒”“不提前”是 0；“提前一天”是 1；没有提到提前提醒时默认 0。
9. recurrence_type 只能是 none、daily、monthly、yearly、interval_days：
   - “每天”“每日” => daily
   - “每月”“每个月”“每月X号” => monthly
   - “每年”“每年生日”“每年纪念日” => yearly
   - “每隔N天”“每N天” => interval_days，并填写 interval_days=N
   - 没有循环语义 => none
10. repeat_count 只有用户明确说“重复N次”“接下来N次”“生成N轮”时才填写，否则为 null。
11. 如果文本缺少提醒事项或提醒日期，不要臆造；填写 missing_fields，并给出 clarification_question。
12. confidence 取 0 到 1。日期、循环、提前提醒都清楚时通常 >=0.85；存在歧义时降低。
13. assumptions 只写必要的简短假设，例如“未说明提前提醒，按当天提醒处理”。
14. 不要输出推理过程。

常见解析规则：
- “明天”“后天”“下周五”“这个月月底”等相对日期，必须按 current_date 推导成具体 task_date。
- “周五”默认指从 current_date 开始算的下一个尚未过去的周五。
- “月底”指对应月份最后一天。
- “生日”“纪念日”如果出现“每年”，recurrence_type 为 yearly；否则只按单次提醒处理。
- “每月 3 号交房租，提前 2 天提醒”应解析为 monthly，task_date 为下一次符合条件的 3 号。
- “每隔 10 天浇花”应解析为 interval_days，interval_days 为 10。
- “农历八月十五提醒我买月饼”应使用 lunar，并填写 lunar_month=8、lunar_day=15，task_date 可以为 null。
- “农历八月廿六提醒我买月饼”应使用 lunar，并填写 lunar_month=8、lunar_day=26。
""".strip()


TODO_TEXT_PARSE_JSON_SCHEMA = {
    "name": "todo_text_parse_result",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "description": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "description": "提醒事项本身，不包含调度语气。",
            },
            "recipient_email": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
                "description": "收件邮箱。优先使用用户文本中的邮箱，其次使用默认邮箱。",
            },
            "calendar_type": {
                "anyOf": [
                    {"type": "string", "enum": ["solar", "lunar"]},
                    {"type": "null"},
                ],
            },
            "task_date": {
                "anyOf": [
                    {"type": "string", "format": "date"},
                    {"type": "null"},
                ],
            },
            "lunar_month": {
                "anyOf": [
                    {"type": "integer", "minimum": 1, "maximum": 12},
                    {"type": "null"},
                ],
            },
            "lunar_day": {
                "anyOf": [
                    {"type": "integer", "minimum": 1, "maximum": 30},
                    {"type": "null"},
                ],
            },
            "lunar_is_leap_month": {"type": "boolean"},
            "remind_days_before": {
                "type": "integer",
                "minimum": 0,
                "maximum": 365,
            },
            "recurrence_type": {
                "type": "string",
                "enum": ["none", "daily", "monthly", "yearly", "interval_days"],
            },
            "interval_days": {
                "anyOf": [{"type": "integer", "minimum": 1}, {"type": "null"}],
            },
            "repeat_count": {
                "anyOf": [
                    {"type": "integer", "minimum": 1, "maximum": 100},
                    {"type": "null"},
                ],
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "missing_fields": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": [
                        "description",
                        "recipient_email",
                        "calendar_type",
                        "task_date",
                        "lunar_month",
                        "lunar_day",
                        "remind_days_before",
                        "recurrence_type",
                        "interval_days",
                        "repeat_count",
                    ],
                },
            },
            "clarification_question": {
                "anyOf": [{"type": "string"}, {"type": "null"}],
            },
            "assumptions": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": [
            "description",
            "recipient_email",
            "calendar_type",
            "task_date",
            "lunar_month",
            "lunar_day",
            "lunar_is_leap_month",
            "remind_days_before",
            "recurrence_type",
            "interval_days",
            "repeat_count",
            "confidence",
            "missing_fields",
            "clarification_question",
            "assumptions",
        ],
    },
    "strict": True,
}


def build_todo_text_parse_messages(
    text: str,
    *,
    current_date: date,
    timezone: str,
    default_recipient_email: str | None = None,
) -> list[ChatCompletionMessageParam]:
    default_email = default_recipient_email or ""
    user_prompt = f"""
解析下面的用户输入，输出符合 schema 的 JSON。

context:
- current_date: {current_date.isoformat()}
- timezone: {timezone}
- default_recipient_email: {default_email}

user_text:
{text}
""".strip()

    return [
        {"role": "system", "content": TODO_TEXT_PARSE_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
