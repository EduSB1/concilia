"""Etapa 1 — transferências internas (RF-20).

Dinheiro que anda entre contas do mesmo dono não é receita nem despesa.
Se passar batido, o fluxo de caixa conta a mesma venda duas vezes: uma
quando o Mercado Pago libera e outra quando o valor chega ao Inter.

Critério (SPEC seção 7): saída na conta A e entrada na conta B, mesmo
valor absoluto, no mesmo dia ou no dia seguinte. A descrição é o que
separa a certeza do palpite — ver CONFIANCA_* abaixo.
"""

from __future__ import annotations

import unicodedata
from datetime import timedelta
from decimal import Decimal

from app.normalizacao.modelos import (
    STATUS_CONCILIADO, TIPO_TRANSFERENCIA, Conciliacao, Lancamento,
)

#: Valor e data batem E o texto diz que é transferência/saque/resgate.
CONFIANCA_COM_TEXTO = Decimal("0.95")

#: Valor e data batem, mas nada no texto confirma. Vai para pendências:
#: duas contas do mesmo dono movimentando o mesmo valor no mesmo dia pode
#: ser coincidência (dois repasses iguais, por exemplo).
CONFIANCA_SEM_TEXTO = Decimal("0.75")

TERMOS = (
    "transferencia", "transferência", "ted", "doc", "pix enviado",
    "saque", "resgate", "aplicacao", "aplicação", "retirada",
    "withdrawal", "transfer", "envio para conta", "entre contas",
)


def _sem_acento(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def parece_transferencia(*textos: str) -> bool:
    """Alguma das pontas diz, em palavras, que é movimento entre contas?"""
    junto = _sem_acento(" ".join(t for t in textos if t))
    return any(_sem_acento(termo) in junto for termo in TERMOS)


def _candidatas(saida: Lancamento, entradas: list[Lancamento]) -> list[Lancamento]:
    alvo = -saida.valor                      # saída é negativa; entrada, positiva
    limite = saida.data + timedelta(days=1)  # D0 ou D+1
    return [
        e for e in entradas
        if e.pendente
        and e.conta != saida.conta
        and e.valor == alvo
        and saida.data <= e.data <= limite
    ]


def detectar(lancamentos: list[Lancamento]) -> tuple[list[Conciliacao], list[tuple[Lancamento, list[Lancamento]]]]:
    """Casa saídas com entradas do mesmo dono.

    Devolve (conciliações, ambíguas). Uma saída com mais de um candidato
    não é adivinhada: vira item de pendência com os candidatos junto, para
    a pessoa escolher (RF-51).
    """
    entradas = [l for l in lancamentos if l.pendente and l.e_entrada]
    saidas = [l for l in lancamentos if l.pendente and l.e_saida]
    saidas.sort(key=lambda l: (l.data, l.id_externo))

    feitas: list[Conciliacao] = []
    ambiguas: list[tuple[Lancamento, list[Lancamento]]] = []

    for saida in saidas:
        if not saida.pendente:
            continue
        candidatas = _candidatas(saida, entradas)
        if not candidatas:
            continue
        if len(candidatas) > 1:
            ambiguas.append((saida, candidatas))
            continue
        entrada = candidatas[0]
        com_texto = parece_transferencia(
            saida.descricao, saida.contraparte, entrada.descricao, entrada.contraparte
        )
        confianca = CONFIANCA_COM_TEXTO if com_texto else CONFIANCA_SEM_TEXTO
        conciliacao = Conciliacao(
            tipo=TIPO_TRANSFERENCIA,
            confianca=confianca,
            lancamento=saida,
            par_lancamento=entrada,
            observacao="" if com_texto else
                       "valor e data batem, mas nada na descrição confirma a transferência",
        )
        if conciliacao.automatica:
            for ponta in (saida, entrada):
                ponta.status = STATUS_CONCILIADO
                ponta.categoria = "Transferência Interna"
                ponta.confianca = confianca
        feitas.append(conciliacao)

    return feitas, ambiguas
