"""Conector para Mercado Pago via API oficial."""

import os
from datetime import date, datetime, timedelta
from decimal import Decimal
import requests
from typing import Optional

from app.conectores import ConectorBase, Transacao


class MercadoPagoAPI(ConectorBase):
    """
    Mercado Pago — pagamentos e recebimentos via API oficial.
    
    Autenticação: Bearer token (Access Token)
    """

    BASE_URL = "https://api.mercadopago.com/v1"

    def __init__(self, access_token: Optional[str] = None):
        """
        Inicializar conector Mercado Pago.

        Args:
            access_token: Token de acesso MP. Se None, lê de MP_ACCESS_TOKEN (env)
        """
        self.access_token = access_token or os.getenv("MP_ACCESS_TOKEN")
        if not self.access_token:
            raise ValueError("Access token obrigatório. Use access_token= ou MP_ACCESS_TOKEN")

        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def autenticar(self) -> bool:
        """
        Testar autenticação consultando conta.

        Returns:
            True se conseguiu autenticar
        """
        try:
            response = requests.get(
                f"{self.BASE_URL}/accounts/me",
                headers=self.headers,
                timeout=10,
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Erro ao autenticar no Mercado Pago: {e}")
            return False

    def listar_contas(self) -> list[dict]:
        """
        Listar contas/usuários conectados.

        Returns:
            Lista de {id, nome, tipo, saldo}
        """
        try:
            response = requests.get(
                f"{self.BASE_URL}/accounts/me",
                headers=self.headers,
                timeout=10,
            )
            response.raise_for_status()

            data = response.json()
            return [{
                "id": data.get("id", ""),
                "nome": data.get("name", "Mercado Pago"),
                "tipo": "wallet",
                "email": data.get("email", ""),
                "saldo": Decimal("0"),  # MP não retorna saldo direto na API
            }]
        except Exception as e:
            print(f"Erro ao listar contas Mercado Pago: {e}")
            return []

    def extrato(self, data_inicio: date, data_fim: date) -> list[Transacao]:
        """
        Puxar extrato de pagamentos do período.

        Utiliza Search API para encontrar pagamentos por data de criação.

        Args:
            data_inicio: Data inicial (YYYY-MM-DD)
            data_fim: Data final (YYYY-MM-DD)

        Returns:
            Lista de Transacao normalizadas
        """
        try:
            # Convertido para timestamps Unix (em ms)
            ts_inicio = int(datetime.combine(data_inicio, datetime.min.time()).timestamp() * 1000)
            ts_fim = int(datetime.combine(data_fim + timedelta(days=1), datetime.min.time()).timestamp() * 1000)

            transacoes = []
            offset = 0
            limit = 100

            # Paginar através dos resultados
            while True:
                response = requests.get(
                    f"{self.BASE_URL}/payments/search",
                    headers=self.headers,
                    params={
                        "range": "date_created",
                        "begin_date": ts_inicio,
                        "end_date": ts_fim,
                        "offset": offset,
                        "limit": limit,
                        "sort": "date_created",
                        "criteria": "desc",
                    },
                    timeout=10,
                )
                response.raise_for_status()

                data = response.json()
                pagamentos = data.get("results", [])

                if not pagamentos:
                    break

                for pag in pagamentos:
                    # Determinar direção (entrada ou saída)
                    status = pag.get("status", "")
                    if status != "approved":
                        continue  # Ignorar pagamentos não aprovados

                    # + entrada / - saída
                    valor = Decimal(str(pag.get("transaction_amount", 0)))
                    if pag.get("operation_type") == "payment":
                        valor = -valor

                    transacao = Transacao(
                        data=datetime.fromisoformat(pag.get("date_created", "")[:19]).date(),
                        valor=valor,
                        descricao=pag.get("description", "Mercado Pago"),
                        contraparte=pag.get("payer", {}).get("email", ""),
                        id_externo=str(pag.get("id", "")),
                        fonte="mercadopago_api",
                        tags=pag,
                    )
                    transacoes.append(transacao)

                offset += limit

                # Se retornou menos que limit, foi a última página
                if len(pagamentos) < limit:
                    break

            return transacoes
        except Exception as e:
            print(f"Erro ao puxar extrato Mercado Pago: {e}")
            return []
