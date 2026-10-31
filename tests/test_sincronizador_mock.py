"""Testes do sincronizador com dados mock."""

import unittest
from datetime import date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, Conta, Transacao
from app.services import SincronizadorTransacoes
from app.conectores.mock import MockConectorMercadoPago, MockConectorInter, MockConectorBling


class TestSincronizadorMock(unittest.TestCase):
    """Testes de sincronização com dados mock."""

    def setUp(self):
        """Criar BD em memória para cada teste (isolado)."""
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        SessionLocal = sessionmaker(bind=self.engine)
        self.db = SessionLocal()

    def tearDown(self):
        """Fechar sessão."""
        self.db.close()

    def test_sincronizar_mercadopago_mock(self):
        """Testar sincronização do Mercado Pago com dados mock."""
        conector = MockConectorMercadoPago()
        sincronizador = SincronizadorTransacoes(self.db)

        data_inicio = date.today() - timedelta(days=30)
        data_fim = date.today()

        resultado = sincronizador.sincronizar_fonte(
            conector=conector,
            fonte="mercadopago_api",
            data_inicio=data_inicio,
            data_fim=data_fim,
        )

        self.assertTrue(resultado["sucesso"])
        self.assertEqual(resultado["contas_sincronizadas"], 1)
        self.assertEqual(resultado["transacoes_inseridas"], 4)

        # Validar dados no BD
        contas = self.db.query(Conta).filter(Conta.fonte == "mercadopago_api").all()
        self.assertEqual(len(contas), 1)
        self.assertEqual(contas[0].nome, "Loja Teste MP")

        # Validar transações
        transacoes = self.db.query(Transacao).filter(
            Transacao.fonte == "mercadopago_api"
        ).all()
        self.assertEqual(len(transacoes), 4)

        # Testar idempotência (sincronizar 2x = mesmo resultado)
        resultado2 = sincronizador.sincronizar_fonte(
            conector=conector,
            fonte="mercadopago_api",
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        self.assertEqual(resultado2["transacoes_inseridas"], 0)
        self.assertEqual(resultado2["transacoes_ignoradas"], 4)

    def test_sincronizar_inter_mock(self):
        """Testar sincronização do Inter com dados mock."""
        conector = MockConectorInter()
        sincronizador = SincronizadorTransacoes(self.db)

        data_inicio = date.today() - timedelta(days=30)
        data_fim = date.today()

        resultado = sincronizador.sincronizar_fonte(
            conector=conector,
            fonte="inter_api",
            data_inicio=data_inicio,
            data_fim=data_fim,
        )

        self.assertTrue(resultado["sucesso"])
        self.assertEqual(resultado["contas_sincronizadas"], 1)
        self.assertEqual(resultado["transacoes_inseridas"], 3)

    def test_sincronizar_bling_mock(self):
        """Testar sincronização do Bling com dados mock."""
        conector = MockConectorBling()
        sincronizador = SincronizadorTransacoes(self.db)

        data_inicio = date.today() - timedelta(days=30)
        data_fim = date.today()

        resultado = sincronizador.sincronizar_fonte(
            conector=conector,
            fonte="bling_api",
            data_inicio=data_inicio,
            data_fim=data_fim,
        )

        self.assertTrue(resultado["sucesso"])
        self.assertEqual(resultado["contas_sincronizadas"], 1)
        self.assertEqual(resultado["transacoes_inseridas"], 2)

    def test_multiplas_fontes(self):
        """Testar sincronização de múltiplas fontes simultâneas."""
        fontes = [
            (MockConectorMercadoPago(), "mercadopago_api"),
            (MockConectorInter(), "inter_api"),
            (MockConectorBling(), "bling_api"),
        ]

        sincronizador = SincronizadorTransacoes(self.db)
        data_inicio = date.today() - timedelta(days=30)
        data_fim = date.today()

        total_contas = 0
        total_transacoes = 0

        for conector, fonte in fontes:
            resultado = sincronizador.sincronizar_fonte(
                conector=conector,
                fonte=fonte,
                data_inicio=data_inicio,
                data_fim=data_fim,
            )
            total_contas += resultado["contas_sincronizadas"]
            total_transacoes += resultado["transacoes_inseridas"]

        self.assertEqual(total_contas, 3)
        self.assertEqual(total_transacoes, 9)

        # Validar que não há duplicatas
        todas_transacoes = self.db.query(Transacao).all()
        self.assertEqual(len(todas_transacoes), 9)


if __name__ == "__main__":
    unittest.main()
