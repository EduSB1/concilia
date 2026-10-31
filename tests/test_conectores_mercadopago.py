"""Testes do conector Mercado Pago."""

import unittest
from datetime import date
from decimal import Decimal
from app.conectores.mercadopago import MercadoPagoAPI


class TestMercadoPagoAPI(unittest.TestCase):
    """Testes do conector Mercado Pago."""

    def test_init_com_token(self):
        """Testar inicialização com token."""
        api = MercadoPagoAPI(access_token="TEST_TOKEN")
        self.assertIsNotNone(api)
        self.assertEqual(api.access_token, "TEST_TOKEN")

    def test_init_sem_token_falha(self):
        """Testar que falha sem token."""
        with self.assertRaises(ValueError):
            MercadoPagoAPI()

    def test_headers_com_bearer(self):
        """Testar que headers têm Bearer token."""
        api = MercadoPagoAPI(access_token="TEST_123")
        self.assertIn("Authorization", api.headers)
        self.assertTrue(api.headers["Authorization"].startswith("Bearer "))

    def test_transacao_formato(self):
        """Testar formato de transação normalizada."""
        from app.conectores import Transacao

        t = Transacao(
            data=date(2026, 10, 23),
            valor=Decimal("-150.00"),  # saída
            descricao="Compra em loja",
            contraparte="cliente@email.com",
            id_externo="MP-999888",
            fonte="mercadopago_api",
        )

        self.assertEqual(t.data, date(2026, 10, 23))
        self.assertEqual(t.valor, Decimal("-150.00"))
        self.assertEqual(t.fonte, "mercadopago_api")


if __name__ == "__main__":
    unittest.main()
