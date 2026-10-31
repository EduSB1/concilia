"""Datas e janelas de dias úteis.

O motor casa repasse com crédito usando "data prevista ± 2 dias úteis"
(SPEC seção 7). Fim de semana não conta. Feriado bancário ainda conta —
ver TODO abaixo.
"""

from __future__ import annotations

from datetime import date, timedelta

#: TODO: carregar os feriados bancários (Anbima) e descontá-los da janela.
#: Sem isso, um repasse previsto para a véspera de um feriado prolongado
#: pode cair fora da janela e ir parar em pendências sem necessidade.
FERIADOS: frozenset[date] = frozenset()


def data(texto) -> date:
    """Lê date, '2026-10-09', '2026-10-09T10:12:00-03:00' ou '09/10/2026'."""
    if isinstance(texto, date):
        return texto
    t = str(texto or "").strip()
    if not t:
        raise ValueError("data vazia")
    if "/" in t[:10]:                                   # 09/10/2026
        dia, mes, ano = t[:10].split("/")
        return date(int(ano), int(mes), int(dia))
    ano, mes, dia = t[:10].split("-")
    return date(int(ano), int(mes), int(dia))


def e_dia_util(d: date) -> bool:
    return d.weekday() < 5 and d not in FERIADOS


def soma_dias_uteis(d: date, n: int) -> date:
    """Avança (n > 0) ou recua (n < 0) n dias úteis a partir de d."""
    if n == 0:
        return d
    passo = timedelta(days=1 if n > 0 else -1)
    restam = abs(n)
    atual = d
    while restam:
        atual += passo
        if e_dia_util(atual):
            restam -= 1
    return atual


def janela_dias_uteis(d: date, dias: int = 2) -> tuple[date, date]:
    """Intervalo fechado [d − dias úteis, d + dias úteis]."""
    return soma_dias_uteis(d, -dias), soma_dias_uteis(d, dias)
