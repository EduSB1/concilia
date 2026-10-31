"""Testes do conector TikTok Shop."""

import unittest
from datetime import date
from decimal import Decimal
from app.conectores.tiktok import TikTokShopAPI


class TestTikTokShopAPI(unittest.TestCase):
    """Testes do conector TikTok Shop."""

    def test_init_com_credenciais(self):
        """Testar inicialização com credenciais."""
        api = TikTokShopAPI(
            client_key="key123",
            client_secret="secret123",
            access_token="token123",
            shop_cipher="shop_cipher_123",
        )
        self.assertIsNotNone(api)

    def test_init_sem_credenciais_falha(self):
        """Testar que falha sem credenciais."""
        with self.assertRaises(ValueError):
            TikTokShopAPI()

    def test_assinatura_hmac(self):
        """Testar geração de assinatura HMAC."""
        api = TikTokShopAPI(
            client_key="key",
            client_secret="secret",
            access_token="token",
            shop_cipher="cipher",
        )
        sig = api._gerar_assinatura("2026-10-23T12:00:00Z", "nonce-123")
        self.assertIsNotNone(sig)
        self.assertTrue(len(sig) == 64)  # SHA256 hex

    def test_transacao_formato(self):
        """Testar formato de transação normalizada."""
        from app.conectores import Transacao

        t = Transacao(
            data=date(2026, 10, 23),
            valor=Decimal("599.99"),
            descricao="Venda TikTok Shop #999",
            contraparte="buyer_username",
            id_externo="TT-777777",
            fonte="tiktok_api",
        )

        self.assertEqual(t.data, date(2026, 10, 23))
        self.assertEqual(t.valor, Decimal("599.99"))
        self.assertEqual(t.fonte, "tiktok_api")


if __name__ == "__main__":
    unittest.main()
