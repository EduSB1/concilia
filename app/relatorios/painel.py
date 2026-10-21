"""Painel em texto: o que o motor fez, o que ficou e o que preocupa.

Versão de terminal do RF-50. A tela (Streamlit) vem depois; o formato de
texto já serve para rodar sobre o dataset de teste e medir a taxa de
conciliação automática a cada ajuste do motor.
"""

from __future__ import annotations

from app.dinheiro import brl
from app.motor.motor import Resultado
from app.normalizacao.modelos import Lancamento, Repasse

META_AUTOMATICA = 85     # % (SPEC seção 11)


def _descrever(item) -> str:
    if isinstance(item, Lancamento):
        return (f"{item.data} · {item.conta} · {brl(item.valor)} · "
                f"{item.descricao or '(sem descrição)'}")
    if isinstance(item, Repasse):
        return (f"{item.data_prevista} · repasse {item.marketplace} · "
                f"{brl(item.valor_liquido)}")
    return str(item)


def painel(resultado: Resultado) -> str:
    linhas: list[str] = []
    add = linhas.append

    add("=" * 68)
    add("PAINEL DE CONCILIAÇÃO")
    add("=" * 68)

    total = resultado.total_lancamentos
    conciliados = len(resultado.conciliados)
    taxa = resultado.taxa_automatica
    marca = "ok" if taxa >= META_AUTOMATICA else f"abaixo da meta de {META_AUTOMATICA}%"
    add(f"Lançamentos: {total} · conciliados sozinhos: {conciliados} ({taxa}% — {marca})")
    add(f"Pendências: {len(resultado.pendencias)} · alertas: {len(resultado.alertas)}")

    if resultado.alertas:
        add("")
        add("ALERTAS")
        add("-" * 68)
        for alerta in resultado.alertas:
            add(f"  [{alerta.tipo}] {alerta.mensagem}")

    add("")
    add("CONCILIADO")
    add("-" * 68)
    automaticas = [c for c in resultado.conciliacoes if c.automatica]
    if not automaticas:
        add("  (nada)")
    for c in automaticas:
        detalhe = c.observacao or ""
        alvo = c.lancamento or (c.lancamentos[0] if c.lancamentos else None)
        add(f"  {c.tipo:<22} conf. {c.confianca}  {_descrever(alvo)}")
        if detalhe:
            add(f"  {'':<22} ↳ {detalhe}")

    add("")
    add("FILA DE PENDÊNCIAS")
    add("-" * 68)
    if not resultado.pendencias:
        add("  (vazia)")
    for p in resultado.pendencias:
        add(f"  {_descrever(p.item)}")
        add(f"      motivo: {p.motivo}")
        for candidato in p.candidatos:
            add(f"      candidato: {_descrever(candidato)}")

    add("")
    return "\n".join(linhas)
