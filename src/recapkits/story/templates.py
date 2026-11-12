"""六种卡型的自动文案模板: 纯数据 + 一个 `copy(kind, refs, year)`。

模板只允许三种成分: CJK 文案、`{{id.fact}}` 占位符、年份字面量。这条限制同时满足
V2 (无手写数字) 与 V6 (无来源不明的专有名词), 而且可以被一条测试遍历所有模板断言 ——
不用逐条背规则。

**不要写「前三」「前五」这类序数。** 它们现在只是靠 `CHINESE_NUMBER` 缺量词才漏过去,
规则一收紧就翻脸; 模板不该依赖校验器的边角行为。
"""

from dataclasses import dataclass

from recapkits.story.schema import InsightRef


def ph(ref: InsightRef, key: str) -> str:
    """拼一个占位符; 花括号只在这里出现一次。"""
    return "{{" + ref.id + "." + key + "}}"


@dataclass(frozen=True)
class Template:
    """一张卡的文案; `sub` 省略时渲染器不会画出副标题那一层。

    `card_id` 用语义名 (`cover` / `big-number` / ...) 而不是 `c1..c6`:
    它们会出现在渲染器的报错里, 语义名才有用。
    """

    card_id: str
    card_type: str
    kicker: str
    headline: str
    sub: str | None = None


#: ranking 的标题按主源换词。git 是既定文案, 一个字节都不能变;
#: 其余源只换这一句, 其余模板与卡片顺序保持共用。
RANKING_HEADLINE = {
    "git": "出现最多的项目",
    "spotify": "听得最多的艺人",
    "netflix": "看得最多的剧集",
}
DEFAULT_RANKING_HEADLINE = RANKING_HEADLINE["git"]


def copy(
    kind: str, refs: dict[str, InsightRef], year: int, *, source: str | None = None
) -> Template:
    """按卡型产出模板。

    `refs` 以 **洞察 kind** 为键, 不是洞察 id: 自动规划每张卡只认一类洞察,
    用 kind 做键可以让调用方不必记住一长串 id。`vol.daily_series` 若有多条,
    调用方已经按 headline 值选过一条。

    `source` 只在多源时由调用方传入; 它目前只影响 ranking 的标题, 未知源回落到
    git 的文案, 保证手写 payload (没有 source 键) 的故事不变。
    """
    if kind == "cover":
        total = refs["vol.total"]
        return Template(
            "cover",
            "cover",
            "本地生成 · 未上传",
            str(year),
            f"{ph(total, 'events')} 条记录，落在 {ph(total, 'active_days')} 个活跃日",  # noqa: RUF001
        )
    if kind == "big-number":
        total = refs["vol.total"]
        return Template(
            "big-number",
            "big-number",
            "全年",
            "记录总数",
            f"覆盖 {ph(total, 'active_days')} 个活跃日",
        )
    if kind == "ranking":
        conc = refs["conc.top_entity"]
        return Template(
            "ranking",
            "ranking",
            "集中度",
            RANKING_HEADLINE.get(source or "git", DEFAULT_RANKING_HEADLINE),
            f"首位占全部记录的 {ph(conc, 'share')}",
        )
    if kind == "heatmap":
        return Template(
            "heatmap",
            "heatmap",
            "分布",
            "全年逐日",
            "颜色越亮，当天记录越多",  # noqa: RUF001
        )
    if kind == "clock":
        hour = refs["time.hour_rhythm"]
        return Template(
            "clock",
            "clock",
            "节律",
            "每小时的样子",
            f"深夜时段占 {ph(hour, 'late_night_share')}",
        )
    if kind == "summary":
        return Template(
            "summary",
            "summary-grid",
            "总览",
            "整年，这样过去",  # noqa: RUF001
        )
    raise KeyError(f"没有卡型 {kind} 的模板")


#: 卡片顺序是固定的: 先立封面, 再给主体数字, 然后逐层收窄到细节与总览。
CARD_ORDER = ("cover", "big-number", "ranking", "heatmap", "clock", "summary")

#: 每张卡消费哪一类洞察; summary 例外, 它引用前四类用过的证据。
CARD_SOURCE = {
    "cover": "vol.total",
    "big-number": "vol.total",
    "ranking": "conc.top_entity",
    "heatmap": "vol.daily_series",
    "clock": "time.hour_rhythm",
}
