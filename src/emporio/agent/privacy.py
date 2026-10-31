"""Barreira conservadora para dados dinâmicos; ainda não habilita provedor externo."""
import re
from emporio.security.contacts import ContactVault

class PrivacyError(ValueError):
    pass

# Um @ residual ou sequência com muitos dígitos pode ser contato em formato não suportado.
SUSPECT_DIGITS = re.compile(r'(?<!\w)(?:\+?\d|\(\d)[\d\s()./\-]{8,}\d(?!\w)')

def protect_dynamic(value, vault: ContactVault):
    if isinstance(value, str):
        sanitized = vault.tokenize(value)
        if '@' in sanitized or re.search(r'\barroba\b', sanitized, re.IGNORECASE) or any(sum(c.isdigit() for c in m.group()) >= 10 for m in SUSPECT_DIGITS.finditer(sanitized)):
            raise PrivacyError('Conteúdo com possível contato não reconhecido')
        return sanitized
    if isinstance(value, list):
        return [protect_dynamic(item, vault) for item in value]
    if isinstance(value, dict):
        return {protect_dynamic(key, vault) if isinstance(key, str) else key: protect_dynamic(item, vault) for key, item in value.items()}
    return value
