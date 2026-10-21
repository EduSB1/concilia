"""Testes do protótipo de auditoria.

Cada caso aqui veio de um defeito real encontrado na v0.1. Roda sem
dependência nenhuma:

    python3 -m unittest discover -s tests -v

Os CSVs de tests/dados/ são derivados do exemplo de prototipo/, cada um com
um problema plantado de propósito.
"""

import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "prototipo"))

import mp_auditoria as mp

DADOS = Path(__file__).resolve().parent / "dados"
EXEMPLO = Path(__file__).resolve().parent.parent / "prototipo" / "exemplo_relatorio_liberacoes.csv"

# Valores de referência do exemplo, conferidos à mão.
CREDITOS = Decimal("9350.00")
DEBITOS = Decimal("9264.90")
SALDO_FINAL = Decimal("85.10")


def ler(caminho):
    """Lê um relatório com a lista de problemas zerada."""
    mp.PROBLEMAS.clear()
    return mp.ler_relatorio(caminho)


def totais(movs):
    return (sum((m.credito for m in movs), mp.ZERO),
            sum((m.debito for m in movs), mp.ZERO))


class TestDinheiro(unittest.TestCase):
    def test_formatos_aceitos(self):
        self.assertEqual(mp.dinheiro("1.234,56"), Decimal("1234.56"))
        self.assertEqual(mp.dinheiro("1234,56"), Decimal("1234.56"))
        self.assertEqual(mp.dinheiro("1234.56"), Decimal("1234.56"))
        self.assertEqual(mp.dinheiro("R$ 99,90"), Decimal("99.90"))
        self.assertEqual(mp.dinheiro("(99,90)"), Decimal("-99.90"))

    def test_vazio_e_zero_de_verdade(self):
        mp.PROBLEMAS.clear()
        self.assertEqual(mp.dinheiro(""), mp.ZERO)
        self.assertEqual(mp.dinheiro(None), mp.ZERO)
        self.assertEqual(mp.PROBLEMAS, [], "campo vazio não é problema")

    def test_valor_ilegivel_nao_passa_calado(self):
        """O pior defeito possível: dinheiro sumir do total sem aviso."""
        mp.PROBLEMAS.clear()
        self.assertEqual(mp.dinheiro("N/A"), mp.ZERO)
        self.assertEqual(len(mp.PROBLEMAS), 1)
        self.assertIn("ilegível", mp.PROBLEMAS[0])

    def test_nunca_usa_float(self):
        self.assertIsInstance(mp.dinheiro(0.1) + mp.dinheiro(0.2), Decimal)
        self.assertEqual(mp.dinheiro("0,1") + mp.dinheiro("0,2"), Decimal("0.3"))


class TestDataIso(unittest.TestCase):
    def test_formatos(self):
        self.assertEqual(mp.data_iso("2026-09-01T10:12:00.000-03:00"), "2026-09-01")
        self.assertEqual(mp.data_iso("01/09/2026"), "2026-09-01")
        self.assertEqual(mp.data_iso("1/9/2026"), "2026-09-01")
        self.assertEqual(mp.data_iso(""), "")


class TestLeituraBase(unittest.TestCase):
    def test_exemplo_sem_problemas(self):
        movs = ler(EXEMPLO)
        self.assertEqual(len(movs), 10)
        self.assertEqual(mp.PROBLEMAS, [])
        self.assertEqual(totais(movs), (CREDITOS, DEBITOS))

    def test_prova_real_fecha(self):
        movs = ler(EXEMPLO)
        texto = "\n".join(mp.bloco_prova_real(movs, *totais(movs)))
        self.assertIn("✅ bate", texto)


class TestOrdemDoRelatorio(unittest.TestCase):
    """Bug v0.1: export do mais recente para o mais antigo dava falso alarme."""

    def test_ordem_e_corrigida(self):
        movs = ler(DADOS / "ordem_decrescente.csv")
        datas = [m.data for m in movs]
        self.assertEqual(datas, sorted(datas))
        self.assertTrue(any("mais recente" in p for p in mp.PROBLEMAS),
                        "a inversão precisa ser avisada")

    def test_mesmo_resultado_nas_duas_ordens(self):
        a = ler(EXEMPLO)
        b = ler(DADOS / "ordem_decrescente.csv")
        self.assertEqual(totais(a), totais(b))
        self.assertIn("✅ bate", "\n".join(mp.bloco_prova_real(b, *totais(b))))


