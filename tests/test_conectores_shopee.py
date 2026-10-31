"""Testes do conector Shopee."""

import unittest
from datetime import date
from decimal import Decimal
from app.conectores.shopee import ShopeeAPI


class TestShopeeAPI(unittest.TestCase):
    """Testes do conector Shopee."""

    def test_init_com_credenciais(self):
        """Testar inicialização com credenciais."""
        api = ShopeeAPI(
            partner_id="123456",
            partner_key="secret_key",
            access_token="shop_token",
        )
        self.assertIsNotNone(api)

    def test_init_sem_credenciais_falha(self):
        """Testar que falha sem credenciais."""
        with self.assertRaises(ValueError):
            ShopeeAPI()

    def test_assinatura_hmac(self):
        """Testar geração de assinatura HMAC."""
        api = ShopeeAPI(
            partner_id="123",
            partner_key="secret",
            access_token="token",
        )
        sig = api._gerar_assinatura("/test/path", 1234567890)
        self.assertIsNotNone(sig)
        self.assertTrue(len(sig) == 64)  # SHA256 hex

    def test_transacao_formato(self):
        """Testar formato de transação normalizada."""
        from app.conectores import Transacao

        t = Transacao(
            data=date(2026, 10, 23),
            valor=Decimal("299.90"),
            descricao="Venda Shopee #12345",
            contraparte="buyer_name",
            id_externo="SHP-88888",
            fonte="shopee_api",
        )

        self.assertEqual(t.data, date(2026, 10, 23))
        self.assertEqual(t.valor, Decimal("299.90"))
        self.assertEqual(t.fonte, "shopee_api")


if __name__ == "__main__":
    unittest.main()
