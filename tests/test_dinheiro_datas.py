"""Dinheiro e datas: a base de tudo. Erro aqui contamina todo relatório."""

import unittest
from decimal import Decimal

from apoio import dia
from app.datas import e_dia_util, janela_dias_uteis, soma_dias_uteis
from app.dinheiro import ValorIlegivel, brl, centavos, dinheiro


class TestDinheiro(unittest.TestCase):
    def test_le_formato_brasileiro(self):
        self.assertEqual(dinheiro("1.234,56"), Decimal("1234.56"))
        self.assertEqual(dinheiro("1234,56"), Decimal("1234.56"))
        self.assertEqual(dinheiro("1234.56"), Decimal("1234.56"))
        self.assertEqual(dinheiro("R$ 3.412,80"), Decimal("3412.80"))

    def test_parenteses_sao_negativo(self):
        self.assertEqual(dinheiro("(99,90)"), Decimal("-99.90"))

    def test_vazio_e_zero_de_verdade(self):
        self.assertEqual(dinheiro(""), Decimal("0"))
        self.assertEqual(dinheiro(None), Decimal("0"))

    def test_ilegivel_nao_vira_zero_em_silencio(self):
        with self.assertRaises(ValorIlegivel):
            dinheiro("mil reais", origem=" na linha 3")

    def test_float_nao_contamina(self):
        # 0,1 + 0,2 em float dá 0,30000000000000004; aqui tem de dar 0,30.
        soma = dinheiro(0.1) + dinheiro(0.2)
        self.assertEqual(centavos(soma), Decimal("0.30"))

    def test_formata_em_reais(self):
        self.assertEqual(brl(Decimal("3412.80")), "R$ 3.412,80")
        self.assertEqual(brl(Decimal("-99.9")), "-R$ 99,90")


class TestDatas(unittest.TestCase):
    def test_fim_de_semana_nao_e_dia_util(self):
        self.assertFalse(e_dia_util(dia("2026-10-10")))   # sábado
        self.assertFalse(e_dia_util(dia("2026-10-11")))   # domingo
        self.assertTrue(e_dia_util(dia("2026-10-09")))    # sexta

    def test_soma_pula_o_fim_de_semana(self):
        # Sexta 09/10 + 2 dias úteis = terça 13/10.
        self.assertEqual(soma_dias_uteis(dia("2026-10-09"), 2), dia("2026-10-13"))
        self.assertEqual(soma_dias_uteis(dia("2026-10-09"), -2), dia("2026-10-07"))

    def test_janela_cobre_os_dois_lados(self):
        inicio, fim = janela_dias_uteis(dia("2026-10-09"), 2)
        self.assertEqual((inicio, fim), (dia("2026-10-07"), dia("2026-10-13")))


if __name__ == "__main__":
    unittest.main()
