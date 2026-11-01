"""Projeção experimental para revisão offline; não é gate de produção."""
import hashlib
import json
import re
from pathlib import Path

from emporio.agent.prompt import INSTRUCTIONS

MANUAL_SHA256 = '1e822acb3e0f80d2455eddcad66dfe57a77aa3bef88e6cab71dd140a87606d79'
INSTRUCTIONS_SHA256 = 'e570e146409c671228ab05369503dad4260e43d8724778030ae12748fd6a674b'
CONTACT_LINE = 'Contato oficial: (67) 3341-4444 e contato@emporiodamusica.com.br; divergências no manual não alteram esse contato.'
REPLACEMENTS = {
    '(67) 3341-4444': ('[CONTATO INSTITUCIONAL NÃO VERIFICADO]', 2),
    '(67) 3321-4500': ('[CONTATO INSTITUCIONAL NÃO VERIFICADO]', 1),
    'contato@emporiodamusica.com.br': ('[CONTATO INSTITUCIONAL NÃO VERIFICADO]', 1),
    'contato@empóriodamusica.com.br': ('[CONTATO INSTITUCIONAL NÃO VERIFICADO]', 1),
    'Rua 14 de Maio, 3200 — Centro, Campo Grande - MS, 79202-333': ('[ENDEREÇO INSTITUCIONAL NÃO VERIFICADO]', 1),
    'Rua 14 de Maio, 3200 — Centro': ('[ENDEREÇO INSTITUCIONAL NÃO VERIFICADO]', 1),
    '79202-333': ('[CEP INSTITUCIONAL NÃO VERIFICADO]', 1),
}


class ProjectionError(ValueError):
    pass


def candidate_prompt(path: Path) -> str:
    raw = path.read_bytes()
    # Versão fechada: qualquer novo contato, mudança de seção ou alteração exige revisão.
    if hashlib.sha256(raw).hexdigest() != MANUAL_SHA256:
        raise ProjectionError('manual_version_unreviewed')
    try:
        manual = raw.decode('utf-8')
    except UnicodeDecodeError:
        raise ProjectionError('manual_invalid') from None
    for section in range(1, 11):
        if not re.search(rf'^\[§{section}(?:\.|\s)', manual, re.MULTILINE):
            raise ProjectionError('manual_section_missing')
    for value, (replacement, count) in REPLACEMENTS.items():
        if manual.count(value) != count:
            raise ProjectionError('manual_contact_mismatch')
        manual = manual.replace(value, replacement)
    if '@' in manual or hashlib.sha256(INSTRUCTIONS.encode()).hexdigest() != INSTRUCTIONS_SHA256 or CONTACT_LINE not in INSTRUCTIONS:
        raise ProjectionError('manual_unprotected')
    instructions = INSTRUCTIONS.replace(CONTACT_LINE, 'Contatos institucionais não verificados; confirme com a equipe.')
    return instructions + manual + '\n--- FIM DO MANUAL ---'


# Cada entrada nomeia campos de fontes estruturadas; texto livre nunca é copiado.
TOOLS = {'search_products', 'get_product', 'quote_payment', 'store_status',
         'verify_order_ownership', 'get_order', 'check_return_eligibility', 'escalate_to_human'}
ERRORS = {'invalid_input', 'not_found', 'ambiguous', 'access_denied', 'not_verified', 'locked', 'internal_error'}
ENUMS = {
    'availability': {'available', 'out_of_stock', 'discontinued', 'coming_soon'},
    'status': {'purchasable', 'not_purchasable', 'pending', 'confirmed', 'shipped', 'delivered', 'cancelled',
               'eligible', 'expired', 'not_applicable', 'not_yet_delivered', 'insufficient_information'},
    'region': {'metro', 'other', 'unknown'}, 'search_backend': {'sqlite_filters', 'sqlite_fts5_bm25', 'rapidfuzz'},
}
BOOLS = {'pix_eligible', 'special_quote_required', 'combined_payment_allowed', 'free', 'valid', 'is_open', 'granted', 'approved'}
INTS = {'product_id', 'category_id', 'stock_quantity', 'total_matches', 'quantity', 'n', 'business_days_min', 'business_days_max', 'days_remaining'}
MONEY = {'list_price', 'final_price', 'price', 'pix_price', 'subtotal', 'pix_subtotal', 'total_with_shipping', 'pix_total_with_shipping', 'total_brl', 'fee', 'valor', 'discount_percent'}
NESTED = {'price_info', 'active_promotion', 'shipping'}
ARRAYS = {'products', 'items', 'installments', 'alternatives'}
FIELDS = {
    'search_products': {'products', 'total_matches', 'search_backend'},
    'get_product': {'product_id', 'category_id', 'stock_quantity', 'availability', 'price_info', 'alternatives', 'special_quote_required'},
    'quote_payment': {'items', 'subtotal', 'pix_subtotal', 'total_with_shipping', 'pix_total_with_shipping', 'installments', 'combined_payment_allowed', 'shipping'},
    'store_status': {'is_open'},
    'verify_order_ownership': {'granted'},
    'get_order': {'status', 'total_brl', 'items'},
    'check_return_eligibility': {'status', 'days_remaining', 'approved'},
    'escalate_to_human': set(),
}
# Nested fields are restricted separately by parent, so e.g. item status cannot carry text.
CHILD = {
    'products': {'product_id', 'availability', 'stock_quantity', 'price_info'},
    'items': {'product_id', 'quantity', 'status', 'list_price', 'final_price', 'active_promotion', 'pix_eligible', 'pix_price', 'subtotal', 'pix_subtotal', 'special_quote_required'},
    'alternatives': {'product_id', 'availability', 'price'},
    'installments': {'n', 'valor', 'valid'},
    'price_info': {'list_price', 'final_price', 'active_promotion'},
    'active_promotion': {'discount_percent'},
    'shipping': {'region', 'fee', 'free', 'special_quote_required'},
}


