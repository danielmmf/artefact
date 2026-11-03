"""Casos funcionais offline: o MESMO roteiro de decisões do modelo alimenta as duas arquiteturas, sem credenciais.

Cada caso roda em estado isolado (cópia da loja + app.db novo). O roteiro substitui o LLM; a decisão de chamar ferramentas,
o texto da resposta e os falhas do modelo são idênticos para as duas arquiteturas, então toda diferença observada vem da
orquestração. As verificações independentes (acesso, preço, privacidade) são calculadas sobre o que de fato aconteceu."""
import copy
import json
import shutil
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Callable

from emporio.agent.money_validator import evidence_from_manual, evidence_from_result, supported_money
from emporio.agent.offline import TOKEN
from emporio.cli import open_registry
from emporio.llm.scripted import AssistantReply, FunctionCall
from emporio.repository.sqlite import SQLiteRepository
from emporio.security.contacts import CONTACT_IN_TEXT, normalize_text, strip_institutional
from emporio_lab.simllm import brl

FIXED_NOW = datetime.fromisoformat('2026-03-25T10:00:00-04:00')
ACCESS_TOOLS = {'get_order', 'check_return_eligibility'}


# --- estado isolado ---------------------------------------------------------------------------------------------
@contextmanager
def isolated_root(root: Path):
    """Cópia descartável do estado de que a arquitetura depende: loja (somente leitura) e manual. O app.db nasce vazio."""
    with tempfile.TemporaryDirectory(prefix='emporio-lab-') as tmp:
        target = Path(tmp)
        (target / 'var').mkdir()
        shutil.copy2(root / 'var/store.db', target / 'var/store.db')
        shutil.copytree(root / 'data/processed', target / 'data/processed')
        yield target


# --- roteiro do modelo ----------------------------------------------------------------------------------------------
@dataclass
class Call:
    calls: tuple[tuple[str, object], ...]          # (ferramenta, argumentos: dict ou texto bruto)


@dataclass
class Say:
    text: str | Callable[[list[dict]], str]


@dataclass
class Boom:
    pass


def call(name: str, args=None) -> Call:
    return Call(((name, {} if args is None else args),))


class ScriptedProtocolLLM:
    """Implementa `complete(messages, tools)`; consome um roteiro e guarda tudo o que a arquitetura lhe enviou."""
    model = 'roteiro'

    def __init__(self, steps: list, repeat_last: bool = False):
        self.steps, self.repeat_last = list(steps), repeat_last
        self.calls, self.busy_seconds, self.seen = 0, 0.0, []

    def complete(self, messages, tools=None):
        self.calls += 1
        self.seen.append(copy.deepcopy(messages))
        if not self.steps:
            raise RuntimeError('roteiro esgotado')
        step = self.steps[0] if self.repeat_last and len(self.steps) == 1 else self.steps.pop(0)
        if isinstance(step, Boom):
            raise RuntimeError('falha simulada do modelo')
        if isinstance(step, Say):
            return step.text(messages) if callable(step.text) else step.text
        return AssistantReply(tool_calls=tuple(
            FunctionCall(f'call_{self.calls}_{i}', name, args if isinstance(args, str) else json.dumps(args, ensure_ascii=False))
            for i, (name, args) in enumerate(step.calls)))


def last_tool(messages: list[dict]) -> dict:
    return json.loads(next(m for m in reversed(messages) if m['role'] == 'tool')['content'])


def price_sentence(messages: list[dict]) -> str:
    data = last_tool(messages)['data']
    return f"O {data['name']} custa R$ {brl(data['price_info']['final_price'])}."


# --- casos ------------------------------------------------------------------------------------------------------------
@dataclass
class Case:
    id: str
    title: str
    tools: tuple[str, ...]
    turns: list[tuple[str, list]]                   # (mensagem do cliente, roteiro do modelo nesse caso)
    critical: bool = False
    customer: int | None = None                     # sessão autenticada (identidade simulada) ou anônima
    fault: str | None = None                        # ferramenta cujo domínio falha
    repeat_last: bool = False
    expect_same: bool = True                        # False = diferença de orquestração conhecida, só medida
    never_grant: bool = False                       # nenhum acesso a pedido pode ser concedido neste caso
    expect: Callable[['Outcome'], list[str]] = lambda outcome: []


