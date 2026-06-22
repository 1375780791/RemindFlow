from datetime import date

from lunardate import LunarDate
from pydantic import BaseModel


class LunarRule(BaseModel):
    year: int
    month: int
    day: int
    is_leap_month: bool = False


def solar_to_lunar(solar_date: date) -> LunarRule:
    lunar_date = LunarDate.fromSolarDate(
        solar_date.year,
        solar_date.month,
        solar_date.day,
    )
    return LunarRule(
        year=lunar_date.year,
        month=lunar_date.month,
        day=lunar_date.day,
        is_leap_month=lunar_date.isLeapMonth,
    )


def lunar_to_solar(
    year: int,
    month: int,
    day: int,
    is_leap_month: bool = False,
) -> date:
    try:
        return LunarDate(year, month, day, is_leap_month).toSolarDate()
    except ValueError as exc:
        raise ValueError(
            f"无效的农历日期：{year}年{month}月{day}日"
        ) from exc


def lunar_rule_to_solar_date(rule: LunarRule, target_year: int) -> date:
    return lunar_to_solar(
        year=target_year,
        month=rule.month,
        day=rule.day,
        is_leap_month=rule.is_leap_month,
    )


def build_lunar_rule_from_solar_date(solar_date: date) -> LunarRule:
    return solar_to_lunar(solar_date)
