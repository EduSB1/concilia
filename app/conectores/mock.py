"""Conector Mock para testes sem chamar APIs reais."""

from datetime import date, timedelta
from decimal import Decimal
from app.conectores import ConectorBase, Transacao


class MockConectorMercadoPago(ConectorBase):
    """Mock do Mercado Pago com dados fake."""

    def autenticar(self) -> bool:
        return True

    def listar_contas(self) -> list[dict]:
        return [{
            "id": "469104662927017",
            "nome": "Loja Teste MP",
            "tipo": "wallet",
            "email": "test_user_19801440731062007@testuser.com",
            "saldo": Decimal("5000.00"),
        }]

    def extrato(self, data_inicio: date, data_fim: date) -> list[Transacao]:
        """Retorna transações fake."""
        hoje = date.today()
        return [
            Transacao(
                data=hoje - timedelta(days=5),
                valor=Decimal("250.00"),
                descricao="Venda online #001",
                contraparte="cliente@email.com",
                id_externo="MP-PAY-001",
                fonte="mercadopago_api",
            ),
            Transacao(
                data=hoje - timedelta(days=4),
                valor=Decimal("180.50"),
                descricao="Venda online #002",
                contraparte="outro@email.com",
                id_externo="MP-PAY-002",
                fonte="mercadopago_api",
            ),
            Transacao(
                data=hoje - timedelta(days=3),
                valor=Decimal("-50.00"),
                descricao="Reembolso #001",
                contraparte="cliente@email.com",
                id_externo="MP-REF-001",
                fonte="mercadopago_api",
            ),
            Transacao(
                data=hoje - timedelta(days=2),
                valor=Decimal("320.00"),
                descricao="Venda online #003",
                contraparte="terceiro@email.com",
                id_externo="MP-PAY-003",
                fonte="mercadopago_api",
            ),
        ]


class MockConectorInter(ConectorBase):
    """Mock do Banco Inter com dados fake."""

    def autenticar(self) -> bool:
        return True

    def listar_contas(self) -> list[dict]:
        return [{
            "id": "12345",
            "nome": "Conta Corrente Inter",
            "tipo": "banco",
            "saldo": Decimal("15000.00"),
        }]

    def extrato(self, data_inicio: date, data_fim: date) -> list[Transacao]:
        """Retorna transações fake de banco."""
        hoje = date.today()
        return [
            Transacao(
                data=hoje - timedelta(days=6),
                valor=Decimal("-100.00"),
                descricao="Boleto pagamento fornecedor",
                contraparte="Fornecedor A",
                id_externo="INTER-TRX-001",
                fonte="inter_api",
            ),
            Transacao(
                data=hoje - timedelta(days=5),
                valor=Decimal("250.00"),
                descricao="Depósito cliente X",
                contraparte="Cliente X",
                id_externo="INTER-DEP-001",
                fonte="inter_api",
            ),
            Transacao(
                data=hoje - timedelta(days=3),
                valor=Decimal("-200.00"),
                descricao="Pagamento fornecedor B",
                contraparte="Fornecedor B",
                id_externo="INTER-TRX-002",
                fonte="inter_api",
            ),
        ]


class MockConectorBling(ConectorBase):
    """Mock do Bling com dados fake de NF."""

    def autenticar(self) -> bool:
        return True

    def listar_contas(self) -> list[dict]:
        return [{
            "id": "1",
            "nome": "Empresa Teste",
            "tipo": "erp",
            "cnpj": "12.345.678/0001-90",
        }]

    def extrato(self, data_inicio: date, data_fim: date) -> list[Transacao]:
        """Retorna notas fiscais fake."""
        hoje = date.today()
        return [
            Transacao(
                data=hoje - timedelta(days=4),
                valor=Decimal("500.00"),
                descricao="NF #001 - Venda produto A",
                contraparte="Cliente Y LTDA",
                id_externo="BLING-NF-001",
                fonte="bling_api",
            ),
            Transacao(
                data=hoje - timedelta(days=2),
                valor=Decimal("750.00"),
                descricao="NF #002 - Venda produto B",
                contraparte="Cliente Z INC",
                id_externo="BLING-NF-002",
                fonte="bling_api",
            ),
        ]