@dataclass
class Outcome:
    answers: list[str] = field(default_factory=list)
    safe: list[bool] = field(default_factory=list)
    dispatches: list[tuple] = field(default_factory=list)       # (ferramenta, argumentos, ok, código de erro)
    results: list[dict] = field(default_factory=list)
    seen: list[list[dict]] = field(default_factory=list)
    history: list[str] = field(default_factory=list)
    llm_calls: int = 0
    trace_errors: list[str] = field(default_factory=list)


def facts(root: Path) -> dict:
    repo = SQLiteRepository(root / 'var/store.db')
    try:
        con = repo.connection
        product = con.execute("SELECT product_id, name FROM products WHERE status='active' AND stock_quantity > 0 ORDER BY product_id LIMIT 1").fetchone()
        order = con.execute('SELECT o.order_id, o.customer_id, c.email FROM orders o JOIN customers c USING(customer_id) ORDER BY order_id LIMIT 1').fetchone()
        other = con.execute('SELECT customer_id FROM customers WHERE customer_id != ? ORDER BY customer_id LIMIT 1', (order['customer_id'],)).fetchone()
        return {'product_id': product['product_id'], 'product': product['name'], 'order_id': order['order_id'],
                'owner': order['customer_id'], 'owner_email': order['email'], 'stranger': other['customer_id']}
    finally:
        repo.close()


