class Diagnostic:
    def __init__(self, stage, message, line=0, col=0, severity="error"):
        self.stage = stage
        self.message = message
        self.line = line
        self.col = col
        self.severity = severity

    def to_dict(self):
        return {
            "stage": self.stage,
            "message": self.message,
            "line": self.line,
            "col": self.col,
            "severity": self.severity,
        }

    def __str__(self):
        where = f"{self.line}:{self.col}" if self.col else f"{self.line}"
        kind = "попередження" if self.severity == "warning" else "помилка"
        return f"[{self.stage}] рядок {where}: {kind}: {self.message}"


class CRuntimeError(Exception):
    def __init__(self, message, line=0):
        super().__init__(message)
        self.line = line
