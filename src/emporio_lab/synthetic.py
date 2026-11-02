"""Carga sintética do lab: determinística pela seed e sempre marcada como sintética."""
import hashlib
import json
import random
from dataclasses import asdict, dataclass

SYNTHETIC_MARK = 'SINTÉTICO'
CATEGORIES = ('violões', 'guitarras', 'baixos', 'ukuleles', 'teclados', 'baterias')
HOURS = ('A loja está aberta agora?', 'Que horas vocês abrem?', 'Vocês fecham que horas hoje?')
SMALL_TALK = ('Oi, tudo bem?', 'Vocês vendem instrumentos de sopro?', 'Obrigado!')
KINDS = (('preco', 40), ('listagem', 25), ('horario', 15), ('conversa', 20))   # pesos (%)


@dataclass(frozen=True)
class Turn:
    user: int
    index: int
    kind: str
    text: str


def build_workload(product_names: list[str], users: int, turns: int, seed: int) -> list[list[Turn]]:
    """`users` listas de `turns` mensagens. Mesma seed e mesmo catálogo geram exatamente a mesma carga."""
    if not product_names:
        raise ValueError('catálogo vazio')
    rng = random.Random(seed)
    kinds, weights = zip(*KINDS)
    workload = []
    for user in range(users):
        rows = []
        for index in range(turns):
            kind = rng.choices(kinds, weights)[0]
            if kind == 'preco':
                text = f'Quanto custa o {rng.choice(product_names)}?'
            elif kind == 'listagem':
                text = f'Quais {rng.choice(CATEGORIES)} vocês têm?'
            elif kind == 'horario':
                text = rng.choice(HOURS)
            else:
                text = rng.choice(SMALL_TALK)
            rows.append(Turn(user, index, kind, text))
        workload.append(rows)
    return workload


def fingerprint(workload: list[list[Turn]]) -> str:
    blob = json.dumps([[asdict(t) for t in user] for user in workload], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()


def kind_counts(workload: list[list[Turn]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for user in workload:
        for turn in user:
            counts[turn.kind] = counts.get(turn.kind, 0) + 1
    return dict(sorted(counts.items()))
