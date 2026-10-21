"""Orquestra as etapas do motor, da mais certa para a mais incerta.

    1. transferências internas   (dinheiro do próprio dono andando)
    2. repasse × crédito         (o marketplace pagou o que prometeu?)
    3. regras de categoria       (o que sobrou, por padrão de texto)
    4. fila de pendências        (o resto, com os candidatos junto)

O motor não grava nada: recebe listas, devolve o que decidiu. Persistir é
trabalho de quem chama — assim dá para rodar o motor inteiro sobre um
dataset de teste sem banco nenhum.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.dinheiro import brl
from app.motor import categorias as etapa_categorias
from app.motor import repasses as etapa_repasses
from app.motor import transferencias as etapa_transferencias
from app.normalizacao.modelos import (
    STATUS_CONCILIADO, Conciliacao, Lancamento, Repasse,
)


@dataclass
class Pendencia:
    """Item que o motor não resolveu sozinho — vai para a tela (RF-51)."""

    item: Lancamento | Repasse
    motivo: str
    candidatos: list = field(default_factory=list)


@dataclass
class Alerta:
    tipo: str                      # repasse_nao_recebido | limite_motor
    mensagem: str
    item: object = None


@dataclass
class Resultado:
    lancamentos: list[Lancamento] = field(default_factory=list)
    conciliacoes: list[Conciliacao] = field(default_factory=list)
    pendencias: list[Pendencia] = field(default_factory=list)
    alertas: list[Alerta] = field(default_factory=list)

    @property
    def total_lancamentos(self) -> int:
        return len(self.lancamentos)

    @property
    def conciliados(self) -> list[Lancamento]:
        return [l for l in self.lancamentos if l.status == STATUS_CONCILIADO]

    @property
    def taxa_automatica(self) -> Decimal:
        """% de lançamentos conciliados sem ajuda humana (meta MVP: >= 85%).

        Conta lançamento, não conciliação: uma transferência interna fecha
        dois lançamentos e um repasse agrupado fecha vários de uma vez.
        """
        if not self.lancamentos:
            return Decimal("0")
        pct = Decimal(len(self.conciliados)) / Decimal(len(self.lancamentos)) * 100
        return pct.quantize(Decimal("0.1"))


def conciliar(
    lancamentos: list[Lancamento],
    repasses: list[Repasse] | None = None,
    regras: list[etapa_categorias.Regra] | None = None,
    hoje: date | None = None,
) -> Resultado:
    repasses = repasses or []
    resultado = Resultado(lancamentos=lancamentos)

    # Etapa 1 — transferências internas
    feitas, ambiguas = etapa_transferencias.detectar(lancamentos)
    resultado.conciliacoes.extend(feitas)
    for conciliacao in feitas:
        if not conciliacao.automatica:
            resultado.pendencias.append(Pendencia(
                item=conciliacao.lancamento,
                motivo=conciliacao.observacao or "transferência interna sem confirmação no texto",
                candidatos=[conciliacao.par_lancamento],
            ))
    for saida, candidatas in ambiguas:
        resultado.pendencias.append(Pendencia(
            item=saida,
            motivo=f"{len(candidatas)} entradas com o mesmo valor na janela — qual é o par?",
            candidatos=candidatas,
        ))

    # Etapa 2 — repasse × crédito bancário
    feitas, ambiguos, nao_recebidos, avisos = etapa_repasses.casar(
        repasses, lancamentos, hoje=hoje
    )
    resultado.conciliacoes.extend(feitas)
    for conciliacao in feitas:
        if not conciliacao.automatica:
            resultado.pendencias.append(Pendencia(
                item=conciliacao.repasse,
                motivo=conciliacao.observacao or "confiança abaixo do mínimo",
                candidatos=[conciliacao.lancamento],
            ))
    for repasse, candidatos in ambiguos:
        resultado.pendencias.append(Pendencia(
            item=repasse,
            motivo=f"{len(candidatos)} créditos possíveis para o mesmo repasse",
            candidatos=candidatos,
        ))
    for repasse in nao_recebidos:
        resultado.alertas.append(Alerta(
            tipo="repasse_nao_recebido",
            mensagem=(f"repasse {repasse.marketplace} de {brl(repasse.valor_liquido)} "
                      f"previsto para {repasse.data_prevista} não caiu em nenhuma conta"),
            item=repasse,
        ))
    for aviso in avisos:
        resultado.alertas.append(Alerta(tipo="limite_motor", mensagem=aviso))

    # Etapa 3 — categorização por regras
    decisoes, sem_categoria = etapa_categorias.aplicar(lancamentos, regras)
    resultado.conciliacoes.extend(decisoes)
    for lancamento in sem_categoria:
        resultado.pendencias.append(Pendencia(
            item=lancamento, motivo="nenhuma regra de categoria casou",
        ))

    return resultado
