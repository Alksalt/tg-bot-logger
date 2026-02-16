from __future__ import annotations

from tg_time_logger.db import Entry
from tg_time_logger.gamification import format_minutes_hm
from tg_time_logger.i18n import localize
from tg_time_logger.service import StatusView

NEGATIVE_WARNING = "⚠️ Limit reached. Fun remaining is negative. Log productive time to earn more."

CATEGORY_LABELS = {
    "en": {
        "study": "📚 Study",
        "build": "🔨 Build",
        "training": "🏋️ Training",
        "job": "💼 Job",
    },
    "uk": {
        "study": "📚 Навчання",
        "build": "🔨 Розробка",
        "training": "🏋️ Тренування",
        "job": "💼 Робота",
    },
}


def _bar(ratio: float, width: int = 20) -> str:
    filled = max(0, min(width, int(round(ratio * width))))
    return "█" * filled + "░" * (width - filled)


def _fun_remaining_lines(value: int, lang: str = "en") -> list[str]:
    if value < 0:
        return [
            localize(lang, "Remaining: {mins}", "Залишок: {mins}", mins=format_minutes_hm(-1)),
            localize(lang, NEGATIVE_WARNING, "⚠️ Ліміт досягнуто. Залишок відпочинку від'ємний. Додай продуктивний час, щоб заробити більше."),
        ]
    return [localize(lang, "Remaining: {mins}", "Залишок: {mins}", mins=format_minutes_hm(value))]


def status_message(view: StatusView, username: str | None = None, lang: str = "en") -> str:
    header = (
        localize(lang, "📊 Status — @{username}", "📊 Статус — @{username}", username=username)
        if username
        else localize(lang, "📊 Status", "📊 Статус")
    )
    lines = [
        header,
        "",
        localize(lang, "⚡ Level {level} — {title}", "⚡ Рівень {level} — {title}", level=view.level, title=view.title),
        localize(
            lang,
            "📊 XP: {current:,} / {next:,} (to Level {to_level})",
            "📊 XP: {current:,} / {next:,} (до Рівня {to_level})",
            current=view.xp_current_level,
            next=view.xp_next_level,
            to_level=view.level + 1,
        ),
        f"{_bar(view.xp_progress_ratio)} {view.xp_progress_ratio * 100:.1f}%",
        localize(
            lang,
            "🔥 Streak: {days} days ({mult:.1f}x XP) | Best: {best}",
            "🔥 Серія: {days} днів ({mult:.1f}x XP) | Рекорд: {best}",
            days=view.streak_current,
            mult=view.streak_multiplier,
            best=view.streak_longest,
        ),
        "",
        localize(lang, "📅 This week (Mon–Sun):", "📅 Цей тиждень (Пн–Нд):"),
    ]

    labels = CATEGORY_LABELS.get(lang, CATEGORY_LABELS["en"])
    for key in ("study", "build", "training", "job"):
        minutes = view.week_categories.get(key, 0)
        fun = (minutes * (15 if key == "study" else 4 if key == "job" else 20)) // 60
        lines.append(
            localize(
                lang,
                "  {label}: {mins} → +{fun} fun",
                "  {label}: {mins} → +{fun} fun",
                label=labels[key],
                mins=format_minutes_hm(minutes),
                fun=fun,
            )
        )

    lines.extend(
        [
            localize(
                lang,
                "  📊 Total: {total} | XP: +{xp}",
                "  📊 Всього: {total} | XP: +{xp}",
                total=format_minutes_hm(view.week.productive_minutes),
                xp=view.xp_week,
            ),
            localize(
                 lang,
                 "  💰 Fun earned: +{fun}m",
                 "  💰 Зароблено відпочинку: +{fun}хв",
                 fun=view.fun_earned_this_week,
            ),
            (
                localize(
                    lang,
                    "  🎯 Plan: {done}m/{target}m this week",
                    "  🎯 План: {done}m/{target}m цього тижня",
                    done=view.week_plan_done_minutes,
                    target=view.week_plan_target_minutes,
                )
                if view.week_plan_target_minutes > 0
                else localize(lang, "  🎯 Plan: not set (/plan set <duration>)", "  🎯 План: не встановлено (/plan set <duration>)")
            ),
            localize(
                lang,
                "  🧠 Deep work (90m+): {count} sessions",
                "  🧠 Deep work (90хв+): {count} сесій",
                count=view.deep_sessions_week,
            ),
            "",
            localize(lang, "💰 Fun Economy:", "💰 Економіка відпочинку:"),
            (
                localize(
                    lang,
                    "  Earned: {base} (base) + {milestone} (10h milestone) + {lvl} (lvl bonus) + {quest} (quest) + {wheel} (wheel)",
                    "  Зароблено: {base} (база) + {milestone} (рубіж 10г) + {lvl} (бонус рівня) + {quest} (квест) + {wheel} (колесо)",
                    base=view.economy.base_fun_minutes,
                    milestone=view.economy.milestone_bonus_minutes,
                    lvl=view.economy.level_bonus_minutes,
                    quest=view.economy.quest_bonus_minutes,
                    wheel=view.economy.wheel_bonus_minutes,
                )
            ),
            localize(lang, "  Spent: -{mins} min", "  Витрачено: -{mins} хв", mins=view.economy.spent_fun_minutes),
            localize(lang, "  Saved: -{mins} min", "  Відкладено: -{mins} хв", mins=view.economy.saved_fun_minutes),
            *_fun_remaining_lines(view.economy.remaining_fun_minutes, lang),
            "",
            localize(lang, "⚔️ Active Quests: {count}", "⚔️ Активні квести: {count}", count=view.active_quests),
        ]
    )
    return "\n".join(lines)



def entry_removed_message(entry: Entry, lang: str = "en") -> str:
    note = f" | note: {entry.note}" if entry.note else ""
    kind = f"{entry.kind} ({entry.category})" if entry.kind == "productive" else entry.kind
    return localize(
        lang,
        "Undid entry: {kind} {minutes} at {at}{note}",
        "Скасовано запис: {kind} {minutes} о {at}{note}",
        kind=kind,
        minutes=format_minutes_hm(entry.minutes),
        at=entry.created_at.strftime("%Y-%m-%d %H:%M"),
        note=note,
    )
