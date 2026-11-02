"""Barreira conservadora para dados dinâmicos; ainda não habilita provedor externo."""
import re
from emporio.security.contacts import ContactVault, strip_institutional

class PrivacyError(ValueError):
    pass

# Um @ residual (ou "arroba", "[at]") pode ser e-mail em formato não suportado e bloqueia o trecho. Sequências de dígitos
# não reconhecidas como telefone NÃO bloqueiam: passam como estão, para o cliente poder informar datas e horários.

def protect_dynamic(value, vault: ContactVault):
    if isinstance(value, str):
        sanitized = vault.tokenize(value)
        checked = strip_institutional(sanitized)
        if '@' in checked or re.search(r'\barroba\b|\[at\]|\(at\)|\[dot\]|\(dot\)', checked, re.IGNORECASE):
            raise PrivacyError('Conteúdo com possível contato não reconhecido')
        return sanitized
    if isinstance(value, list):
        return [protect_dynamic(item, vault) for item in value]
    if isinstance(value, dict):
        return {protect_dynamic(key, vault) if isinstance(key, str) else key: protect_dynamic(item, vault) for key, item in value.items()}
    return value
