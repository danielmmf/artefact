"""Vocabulário e separação entre descrições e consultas de intenção.

A garantia é construída em duas camadas e verificada por teste e em cada execução:
1. fonte: as frases de nível/uso das consultas (LEVEL_QUERY/USE_QUERY) e os sinônimos de tipo não compartilham nenhum radical de conteúdo
   com as frases das descrições (LEVEL_DESC/USE_DESC) nem com o termo do tipo no catálogo;
2. realizado: nenhum radical de conteúdo dessas frases aparece no vocabulário (nomes + descrições) do catálogo efetivamente gerado.
O substantivo que nomeia o instrumento (violão, teclado...) é a única palavra permitida em comum: sem citá-lo, nenhuma consulta é possível.
"""
import re
import unicodedata

from py_rust_stemmers import SnowballStemmer

from emporio_lab.s2 import lexicon as lx

STOPWORDS = frozenset('''a o as os um uma uns umas de do da dos das em no na nos nas por para com sem sob sobre entre e ou mas que se ao aos à às
 é são foi ser ter tem há já não mais muito pouco seu sua seus suas meu minha meus minhas ele ela eles elas nós me te lhe isso isto esse essa este esta
 como quando onde qual quais quem até num numa pelo pela pelos pelas depois também só bem'''.split())
_stemmer = SnowballStemmer('portuguese')
# palavras do domínio impossíveis de evitar (música, instrumento, tocar, cordas) e substantivos de família de instrumento (naming mínimo da consulta)
ALLOWED_STEMS = frozenset({'music', 'instrument', 'toc', 'cord', 'guitarr', 'viola', 'flaut', 'pian', 'tecl'})


def fold(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))


def tokens(text: str) -> list[str]:
    return re.findall(r'[^\W_]+', fold(text))


def content_stems(text: str) -> set[str]:
    return {_stemmer.stem_word(t) for t in tokens(text) if t not in {fold(w) for w in STOPWORDS} and len(t) > 1}


def stems_of(phrases) -> set[str]:
    out: set[str] = set()
    for p in phrases:
        out |= content_stems(p)
    return out


def description_stems() -> set[str]:
    """Radicais de TODO o texto que o gerador pode pôr numa descrição (frases de nível/uso, preço, trechos fixos e ruído)."""
    pools = [p for table in (lx.LEVEL_DESC, lx.USE_DESC, lx.TIER_DESC) for phrases in table.values() for p in phrases]
    pools += [b for blurbs in lx.BLURBS.values() for b in blurbs] + list(lx.NOISE) + list(lx.FINISHES)
    pools += ['série no acabamento categoria']
    return stems_of(pools)


def catalog_stems(products) -> set[str]:
    out: set[str] = set()
    for p in products:
        out |= content_stems(p.name)
        out |= content_stems(p.description)
    return out


def overlap_report() -> dict:
    """Colisões da camada 1 (devem ser vazias)."""
    desc = description_stems()
    bad = {}
    for table, name in ((lx.LEVEL_QUERY, 'nivel'), (lx.USE_QUERY, 'uso')):
        for key, phrases in table.items():
            for p in phrases:
                hit = content_stems(p) & desc - ALLOWED_STEMS
                if hit:
                    bad[f'{name}:{key}:{p}'] = sorted(hit)
    term_stems = {t[0]: content_stems(t[2]) for t in lx.TYPES}
    for t in lx.TYPES:
        hit = content_stems(t[3]) & term_stems[t[0]] - ALLOWED_STEMS
        if hit:
            bad[f'sinonimo:{t[0]}:{t[3]}'] = sorted(hit)
    return bad


def realized_overlap(products) -> dict:
    """Camada 2: radicais das frases de nível/uso das consultas que aparecem no catálogo efetivamente gerado (deve ser vazio)."""
    realized = catalog_stems(products) | description_stems()
    bad = {}
    for table, name in ((lx.LEVEL_QUERY, 'nivel'), (lx.USE_QUERY, 'uso')):
        for key, phrases in table.items():
            for p in phrases:
                hit = content_stems(p) & realized - ALLOWED_STEMS
                if hit:
                    bad[f'{name}:{key}:{p}'] = sorted(hit)
    return bad


def synonym_overlap(products) -> dict:
    """Informativo: fração dos radicais de cada sinônimo de tipo que existe no vocabulário do catálogo (palavras genéricas como 'grave')."""
    realized = catalog_stems(products)
    return {t[0]: round(len(content_stems(t[3]) & realized) / max(1, len(content_stems(t[3]))), 2) for t in lx.TYPES}
