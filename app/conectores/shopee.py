"""Conector para Shopee Open Platform."""

import os
import hmac
import hashlib
from datetime import date
from decimal import Decimal
import requests
from typing import Optional

from app.conectores import ConectorBase, Transacao


class ShopeeAPI(ConectorBase):
    """
    Shopee — vendas e comissões via Open Platform.
    
    Autenticação: Partner ID + Partner Key (HMAC-SHA256)
    + Access Token de loja
    """

    BASE_URL = "https://partner.shopeemx.com/api/v2"
    # Mudar region conforme necessário: shopeemx.com (MX), shopeeapi.com (BR/LATAM)

    def __init__(
        self,
        partner_id: Optional[str] = None,
        partner_key: Optional[str] = None,
        access_token: Optional[str] = None,
    ):
        """
        Inicializar conector Shopee.

        Args:
            partner_id: ID da aplicação (Partner ID)
            partner_key: Chave privada (Partner Key)
            access_token: Token de acesso da loja
        """
        self.partner_id = partner_id or os.getenv("SHOPEE_PARTNER_ID")
        self.partner_key = partner_key or os.getenv("SHOPEE_PARTNER_KEY")
        self.access_token = access_token or os.getenv("SHOPEE_ACCESS_TOKEN")

        if not all([self.partner_id, self.partner_key, self.access_token]):
            raise ValueError(
                "Partner ID, Partner Key e Access Token obrigatórios. "
                "Use os parâmetros ou env vars SHOPEE_PARTNER_ID, SHOPEE_PARTNER_KEY, SHOPEE_ACCESS_TOKEN"
            )

    def _gerar_assinatura(self, path: str, timestamp: int) -> str:
        """
        Gerar assinatura HMAC-SHA256 para autenticação Shopee.

        Args:
            path: Endpoint da API
            timestamp: Unix timestamp

        Returns:
            Hex da assinatura
        """
        base_string = f"{path}{self.access_token}{self.partner_id}{timestamp}"
        signature = hmac.new(
            self.partner_key.encode(),
            base_string.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature

    def autenticar(self) -> bool:
        """
        Testar autenticação consultando shop.

        Returns:
            True se conseguiu autenticar
        """
        try:
            # Chamar endpoint simples para validar credenciais
            import time
            timestamp = int(time.time())
            path = "/shop/get_shop_info"
            signature = self._gerar_assinatura(path, timestamp)

            headers = {
                "Content-Type": "application/json",
                "X-API-Source": "menus",
            }

            response = requests.post(
                f"{self.BASE_URL}{path}",
                headers=headers,
                params={
                    "partner_id": self.partner_id,
                    "timestamp": timestamp,
                    "access_token": self.access_token,
                    "sign": signature,
                },
                timeout=10,
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Erro ao autenticar no Shopee: {e}")
            return False

    def listar_contas(self) -> list[dict]:
        """
        Listar lojas/contas conectadas.

        Returns:
            Lista de {id, nome, tipo}
        """
        try:
            import time
            timestamp = int(time.time())
            path = "/shop/get_shop_info"
            signature = self._gerar_assinatura(path, timestamp)

            headers = {
                "Content-Type": "application/json",
                "X-API-Source": "menus",
            }

            response = requests.post(
                f"{self.BASE_URL}{path}",
                headers=headers,
                params={
                    "partner_id": self.partner_id,
                    "timestamp": timestamp,
                    "access_token": self.access_token,
                    "sign": signature,
                },
                timeout=10,
            )
            response.raise_for_status()

            data = response.json()
            shop_info = data.get("response", {})
            return [{
                "id": shop_info.get("shop_id", ""),
                "nome": shop_info.get("shop_name", "Loja Shopee"),
                "tipo": "marketplace",
            }]
        except Exception as e:
            print(f"Erro ao listar lojas Shopee: {e}")
            return []

    def extrato(self, data_inicio: date, data_fim: date) -> list[Transacao]:
        """
        Puxar extrato de vendas e comissões do período.

        Utiliza endpoint /order/get_order_list com filtro de datas.

        Args:
            data_inicio: Data inicial (YYYY-MM-DD)
            data_fim: Data final (YYYY-MM-DD)

        Returns:
            Lista de Transacao normalizadas
        """
        try:
            import time
            timestamp = int(time.time())
            path = "/order/get_order_list"

            transacoes = []
            cursor = ""

            # Paginar através dos pedidos
            while True:
                signature = self._gerar_assinatura(path, timestamp)

                headers = {
                    "Content-Type": "application/json",
                    "X-API-Source": "menus",
                }

                payload = {
                    "data": {
                        "cursor": cursor,
                        "pagination_entries_per_page": 100,
                        "order_status": "COMPLETED",  # Apenas pedidos completos
                    }
                }

                response = requests.post(
                    f"{self.BASE_URL}{path}",
                    headers=headers,
                    json=payload,
                    params={
                        "partner_id": self.partner_id,
                        "timestamp": timestamp,
                        "access_token": self.access_token,
                        "sign": signature,
                    },
                    timeout=10,
                )
                response.raise_for_status()

                data = response.json()
                orders = data.get("response", {}).get("orders", [])

                if not orders:
                    break

                for order in orders:
                    # Apenas incluir vendas no período
                    order_date = date.fromtimestamp(order.get("create_time", 0))
                    if not (data_inicio <= order_date <= data_fim):
                        continue

                    # Valor total do pedido (sem descontos da plataforma por enquanto)
                    valor = Decimal(str(order.get("original_price", 0)))

                    transacao = Transacao(
                        data=order_date,
                        valor=valor,  # + entrada (venda)
                        descricao=f"Venda Shopee #{order.get('order_sn', '')}",
                        contraparte=order.get("buyer_username", ""),
                        id_externo=str(order.get("order_id", "")),
                        fonte="shopee_api",
                        tags=order,
                    )
                    transacoes.append(transacao)

                # Verificar se há mais páginas
                cursor = data.get("response", {}).get("next_cursor", "")
                if not cursor:
                    break

            return transacoes
        except Exception as e:
            print(f"Erro ao puxar extrato Shopee: {e}")
            return []
