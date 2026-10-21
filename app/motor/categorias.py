"""Etapa 3 — categorização por regras (RF-23).

Regra é determinística e explicável: casou o padrão, a categoria é aquela,
e a trilha de auditoria registra qual regra decidiu (RNF-08). A IA entra
só depois, para o que nenhuma regra cobriu, e **sempre** como sugestão
(RF-24) — por isso o módulo de IA não decide status, apenas propõe.

Prioridade: **menor número é avaliado primeiro**. A primeira regra que
casar vence, então `prioridade=10` ganha de `prioridade=100`.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

from app.normalizacao.modelos import TIPO_REGRA, Conciliacao, Lancamento

CONFIANCA_REGRA = Decimal("0.90")

#: Teto da sugestão por IA: fica sempre abaixo de CONFIANCA_MINIMA, ou seja,
#: toda sugestão passa pela fila de pendências (SPEC seção 7, etapa 4).
CONFIANCA_MAX_IA = Decimal("0.60")


@dataclass
class Regra:
    """Padrão → categoria. `padrao` é regex, sem distinguir acento ou caixa."""

    padrao: str
    categoria: str
    campo: str = "descricao"        # descricao | contraparte | ambos
    prioridade: int = 100

    def __post_init__(self) -> None:
        self._regex = re.compile(_sem_acento(self.padrao), re.IGNORECASE)

    def casa(self, lancamento: Lancamento) -> bool:
        if self.campo == "contraparte":
            alvo = lancamento.contraparte
        elif self.campo == "ambos":
            alvo = f"{lancamento.descricao} {lancamento.contraparte}"
        else:
            alvo = lancamento.descricao
        return bool(self._regex.search(_sem_acento(alvo)))


def _sem_acento(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c))


#: Primeiro conjunto, tirado do histórico descrito no ROADMAP (Anexo A).
#: Cada correção manual do usuário deve virar uma regra nova aqui (RF-25).
REGRAS_INICIAIS: list[Regra] = [
    Regra(r"\buber\b|\b99\s*pop\b|cabify", "Transporte", "ambos", 10),
    Regra(r"\bcptm\b|\bmetro\b|bilhete unico|estacionamento", "Transporte", "ambos", 10),
    Regra(r"rendimento|aplicacao automatica|cdb|porquinho", "Receita Financeira", "ambos", 20),
    Regra(r"\bdas\b|\bdare\b|\bdarf\b|simples nacional", "Impostos", "ambos", 20),
    Regra(r"tarifa|taxa de|comissao|comissão", "Taxas de Marketplace", "ambos", 30),
    Regra(r"frete|correios|envio|logistica|logística", "Frete/Envios", "ambos", 30),
    Regra(r"estorno|devolucao|devolução|chargeback", "Devoluções/Estornos", "ambos", 30),
    Regra(r"pix recebido", "Vendas Parceiros (Pix)", "descricao", 50),
]


def aplicar(
    lancamentos: list[Lancamento],
    regras: list[Regra] | None = None,
) -> tuple[list[Conciliacao], list[Lancamento]]:
    """Categoriza os lançamentos ainda pendentes.

    Devolve (decisões, sem_categoria). Categorizar não concilia: o
    lançamento ganha categoria e continua `pendente` até alguém confirmar
    ou até a etapa 2 casá-lo com um repasse. Categoria errada em lote é
    pior do que categoria vazia.
    """
    regras = sorted(regras if regras is not None else REGRAS_INICIAIS,
                    key=lambda r: r.prioridade)
    decisoes: list[Conciliacao] = []
    sem_categoria: list[Lancamento] = []

    for lancamento in lancamentos:
        if not lancamento.pendente or lancamento.categoria:
            continue
        regra = next((r for r in regras if r.casa(lancamento)), None)
        if regra is None:
            sem_categoria.append(lancamento)
            continue
        lancamento.categoria = regra.categoria
        decisoes.append(Conciliacao(
            tipo=TIPO_REGRA, confianca=CONFIANCA_REGRA, lancamento=lancamento,
            observacao=f"regra /{regra.padrao}/ → {regra.categoria}",
        ))

    return decisoes, sem_categoria
