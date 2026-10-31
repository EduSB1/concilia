"""Testes do conector Bling."""

import unittest
from datetime import date
from decimal import Decimal
from app.conectores.bling import BlingAPI


class TestBlingAPI(unittest.TestCase):
    """Testes do conector Bling."""

    def test_init_com_token(self):
        """Testar inicialização com token."""
        api = BlingAPI(access_token="TEST_TOKEN_BLING")
        self.assertIsNotNone(api)
        self.assertEqual(api.access_token, "TEST_TOKEN_BLING")

    def test_init_sem_token_falha(self):
        """Testar que falha sem token."""
        with self.assertRaises(ValueError):
            BlingAPI()

    def test_headers_com_bearer(self):
        """Testar que headers têm Bearer token."""
        api = BlingAPI(access_token="TEST_999")
        self.assertIn("Authorization", api.headers)
        self.assertTrue(api.headers["Authorization"].startswith("Bearer "))

    def test_transacao_formato(self):
        """Testar formato de transação normalizada."""
        from app.conectores import Transacao

        t = Transacao(
            data=date(2026, 10, 23),
            valor=Decimal("5000.00"),
            descricao="NF #123456",
            contraparte="Cliente LTDA",
            id_externo="BLG-555555",
            fonte="bling_api",
        )

        self.assertEqual(t.data, date(2026, 10, 23))
        self.assertEqual(t.valor, Decimal("5000.00"))
        self.assertEqual(t.fonte, "bling_api")


if __name__ == "__main__":
    unittest.main()
