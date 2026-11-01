"""Elegibilidade preliminar; não aprova, nem comprova declarações do cliente."""
from datetime import date, timedelta

# Recebimento declarado mais de 14 dias depois da previsão de entrega registrada: sinaliza para a equipe conferir (S-n).
DIVERGENCE_DAYS = 14
EXCLUSIONS = ['personalização ou ajustes sob encomenda', 'promoção com aviso de venda final', 'boquilhas de instrumentos de sopro']

def _late_receipt(order: dict, received_at: date) -> dict | None:
    """Compara a data declarada com a previsão da loja; a previsão nunca vira data de recebimento (A2)."""
    try:
        estimated = date.fromisoformat(order.get('estimated_delivery') or '')
    except ValueError:
        return None
    late = (received_at - estimated).days
    if late <= DIVERGENCE_DAYS:
        return None
    return {'code': 'received_after_estimated_delivery', 'estimated_delivery': estimated.isoformat(),
            'received_at': received_at.isoformat(), 'days_after_estimate': late,
            'note': f'A data de recebimento informada é {late} dias posterior à previsão de entrega registrada; a equipe vai conferir. O pedido não foi negado e a análise segue preliminar.'}


def evaluate_return(order: dict, reason: str, today: date, received_at: date | None, purchase_channel: str | None) -> dict:
    sources = {'order_date': 'registro da loja', 'order_status': 'registro da loja',
               'received_at': 'declaração não verificada' if received_at else 'não informado',
               'purchase_channel': 'declaração não verificada' if purchase_channel else 'não informado'}
    result = {'status': None, 'rule_ref': None, 'deadline': None, 'days_remaining': None,
              'missing_information': [], 'conditions': [], 'exclusions_to_confirm': EXCLUSIONS.copy(),
              'information_sources': sources, 'eligibility': 'preliminar', 'approved': False, 'divergences': []}
    if order['status'] == 'cancelled':
        result.update(status='cancelled', conditions=['Pedido cancelado.'], order_note=order['notes'])
        return result
    if order['status'] in ('pending', 'confirmed', 'shipped'):
        result.update(status='not_yet_delivered', conditions=['A previsão não comprova recebimento.'])
        return result
    purchase = date.fromisoformat(order['order_date'])
    if reason == 'arrependimento':
        result['rule_ref'] = '§4.1'
        if purchase_channel == 'presencial':
            result.update(status='not_applicable', conditions=['Direito de arrependimento informado para compras online; canal declarado não verificado.'])
            return result
        if purchase_channel is None:
            result['missing_information'].append('purchase_channel')
    elif reason == 'defeito':
        result['rule_ref'] = '§4.2'
    else:
        result['rule_ref'] = '§4.3'
    if reason in ('arrependimento', 'preferência'):
        if received_at is None or received_at < purchase or received_at > today:
            result['missing_information'].append('received_at')
        if result['missing_information']:
            result['status'] = 'insufficient_information'
            result['conditions'].append('Informações declaradas não são comprovantes.')
            return result
        start, days = received_at, 7
        divergence = _late_receipt(order, received_at)
        if divergence:
            result['divergences'].append(divergence)
    else:
        start, days = purchase, 30
    elapsed = (today - start).days
    if elapsed < 0:
        result.update(status='insufficient_information', missing_information=['order_date'], conditions=['Data de compra posterior ao relógio informado.'])
        return result
    deadline = start + timedelta(days=days)
    result.update(status='eligible' if today <= deadline else 'expired', deadline=deadline.isoformat(), days_remaining=max(0, (deadline-today).days))
    if reason == 'arrependimento':
        result['conditions'] += ['Compra online e recebimento informados devem ser confirmados.', 'Embalagem original, sem sinais de uso, acessórios e manuais.']
    elif reason == 'preferência':
        result['conditions'] += ['Recebimento informado deve ser confirmado.', 'Sujeito à disponibilidade, perfeito estado e embalagem original.']
    else:
        result['conditions'] += ['Defeito de fabricação e exclusões devem ser verificados.', 'Garantia legal de 90 dias a partir do recebimento deve ser avaliada pela equipe.']
        if result['status'] == 'expired':
            result['conditions'].append('Após 30 dias, procure a garantia do fabricante; a loja pode intermediar.')
    result['conditions'].append('Elegibilidade preliminar; a equipe deve verificar as condições. Nenhuma devolução foi aprovada.')
    return result
