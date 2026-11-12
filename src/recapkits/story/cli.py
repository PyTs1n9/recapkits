"""`recap story`: `--check` 校验已有故事, `--auto` 从洞察规划一份故事。

两条路径共用同一个校验器: 自动生成的故事不是「另一种故事」, 它只是省掉了手写
JSON 这一步。`--auto` 在写盘之前就把校验跑完, 失败时不留下半成品 —— 写出坏
`story.json` 只会把失败推迟到 render, 用户会看到两条互相矛盾的错误。
"""

import argparse
import sys
from pathlib import Path

from recapkits.errors import RecapError
from recapkits.story.auto import Plan, plan
from recapkits.story.load import load_json, resolve_insights_path
from recapkits.story.schema import Story, StorySchemaError, format_errors
from recapkits.story.validate import build_refs, validate_story
from recapkits.tz import utc_now_iso
from recapkits.workspace import load_workspace


def _period_year(payload: dict[str, object]) -> int:
    """没有工作区时, 用 insights.json 的窗口结束年; 再不行才用当前 UTC 年。"""
    items = payload.get("insights")
    if isinstance(items, list) and items and isinstance(items[0], dict):
        period = items[0].get("period")
        if isinstance(period, dict):
            end = period.get("end")
            if isinstance(end, str) and len(end) >= 4 and end[:4].isdigit():
                return int(end[:4])
    return int(utc_now_iso()[:4])


def _print_skips(result: Plan) -> None:
    """跳过表: 每一条都要说清是哪张卡、为什么不在。"""
    if not result.skips:
        print("跳过 0 张: 六类洞察都在")
        return
    print(f"跳过 {len(result.skips)} 张:")
    for skip in result.skips:
        print(f"  - {skip.card}: {skip.reason}")


def auto_story(
    *,
    insights: str | None,
    out: str | None,
    year: int | None,
    theme: str,
    tone: str,
    locale: str,
    force: bool,
) -> int:
    """规划 → 自检 → 写盘; 返回进程退出码。`recap <路径>` 也走这里。"""
    workspace = load_workspace()
    if out:
        out_path = Path(out).expanduser()
    elif workspace is not None:
        out_path = workspace.story_path
    else:
        # 把故事写到当前目录是最容易被忽略的副作用; 没有工作区就要求显式 --out。
        raise RecapError("没有工作区: 先 recap init, 或用 --out 指定故事文件")

    if out_path.is_file() and not force:
        raise RecapError(f"已存在手写故事: {out_path}\n要重新生成加 --force, 或先移走它")

    if insights:
        insights_path = Path(insights).expanduser()
    elif workspace is not None and workspace.out_path.is_file():
        insights_path = workspace.out_path
    else:
        raise RecapError("未找到 insights.json: 先运行 recap insights, 或用 --insights 指定")

    payload = load_json(insights_path, "insights.json")
    resolved_year = year if year is not None else (workspace.year if workspace else None)
    if resolved_year is None:
        resolved_year = _period_year(payload)
    result = plan(payload, year=resolved_year, theme=theme, tone=tone, locale=locale)

    try:
        story = Story.from_dict(result.story)
    except StorySchemaError as exc:
        print(f"自动故事没有通过校验, 已放弃写盘: {out_path}", file=sys.stderr)
        print(f"错误: {exc}", file=sys.stderr)
        return 1
    errors = validate_story(story, build_refs(payload), allow_sensitive=False)
    if errors:
        print(f"自动故事没有通过校验, 已放弃写盘: {out_path}", file=sys.stderr)
        print(format_errors(errors), file=sys.stderr)
        return 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # 写字节而不是 write_text: 行尾由我们决定, 不由平台决定。
    out_path.write_bytes(result.as_json().encode("utf-8"))
    print(f"已写入 {out_path}")
    print(f"  {len(story.cards)} 张卡: {' → '.join(result.cards)}")
    _print_skips(result)
    return 0


def cmd_story(args: argparse.Namespace) -> int:
    """校验或自动生成 story.json; 成功返回 0。"""
    if args.auto:
        return auto_story(
            insights=args.insights,
            out=args.out,
            year=args.year,
            theme=args.theme,
            tone=args.tone,
            locale=args.locale,
            force=bool(args.force),
        )

    story_path = Path(args.check).expanduser()
    try:
        story = Story.from_dict(load_json(story_path, "story.json"))
    except StorySchemaError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    refs = build_refs(load_json(resolve_insights_path(args.insights, story_path), "insights.json"))
    errors = validate_story(
        story,
        refs,
        allow_sensitive=bool(args.allow_sensitive),
        allow_unknown_names=bool(args.allow_unknown_names),
    )
    if not errors:
        print(f"通过: {story_path.name} 共 {len(story.cards)} 张卡")
        return 0
    print(f"{story_path.name} {format_errors(errors)}", file=sys.stderr)
    return 1
