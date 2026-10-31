from pydantic import BaseModel, Field, ValidationError
from emporio.repository.base import StoreRepository
from emporio.tools.contracts import ToolError, ToolResult

class GetProductInput(BaseModel):
    product_id: int = Field(gt=0, strict=True)

def get_product(repository: StoreRepository, args: dict) -> ToolResult:
    try:
        parsed = GetProductInput.model_validate(args)
    except ValidationError:
        return ToolResult(ok=False, error=ToolError(code='invalid_input', message_for_agent='Identificador inválido.'))
    product = repository.get_product(parsed.product_id)
    if product is None:
        return ToolResult(ok=False, error=ToolError(code='not_found', message_for_agent='Produto não encontrado.'))
    return ToolResult(ok=True, data=product.model_dump(mode='json'))
