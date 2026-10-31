"""Utilitários para motor de conciliação."""

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum


class DiaSemana(Enum):
    """Dias da semana."""
    SEGUNDA = 0
    TERCA = 1
    QUARTA = 2
    QUINTA = 3
    SEXTA = 4
    SABADO = 5
    DOMINGO = 6


def eh_dia_util(d: date) -> bool:
    """Verificar se é dia útil (seg-sex, sem feriados)."""
    # TODO: integrar com banco de feriados
    return d.weekday() < 5  # 0-4 = seg-sex


def contar_dias_uteis(data_inicio: date, data_fim: date) -> int:
    """Contar dias úteis entre duas datas (inclusive)."""
    dias = 0
    d = data_inicio
    while d <= data_fim:
        if eh_dia_util(d):
            dias += 1
        d += timedelta(days=1)
    return dias


def adicionar_dias_uteis(data: date, dias_uteis: int) -> date:
    """Adicionar N dias úteis a uma data."""
    d = data
    contados = 0
    while contados < dias_uteis:
        d += timedelta(days=1)
        if eh_dia_util(d):
            contados += 1
    return d


def normalizar_valor(valor: Decimal, casas: int = 2) -> Decimal:
    """Normalizar valor monetário para N casas decimais (com ROUND_HALF_UP)."""
    return valor.quantize(Decimal(10) ** -casas, rounding=ROUND_HALF_UP)


def valores_compativel(v1: Decimal, v2: Decimal, tolerancia: Decimal = Decimal("0.01")) -> bool:
    """Verificar se dois valores são compatíveis (dentro da tolerância)."""
    return abs(v1 - v2) <= tolerancia