def _project(data, allowed):
    if not isinstance(data, dict):
        raise ProjectionError('tool_result_invalid')
    output = {}
    for key in sorted(allowed & data.keys()):
        value = data[key]
        if value is None:
            output[key] = None
        elif key in ENUMS:
            if isinstance(value, str) and value in ENUMS[key]:
                output[key] = value
        elif key in BOOLS:
            if type(value) is bool:
                output[key] = value
        elif key in INTS:
            if type(value) is int and 0 <= value <= 1000000:
                output[key] = value
        elif key in MONEY:
            # Somente número decimal curto; strings arbitrárias jamais são copiadas.
            if isinstance(value, (str, int)) and not isinstance(value, bool) and re.fullmatch(r'\d{1,9}(?:\.\d{1,2})?', str(value)):
                output[key] = str(value)
        elif key in NESTED and isinstance(value, dict):
            output[key] = _project(value, CHILD[key])
        elif key in ARRAYS and isinstance(value, list) and len(value) <= 100:
            output[key] = [_project(item, CHILD[key]) for item in value]
    return output


def project_tool(name, result):
    if name not in TOOLS or not isinstance(result, dict) or type(result.get('ok')) is not bool:
        raise ProjectionError('tool_result_invalid')
    if not result['ok']:
        error = result.get('error')
        code = error.get('code') if isinstance(error, dict) else None
        return {'ok': False, 'error': {'code': code if code in ERRORS else 'internal_error'}}
    return {'ok': True, 'data': _project(result.get('data'), FIELDS[name])}


def project_messages(messages, trusted_definitions, registry, manual_path):
    """Reconstrói mensagens para análise, descartando texto livre e IDs do canal."""
    if trusted_definitions != registry.definitions():
        raise ProjectionError('schemas_untrusted')
    projected = []
    ids = {}
    call_sequence = 0
    for message in messages:
        if not isinstance(message, dict):
            raise ProjectionError('message_invalid')
        role = message.get('role')
        if role == 'system':
            if projected:
                raise ProjectionError('system_invalid')
            projected.append({'role': 'system', 'content': candidate_prompt(manual_path)})
        elif role in {'user', 'assistant'}:
            item = {'role': role, 'content': '[TEXTO LIVRE OMITIDO]'}
            if role == 'assistant' and 'tool_calls' in message:
                calls = []
                for call in message['tool_calls']:
                    name = call['function']['name']
                    original = call['id']
                    if name not in TOOLS or original in ids:
                        raise ProjectionError('tool_call_invalid')
                    call_sequence += 1
                    call_id = f'call_{call_sequence}'
                    ids[original] = (call_id, name)
                    calls.append({'id': call_id, 'type': 'function', 'function': {'name': name, 'arguments': '{}'}})
                item['tool_calls'] = calls
            projected.append(item)
        elif role == 'tool':
            entry = ids.pop(message.get('tool_call_id'), None)
            if entry is None:
                raise ProjectionError('tool_call_missing')
            try:
                result = json.loads(message['content'])
            except (ValueError, KeyError, TypeError):
                raise ProjectionError('tool_result_invalid') from None
            projected.append({'role': 'tool', 'tool_call_id': entry[0], 'content': json.dumps(project_tool(entry[1], result), ensure_ascii=False)})
        else:
            raise ProjectionError('message_invalid')
    if not projected or projected[0]['role'] != 'system' or ids:
        raise ProjectionError('message_sequence_invalid')
    return projected, trusted_definitions
