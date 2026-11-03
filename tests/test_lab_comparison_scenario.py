"""O cenário comparativo entregue declara, antes da execução, a paridade funcional e as condições do S0."""
from pathlib import Path

from emporio_lab import scenario as sc

ROOT = Path(__file__).resolve().parents[1]


def test_shipped_comparison_scenario_is_valid_and_pre_declares_parity_criteria():
    s = sc.load('S0-baseline-comparacao', ROOT)
    assert s.arquiteturas == ['v1.0.2', 'pydantic-ai'] and s.parametros.repeticoes >= 3 and s.parametros.alternar_ordem
    ids = {m.id for m in s.metricas if m.tipo == 'criterio'}
    assert {'concessoes_indevidas_de_acesso', 'precos_inventados_aceitos', 'regressoes_de_privacidade', 'divergencias_em_casos_criticos'} <= ids
    assert sc.load('S0-baseline', ROOT).parametros.repeticoes == 1          # o S0 original não muda
