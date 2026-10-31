"""Testes do motor de conciliação."""

import unittest
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Conta, Transacao
from app.motor import MotorConciliacao


class TestMotorConciliacao(unittest.TestCase):
    """Testes dos 4 estágios do motor."""

    def setUp(self):
        """Criar BD em memória e inserir dados de teste."""
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
        
        self.motor = MotorConciliacao(self.db)

    def tearDown(self):
        self.db.close()

    def test_validacao_ok(self):
        """Testar validação de transação válida."""
        trans = Transacao(
            conta_id=self.conta.id,
            data=date.today(),
            valor=Decimal("100.00"),
            descricao="Transação válida",
            id_externo="TEST-001",
            fonte="teste",
        )
        self.db.add(trans)
        self.db.commit()

        validacao = self.motor.validar_transacao(trans)
        self.assertTrue(validacao.valida)
        self.assertEqual(len(validacao.erros), 0)

    def test_validacao_erro_valor_zero(self):
        """Testar validação com valor zero (inválido)."""
        trans = Transacao(
            conta_id=self.conta.id,
            data=date.today(),
            valor=Decimal("0.00"),
            descricao="Transação inválida",
            id_externo="TEST-002",
            fonte="teste",
        )
        self.db.add(trans)
        self.db.commit()

        validacao = self.motor.validar_transacao(trans)
        self.assertFalse(validacao.valida)
        self.assertTrue(any("zero" in e.lower() for e in validacao.erros))

    def test_normalizacao(self):
        """Testar normalização de valores."""
        trans = Transacao(
            conta_id=self.conta.id,
            data=date.today(),
            valor=Decimal("100.006"),
            descricao="  Desc com espaço  ",
            id_externo="TEST-003",
            fonte="teste",
        )
        self.db.add(trans)
        self.db.commit()

        norm = self.motor.normalizar_transacao(trans)
        self.assertEqual(norm.valor, Decimal("100.01"))
        self.assertEqual(norm.descricao, "Desc com espaço")

    def test_encontrar_pares(self):
        """Testar matching de entrada vs saída."""
        hoje = date.today()
        
        # Criar entrada
        entrada = Transacao(
            conta_id=self.conta.id,
            data=hoje - timedelta(days=1),
            valor=Decimal("250.00"),
            descricao="Recebimento",
            id_externo="ENTRADA-001",
            fonte="teste",
        )
        
        # Criar saída correspondente
        saida = Transacao(
            conta_id=self.conta.id,
            data=hoje,
            valor=Decimal("-250.00"),
            descricao="Pagamento",
            id_externo="SAIDA-001",
            fonte="teste",
        )
        
        self.db.add(entrada)
        self.db.add(saida)
        self.db.commit()
        
        # Buscar pares
        pares = self.motor.encontrar_pares(
            self.conta.id,
            hoje - timedelta(days=2),
            hoje,
        )
        
        self.assertEqual(len(pares), 1)
        self.assertEqual(pares[0][0].id, entrada.id)
        self.assertEqual(pares[0][1].id, saida.id)

    def test_conferencia_cobranca(self):
        """Testar identificação de pendências vencidas."""
        # Criar saída muito antiga (> 7 dias úteis)
        data_antiga = date.today() - timedelta(days=15)
        
        saida = Transacao(
            conta_id=self.conta.id,
            data=data_antiga,
            valor=Decimal("-500.00"),
            descricao="Pagamento vencido",
            id_externo="VENC-001",
            fonte="teste",
        )
        
        self.db.add(saida)
        self.db.commit()
        
        # Conferir cobrança
        pendencias = self.motor.conferir_cobranca(
            self.conta.id,
            dias_uteis_repayment=7,
        )
        
        self.assertEqual(len(pendencias), 1)
        self.assertIn("VENCIDA", pendencias[0]["descricao"])


if __name__ == "__main__":
    unittest.main()
