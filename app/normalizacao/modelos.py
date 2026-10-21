"""Modelos do domínio — espelham as tabelas do SPEC (seção 6).

Regras que valem para todos:
  · dinheiro é sempre Decimal (RNF-01);
  · `valor` de lançamento é positivo na entrada e negativo na saída;
  · `id_externo` é o que garante a idempotência ao reimportar (RF-12).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app.dinheiro import ZERO

# --- status de lançamento (SPEC 6) -----------------------------------------
STATUS_PENDENTE = "pendente"
STATUS_CONCILIADO = "conciliado"
STATUS_IGNORADO = "ignorado"

# --- status de repasse ------------------------------------------------------
REPASSE_AGUARDANDO = "aguardando"
REPASSE_RECEBIDO = "recebido"
REPASSE_DIVERGENTE = "divergente"
REPASSE_RETIDO = "retido"

# --- tipos de conciliação ---------------------------------------------------
TIPO_TRANSFERENCIA = "transferencia_interna"
TIPO_REPASSE = "repasse"
TIPO_REGRA = "regra"
TIPO_MANUAL = "manual"

#: Abaixo disto o item vai para a fila de pendências (RF-26).
CONFIANCA_MINIMA = Decimal("0.80")


@dataclass
class Conta:
    """Banco, carteira de marketplace ou investimento — tudo do mesmo dono."""

    nome: str                      # "Inter PJ", "Mercado Pago", "Carteira Shopee"
    tipo: str = "banco"            # banco | carteira_marketplace | investimento

    def __hash__(self) -> int:
        return hash(self.nome)


@dataclass
class Lancamento:
    """Um movimento de dinheiro numa conta, já normalizado."""

    conta: str
    data: date
    valor: Decimal                 # + entrada / − saída
    descricao: str = ""
    contraparte: str = ""
    id_externo: str = ""
    fonte: str = ""                # inter_api | mercadopago_api | ofx_itau ...
    categoria: str = ""
    status: str = STATUS_PENDENTE
    confianca: Decimal | None = None
    bling_id: str = ""

    @property
    def chave(self) -> tuple[str, str]:
        """Par que o banco usa em UNIQUE (conta_id, id_externo)."""
        return (self.conta, self.id_externo)

    @property
    def e_entrada(self) -> bool:
        return self.valor > ZERO

    @property
    def e_saida(self) -> bool:
        return self.valor < ZERO

    @property
    def pendente(self) -> bool:
        return self.status == STATUS_PENDENTE


@dataclass
class Repasse:
    """O que o marketplace diz que pagou, decomposto (RF-22)."""

    marketplace: str               # mercado_livre | shopee | tiktok
    data_prevista: date
    valor_liquido: Decimal
    valor_bruto: Decimal = ZERO
    taxas: Decimal = ZERO
    frete: Decimal = ZERO
    estornos: Decimal = ZERO
    id_externo: str = ""
    status: str = REPASSE_AGUARDANDO

    @property
    def chave(self) -> tuple[str, str]:
        return (self.marketplace, self.id_externo)

    @property
    def aguardando(self) -> bool:
        return self.status == REPASSE_AGUARDANDO

    def confere(self) -> Decimal:
        """bruto − taxas − frete − estornos − líquido. Zero = decomposição fecha."""
        return self.valor_bruto - self.taxas - self.frete - self.estornos - self.valor_liquido


@dataclass
class Conciliacao:
    """Ligação criada pelo motor ou pelo usuário (trilha de auditoria, RNF-08)."""

    tipo: str
    confianca: Decimal
    lancamento: Lancamento | None = None
    par_lancamento: Lancamento | None = None       # outra ponta da transferência
    repasse: Repasse | None = None
    lancamentos: list[Lancamento] = field(default_factory=list)   # match N:1
    repasses: list[Repasse] = field(default_factory=list)         # match 1:N
    decidido_por: str = "motor"                    # motor | ia | usuario:<id>
    observacao: str = ""

    @property
    def automatica(self) -> bool:
        """Confiança suficiente para não passar pela fila de pendências."""
        return self.confianca >= CONFIANCA_MINIMA
