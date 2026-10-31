"""Testes dos endpoints de orquestração."""

import unittest
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Conta, Transacao
from app.services import SincronizadorTransacoes
from app.motor import MotorConciliacao
from app.conectores.mock import MockConectorMercadoPago


class TestEndpointsOrquestrar(unittest.TestCase):
    """Testes dos endpoints de orquestração."""

    def setUp(self):
        """Criar BD e dados de teste."""
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        SessionLocal = sessionmaker(bind=self.engine)
        self.db = SessionLocal()
        
        # Criar conta de teste
        self.conta = Conta(
            fonte="teste",
            conta_id_externo="123",
            nome="Conta Teste",
            tipo="banco",
            saldo=Decimal("1000.00"),
        )
        self.db.add(self.conta)
        self.db.commit()
        
        # Inserir algumas transações
        trans1 = Transacao(
            conta_id=self.conta.id,
            data=date.today() - timedelta(days=5),
            valor=Decimal("100.00"),
            descricao="Transação 1",
            id_externo="T1",
            fonte="teste",
        )
        trans2 = Transacao(
            conta_id=self.conta.id,
            data=date.today() - timedelta(days=3),
            valor=Decimal("-50.00"),
            descricao="Transação 2",
            id_externo="T2",
            fonte="teste",
        )
        self.db.add(trans1)
        self.db.add(trans2)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_processar_conta_basico(self):
        """Testar orquestração básica: motor processa conta."""
        motor = MotorConciliacao(self.db)
        
        resultado = motor.processar_conta(
            conta_id=self.conta.id,
            data_inicio=date.today() - timedelta(days=30),
            data_fim=date.today(),
        )
        
        self.assertEqual(resultado["validadas"], 2)
        self.assertEqual(resultado["erros_validacao"], 0)

    def test_sincronizar_e_processar_mock(self):
        """Testar orquestração completa: sync + motor com mock."""
        conector_mp = MockConectorMercadoPago()
        sincronizador = SincronizadorTransacoes(self.db)
        motor = MotorConciliacao(self.db)
        
        data_inicio = date.today() - timedelta(days=30)
        data_fim = date.today()
        
        # SYNC
        sync_result = sincronizador.sincronizar_fonte(
            conector=conector_mp,
            fonte="mercadopago_api",
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        self.assertTrue(sync_result["sucesso"])
        self.assertEqual(sync_result["transacoes_inseridas"], 4)
        
        # ENCONTRAR CONTA
        conta_mp = self.db.query(Conta).filter(
            Conta.fonte == "mercadopago_api"
        ).first()
        self.assertIsNotNone(conta_mp)
        
        # PROCESSAR
        motor_result = motor.processar_conta(
            conta_id=conta_mp.id,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        
        self.assertEqual(motor_result["validadas"], 4)


if __name__ == "__main__":
    unittest.main()
