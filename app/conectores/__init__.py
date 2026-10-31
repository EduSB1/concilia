"""Conectores de API — padrão único de saída."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

@dataclass
class Transacao:
    """Formato normalizado de transação de qualquer fonte."""
    data: date
    valor: Decimal  # + entrada / - saída
    descricao: str
    contraparte: str = ""
    id_externo: str = ""  # chave única por fonte para idempotência
    fonte: str = ""  # inter_api, mercadopago_api, shopee_api, tiktok_api
    tags: dict = None  # dados brutos da API para debug


class ConectorBase(ABC):
    """Todo conector deve seguir essa interface."""

    @abstractmethod
    def autenticar(self) -> bool:
        """Retorna True se autenticação funcionou."""
        pass

    @abstractmethod
    def extrato(self, data_inicio: date, data_fim: date) -> list[Transacao]:
        """Retorna todas as transações no período."""
        pass

    @abstractmethod
    def listar_contas(self) -> list[dict]:
        """Retorna {id, nome, tipo} de cada conta conectada."""
        pass


__all__ = ["Transacao", "ConectorBase"]