class TestSinalDoDebito(unittest.TestCase):
    """Bug v0.1: NET_DEBIT_AMOUNT negativo invertia todos os totais."""

    def test_sinal_normalizado(self):
        movs = ler(DADOS / "debito_negativo.csv")
        self.assertEqual(totais(movs), (CREDITOS, DEBITOS))
        self.assertTrue(all(m.debito >= 0 for m in movs))
        self.assertTrue(any("negativo" in p for p in mp.PROBLEMAS))

    def test_prova_real_continua_fechando(self):
        movs = ler(DADOS / "debito_negativo.csv")
        self.assertIn("✅ bate", "\n".join(mp.bloco_prova_real(movs, *totais(movs))))

    def test_suspeitos_continuam_aparecendo(self):
        movs = ler(DADOS / "debito_negativo.csv")
        suspeitos = [m for m in movs if m.debito > 0 and m.tipo not in mp.TIPO_SAQUE]
        self.assertEqual(len(suspeitos), 3)


class TestValorIlegivel(unittest.TestCase):
    """Bug v0.1: R$ 3.400 evaporavam do total sem uma palavra."""

    def test_avisa_e_nao_some_calado(self):
        movs = ler(DADOS / "valor_corrompido.csv")
        cred, _ = totais(movs)
        self.assertEqual(cred, CREDITOS - Decimal("3400.00"))
        self.assertTrue(mp.PROBLEMAS, "o total ficou menor e ninguém avisou")
        self.assertIn("ATENÇÃO", "\n".join(mp.bloco_problemas()))


class TestConferenciaDeCobranca(unittest.TestCase):
    """Lacuna v0.1: bruto e taxa eram lidos e nunca conferidos."""

    def test_exemplo_todas_as_taxas_batem(self):
        movs = ler(EXEMPLO)
        linhas, divergentes = mp.bloco_conferencia_taxas(movs)
        self.assertEqual(divergentes, [])
        self.assertIn("✅ todas batem", "\n".join(linhas))

    def test_taxa_cobrada_a_mais_e_pega(self):
        movs = ler(DADOS / "taxa_errada.csv")
        linhas, divergentes = mp.bloco_conferencia_taxas(movs)
        self.assertEqual(len(divergentes), 1)
        self.assertEqual(divergentes[0].diferenca_taxa, Decimal("750.00"))
        self.assertIn("NÃO bate", "\n".join(linhas))

    def test_resumo_de_vendas_e_taxas(self):
        movs = ler(EXEMPLO)
        texto = "\n".join(mp.bloco_vendas_e_taxas(movs))
        self.assertIn("R$ 11.000,00", texto)   # bruto vendido
        self.assertIn("R$ 1.650,00", texto)    # taxas
        self.assertIn("15,00%", texto)         # taxa efetiva (vírgula, pt-BR)


class TestProvaReal(unittest.TestCase):
    def test_linha_faltante_e_detectada(self):
        """O que a prova real existe para pegar: relatório truncado."""
        movs = ler(DADOS / "linha_faltante.csv")
        texto = "\n".join(mp.bloco_prova_real(movs, *totais(movs)))
        self.assertIn("NÃO BATE", texto)
        self.assertIn("3.000,00", texto)

    def test_sem_coluna_de_saldo_avisa(self):
        """Bug v0.1: a prova era pulada em silêncio."""
        movs = ler(DADOS / "sem_saldo.csv")
        texto = "\n".join(mp.bloco_prova_real(movs, *totais(movs)))
        self.assertIn("não foi possível", texto)


class TestFormatacao(unittest.TestCase):
    def test_brl(self):
        self.assertEqual(mp.brl(Decimal("1234.5")), "R$ 1.234,50")
        self.assertEqual(mp.brl(Decimal("-3000")), "-R$ 3.000,00")
        self.assertEqual(mp.brl(mp.ZERO), "R$ 0,00")


if __name__ == "__main__":
    unittest.main(verbosity=2)
