"""Etapa 2 — repasse do marketplace × crédito no banco (RF-21).

É a pergunta que o vendedor faz todo dia: "o que a Shopee disse que ia
pagar caiu mesmo, com o valor certo?". A ordem das tentativas vai da mais
segura para a mais frouxa, e cada uma tem sua confiança (SPEC seção 7):

    2a. exato      — um crédito igual ao líquido, na janela       0,95
    2b. agrupado   — N repasses somam um crédito (ou o inverso)   0,80
    2c. tolerância — diferença de até R$ 0,05 (arredondamento)    0,70 + sinal

O que não casar continua `aguardando`; passado o prazo, vira alerta de
repasse não recebido (RF-30).
"""

from __future__ import annotations

import unicodedata
from datetime import date
from decimal import Decimal
from itertools import combinations

from app.datas import janela_dias_uteis, soma_dias_uteis
from app.dinheiro import TOLERANCIA_CENTAVOS
from app.normalizacao.modelos import (
    REPASSE_DIVERGENTE, REPASSE_RECEBIDO, STATUS_CONCILIADO, TIPO_REPASSE,
    Conciliacao, Lancamento, Repasse,
)

CONFIANCA_EXATO = Decimal("0.95")
CONFIANCA_AGRUPADO = Decimal("0.80")
CONFIANCA_TOLERANCIA = Decimal("0.70")

#: Dias úteis de folga em torno da data prevista (SPEC 7, etapa 2a).
JANELA_DIAS_UTEIS = 2

#: Dias úteis após a data prevista antes de alertar "não recebido" (RF-30).
PRAZO_ALERTA_DIAS_UTEIS = 3

#: Teto do match agrupado. Testar todas as combinações é exponencial; acima
#: destes limites o motor não tenta e **avisa** — silêncio aqui viraria
#: "não achei" quando na verdade foi "não procurei".
MAX_ITENS_AGRUPADO = 4
MAX_CANDIDATOS_AGRUPADO = 12

PALAVRAS_MARKETPLACE = {
    "mercado_livre": ("mercado livre", "mercadolivre", "mercado pago", "mercadopago", "meli"),
    "mercado_pago": ("mercado pago", "mercadopago", "mercado livre", "mercadolivre"),
    "shopee": ("shopee",),
    "tiktok": ("tiktok", "tik tok", "bytedance"),
}


