"""Bruto do conector → Lancamento, sem duplicar e sem perder valor.

Entrada: dicionários no contrato do SPEC (seção 6):

    {"conta": "Inter PJ", "data": "2026-10-09", "valor": 3412.80,
     "descricao": "Repasse Shopee", "contraparte": "Shopee",
     "id_externo": "E123...", "fonte": "inter_api"}

Saída: lançamentos normalizados + a lista do que não deu para ler. Nada é
descartado em silêncio — esse é o contrato com quem confere o número.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.datas import data as ler_data
from app.dinheiro import ValorIlegivel, centavos, dinheiro
from app.normalizacao.modelos import Lancamento


@dataclass
class Problema:
    """Linha recusada na normalização, com o motivo e o dado original."""

    motivo: str
    bruto: dict


def normalizar(bruto: dict) -> Lancamento:
    """Converte um registro bruto. Levanta ValueError se faltar o essencial."""
    conta = str(bruto.get("conta") or "").strip()
    if not conta:
        raise ValueError("lançamento sem conta")
    try:
        quando = ler_data(bruto.get("data"))
    except ValueError as erro:
        raise ValueError(f"data inválida: {bruto.get('data')!r}") from erro
    try:
        valor = centavos(dinheiro(bruto.get("valor"), origem=f" na conta {conta}"))
    except ValorIlegivel as erro:
        raise ValueError(str(erro)) from erro
    return Lancamento(
        conta=conta,
        data=quando,
        valor=valor,
        descricao=str(bruto.get("descricao") or "").strip(),
        contraparte=str(bruto.get("contraparte") or "").strip(),
        id_externo=str(bruto.get("id_externo") or "").strip(),
        fonte=str(bruto.get("fonte") or "").strip(),
    )


def normalizar_lote(
    brutos: Iterable[dict],
    ja_importados: Iterable[tuple[str, str]] = (),
) -> tuple[list[Lancamento], list[Lancamento], list[Problema]]:
    """Normaliza um lote inteiro.

    Devolve (novos, duplicados, problemas). `ja_importados` são as chaves
    (conta, id_externo) que o banco já tem — é o que torna a reimportação
    idempotente (RF-12). Registro sem id_externo nunca é tratado como
    duplicado: sem chave não dá para afirmar que é o mesmo movimento.
    """
    vistos = set(ja_importados)
    novos: list[Lancamento] = []
    duplicados: list[Lancamento] = []
    problemas: list[Problema] = []

    for bruto in brutos:
        try:
            lancamento = normalizar(bruto)
        except ValueError as erro:
            problemas.append(Problema(motivo=str(erro), bruto=dict(bruto)))
            continue
        if lancamento.id_externo and lancamento.chave in vistos:
            duplicados.append(lancamento)
            continue
        if lancamento.id_externo:
            vistos.add(lancamento.chave)
        novos.append(lancamento)

    return novos, duplicados, problemas
