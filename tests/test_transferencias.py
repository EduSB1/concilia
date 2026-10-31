"""Etapa 1 — transferência interna.

O erro que esta etapa evita: contar a mesma venda duas vezes, uma quando
o Mercado Pago libera e outra quando o valor chega ao Inter.
"""

import unittest
from decimal import Decimal

from apoio import lanc
from app.motor import transferencias
from app.normalizacao.modelos import STATUS_CONCILIADO, STATUS_PENDENTE


class TestTransferencias(unittest.TestCase):
    def test_saque_do_mercado_pago_para_o_inter(self):
        saida = lanc("Mercado Pago", "2026-10-09", -5000, "Saque para conta bancária")
        entrada = lanc("Inter PJ", "2026-10-09", 5000, "Transferência recebida Mercado Pago")
        feitas, ambiguas = transferencias.detectar([saida, entrada])

        self.assertEqual(len(feitas), 1)
        self.assertEqual(feitas[0].confianca, Decimal("0.95"))
        self.assertEqual(saida.status, STATUS_CONCILIADO)
        self.assertEqual(entrada.status, STATUS_CONCILIADO)
        self.assertEqual(entrada.categoria, "Transferência Interna")
        self.assertEqual(ambiguas, [])

    def test_aceita_chegada_no_dia_seguinte(self):
        saida = lanc("Carteira Shopee", "2026-10-09", -1200, "Saque carteira")
        entrada = lanc("Inter PJ", "2026-10-10", 1200, "Resgate Shopee")
        feitas, _ = transferencias.detectar([saida, entrada])
        self.assertEqual(len(feitas), 1)

    def test_dois_dias_depois_nao_e_par(self):
        saida = lanc("Mercado Pago", "2026-10-09", -800, "Saque")
        entrada = lanc("Inter PJ", "2026-10-11", 800, "Transferência")
        feitas, _ = transferencias.detectar([saida, entrada])
        self.assertEqual(feitas, [])

    def test_mesma_conta_nao_conta(self):
        saida = lanc("Inter PJ", "2026-10-09", -300, "Transferência")
        entrada = lanc("Inter PJ", "2026-10-09", 300, "Transferência")
        feitas, _ = transferencias.detectar([saida, entrada])
        self.assertEqual(feitas, [])

    def test_sem_pista_no_texto_fica_para_conferir(self):
        # Valor e data batem, mas nada diz que é transferência: pode ser
        # coincidência de dois repasses iguais. Não fecha sozinho.
        saida = lanc("Mercado Pago", "2026-10-09", -2000, "Débito")
        entrada = lanc("Inter PJ", "2026-10-09", 2000, "Crédito")
        feitas, _ = transferencias.detectar([saida, entrada])

        self.assertEqual(len(feitas), 1)
        self.assertEqual(feitas[0].confianca, Decimal("0.75"))
        self.assertFalse(feitas[0].automatica)
        self.assertEqual(saida.status, STATUS_PENDENTE)

    def test_duas_entradas_iguais_viram_pendencia(self):
        saida = lanc("Mercado Pago", "2026-10-09", -1000, "Saque")
        a = lanc("Inter PJ", "2026-10-09", 1000, "Transferência recebida")
        b = lanc("Carteira Shopee", "2026-10-09", 1000, "Transferência recebida")
        feitas, ambiguas = transferencias.detectar([saida, a, b])

        self.assertEqual(feitas, [])
        self.assertEqual(len(ambiguas), 1)
        self.assertEqual(len(ambiguas[0][1]), 2)

    def test_acento_nao_atrapalha(self):
        self.assertTrue(transferencias.parece_transferencia("TRANSFERENCIA ENVIADA"))
        self.assertTrue(transferencias.parece_transferencia("Aplicação automática"))
        self.assertFalse(transferencias.parece_transferencia("Compra no mercado"))


if __name__ == "__main__":
    unittest.main()
