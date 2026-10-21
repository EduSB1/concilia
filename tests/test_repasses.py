"""Etapa 2 — repasse do marketplace × crédito no banco.

Cada caso aqui é uma forma conhecida de o dinheiro "não bater": o crédito
vem somado, vem fracionado, vem com centavo de diferença, ou não vem.
"""

import unittest
from decimal import Decimal

from apoio import dia, lanc, rep
from app.motor import repasses as motor_repasses
from app.normalizacao.modelos import (
    REPASSE_AGUARDANDO, REPASSE_DIVERGENTE, REPASSE_RECEBIDO, STATUS_CONCILIADO,
)

HOJE = dia("2026-10-20")


class TestMatchExato(unittest.TestCase):
    def test_credito_igual_ao_liquido_na_janela(self):
        r = rep("shopee", "2026-10-09", 3412.80, bruto=4100, taxas=600, frete=87.20)
        credito = lanc("Inter PJ", "2026-10-09", 3412.80, "Repasse Shopee")
        feitas, ambiguos, nao_recebidos, _ = motor_repasses.casar([r], [credito], hoje=HOJE)

        self.assertEqual(len(feitas), 1)
        self.assertEqual(feitas[0].confianca, Decimal("0.95"))
        self.assertEqual(r.status, REPASSE_RECEBIDO)
        self.assertEqual(credito.status, STATUS_CONCILIADO)
        self.assertEqual(credito.categoria, "Receita Shopee")
        self.assertEqual((ambiguos, nao_recebidos), ([], []))

    def test_aceita_atraso_de_ate_dois_dias_uteis(self):
        r = rep("shopee", "2026-10-09", 1000)          # sexta
        credito = lanc("Inter PJ", "2026-10-13", 1000, "Repasse Shopee")   # terça
        feitas, _, _, _ = motor_repasses.casar([r], [credito], hoje=HOJE)
        self.assertEqual(len(feitas), 1)

    def test_fora_da_janela_nao_casa(self):
        r = rep("shopee", "2026-10-09", 1000)
        credito = lanc("Inter PJ", "2026-10-14", 1000, "Repasse Shopee")
        feitas, _, nao_recebidos, _ = motor_repasses.casar([r], [credito], hoje=HOJE)
        self.assertEqual(feitas, [])
        self.assertEqual(len(nao_recebidos), 1)

    def test_descricao_de_outro_marketplace_nao_casa(self):
        r = rep("shopee", "2026-10-09", 1000)
        credito = lanc("Inter PJ", "2026-10-09", 1000, "Repasse Mercado Livre")
        feitas, _, _, _ = motor_repasses.casar([r], [credito], hoje=HOJE)
        self.assertEqual(feitas, [])

    def test_tiktok_chega_como_bytedance(self):
        r = rep("tiktok", "2026-10-09", 1500)
        credito = lanc("Inter PJ", "2026-10-09", 1500, "Pix recebido BYTEDANCE BRASIL")
        feitas, _, _, _ = motor_repasses.casar([r], [credito], hoje=HOJE)
        self.assertEqual(len(feitas), 1)
        self.assertEqual(credito.categoria, "Receita TikTok Shop")

    def test_dois_creditos_identicos_viram_pendencia(self):
        r = rep("shopee", "2026-10-09", 1000)
        a = lanc("Inter PJ", "2026-10-09", 1000, "Repasse Shopee", id_externo="A")
        b = lanc("Inter PJ", "2026-10-09", 1000, "Repasse Shopee", id_externo="B")
        feitas, ambiguos, _, _ = motor_repasses.casar([r], [a, b], hoje=HOJE)
        self.assertEqual(feitas, [])
        self.assertEqual(len(ambiguos[0][1]), 2)
        self.assertEqual(r.status, REPASSE_AGUARDANDO)


