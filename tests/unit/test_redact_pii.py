"""结构化 PII: 每条规则都要有正例, 也要有"看起来像但不该抹"的反例。"""

import pytest

from recapkits.redact import pii


def categories(text: str) -> list[str]:
    return [ruling.category for ruling in pii.scan(text)]


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("联系 alice@example.com 处理", "邮箱"),
        ("主页 https://example.com/u/1 在这", "URL"),
        ("备用 http://example.org 在这", "URL"),
        ("账号 +86 138 0013 8000 联系", "电话"),
        ("电话 138 0013 8000 联系", "电话"),
        ("服务器 192.168.1.10 上", "IP"),
        ("地址 fe80::1 的网关", "IP"),
        ("坐标 31.2304, 121.4737 附近", "坐标"),
        ("坐标 31.2304\uff0c121.4737 附近", "坐标"),
        ("关注 @some_one 看", "@handle"),
        ("卡号 4111 1111 1111 1111 过期", "卡号"),
        ("卡号 4111111111111111 过期", "卡号"),
        ("IBAN GB82WEST12345698765432 收款", "IBAN"),
        ("源文件 C:\\Users\\alice\\recap\\story.json", "路径"),
        ("源文件 ~/Downloads/export.json", "路径"),
        ("源文件 /home/alice/recap.db", "路径"),
    ],
)
def test_each_rule_has_a_positive(text: str, category: str) -> None:
    assert category in categories(text)


@pytest.mark.parametrize(
    "text",
    [
        # Luhn 过不了的 16 位纯数字: 播放时长不该被当成卡号
        "时长 1234567890123456 秒",
        # 日期与分辨率: 电话要求国别或三组分隔, 两者都不满足
        "日期 2024-03-11",
        "分辨率 1080 1920",
        # 时间不是 IPv6
        "时间 23:41:07",
        # 版本号不是 IPv4
        "版本 v1.2.3.4",
        # mod-97 校验失败
        "IBAN GB82WEST12345698765431 收款",
        # 纬度越界
        "坐标 999.123, 12.345 附近",
        # 盘符后面没有分隔符, 是选项而不是路径
        "选项 C: 继续",
        "比例 a/b",
    ],
)
def test_lookalikes_are_not_redacted(text: str) -> None:
    assert categories(text) == []


def test_email_wins_over_handle() -> None:
    """重叠只留一处: 邮箱覆盖了 @handle, 而不是把地址拆成两段各抹一次。"""
    rulings = pii.scan("alice@example.com")

    assert [ruling.category for ruling in rulings] == ["邮箱"]
    assert rulings[0].sample == "alice@example.com"


def test_card_wins_over_phone() -> None:
    """同一串数字既像卡号又像电话时, 取更长的那一处。"""
    rulings = pii.scan("4111 1111 1111 1111")

    assert [ruling.category for ruling in rulings] == ["卡号"]


def test_url_trailing_punctuation_is_kept() -> None:
    """URL 末尾的句号属于句子, 不属于地址; 否则替换会把标点一起吃掉。"""
    text = "见 https://example.com/a."

    redacted, rulings = pii.redact(text)

    assert redacted == f"见 {pii.REMOVED}."
    assert rulings[0].sample == "https://example.com/a"


def test_redact_replaces_every_category_and_keeps_samples() -> None:
    text = "alice@example.com 在 192.168.1.10 上留了 +86 138 0013 8000"

    redacted, rulings = pii.redact(text)

    assert "@" not in redacted
    assert "192.168" not in redacted
    assert "+86" not in redacted
    assert [ruling.category for ruling in rulings] == ["邮箱", "IP", "电话"]
    assert [ruling.sample for ruling in rulings] == [
        "alice@example.com",
        "192.168.1.10",
        "+86 138 0013 8000",
    ]


def test_plain_chinese_text_is_untouched() -> None:
    text = "这一年你听了很多歌, 主要在深夜."

    assert pii.redact(text) == (text, [])
