class AppError(Exception):
    def __init__(self, status_code=400, error_code="ERROR", detail="Application Error"):
        self.status_code = status_code
        self.error_code = error_code
        self.detail = detail
        super().__init__(self.detail)

    def __str__(self):
        return f"[{self.error_code}] {self.detail}"