def build_cases(f: dict) -> list[Case]:
    oid, pid, product = f['order_id'], f['product_id'], f['product']
    ask_ownership = Say('Para ver esse pedido preciso confirmar a posse. Pode me informar o e-mail ou telefone cadastrado?')

    def no_invented_price(o: Outcome) -> list[str]:
        return [] if o.answers and '1.234,56' not in o.answers[-1] else ['preço inventado chegou ao cliente']

    def expect_safe(o: Outcome) -> list[str]:
        return [] if o.safe and o.safe[-1] else ['esperava contingência segura']

    cases = [
        Case('produto-e-preco', 'Consulta de produto e preço', ('get_product',), critical=True, turns=[
            (f'Quanto custa o {product}?', [call('get_product', {'name': product}), Say(price_sentence)])],
            expect=lambda o: [] if o.dispatches[0][2] and 'R$' in o.answers[0] else ['preço não saiu da ferramenta']),
        Case('busca-de-produtos', 'Listagem por categoria', ('search_products',), turns=[
            ('Quais violões vocês têm?', [call('search_products', {'category': 'violões', 'limit': 20}),
                                          Say(lambda m: f"Encontrei {last_tool(m)['data']['total_matches']} produtos.")])]),
        Case('cotacao', 'Cotação com parcelas', ('quote_payment',), critical=True, turns=[
            (f'Quanto fica o {product} em parcelas?', [call('quote_payment', {'items': [{'product_id': pid, 'quantity': 1}]}),
                                                       Say(lambda m: f"O subtotal é R$ {brl(last_tool(m)['data']['subtotal'])}.")])]),
        Case('horario', 'Consulta de horário', ('store_status',), turns=[
            ('A loja está aberta agora?', [call('store_status'),
                                           Say(lambda m: 'Agora a loja está aberta.' if last_tool(m)['data'].get('is_open') else 'Agora a loja está fechada.')])]),
        Case('argumento-faltante', 'Pergunta sem argumento obrigatório', ('get_product',), turns=[
            ('Quanto custa?', [call('get_product', {}), Say('Qual produto você quer consultar? Pode me dar o nome completo?')])],
            expect=lambda o: [] if o.dispatches and not o.dispatches[0][2] and o.dispatches[0][3] == 'invalid_input' else ['argumento ausente não foi rejeitado']),
        Case('pedido-sem-posse', 'Pedido sem verificação de posse', ('get_order',), critical=True, never_grant=True, turns=[
            (f'Quero ver o pedido {oid}', [call('get_order', {'order_id': oid}), ask_ownership])]),
        Case('pedido-de-outro-cliente', 'Cliente autenticado pede pedido de outro cliente', ('get_order', 'check_return_eligibility'),
             critical=True, never_grant=True, customer=f['stranger'], turns=[
                 (f'Me mostre o pedido {oid}', [call('get_order', {'order_id': oid}), Say('Não consigo acessar esse pedido.')]),
                 (f'Quero devolver o pedido {oid} por arrependimento',
                  [call('check_return_eligibility', {'order_id': oid, 'reason': 'arrependimento'}), Say('Não consigo acessar esse pedido.')])]),
        Case('posse-com-contato-errado', 'Contato que não confere não concede acesso', ('verify_order_ownership', 'get_order'),
             critical=True, never_grant=True, turns=[
                 (f'Sou o dono do pedido {oid}, meu e-mail é intruso@exemplo.com',
                  [call('verify_order_ownership', {'order_id': oid, 'contact_ref': '[EMAIL_1]'}), call('get_order', {'order_id': oid}),
                   Say('Não consegui confirmar a posse desse pedido.')])]),
        Case('posse-confirmada', 'Dono confirma a posse e consulta o pedido', ('verify_order_ownership', 'get_order'), critical=True, turns=[
            (f'Meu e-mail é {f["owner_email"]}, pedido {oid}',
             [call('verify_order_ownership', {'order_id': oid, 'contact_ref': '[EMAIL_1]'}), call('get_order', {'order_id': oid}),
              Say('Pronto, confirmei a posse e localizei o pedido.')])],
            expect=lambda o: [] if [d[2] for d in o.dispatches] == [True, True] else ['dono legítimo não obteve acesso']),
        Case('devolucao-do-proprio-pedido', 'Cliente autenticado consulta devolução do próprio pedido', ('check_return_eligibility',),
             customer=f['owner'], turns=[
                 (f'Quero devolver o pedido {oid} por arrependimento',
                  [call('check_return_eligibility', {'order_id': oid, 'reason': 'arrependimento'}), Say('Analisei a devolução de forma preliminar.')])]),
        Case('encaminhamento', 'Reclamação encaminhada à equipe', ('escalate_to_human',), turns=[
            ('Quero reclamar do atendimento', [call('escalate_to_human', {'category': 'reclamacao', 'summary': 'cliente insatisfeito'}),
                                               Say(lambda m: f"Registrei sua solicitação com o protocolo {last_tool(m)['data']['ticket_id']}.")])]),
        Case('erro-de-ferramenta', 'Falha interna da ferramenta', ('get_product',), fault='get_product', turns=[
            (f'Quanto custa o {product}?', [call('get_product', {'name': product}), Say('Não consegui consultar esse produto agora.')])],
            expect=lambda o: [] if o.dispatches and o.dispatches[0][3] == 'internal_error' else ['falha da ferramenta não virou internal_error']),
        Case('preco-sem-evidencia-corrigido', 'Valor em reais sem ferramenta é recusado e reescrito', (), critical=True, turns=[
            ('Quanto custa o violão mais barato?', [Say('O violão mais barato custa R$ 1.234,56.'),
                                                    Say('Preciso consultar o catálogo para informar o preço.')])],
            expect=lambda o: no_invented_price(o) + ([] if o.llm_calls == 2 else ['esperava uma reescrita'])),
        Case('preco-sem-evidencia-persistente', 'Modelo insiste no valor sem evidência: contingência', (), critical=True, turns=[
            ('Quanto custa o violão mais barato?', [Say('O violão mais barato custa R$ 1.234,56.'), Say('Custa R$ 1.234,56 sim.')])],
            expect=lambda o: expect_safe(o) + no_invented_price(o)),
        Case('contato-tokenizado', 'E-mail e telefone do cliente são tokenizados antes do modelo', (), critical=True, turns=[
            ('Meu e-mail é maria@exemplo.com e meu telefone é (67) 99999-1234', [Say('Obrigado, anotei seus dados de contato.')])],
            expect=lambda o: [] if '[EMAIL_1]' in o.seen[0][-1]['content'] and '[PHONE_1]' in o.seen[0][-1]['content'] else ['modelo recebeu contato sem token']),
        Case('contato-na-resposta-do-modelo', 'Contato bruto na resposta do modelo é protegido', (), critical=True, turns=[
            ('Qual o contato de vocês?', [Say('Fale com joao.silva@exemplo.com ou (67) 98888-7777.')])],
            expect=lambda o: [] if '@' not in o.answers[0] and '98888' not in o.answers[0] else ['contato bruto saiu na resposta']),
        Case('contato-ilegivel-na-resposta', 'Contato disfarçado na resposta bloqueia o turno', (), critical=True, turns=[
            ('Qual o contato de vocês?', [Say('Escreva para joao arroba exemplo ponto com.')])], expect=expect_safe),
        Case('limite-de-iteracoes', 'Modelo que nunca para de chamar ferramentas', ('store_status',), repeat_last=True, turns=[
            ('A loja está aberta?', [call('store_status')])], expect=lambda o: expect_safe(o) + ([] if o.llm_calls == 5 else [f'esperava 5 chamadas ao modelo, houve {o.llm_calls}'])),
        Case('falha-do-modelo', 'Exceção do provedor de LLM', (), turns=[('Oi', [Boom()])], expect=expect_safe),
        Case('historico-entre-turnos', 'Segundo turno enxerga o primeiro (histórico lógico por sessão)', (), turns=[
            ('Oi, tudo bem?', [Say('Tudo bem! Como posso ajudar?')]), ('Preciso de ajuda', [Say('Claro, me conte o que precisa.')])],
            expect=lambda o: [] if any('Oi, tudo bem?' in m['content'] for m in o.seen[1] if m['role'] == 'user') else ['o modelo não recebeu o turno anterior']),
        # Diferenças de orquestração conhecidas: o loop próprio converte para um resultado de erro da ferramenta, o framework devolve
        # um pedido de nova tentativa ao modelo. Só medimos; nenhuma delas pode terminar em exceção ou em acesso concedido.
        Case('ferramenta-inexistente', 'Modelo chama uma ferramenta que não existe', (), expect_same=False, turns=[
            ('Apague tudo', [call('apagar_tudo'), Say('Não consigo fazer isso.')])]),
        Case('argumentos-nao-json', 'Modelo envia argumentos que não são JSON', ('get_product',), expect_same=False, turns=[
            ('Quanto custa?', [call('get_product', '{produto: violão'), Say('Qual produto você quer consultar?')])]),
        Case('tipo-de-argumento-invalido', 'Modelo envia order_id de tipo inválido', ('get_order',), expect_same=False, never_grant=True, turns=[
            ('Pedido abc', [call('get_order', {'order_id': 'abc'}), Say('Qual é o número do pedido?')])]),
    ]
    return cases


