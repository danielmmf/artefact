from typing import Any, Literal
from pydantic import BaseModel, model_validator

class ToolError(BaseModel):
    code: Literal['invalid_input', 'not_found', 'ambiguous', 'access_denied', 'not_verified', 'locked', 'internal_error']
    message_for_agent: str

class ToolResult(BaseModel):
    ok: bool
    data: Any = None
    error: ToolError | None = None
    @model_validator(mode='after')
    def check_envelope(self):
        if self.ok == (self.error is not None) or (not self.ok and self.data is not None):
            raise ValueError('envelope inconsistente')
        return self
