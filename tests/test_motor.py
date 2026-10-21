"""Motor completo: um dia de movimento das 3 contas do piloto."""

import unittest
from decimal import Decimal

from apoio import dia, lanc, rep
from app.motor import conciliar
from app.normalizacao.modelos import STATUS_CONCILIADO

HOJE = dia("2026-10-20")


def cenario():
    """Dia típico: um repasse que caiu, um saque, despesas e um repasse atrasado."""
    lancamentos = [
        # repasse Shopee que caiu certinho
        lanc("Inter PJ", "2026-10-09", 3412.80, "Repasse Shopee", id_externo="L1"),
        # saque do Mercado Pago para o Inter (transferência interna)
        lanc("Mercado Pago", "2026-10-09", -5000, "Saque para conta bancária", id_externo="L2"),
        lanc("Inter PJ", "2026-10-09", 5000, "Transferência recebida Mercado Pago", id_externo="L3"),
        # despesas do dia
        lanc("Inter PJ", "2026-10-09", -32.50, "Débito Uber *trip", id_externo="L4"),
        lanc("Inter PJ", "2026-10-09", -980.00, "DAS Simples Nacional", id_externo="L5"),
        # rendimento do CDB
        lanc("Inter PJ", "2026-10-09", 14.22, "Rendimento aplicação automática", id_externo="L6"),
        # pagamento a fornecedor: nenhuma regra cobre
        lanc("Inter PJ", "2026-10-09", -2400.00, "Pix enviado", contraparte="JOAO", id_externo="L7"),
    ]
    repasses = [
        rep("shopee", "2026-10-09", 3412.80, bruto=4100, taxas=600, frete=87.20, id_externo="R1"),
        rep("tiktok", "2026-10-08", 1850.00, id_externo="R2"),   # não caiu
    ]
    return lancamentos, repasses


class TestMotor(unittest.TestCase):
    def setUp(self):
        self.lancamentos, self.repasses = cenario()
        self.resultado = conciliar(self.lancamentos, self.repasses, hoje=HOJE)

    def test_fecha_repasse_e_transferencia(self):
        por_tipo = {}
        for c in self.resultado.conciliacoes:
            por_tipo.setdefault(c.tipo, []).append(c)
        self.assertEqual(len(por_tipo["repasse"]), 1)
        self.assertEqual(len(por_tipo["transferencia_interna"]), 1)

    def test_tres_lancamentos_ficam_conciliados(self):
        # o crédito do repasse + as duas pontas da transferência
        conciliados = [l.id_externo for l in self.lancamentos if l.status == STATUS_CONCILIADO]
        self.assertEqual(sorted(conciliados), ["L1", "L2", "L3"])

    def test_repasse_que_nao_caiu_vira_alerta(self):
        alertas = [a for a in self.resultado.alertas if a.tipo == "repasse_nao_recebido"]
        self.assertEqual(len(alertas), 1)
        self.assertEqual(alertas[0].item.marketplace, "tiktok")

    def test_o_que_sobrou_tem_categoria_ou_vai_para_a_fila(self):
        pendentes = [l for l in self.lancamentos if l.status != STATUS_CONCILIADO]
        self.assertEqual(len(pendentes), 4)                     # L4, L5, L6, L7
        sem_categoria = [l.id_externo for l in pendentes if not l.categoria]
        self.assertEqual(sem_categoria, ["L7"])                 # o Pix para o João

    def test_pendencia_do_pix_explica_o_motivo(self):
        motivos = [p.motivo for p in self.resultado.pendencias]
        self.assertIn("nenhuma regra de categoria casou", motivos)

    def test_taxa_automatica_e_contada_por_lancamento(self):
        # 3 de 7 lançamentos fechados sozinhos.
        self.assertEqual(self.resultado.taxa_automatica, Decimal("42.9"))

    def test_rodar_duas_vezes_nao_duplica_conciliacao(self):
        de_novo = conciliar(self.lancamentos, self.repasses, hoje=HOJE)
        repasses_fechados = [c for c in de_novo.conciliacoes if c.tipo == "repasse"]
        self.assertEqual(repasses_fechados, [])


if __name__ == "__main__":
    unittest.main()