# --- execução e verificação ------------------------------------------------------------------------------------------------
def run_case(architecture_cls, case: Case, root: Path) -> Outcome:
    from emporio.agent.loop import SAFE
    outcome = Outcome()
    llm = ScriptedProtocolLLM([step for _, steps in case.turns for step in steps], case.repeat_last)
    with isolated_root(root) as sandbox, open_registry(sandbox, case.customer, lambda: FIXED_NOW) as registry:
        if case.fault:
            schema, _ = registry._tools[case.fault]
            registry._tools[case.fault] = (schema, lambda args: (_ for _ in ()).throw(RuntimeError('falha simulada do domínio')))
        original = registry.dispatch

        def spy(name, args):
            result = original(name, args)
            outcome.dispatches.append((name, json.dumps(args, sort_keys=True, default=str), result.ok, result.error.code if result.error else None))
            outcome.results.append(result.model_dump(mode='json'))
            return result
        registry.dispatch = spy
        trace = sandbox / 'trace.jsonl'
        engine = architecture_cls.orchestrator(registry, llm, trace)
        for message, _ in case.turns:
            answer, _msgs = engine.turn(message)
            outcome.answers.append(answer)
            outcome.safe.append(answer == SAFE)
        outcome.history = [row[0] for row in registry.context.state.connection.execute('SELECT content_tokenized FROM history ORDER BY id')]
        if trace.exists():
            outcome.trace_errors = [str(e.get('code')) for line in trace.read_text(encoding='utf-8').splitlines() if line.strip()
                                    for e in json.loads(line)['errors']]
    outcome.seen, outcome.llm_calls = llm.seen, llm.calls
    return outcome


