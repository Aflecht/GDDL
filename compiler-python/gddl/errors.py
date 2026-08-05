# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Shared error/warning types for every compile phase (3 through 8). Carry
enough structure that downstream consumers (golden-output export, corpus
tooling) can report "which phase, which specific check" rather than a
single undifferentiated error string.
"""


class CompileError(Exception):
    def __init__(self, phase: int, message: str, line=None, check=None):
        self.phase = phase
        self.check = check
        self.line = line
        self.message = message
        super().__init__(str(self))

    def __str__(self):
        loc = f"line {self.line}: " if self.line is not None else ""
        return f"{loc}{self.message}"

    def to_dict(self):
        return {
            "phase": self.phase,
            "check": self.check,
            "line": self.line,
            "message": str(self),
        }


class CompileWarning:
    """Advisory diagnostic (spec §12.1) -- same phase/location/message
    attribution as CompileError for traceability, but deliberately NOT
    an Exception subclass: a warning is data to collect, never a
    control-flow signal. Warnings never block any phase or export."""

    def __init__(self, phase: int, message: str, line=None, check=None):
        self.phase = phase
        self.check = check
        self.line = line
        self.message = message

    def __str__(self):
        loc = f"line {self.line}: " if self.line is not None else ""
        return f"{loc}{self.message}"

    def __repr__(self):
        return f"CompileWarning({self!s})"

    def to_dict(self):
        return {
            "phase": self.phase,
            "check": self.check,
            "line": self.line,
            "message": str(self),
        }
