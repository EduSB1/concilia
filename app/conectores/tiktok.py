"""Conector para TikTok Shop Partner API."""

import os
import hmac
import hashlib
from datetime import date, datetime
from decimal import Decimal
import requests
from typing import Optional

from app.conectores import ConectorBase, Transacao


class TikTokShopAPI(ConectorBase):
    """
    TikTok Shop — vendas via Partner API.
    
    Autenticação: Authorization Code flow (OAuth 2.0)
    + Client Key + Client Secret
    """

    BASE_URL = "https://open-api.tiktokglobalshop.com"

    def __init__(
        self,
        client_key: Optional[str] = None,
        client_secret: Optional[str] = None,
        access_token: Optional[str] = None,
        shop_cipher: Optional[str] = None,
    ):
        """
        Inicializar conector TikTok Shop.

        Args:
            client_key: Client ID da aplicação TikTok
            client_secret: Client Secret da aplicação TikTok
            access_token: Access token OAuth (obtido via flow)
            shop_cipher: Identificador único da loja (cifra)
        """
        self.client_key = client_key or os.getenv("TIKTOK_CLIENT_KEY")
        self.client_secret = client_secret or os.getenv("TIKTOK_CLIENT_SECRET")
        self.access_token = access_token or os.getenv("TIKTOK_ACCESS_TOKEN")
        self.shop_cipher = shop_cipher or os.getenv("TIKTOK_SHOP_CIPHER")

        if not all([self.client_key, self.client_secret, self.access_token, self.shop_cipher]):
            raise ValueError(
                "Client Key, Client Secret, Access Token e Shop Cipher obrigatórios. "
                "Use os parâmetros ou env vars TIKTOK_*"
            )

    def _gerar_assinatura(self, timestamp: str, nonce: str, body: str = "") -> str:
        """
        Gerar assinatura HMAC-SHA256 para TikTok Shop API.

        Args:
            timestamp: ISO 8601 timestamp
            nonce: Random nonce string
            body: Request body (JSON)

        Returns:
            Assinatura base64
        """
        base_string = f"{body}{nonce}{timestamp}"
        signature = hmac.new(
            self.client_secret.encode(),
            base_string.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature

    def autenticar(self) -> bool:
        """
        Testar autenticação consultando loja.

        Returns:
            True se conseguiu autenticar
        """
        try:
            import uuid
            from datetime import datetime as dt
            
            timestamp = dt.utcnow().isoformat() + "Z"
            nonce = str(uuid.uuid4())
            signature = self._gerar_assinatura(timestamp, nonce)

            headers = {
                "Content-Type": "application/json",
                "x-tiktok-access-token": self.access_token,
                "x-api-source": "menus",
                "x-timestamp": timestamp,
                "x-request-id": nonce,
                "Authorization": f"Bearer {self.access_token}",
            }

            response = requests.post(
                f"{self.BASE_URL}/shop/api/auth/shop/get",
                headers=headers,
                timeout=10,
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Erro ao autenticar no TikTok Shop: {e}")
            return False

    def listar_contas(self) -> list[dict]:
        """
        Listar lojas/contas conectadas.

        Returns:
            Lista de {id, nome, tipo}
        """
        try:
            import uuid
            from datetime import datetime as dt

            timestamp = dt.utcnow().isoformat() + "Z"
            nonce = str(uuid.uuid4())

            headers = {
                "Content-Type": "application/json",
                "x-tiktok-access-token": self.access_token,
                "x-api-source": "menus",
                "x-timestamp": timestamp,
                "x-request-id": nonce,
                "Authorization": f"Bearer {self.access_token}",
            }

            response = requests.post(
                f"{self.BASE_URL}/shop/api/auth/shop/get",
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()

            data = response.json()
            shop = data.get("data", {}).get("shop", {})
            return [{
                "id": self.shop_cipher,
                "nome": shop.get("shop_name", "Loja TikTok"),
                "tipo": "marketplace",
            }]
        except Exception as e:
            print(f"Erro ao listar lojas TikTok: {e}")
            return []

    def extrato(self, data_inicio: date, data_fim: date) -> list[Transacao]:
        """
        Puxar extrato de vendas do período.

        Utiliza endpoint /order/search para encontrar pedidos.

        Args:
            data_inicio: Data inicial (YYYY-MM-DD)
            data_fim: Data final (YYYY-MM-DD)

        Returns:
            Lista de Transacao normalizadas
        """
        try:
            import uuid
            from datetime import datetime as dt

            transacoes = []
            cursor = ""
            
            # Paginar através dos pedidos
            while True:
                timestamp = dt.utcnow().isoformat() + "Z"
                nonce = str(uuid.uuid4())
                
                payload = {
                    "create_time_from": int(datetime.combine(data_inicio, datetime.min.time()).timestamp()),
                    "create_time_to": int(datetime.combine(data_fim, datetime.max.time()).timestamp()),
                    "order_status": "COMPLETED",
                    "page_size": 100,
                    "cursor": cursor,
                }
                
                import json
                body_str = json.dumps(payload)
                signature = self._gerar_assinatura(timestamp, nonce, body_str)

                headers = {
                    "Content-Type": "application/json",
                    "x-tiktok-access-token": self.access_token,
                    "x-api-source": "menus",
                    "x-timestamp": timestamp,
                    "x-request-id": nonce,
                    "Authorization": f"Bearer {self.access_token}",
                    "x-sign": signature,
                }

                response = requests.post(
                    f"{self.BASE_URL}/shop/api/orders",
                    headers=headers,
                    json=payload,
                    timeout=10,
                )
                response.raise_for_status()

                data = response.json()
                orders = data.get("data", {}).get("orders", [])

                if not orders:
                    break

                for order in orders:
                    valor = Decimal("0")
                    for item in order.get("line_items", []):
                        valor += Decimal(str(item.get("sale_price", 0)))

                    order_time = datetime.fromtimestamp(order.get("create_time", 0))
                    transacao = Transacao(
                        data=order_time.date(),
                        valor=valor,  # + entrada (venda)
                        descricao=f"Venda TikTok Shop #{order.get('order_id', '')}",
                        contraparte=order.get("buyer_username", ""),
                        id_externo=str(order.get("order_id", "")),
                        fonte="tiktok_api",
                        tags=order,
                    )
                    transacoes.append(transacao)

                # Verificar se há mais páginas
                cursor = data.get("data", {}).get("next_cursor", "")
                if not cursor:
                    break

            return transacoes
        except Exception as e:
            print(f"Erro ao puxar extrato TikTok Shop: {e}")
            return []
