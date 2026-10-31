"""Atalhos para montar cenários nos testes do app."""

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.normalizacao.modelos import Lancamento, Repasse   # noqa: E402


def dia(texto: str) -> date:
    ano, mes, d = texto.split("-")
    return date(int(ano), int(mes), int(d))


def lanc(conta, data, valor, descricao="", contraparte="", id_externo="", fonte="teste"):
    return Lancamento(
        conta=conta, data=dia(data), valor=Decimal(str(valor)),
        descricao=descricao, contraparte=contraparte,
        id_externo=id_externo, fonte=fonte,
    )


def rep(marketplace, data_prevista, liquido, bruto=0, taxas=0, frete=0,
        estornos=0, id_externo=""):
    return Repasse(
        marketplace=marketplace, data_prevista=dia(data_prevista),
        valor_liquido=Decimal(str(liquido)), valor_bruto=Decimal(str(bruto)),
        taxas=Decimal(str(taxas)), frete=Decimal(str(frete)),
        estornos=Decimal(str(estornos)), id_externo=id_externo,
    )
