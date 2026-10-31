"""Initial schema: contas, transacoes, pendencias

Revision ID: 001
Revises: 
Create Date: 2026-10-23

"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tabela contas
    op.create_table(
        "contas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fonte", sa.String(50), nullable=False),
        sa.Column("conta_id_externo", sa.String(255), nullable=False),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("tipo", sa.String(50), nullable=False),
        sa.Column("saldo", sa.Numeric(19, 2), nullable=False, server_default="0"),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fonte", "conta_id_externo", name="uq_conta_fonte_externo"),
    )
    op.create_index("ix_conta_fonte", "contas", ["fonte"])

    # Tabela transacoes
    op.create_table(
        "transacoes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conta_id", sa.Integer(), nullable=False),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("valor", sa.Numeric(19, 2), nullable=False),
        sa.Column("descricao", sa.String(500), nullable=False),
        sa.Column("contraparte", sa.String(255), server_default=""),
        sa.Column("id_externo", sa.String(255), nullable=False),
        sa.Column("fonte", sa.String(50), nullable=False),
        sa.Column("dados_brutos", sa.String(4000), server_default="{}"),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["conta_id"], ["contas.id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conta_id", "id_externo", name="uq_transacao_conta_externo"),
    )
    op.create_index("ix_transacao_data", "transacoes", ["data"])
    op.create_index("ix_transacao_conta_fonte", "transacoes", ["conta_id", "fonte"])

    # Tabela pendencias
    op.create_table(
        "pendencias",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conta_id", sa.Integer(), nullable=False),
        sa.Column("transacao_entrada_id", sa.Integer()),
        sa.Column("transacao_saida_id", sa.Integer()),
        sa.Column("status", sa.String(50), server_default="ABERTA"),
        sa.Column("motivo", sa.String(500), server_default=""),
        sa.Column("data", sa.Date(), nullable=False),
        sa.Column("valor", sa.Numeric(19, 2), nullable=False),
        sa.Column("descricao", sa.String(500), nullable=False),
        sa.Column("dias_uteis_repayment", sa.Integer(), server_default="0"),
        sa.Column("data_vencimento", sa.Date()),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["conta_id"], ["contas.id"], ),
        sa.ForeignKeyConstraint(["transacao_entrada_id"], ["transacoes.id"], ),
        sa.ForeignKeyConstraint(["transacao_saida_id"], ["transacoes.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pendencia_status", "pendencias", ["status"])
    op.create_index("ix_pendencia_conta_data", "pendencias", ["conta_id", "data"])


def downgrade() -> None:
    op.drop_index("ix_pendencia_conta_data", table_name="pendencias")
    op.drop_index("ix_pendencia_status", table_name="pendencias")
    op.drop_table("pendencias")
    
    op.drop_index("ix_transacao_conta_fonte", table_name="transacoes")
    op.drop_index("ix_transacao_data", table_name="transacoes")
    op.drop_table("transacoes")
    
    op.drop_index("ix_conta_fonte", table_name="contas")
    op.drop_table("contas")
