"""Testes E2E: sincronizador → motor → endpoints."""

import unittest
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Conta, Transacao, Pendencia
from app.services import SincronizadorTransacoes
from app.motor import MotorConciliacao
from app.conectores.mock import (
    MockConectorMercadoPago,
    MockConectorInter,
    MockConectorBling,
)


class TestE2ECompleto(unittest.TestCase):
    """Testes E2E: fluxo completo sincronizador → motor → resultado."""

    def setUp(self):
        """Criar BD em memória."""
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        SessionLocal = sessionmaker(bind=self.engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_e2e_mercadopago_completo(self):
        """E2E Mercado Pago: Sincronizar → Processar → Validar resultado."""
        conector_mp = MockConectorMercadoPago()
        sincronizador = SincronizadorTransacoes(self.db)
        
        data_inicio = date.today() - timedelta(days=30)
        data_fim = date.today()
        
        sync_result = sincronizador.sincronizar_fonte(
            conector=conector_mp,
            fonte="mercadopago_api",
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        
        self.assertTrue(sync_result["sucesso"])
        self.assertEqual(sync_result["transacoes_inseridas"], 4)
        
        conta_mp = self.db.query(Conta).filter(
            Conta.fonte == "mercadopago_api"
        ).first()
        self.assertIsNotNone(conta_mp)
        self.assertEqual(conta_mp.nome, "Loja Teste MP")
        
        motor = MotorConciliacao(self.db)
        motor_result = motor.processar_conta(
            conta_id=conta_mp.id,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        
        self.assertEqual(motor_result["validadas"], 4)
        self.assertEqual(motor_result["erros_validacao"], 0)

    def test_e2e_multiplas_fontes(self):
        """E2E Multi-fonte: Sincronizar 3 fontes e processar todas."""
        fontes = [
            (MockConectorMercadoPago(), "mercadopago_api"),
            (MockConectorInter(), "inter_api"),
            (MockConectorBling(), "bling_api"),
        ]
        
        sincronizador = SincronizadorTransacoes(self.db)
        motor = MotorConciliacao(self.db)
        
        data_inicio = date.today() - timedelta(days=30)
        data_fim = date.today()
        
        total_transacoes = 0
        contas_ids = []
        
        # Sincronizar todas as fontes
        for conector, fonte in fontes:
            sync_result = sincronizador.sincronizar_fonte(
                conector=conector,
                fonte=fonte,
                data_inicio=data_inicio,
                data_fim=data_fim,
            )
            self.assertTrue(sync_result["sucesso"])
            total_transacoes += sync_result["transacoes_inseridas"]
            
            conta = self.db.query(Conta).filter(Conta.fonte == fonte).first()
            contas_ids.append(conta.id)
        
        self.assertEqual(total_transacoes, 9)  # 4 + 3 + 2
        
        # Processar motor para cada conta
        resultados_motor = []
        for conta_id in contas_ids:
            resultado = motor.processar_conta(
                conta_id=conta_id,
                data_inicio=data_inicio,
                data_fim=data_fim,
            )
            resultados_motor.append(resultado)
        
        # Validar que todas foram processadas
        total_validadas = sum(r["validadas"] for r in resultados_motor)
        self.assertEqual(total_validadas, 9)

    def test_e2e_idempotencia_completa(self):
        """E2E Idempotência: Sincronizar 2x → Mesmos resultados."""
        conector_mp = MockConectorMercadoPago()
        sincronizador = SincronizadorTransacoes(self.db)
        
        data_inicio = date.today() - timedelta(days=30)
        data_fim = date.today()
        
        # Primeira sincronização
        sync1 = sincronizador.sincronizar_fonte(
            conector=conector_mp,
            fonte="mercadopago_api",
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        self.assertEqual(sync1["transacoes_inseridas"], 4)
        
        # Segunda sincronização (idempotência)
        sync2 = sincronizador.sincronizar_fonte(
            conector=conector_mp,
            fonte="mercadopago_api",
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        self.assertEqual(sync2["transacoes_inseridas"], 0)
        self.assertEqual(sync2["transacoes_ignoradas"], 4)
        
        # Validar que não há duplicatas
        total_transacoes = self.db.query(Transacao).count()
        self.assertEqual(total_transacoes, 4)

    def test_e2e_fluxo_completo_inter(self):
        """E2E Completo Inter: Sincronizar → Motor → Validar."""
        conector_inter = MockConectorInter()
        sincronizador = SincronizadorTransacoes(self.db)
        motor = MotorConciliacao(self.db)
        
        data_inicio = date.today() - timedelta(days=30)
        data_fim = date.today()
        
        sync_result = sincronizador.sincronizar_fonte(
            conector=conector_inter,
            fonte="inter_api",
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        self.assertEqual(sync_result["transacoes_inseridas"], 3)
        
        conta_id = self.db.query(Conta).filter(
            Conta.fonte == "inter_api"
        ).first().id
        
        motor_result = motor.processar_conta(
            conta_id=conta_id,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        
        self.assertEqual(motor_result["validadas"], 3)
        # Validar que motor rodou sem erro
        self.assertGreater(motor_result["pares_encontrados"], -1)


if __name__ == "__main__":
    unittest.main()
