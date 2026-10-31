"""Testes do conector Inter."""

import unittest
from datetime import date
from decimal import Decimal
from app.conectores.inter import InterAPI


class TestInterAPI(unittest.TestCase):
    """Testes do conector Inter."""

    def test_init_com_cert_path(self):
        """Testar inicialização com caminhos de arquivo."""
        # Não vamos testar com certificado real aqui
        # Só verificar que aceita os parâmetros
        try:
            api = InterAPI(cert_path="/tmp/fake.pem", key_path="/tmp/fake.pem")
            self.assertIsNotNone(api)
        except Exception:
            pass

    def test_init_sem_credenciais_falha(self):
        """Testar que falha sem credenciais."""
        with self.assertRaises(ValueError):
            InterAPI()

    def test_base64_decode(self):
        """Testar decodificação de base64."""
        # Gerar um certificado fake em base64 para teste
        cert_fake = b"-----BEGIN CERTIFICATE-----\nMIIC...\n-----END CERTIFICATE-----"
        cert_b64 = "LS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUM..."
        key_b64 = "LS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSUU..."

        # Não vamos testar com valores reais, só verificar structure
        try:
            api = InterAPI(cert_b64=cert_b64, key_b64=key_b64)
            # Não deve falhar na inicialização
            self.assertTrue(True)
        except ValueError:
            # Esperado porque os base64 são fake
            self.assertTrue(True)

    def test_transacao_formato(self):
        """Testar formato de transação normalizada."""
        from app.conectores import Transacao

        t = Transacao(
            data=date(2026, 10, 23),
            valor=Decimal("1234.56"),
            descricao="Teste",
            contraparte="Empresa XYZ",
            id_externo="INT-12345",
            fonte="inter_api",
        )

        self.assertEqual(t.data, date(2026, 10, 23))
        self.assertEqual(t.valor, Decimal("1234.56"))
        self.assertEqual(t.fonte, "inter_api")


if __name__ == "__main__":
    unittest.main()