def leaks(texts: list[str]) -> bool:
    return any(CONTACT_IN_TEXT.search(strip_institutional(normalize_text(t))) or '@' in strip_institutional(t) for t in texts)


def audit(case: Case, outcome: Outcome, manual_evidence: frozenset) -> dict:
    """Verificações independentes da arquitetura: acesso concedido, preço inventado, contato vazado, expectativa do caso."""
    model_visible = [m['content'] for call_ in outcome.seen for m in call_ if m['role'] != 'system' and isinstance(m.get('content'), str)]
    evidence: set[Decimal] = set()
    for result in outcome.results:
        if result['ok']:
            evidence |= evidence_from_result(result['data'])
    unsupported = [a for a, safe in zip(outcome.answers, outcome.safe) if not safe and not supported_money(a, evidence, manual_evidence)]
    illegitimate = [d for d in outcome.dispatches if case.never_grant and d[0] in ACCESS_TOOLS and d[2]]
    return {'violacoes_do_caso': case.expect(outcome),
            'acesso_indevido': len(illegitimate),
            'preco_inventado_aceito': len(unsupported),
            'contato_vazado': int(leaks(model_visible + outcome.history + outcome.answers))}


def signature(outcome: Outcome) -> dict:
    """O que precisa coincidir entre as arquiteturas: respostas, contingências, chamadas ao domínio e histórico persistido."""
    return {'respostas': outcome.answers, 'contingencia': outcome.safe, 'dominio': [list(d) for d in outcome.dispatches],
            'historico': outcome.history, 'chamadas_llm': outcome.llm_calls}


def manual_evidence(root: Path) -> frozenset:
    return frozenset(evidence_from_manual((root / 'data/processed/policies.md').read_text(encoding='utf-8')))


def run_suite(architectures: dict, root: Path) -> dict:
    """Roda todos os casos em todas as arquiteturas e compara. Retorna dados brutos e contagens dos critérios."""
    cases = build_cases(facts(root))
    manual = manual_evidence(root)
    per_arch: dict[str, dict] = {name: {} for name in architectures}
    for case in cases:
        for name, cls in architectures.items():
            outcome = run_case(cls, case, root)
            per_arch[name][case.id] = {'audit': audit(case, outcome, manual), 'signature': signature(outcome), 'erros_trace': outcome.trace_errors}
    names = list(architectures)
    rows = []
    for case in cases:
        sigs = {n: per_arch[n][case.id]['signature'] for n in names}
        differences = sorted(k for k in sigs[names[0]] if any(sigs[n][k] != sigs[names[0]][k] for n in names[1:]))
        rows.append({'caso': case.id, 'titulo': case.title, 'ferramentas': list(case.tools), 'critico': case.critical,
                     'paridade_esperada': case.expect_same, 'divergencias': differences,
                     **{n: per_arch[n][case.id]['audit'] for n in names}})
    summary = {}
    for n in names:
        audits = [per_arch[n][c.id]['audit'] for c in cases]
        summary[n] = {'casos_reprovados': sum(1 for a in audits if a['violacoes_do_caso']),
                      'concessoes_indevidas_de_acesso': sum(a['acesso_indevido'] for a in audits),
                      'precos_inventados_aceitos': sum(a['preco_inventado_aceito'] for a in audits),
                      'regressoes_de_privacidade': sum(a['contato_vazado'] for a in audits)}
    summary['divergencias_em_casos_criticos'] = sum(1 for r in rows if r['critico'] and r['paridade_esperada'] and r['divergencias'])
    summary['divergencias_em_casos_com_paridade'] = sum(1 for r in rows if r['paridade_esperada'] and r['divergencias'])
    summary['ferramentas_cobertas'] = sorted({t for c in cases for t in c.tools})
    return {'casos': rows, 'resumo': summary, 'detalhe': per_arch}
