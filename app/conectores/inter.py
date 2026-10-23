"""Conector para Banco Inter PJ via API oficial com mTLS."""

import base64
import os
import tempfile
from datetime import date
from decimal import Decimal
import requests
from typing import Optional

from app.conectores import ConectorBase, Transacao


class InterAPI(ConectorBase):
    """
    Banco Inter PJ — extrato via API oficial.
    
    Autenticação: certificado mTLS (cert.pem + key.pem)
    """

    BASE_URL = "https://api.inter.co/gateway/v1"

    def __init__(
        self,
        cert_path: Optional[str] = None,
        key_path: Optional[str] = None,
        cert_b64: Optional[str] = None,
        key_b64: Optional[str] = None,
    ):
        """
        Inicializar conector Inter.

        Opções de autenticação:
        1. Caminhos diretos: cert_path="/path/to/cert.pem", key_path="/path/to/key.pem"
        2. Base64 (para Render): cert_b64="base64...", key_b64="base64..."
        3. Variáveis de ambiente: INTER_CERT_B64, INTER_KEY_B64

        Args:
            cert_path: Caminho para arquivo .pem do certificado
            key_path: Caminho para arquivo .pem da chave privada
            cert_b64: Certificado em base64
            key_b64: Chave em base64
        """
        self.cert_path = cert_path
        self.key_path = key_path

        # Se vem em base64, decodificar e salvar em temp
        if cert_b64 or key_b64:
            cert_b64 = cert_b64 or os.getenv("INTER_CERT_B64", "")
            key_b64 = key_b64 or os.getenv("INTER_KEY_B64", "")

            if cert_b64 and key_b64:
                self._setup_from_base64(cert_b64, key_b64)
            else:
                raise ValueError(
                    "Se usar base64, ambos INTER_CERT_B64 e INTER_KEY_B64 são obrigatórios"
                )

        # Se não tem caminhos, tentar env vars
        if not self.cert_path:
            self.cert_path = os.getenv("INTER_CERT_PATH")
        if not self.key_path:
            self.key_path = os.getenv("INTER_KEY_PATH")

        if not self.cert_path or not self.key_path:
            raise ValueError(
                "Certificado e chave privada obrigatórios. "
                "Use cert_path + key_path OU cert_b64 + key_b64"
            )

        self._session = None

    def _setup_from_base64(self, cert_b64: str, key_b64: str) -> None:
        """Decodificar base64 e salvar em arquivos temporários."""
        try:
            cert_data = base64.b64decode(cert_b64)
            key_data = base64.b64decode(key_b64)

            # Salvar em temp (Render vai limpar automaticamente)
            cert_file = tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".pem")
            cert_file.write(cert_data)
            cert_file.close()

            key_file = tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".pem")
            key_file.write(key_data)
            key_file.close()

            self.cert_path = cert_file.name
            self.key_path = key_file.name
        except Exception as e:
            raise ValueError(f"Erro ao decodificar base64: {e}")

    def autenticar(self) -> bool:
        """
        Testar autenticação fazendo uma chamada simples.

        Returns:
            True se conseguiu autenticar
        """
        try:
            response = requests.get(
                f"{self.BASE_URL}/accounts",
                cert=(self.cert_path, self.key_path),
                timeout=10,
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Erro ao autenticar no Inter: {e}")
            return False

    def listar_contas(self) -> list[dict]:
        """
        Listar contas conectadas.

        Returns:
            Lista de {id, nome, tipo, saldo}
        """
        try:
            response = requests.get(
                f"{self.BASE_URL}/accounts",
                cert=(self.cert_path, self.key_path),
                timeout=10,
            )
            response.raise_for_status()

            contas = []
            for conta in response.json().get("accounts", []):
                contas.append({
                    "id": conta.get("id"),
                    "nome": conta.get("name", "Conta Inter"),
                    "tipo": "banco",
                    "saldo": Decimal(str(conta.get("balance", 0))),
                })
            return contas
        except Exception as e:
            print(f"Erro ao listar contas Inter: {e}")
            return []

    def extrato(self, data_inicio: date, data_fim: date) -> list[Transacao]:
        """
        Puxar extrato do período.

        Args:
            data_inicio: Data inicial (YYYY-MM-DD)
            data_fim: Data final (YYYY-MM-DD)

        Returns:
            Lista de Transacao normalizadas
        """
        try:
            contas = self.listar_contas()
            if not contas:
                print("Nenhuma conta encontrada")
                return []

            transacoes = []

            # Puxar extrato de cada conta
            for conta in contas:
                account_id = conta["id"]
                response = requests.get(
                    f"{self.BASE_URL}/accounts/{account_id}/transactions",
                    params={
                        "startDate": data_inicio.isoformat(),
                        "endDate": data_fim.isoformat(),
                    },
                    cert=(self.cert_path, self.key_path),
                    timeout=10,
                )
                response.raise_for_status()

                for transacao_raw in response.json().get("transactions", []):
                    # Normalizar
                    valor = Decimal(str(transacao_raw.get("amount", 0)))
                    if transacao_raw.get("type") == "DEBIT":
                        valor = -valor

                    transacao = Transacao(
                        data=date.fromisoformat(transacao_raw.get("date", "")[:10]),
                        valor=valor,
                        descricao=transacao_raw.get("description", ""),
                        contraparte=transacao_raw.get("counterpart", ""),
                        id_externo=transacao_raw.get("id", ""),
                        fonte="inter_api",
                        tags=transacao_raw,
                    )
                    transacoes.append(transacao)

            return transacoes
        except Exception as e:
            print(f"Erro ao puxar extrato Inter: {e}")
            return []
