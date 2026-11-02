"""Cofre por sessão, exclusivamente em memória; sem autenticação real."""
import re
import unicodedata

EMAIL = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')

# Telefone brasileiro: prefixo 55 opcional, DDD válido (lista da Anatel), e 8 ou 9 dígitos no agrupamento usual
# (celular 9xxxx-xxxx; fixo xxxx-xxxx). Qualquer separador comum entre os grupos (espaço . - _ : / , ; |), no máximo 3.
# Datas (20/03/2026 10:00), CEP (79202-333), valores (R$ 2.199,00), pedidos e rastreio não têm esse formato.
_SEP = r'[\s._:/,;|\-]{0,3}'
_DDD = r'(?:1[1-9]|2[12478]|3[1-578]|4[1-9]|5[1345]|6[1-9]|7[134579]|8[1-9]|9[1-9])'
_PHONE_CORE = rf'(?:\+?55{_SEP})?(?:\({_DDD}\)|{_DDD}){_SEP}(?:9\d{{4}}{_SEP}\d{{4}}|[2-9]\d{{3}}{_SEP}\d{{4}})'
PHONE = re.compile(rf'^{_PHONE_CORE}$')
_EMAIL_IN_TEXT = r"[\w.!#$%&'*+/=?^_`{|}~-]+@[\w.-]+\.[^\W\d_]{2,}"
CONTACT_IN_TEXT = re.compile(rf"{_EMAIL_IN_TEXT}|(?<![\w+]){_PHONE_CORE}(?!\w)")
UNICODE_DASHES = re.compile('[\u2010-\u2015\u2212\ufe58\ufe63\uff0d]')
UNICODE_SPACES = re.compile('[\u00a0\u2007\u202f]')

# Contatos institucionais da loja (manual §1.2 e §7): dados públicos, não pessoais (DECISIONS §8).
INSTITUTIONAL = frozenset({
    ('phone', '6733414444'), ('phone', '6733214500'),
    ('email', 'contato@emporiodamusica.com.br'), ('email', 'contato@empóriodamusica.com.br'),
})

def normalize_text(text: str) -> str:
    """NFKC, sem caracteres de formatação Unicode (categoria Cf: espaço de largura zero, junções, marcas bidi, hífen
    suave), com dígitos de qualquer alfabeto em ASCII e hífens/espaços especiais comuns."""
    text = unicodedata.normalize('NFKC', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Cf')
    text = ''.join(str(unicodedata.decimal(c)) if c.isdecimal() and not c.isascii() else c for c in text)
    return UNICODE_SPACES.sub(' ', UNICODE_DASHES.sub('-', text))


def is_institutional(value: str) -> bool:
    # Markdown (**negrito**, _itálico_) e pontuação nas bordas não mudam o contato.
    return normalize_contact(value.strip('*_~`<>[]"\' ,;:')) in INSTITUTIONAL

def strip_institutional(text: str) -> str:
    return CONTACT_IN_TEXT.sub(lambda m: ' ' if is_institutional(m.group(0)) else m.group(0), text)

def normalize_contact(value: str) -> tuple[str, str] | None:
    value = value.strip()
    if EMAIL.fullmatch(value):
        return 'email', value.casefold()
    if PHONE.fullmatch(value):
        digits = ''.join(c for c in value if c.isascii() and c.isdigit())
        if len(digits) in (12, 13) and digits.startswith('55'):
            digits = digits[2:]
        if len(digits) in (10, 11):
            return 'phone', digits
    return None

class ContactVault:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._contacts: dict[str, tuple[str, str]] = {}
        self._originals: dict[str, str] = {}

    def add(self, value: str) -> str:
        contact = normalize_contact(value)
        if contact is None:
            raise ValueError('Contato inválido')
        for existing, original in self._originals.items():
            if original == value:
                return existing
        prefix = 'EMAIL' if contact[0] == 'email' else 'PHONE'
        n = sum(1 for x in self._contacts if x.startswith('[' + prefix + '_')) + 1
        token = f'[{prefix}_{n}]'
        self._contacts[token] = contact
        self._originals[token] = value
        return token

    def resolve(self, token: str) -> tuple[str, str] | None:
        return self._contacts.get(token)

    def tokenize(self, text: str) -> str:
        text = normalize_text(text)  # separadores invisíveis, formas compatíveis e hífens especiais não escondem contatos
        def replace(match: re.Match) -> str:
            value = match.group(0)
            if is_institutional(value):
                return value
            return self.add(value) if normalize_contact(value) is not None else value
        return CONTACT_IN_TEXT.sub(replace, text)

    def restore(self, text: str) -> str:
        # Restaure apenas texto de confiança, não conteúdo arbitrário criado pelo LLM.
        return re.sub(r'\[(?:EMAIL|PHONE)_\d+\]', lambda m: self._originals.get(m.group(0), m.group(0)), text)
