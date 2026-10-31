"""Conector para Bling v3 API."""

import os
import base64
from datetime import date, datetime
from decimal import Decimal
import requests
from typing import Optional

from app.conectores import ConectorBase, Transacao


class BlingAPI(ConectorBase):
    """
    Bling ERP — notas fiscais de venda e compra via API v3.
    
    Autenticação: OAuth 2.0 (Access Token)
    """

    BASE_URL = "https://bling.com.br/Api/v3"

    def __init__(self, access_token: Optional[str] = None):
        """
        Inicializar conector Bling.

        Args:
            access_token: Token de acesso OAuth. Se None, lê de BLING_ACCESS_TOKEN (env)
        """
        self.access_token = access_token or os.getenv("BLING_ACCESS_TOKEN")
        if not self.access_token:
            raise ValueError(
                "Access token obrigatório. Use access_token= ou BLING_ACCESS_TOKEN"
            )

        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

    def autenticar(self) -> bool:
        """
        Testar autenticação consultando dados da empresa.

        Returns:
            True se conseguiu autenticar
        """
        try:
            response = requests.get(
                f"{self.BASE_URL}/empresa",
                headers=self.headers,
                timeout=10,
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Erro ao autenticar no Bling: {e}")
            return False

    def listar_contas(self) -> list[dict]:
        """
        Listar empresas/filiais conectadas.

        Returns:
            Lista de {id, nome, tipo}
        """
        try:
            response = requests.get(
                f"{self.BASE_URL}/empresa",
                headers=self.headers,
                timeout=10,
            )
            response.raise_for_status()

            data = response.json()
            empresa = data.get("data", {})
            return [{
                "id": empresa.get("id", ""),
                "nome": empresa.get("nome", "Empresa Bling"),
                "tipo": "erp",
                "cnpj": empresa.get("cnpj", ""),
            }]
        except Exception as e:
            print(f"Erro ao listar empresas Bling: {e}")
            return []

    def extrato(self, data_inicio: date, data_fim: date) -> list[Transacao]:
        """
        Puxar extrato de notas fiscais de venda do período.

        Utiliza endpoint /notasfiscais com filtro de datas.

        Args:
            data_inicio: Data inicial (YYYY-MM-DD)
            data_fim: Data final (YYYY-MM-DD)

        Returns:
            Lista de Transacao normalizadas (vendas)
        """
        try:
            transacoes = []
            page = 1

            # Paginar através das notas fiscais
            while True:
                response = requests.get(
                    f"{self.BASE_URL}/notasfiscais",
                    headers=self.headers,
                    params={
                        "dataEmissaoInicio": data_inicio.isoformat(),
                        "dataEmissaoFim": data_fim.isoformat(),
                        "tipo": "NF",  # Apenas notas fiscais de venda
                        "pagina": page,
                        "limite": 100,
                    },
                    timeout=10,
                )
                response.raise_for_status()

                data = response.json()
                notas = data.get("data", [])

                if not notas:
                    break

                for nota in notas:
                    # Apenas notas com status enviada ou autorizada
                    status = nota.get("status", "")
                    if status not in ["Enviada", "Autorizada"]:
                        continue

                    # Valor total da nota
                    valor = Decimal(str(nota.get("totalNota", 0)))

                    transacao = Transacao(
                        data=datetime.fromisoformat(nota.get("dataEmissao", "")[:10]).date(),
                        valor=valor,  # + entrada (venda)
                        descricao=f"NF #{nota.get('numeroNota', '')}",
                        contraparte=nota.get("cliente", {}).get("nome", ""),
                        id_externo=str(nota.get("id", "")),
                        fonte="bling_api",
                        tags=nota,
                    )
                    transacoes.append(transacao)

                # Se retornou menos que 100, foi a última página
                if len(notas) < 100:
                    break

                page += 1

            return transacoes
        except Exception as e:
            print(f"Erro ao puxar extrato Bling: {e}")
            return []
