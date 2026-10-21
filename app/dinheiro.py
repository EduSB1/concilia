"""Dinheiro em Decimal. Nunca float (RNF-01).

Mesma regra do protótipo (`prototipo/mp_auditoria.py`), com uma diferença
de propósito: ali um valor ilegível vira R$ 0,00 e é registrado num aviso,
porque o objetivo é não interromper a leitura de um relatório inteiro.
Aqui o valor ilegível **levanta exceção** — quem chama (o normalizador)
decide se descarta a linha ou a manda para pendências. Valor que some em
silêncio é o bug que este projeto existe para evitar.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

ZERO = Decimal("0")
CENTAVO = Decimal("0.01")

#: Diferença aceita como arredondamento no match de repasse (SPEC 7, etapa 2c).
TOLERANCIA_CENTAVOS = Decimal("0.05")


class ValorIlegivel(ValueError):
    """O campo veio preenchido, mas não dá para lê-lo como dinheiro."""


def dinheiro(valor, origem: str = "") -> Decimal:
    """Converte '1.234,56', '1234.56', '(99,90)', 1234.56 ou None em Decimal.

    Campo vazio é zero de verdade. Campo preenchido e ilegível levanta
    ValorIlegivel — não existe "zero por desencargo".
    """
    if valor is None or valor == "":
        return ZERO
    if isinstance(valor, (int, Decimal)):
        return Decimal(valor)
    if isinstance(valor, float):
        # float chega de JSON de API; converter pela representação textual
        # evita o 0,1 + 0,2 = 0,30000000000000004.
        return Decimal(str(valor))
    texto = str(valor).strip().replace("R$", "").replace(" ", "")
    if not texto:
        return ZERO
    negativo = texto.startswith("(") and texto.endswith(")")   # (1.234,56) = negativo
    if negativo:
        texto = texto[1:-1]
    if "," in texto and "." in texto:          # 1.234,56
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:                         # 1234,56
        texto = texto.replace(",", ".")
    try:
        convertido = Decimal(texto)
    except InvalidOperation as erro:
        raise ValorIlegivel(f"valor ilegível {valor!r}{origem}") from erro
    return -convertido if negativo else convertido


def centavos(valor: Decimal) -> Decimal:
    """Arredonda para 2 casas, como o NUMERIC(14,2) do banco."""
    return valor.quantize(CENTAVO)


def brl(valor: Decimal) -> str:
    """Formata Decimal como R$ 1.234,56."""
    sinal = "-" if valor < 0 else ""
    inteiro, _, cent = f"{abs(valor):.2f}".partition(".")
    inteiro = f"{int(inteiro):,}".replace(",", ".")
    return f"{sinal}R$ {inteiro},{cent}"