def _sem_acento(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def descricao_compativel(lancamento: Lancamento, marketplace: str) -> bool:
    """O texto do crédito aponta para esse marketplace?

    Marketplace desconhecido não bloqueia o match: cai no nome do próprio
    marketplace como palavra-chave. Melhor casar por valor e data do que
    descartar porque ninguém cadastrou o apelido do repasse ainda.
    """
    palavras = PALAVRAS_MARKETPLACE.get(marketplace, (marketplace.replace("_", " "),))
    texto = _sem_acento(f"{lancamento.descricao} {lancamento.contraparte}")
    return any(_sem_acento(p) in texto for p in palavras)


def _na_janela(repasse: Repasse, lancamento: Lancamento) -> bool:
    inicio, fim = janela_dias_uteis(repasse.data_prevista, JANELA_DIAS_UTEIS)
    return inicio <= lancamento.data <= fim


def _candidatos(repasse: Repasse, creditos: list[Lancamento]) -> list[Lancamento]:
    return [
        c for c in creditos
        if c.pendente and _na_janela(repasse, c) and descricao_compativel(c, repasse.marketplace)
    ]


#: Nome de exibição → vira a categoria "Receita <marketplace>" (SPEC seção 9).
NOME_MARKETPLACE = {
    "mercado_livre": "Mercado Livre",
    "mercado_pago": "Mercado Pago",
    "shopee": "Shopee",
    "tiktok": "TikTok Shop",
}


def categoria_receita(marketplace: str) -> str:
    return f"Receita {NOME_MARKETPLACE.get(marketplace, marketplace.replace('_', ' ').title())}"


def _fechar(conciliacao: Conciliacao) -> None:
    """Marca as duas pontas quando a confiança dispensa revisão humana."""
    if not conciliacao.automatica:
        return
    envolvidos = conciliacao.repasses or ([conciliacao.repasse] if conciliacao.repasse else [])
    categoria = categoria_receita(envolvidos[0].marketplace) if envolvidos else ""
    for lancamento in conciliacao.lancamentos or ([conciliacao.lancamento] if conciliacao.lancamento else []):
        lancamento.status = STATUS_CONCILIADO
        lancamento.confianca = conciliacao.confianca
        if not lancamento.categoria:
            lancamento.categoria = categoria
    for repasse in envolvidos:
        repasse.status = REPASSE_RECEBIDO


def casar(
    repasses: list[Repasse],
    lancamentos: list[Lancamento],
    hoje: date | None = None,
) -> tuple[list[Conciliacao], list[tuple[Repasse, list[Lancamento]]], list[Repasse], list[str]]:
    """Casa repasses com créditos bancários.

    Devolve (conciliações, ambíguos, não_recebidos, avisos).
    """
    creditos = [l for l in lancamentos if l.pendente and l.e_entrada]
    pendentes = [r for r in repasses if r.aguardando]
    feitas: list[Conciliacao] = []
    ambiguos: list[tuple[Repasse, list[Lancamento]]] = []
    avisos: list[str] = []

    # --- 2a. match exato ---------------------------------------------------
    for repasse in pendentes:
        if not repasse.aguardando:
            continue
        candidatos = [c for c in _candidatos(repasse, creditos) if c.valor == repasse.valor_liquido]
        if not candidatos:
            continue
        if len(candidatos) > 1:
            ambiguos.append((repasse, candidatos))
            continue
        conciliacao = Conciliacao(
            tipo=TIPO_REPASSE, confianca=CONFIANCA_EXATO,
            lancamento=candidatos[0], repasse=repasse,
        )
        _fechar(conciliacao)
        feitas.append(conciliacao)

    # --- 2b. match agrupado (N repasses → 1 crédito) -----------------------
    restantes = [r for r in pendentes if r.aguardando]
    for credito in [c for c in creditos if c.pendente]:
        grupo = [
            r for r in restantes
            if r.aguardando and _na_janela(r, credito)
            and descricao_compativel(credito, r.marketplace)
        ]
        if len(grupo) < 2:
            continue
        if len(grupo) > MAX_CANDIDATOS_AGRUPADO:
            avisos.append(
                f"crédito de {credito.data} tem {len(grupo)} repasses candidatos "
                f"(teto {MAX_CANDIDATOS_AGRUPADO}) — match agrupado não tentado, "
                "item vai para pendências"
            )
            continue
        achado = None
        for tamanho in range(2, min(MAX_ITENS_AGRUPADO, len(grupo)) + 1):
            for combinacao in combinations(grupo, tamanho):
                if sum((r.valor_liquido for r in combinacao), Decimal("0")) == credito.valor:
                    achado = combinacao
                    break
            if achado:
                break
        if achado:
            conciliacao = Conciliacao(
                tipo=TIPO_REPASSE, confianca=CONFIANCA_AGRUPADO,
                lancamento=credito, repasses=list(achado),
                observacao=f"{len(achado)} repasses somam este crédito",
            )
            _fechar(conciliacao)
            feitas.append(conciliacao)

    # --- 2b'. match agrupado invertido (1 repasse → N créditos) ------------
    for repasse in [r for r in restantes if r.aguardando]:
        grupo = [c for c in _candidatos(repasse, creditos) if c.pendente]
        if len(grupo) < 2:
            continue
        if len(grupo) > MAX_CANDIDATOS_AGRUPADO:
            avisos.append(
                f"repasse {repasse.id_externo or repasse.marketplace} tem {len(grupo)} "
                f"créditos candidatos (teto {MAX_CANDIDATOS_AGRUPADO}) — "
                "match fracionado não tentado"
            )
            continue
        achado = None
        for tamanho in range(2, min(MAX_ITENS_AGRUPADO, len(grupo)) + 1):
            for combinacao in combinations(grupo, tamanho):
                if sum((c.valor for c in combinacao), Decimal("0")) == repasse.valor_liquido:
                    achado = combinacao
                    break
            if achado:
                break
        if achado:
            conciliacao = Conciliacao(
                tipo=TIPO_REPASSE, confianca=CONFIANCA_AGRUPADO,
                repasse=repasse, lancamentos=list(achado),
                observacao=f"repasse fracionado em {len(achado)} créditos",
            )
            _fechar(conciliacao)
            feitas.append(conciliacao)

    # --- 2c. tolerância de centavos ---------------------------------------
    for repasse in [r for r in restantes if r.aguardando]:
        candidatos = [
            c for c in _candidatos(repasse, creditos)
            if abs(c.valor - repasse.valor_liquido) <= TOLERANCIA_CENTAVOS
        ]
        if len(candidatos) != 1:
            continue
        credito = candidatos[0]
        diferenca = credito.valor - repasse.valor_liquido
        repasse.status = REPASSE_DIVERGENTE
        feitas.append(Conciliacao(
            tipo=TIPO_REPASSE, confianca=CONFIANCA_TOLERANCIA,
            lancamento=credito, repasse=repasse,
            observacao=f"diferença de {diferenca} — conferir antes de aceitar",
        ))

    # --- RF-30: repasse que passou do prazo e não caiu ---------------------
    referencia = hoje or date.today()
    nao_recebidos = [
        r for r in repasses
        if r.aguardando
        and soma_dias_uteis(r.data_prevista, PRAZO_ALERTA_DIAS_UTEIS) < referencia
    ]

    return feitas, ambiguos, nao_recebidos, avisos
