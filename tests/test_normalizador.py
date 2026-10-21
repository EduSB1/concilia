"""Normalização: reimportar não pode duplicar, e nada some calado."""

import unittest
from decimal import Decimal

import apoio  # noqa: F401  (ajusta o sys.path)
from app.normalizacao import normalizar_lote


BRUTOS = [
    {"conta": "Inter PJ", "data": "2026-10-09", "valor": "3.412,80",
     "descricao": "Repasse Shopee", "id_externo": "E1", "fonte": "inter_api"},
    {"conta": "Inter PJ", "data": "09/10/2026", "valor": -250.00,
     "descricao": "Pix enviado fornecedor", "id_externo": "E2", "fonte": "inter_api"},
]


class TestNormalizador(unittest.TestCase):
    def test_converte_os_dois_formatos_de_data_e_valor(self):
        novos, duplicados, problemas = normalizar_lote(BRUTOS)
        self.assertEqual(len(novos), 2)
        self.assertEqual(novos[0].valor, Decimal("3412.80"))
        self.assertTrue(novos[0].e_entrada)
        self.assertTrue(novos[1].e_saida)
        self.assertEqual((duplicados, problemas), ([], []))

    def test_reimportar_o_mesmo_extrato_nao_duplica(self):
        novos, _, _ = normalizar_lote(BRUTOS)
        chaves = [l.chave for l in novos]
        de_novo, duplicados, _ = normalizar_lote(BRUTOS, ja_importados=chaves)
        self.assertEqual(de_novo, [])
        self.assertEqual(len(duplicados), 2)

    def test_sem_id_externo_nunca_e_tratado_como_duplicado(self):
        sem_id = [{"conta": "Itaú", "data": "2026-10-09", "valor": "10,00"}] * 2
        novos, duplicados, _ = normalizar_lote(sem_id)
        self.assertEqual(len(novos), 2)
        self.assertEqual(duplicados, [])

    def test_linha_ruim_vira_problema_e_nao_some(self):
        ruins = [
            {"conta": "Inter PJ", "data": "2026-10-09", "valor": "mil reais"},
            {"conta": "", "data": "2026-10-09", "valor": "10"},
            {"conta": "Inter PJ", "data": "trinta de outubro", "valor": "10"},
        ]
        novos, _, problemas = normalizar_lote(ruins)
        self.assertEqual(novos, [])
        self.assertEqual(len(problemas), 3)
        self.assertIn("ilegível", problemas[0].motivo)
        self.assertEqual(problemas[1].motivo, "lançamento sem conta")


if __name__ == "__main__":
    unittest.main()