class TestMatchAgrupado(unittest.TestCase):
    def test_tres_repasses_somam_um_credito(self):
        rs = [
            rep("shopee", "2026-10-08", 1000, id_externo="R1"),
            rep("shopee", "2026-10-09", 2000, id_externo="R2"),
            rep("shopee", "2026-10-09", 412.80, id_externo="R3"),
        ]
        credito = lanc("Inter PJ", "2026-10-09", 3412.80, "Repasse Shopee")
        feitas, _, _, _ = motor_repasses.casar(rs, [credito], hoje=HOJE)

        self.assertEqual(len(feitas), 1)
        self.assertEqual(feitas[0].confianca, Decimal("0.80"))
        self.assertEqual(len(feitas[0].repasses), 3)
        self.assertTrue(all(r.status == REPASSE_RECEBIDO for r in rs))
        self.assertEqual(credito.status, STATUS_CONCILIADO)

    def test_um_repasse_cai_fracionado_em_dois_creditos(self):
        r = rep("mercado_livre", "2026-10-09", 5000)
        a = lanc("Inter PJ", "2026-10-09", 3000, "Repasse Mercado Livre", id_externo="A")
        b = lanc("Inter PJ", "2026-10-09", 2000, "Repasse Mercado Livre", id_externo="B")
        feitas, _, _, _ = motor_repasses.casar([r], [a, b], hoje=HOJE)

        self.assertEqual(len(feitas), 1)
        self.assertEqual(len(feitas[0].lancamentos), 2)
        self.assertEqual(r.status, REPASSE_RECEBIDO)

    def test_match_exato_tem_prioridade_sobre_o_agrupado(self):
        exato = rep("shopee", "2026-10-09", 3000, id_externo="EXATO")
        outros = [rep("shopee", "2026-10-09", 1000, id_externo="X"),
                  rep("shopee", "2026-10-09", 2000, id_externo="Y")]
        credito = lanc("Inter PJ", "2026-10-09", 3000, "Repasse Shopee")
        feitas, _, _, _ = motor_repasses.casar([exato] + outros, [credito], hoje=HOJE)

        self.assertEqual(len(feitas), 1)
        self.assertEqual(feitas[0].repasse, exato)
        self.assertTrue(all(r.status == REPASSE_AGUARDANDO for r in outros))

    def test_excesso_de_candidatos_avisa_em_vez_de_calar(self):
        muitos = [rep("shopee", "2026-10-09", 1, id_externo=f"R{i}") for i in range(15)]
        credito = lanc("Inter PJ", "2026-10-09", 15, "Repasse Shopee")
        feitas, _, _, avisos = motor_repasses.casar(muitos, [credito], hoje=HOJE)

        self.assertEqual(feitas, [])
        self.assertTrue(any("não tentado" in a for a in avisos))


class TestToleranciaEAlerta(unittest.TestCase):
    def test_centavo_de_diferenca_casa_mas_pede_conferencia(self):
        r = rep("shopee", "2026-10-09", 1000.00)
        credito = lanc("Inter PJ", "2026-10-09", 999.97, "Repasse Shopee")
        feitas, _, _, _ = motor_repasses.casar([r], [credito], hoje=HOJE)

        self.assertEqual(len(feitas), 1)
        self.assertEqual(feitas[0].confianca, Decimal("0.70"))
        self.assertFalse(feitas[0].automatica)
        self.assertEqual(r.status, REPASSE_DIVERGENTE)

    def test_diferenca_grande_nao_e_arredondamento(self):
        r = rep("shopee", "2026-10-09", 1000.00)
        credito = lanc("Inter PJ", "2026-10-09", 900.00, "Repasse Shopee")
        feitas, _, nao_recebidos, _ = motor_repasses.casar([r], [credito], hoje=HOJE)
        self.assertEqual(feitas, [])
        self.assertEqual(len(nao_recebidos), 1)

    def test_repasse_vencido_vira_alerta(self):
        # Previsto 09/10 (sexta) + 3 dias úteis = 14/10. Em 20/10, atrasou.
        r = rep("shopee", "2026-10-09", 3000)
        _, _, nao_recebidos, _ = motor_repasses.casar([r], [], hoje=HOJE)
        self.assertEqual(nao_recebidos, [r])

    def test_dentro_do_prazo_ainda_nao_alerta(self):
        r = rep("shopee", "2026-10-09", 3000)
        _, _, nao_recebidos, _ = motor_repasses.casar([r], [], hoje=dia("2026-10-13"))
        self.assertEqual(nao_recebidos, [])


class TestDecomposicao(unittest.TestCase):
    def test_bruto_menos_deducoes_fecha_no_liquido(self):
        r = rep("shopee", "2026-10-09", 3412.80, bruto=4100, taxas=600, frete=87.20)
        self.assertEqual(r.confere(), Decimal("0"))

    def test_decomposicao_que_nao_fecha_aparece(self):
        r = rep("shopee", "2026-10-09", 3000, bruto=4100, taxas=600, frete=87.20)
        self.assertNotEqual(r.confere(), Decimal("0"))


if __name__ == "__main__":
    unittest.main()
