"""Etapa 3 — regras de categoria."""

import unittest
from decimal import Decimal

from apoio import lanc
from app.motor.categorias import Regra, aplicar
from app.normalizacao.modelos import STATUS_PENDENTE


class TestCategorias(unittest.TestCase):
    def test_regras_iniciais_pegam_os_casos_do_roadmap(self):
        movimentos = [
            lanc("Inter PJ", "2026-10-09", -32.50, "Débito Uber *trip"),
            lanc("Inter PJ", "2026-10-09", -8.80, "CPTM bilhete"),
            lanc("Inter PJ", "2026-10-09", 14.22, "Rendimento aplicação automática"),
            lanc("Inter PJ", "2026-10-09", -980.00, "DAS Simples Nacional"),
        ]
        decisoes, sem_categoria = aplicar(movimentos)

        self.assertEqual(sem_categoria, [])
        self.assertEqual([m.categoria for m in movimentos],
                         ["Transporte", "Transporte", "Receita Financeira", "Impostos"])
        self.assertTrue(all(d.confianca == Decimal("0.90") for d in decisoes))

    def test_categorizar_nao_concilia(self):
        # Ganhar categoria não é ganhar conferência: o lançamento segue
        # pendente até alguém (ou a etapa 2) confirmar.
        movimento = lanc("Inter PJ", "2026-10-09", -32.50, "Uber")
        aplicar([movimento])
        self.assertEqual(movimento.status, STATUS_PENDENTE)

    def test_prioridade_menor_vence(self):
        movimento = lanc("Inter PJ", "2026-10-09", -50, "Taxa de frete Shopee")
        regras = [
            Regra(r"frete", "Frete/Envios", "ambos", 5),
            Regra(r"taxa de", "Taxas de Marketplace", "ambos", 10),
        ]
        aplicar([movimento], regras)
        self.assertEqual(movimento.categoria, "Frete/Envios")

    def test_acento_e_caixa_nao_importam(self):
        movimento = lanc("Inter PJ", "2026-10-09", -100, "DEVOLUÇÃO DE PEDIDO")
        aplicar([movimento])
        self.assertEqual(movimento.categoria, "Devoluções/Estornos")

    def test_o_que_nenhuma_regra_cobre_e_devolvido_para_a_fila(self):
        movimento = lanc("Inter PJ", "2026-10-09", -412.00, "Pix enviado JOAO DA SILVA")
        _, sem_categoria = aplicar([movimento])
        self.assertEqual(sem_categoria, [movimento])
        self.assertEqual(movimento.categoria, "")

    def test_regra_por_contraparte(self):
        movimento = lanc("Inter PJ", "2026-10-09", -2000, "Pix enviado",
                         contraparte="DISTRIBUIDORA XYZ LTDA")
        regras = [Regra(r"distribuidora", "Fornecedores/Mercadoria", "contraparte", 10)]
        aplicar([movimento], regras)
        self.assertEqual(movimento.categoria, "Fornecedores/Mercadoria")


if __name__ == "__main__":
    unittest.main()
