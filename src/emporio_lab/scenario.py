"""Formato dos cenários do lab (`scenarios/<nome>.yaml`) e sua validação.

Regras que o código impõe, para o lab não virar adoção de tecnologia por si só:
- todo cenário mensurável declara, ANTES de rodar, as métricas e os critérios (ou marca a métrica como referência);
- cenário `planejado` pode ter hipótese e candidata, mas não pode ser executado: não há critério, não há medição;
- sem medição não há conclusão.
"""
import hashlib
import operator
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

SCENARIOS_DIR = Path('scenarios')
OPERATORS = {'<=': operator.le, '<': operator.lt, '>=': operator.ge, '>': operator.gt, '==': operator.eq}


class Criterio(BaseModel):
    model_config = ConfigDict(extra='forbid')
    operador: Literal['<=', '<', '>=', '>', '==']
    valor: float

    def satisfeito(self, medido: float) -> bool:
        return OPERATORS[self.operador](medido, self.valor)

    def texto(self) -> str:
        return f'{self.operador} {self.valor:g}'


class Metrica(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(pattern=r'^[a-z0-9_]+$')
    descricao: str = Field(min_length=5)
    unidade: str
    tipo: Literal['criterio', 'referencia']
    criterio: Criterio | None = None
    escopo: Literal['arquitetura', 'comparativo'] = 'arquitetura'   # 'comparativo' = uma medida do par de arquiteturas, não de cada uma

    @model_validator(mode='after')
    def criterio_so_quando_tipo_criterio(self):
        if self.tipo == 'criterio' and self.criterio is None:
            raise ValueError(f'métrica {self.id}: tipo "criterio" exige criterio')
        if self.tipo == 'referencia' and self.criterio is not None:
            raise ValueError(f'métrica {self.id}: tipo "referencia" não tem criterio')
        return self


class Parametros(BaseModel):
    model_config = ConfigDict(extra='forbid')
    usuarios_simultaneos: int = Field(ge=1)
    turnos_por_usuario: int = Field(ge=1)
    tamanho_do_catalogo: int = Field(ge=1)
    tamanho_do_conhecimento: str
    requisitos_de_fluxo: str
    latencia_llm_simulada_ms: int = Field(ge=0)
    seed: int
    repeticoes: int = Field(default=1, ge=1)                         # execuções completas de cada arquitetura
    alternar_ordem: bool = False                                     # repetições pares: A,B; ímpares: B,A


class Scenario(BaseModel):
    model_config = ConfigDict(extra='forbid')
    nome: str = Field(pattern=r'^S\d+-[a-z0-9-]+$')
    status: Literal['mensuravel', 'planejado']
    descricao: str = Field(min_length=10)
    mudanca_em_relacao_a_v1_0_2: str
    hipotese: str
    arquitetura_candidata: str | None = None
    arquiteturas: list[str] = Field(default_factory=list)
    relatorio_em: str | None = None                                  # diretório de relatório (padrão: o nome do cenário)
    protocolo: str | None = None                                     # documento do protocolo, também pré-registrado
    parametros: Parametros | None = None
    metricas: list[Metrica] = Field(default_factory=list)

    @model_validator(mode='after')
    def coerencia(self):
        if self.status == 'mensuravel':
            if self.parametros is None:
                raise ValueError('cenário mensurável exige parametros')
            if not any(m.tipo == 'criterio' for m in self.metricas):
                raise ValueError('cenário mensurável exige ao menos uma métrica com critério definido antes da execução')
            if not self.arquiteturas:
                raise ValueError('cenário mensurável exige a lista de arquiteturas a rodar')
            if len(self.arquiteturas) > 1 and (self.parametros.repeticoes < 3 or not self.parametros.alternar_ordem):
                raise ValueError('comparação entre arquiteturas exige ao menos 3 repetições com ordem alternada')
            ids = [m.id for m in self.metricas]
            if len(ids) != len(set(ids)):
                raise ValueError('ids de métricas duplicados')
        return self

    def resumo(self, limite: int = 100) -> str:
        """Primeira frase da descrição, em uma linha (para `scenario-list`)."""
        frase = self.descricao.strip().split('. ')[0].rstrip('.')
        return frase if len(frase) <= limite else frase[:limite - 1].rstrip() + '…'


class ScenarioError(Exception):
    pass


def path_of(name: str, root: Path = Path('.')) -> Path:
    if '/' in name or '..' in name:
        raise ScenarioError(f'nome de cenário inválido: {name!r}')
    return root / SCENARIOS_DIR / f'{name}.yaml'


def load(name: str, root: Path = Path('.')) -> Scenario:
    path = path_of(name, root)
    if not path.exists():
        raise ScenarioError(f'cenário "{name}" não existe; use `make scenario-list`')
    try:
        scenario = Scenario.model_validate(yaml.safe_load(path.read_text(encoding='utf-8')))
    except (ValidationError, yaml.YAMLError) as error:
        raise ScenarioError(f'cenário "{name}" inválido: {error}') from None
    if scenario.nome != name:
        raise ScenarioError(f'o arquivo {path.name} declara nome "{scenario.nome}"')
    return scenario


def list_all(root: Path = Path('.')) -> list[Scenario]:
    return [load(p.stem, root) for p in sorted((root / SCENARIOS_DIR).glob('S*.yaml'))]


def sha256_of(name: str, root: Path = Path('.')) -> str:
    return hashlib.sha256(path_of(name, root).read_bytes()).hexdigest()
