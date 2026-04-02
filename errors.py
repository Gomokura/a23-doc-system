"""
自定义异常类 - 负责人: 成员1
"""


class AppError(Exception):
    """应用自定义异常"""
    
    def __init__(self, status_code: int, error_code: str, detail: str):
        self.status_code = status_code
        self.error_code = error_code
        self.detail = detail
        super().__init__(detail)
