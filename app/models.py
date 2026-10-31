"""Modelos de banco de dados com SQLAlchemy."""

from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import (
    Column, String, DateTime, Date, Numeric, Integer, 
    ForeignKey, UniqueConstraint, Index, func
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Conta(Base):
    """Conta bancária ou marketplace vinculada."""
    __tablename__ = "contas"

    id = Column(Integer, primary_key=True)
    fonte = Column(String(50), nullable=False)  # inter_api, mercadopago_api, etc
    conta_id_externo = Column(String(255), nullable=False)  # ID na API externa
    nome = Column(String(255), nullable=False)
    tipo = Column(String(50), nullable=False)  # banco, marketplace, wallet
    saldo = Column(Numeric(19, 2), default=Decimal("0"), nullable=False)
    
    # Metadados
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relações
    transacoes = relationship("Transacao", back_populates="conta", cascade="all, delete-orphan")
    pendencias = relationship("Pendencia", back_populates="conta", cascade="all, delete-orphan")

    # Índices únicos: garante idempotência (mesma conta não duplica)
    __table_args__ = (
        UniqueConstraint("fonte", "conta_id_externo", name="uq_conta_fonte_externo"),
        Index("ix_conta_fonte", "fonte"),
    )

    def __repr__(self):
        return f"<Conta {self.fonte}:{self.nome}>"


class Transacao(Base):
    """Transação normalizada de qualquer fonte."""
    __tablename__ = "transacoes"

    id = Column(Integer, primary_key=True)
    conta_id = Column(Integer, ForeignKey("contas.id"), nullable=False)
    
    # Dados normalizados
    data = Column(Date, nullable=False)
    valor = Column(Numeric(19, 2), nullable=False)  # Decimal: + entrada / - saída
    descricao = Column(String(500), nullable=False)
    contraparte = Column(String(255), default="")
    
    # Rastreabilidade de origem (idempotência)
    id_externo = Column(String(255), nullable=False)  # ID único na fonte
    fonte = Column(String(50), nullable=False)  # inter_api, mercadopago_api, etc
    
    # Dados brutos da API (para debug/reprocessamento)
    dados_brutos = Column(String(4000), default="{}")  # JSON
    
    # Metadados
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relações
    conta = relationship("Conta", back_populates="transacoes")
    
    # Índices: idempotência via (conta_id, id_externo)
    __table_args__ = (
        UniqueConstraint("conta_id", "id_externo", name="uq_transacao_conta_externo"),
        Index("ix_transacao_data", "data"),
        Index("ix_transacao_conta_fonte", "conta_id", "fonte"),
    )

    def __repr__(self):
        return f"<Transacao {self.data} {self.valor}>"


class Pendencia(Base):
    """Transação pendente de conciliação."""
    __tablename__ = "pendencias"

    id = Column(Integer, primary_key=True)
    conta_id = Column(Integer, ForeignKey("contas.id"), nullable=False)
    
    # Referência cruzada (entrada vs saída)
    transacao_entrada_id = Column(Integer, ForeignKey("transacoes.id"))
    transacao_saida_id = Column(Integer, ForeignKey("transacoes.id"))
    
    # Status da conciliação
    status = Column(String(50), default="ABERTA")  # ABERTA, CONCILIADA, REJEITADA
    motivo = Column(String(500), default="")  # Razão da rejeição
    
    # Dados da pendência
    data = Column(Date, nullable=False)
    valor = Column(Numeric(19, 2), nullable=False)
    descricao = Column(String(500), nullable=False)
    
    # Janela de repayment (dias úteis)
    dias_uteis_repayment = Column(Integer, default=0)
    data_vencimento = Column(Date)
    
    # Metadados
    criado_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    atualizado_em = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relações
    conta = relationship("Conta", back_populates="pendencias")
    
    __table_args__ = (
        Index("ix_pendencia_status", "status"),
        Index("ix_pendencia_conta_data", "conta_id", "data"),
    )

    def __repr__(self):
        return f"<Pendencia {self.status} {self.valor}>"
