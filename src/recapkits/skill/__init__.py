"""随包发布的 agent skill 文本。

`SKILL.md` 与校验器同源: 它写的就是 `--check` 会拦的东西, 所以只做分发,
不在运行时拼提示词 —— 拼出来的文本没法被 CI lint, 校验器新增一个错误码
也没人会记得同步。

行尾在这里统一成 LF: 安装出去的字节由我们决定, 不由 checkout 配置决定。
"""

from importlib.resources import files

RESOURCE = "SKILL.md"


def read_text() -> str:
    """读同目录的 SKILL.md; 调用方负责决定装到哪里。

    用 `__name__` 而不是 `__package__`: 包的 `__init__` 里两者相等, 但后者的
    类型是 `str | None`, 3.11 的 typeshed 会拒绝它作为 `files()` 的参数。
    """
    raw = files(__name__).joinpath(RESOURCE).read_text(encoding="utf-8")
    return raw.replace("\r\n", "\n")
