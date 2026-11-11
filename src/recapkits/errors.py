"""CLI 层共用的错误类型: 一句话、可操作、不打 traceback。"""


class RecapError(Exception):
    """可以直接展示给用户的一句话错误。"""
