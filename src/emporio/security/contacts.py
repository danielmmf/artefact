"""Cofre por sessão, exclusivamente em memória; sem autenticação real."""
import re

EMAIL = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
PHONE = re.compile(r'^\+?[\d\s().-]+$')
CONTACT_IN_TEXT = re.compile(r"[\w.!#$%&'*+/=?^_`{|}~-]+@[\w.-]+\.[^\W\d_]{2,}|(?<!\w)(?:\+?\d|\(\d)[\d ().-]{7,}\d(?!\w)")

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
        def replace(match: re.Match) -> str:
            value = match.group(0)
            return self.add(value) if normalize_contact(value) is not None else value
        return CONTACT_IN_TEXT.sub(replace, text)

    def restore(self, text: str) -> str:
        # Restaure apenas texto de confiança, não conteúdo arbitrário criado pelo LLM.
        return re.sub(r'\[(?:EMAIL|PHONE)_\d+\]', lambda m: self._originals.get(m.group(0), m.group(0)), text)
