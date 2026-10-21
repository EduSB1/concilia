"""Roda o motor sobre um dia fictício e imprime o painel.

    python3 -m app.demo

Serve para ver a Fase 1 funcionando sem banco, sem token e sem API — e
para ter um número de referência de conciliação automática antes de
plugar os dados reais.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.motor import conciliar
from app.normalizacao.modelos import Lancamento, Repasse
from app.relatorios import painel


def _l(conta, dia, valor, descricao, contraparte="", id_externo=""):
    return Lancamento(
        conta=conta, data=date(2026, 10, dia), valor=Decimal(str(valor)),
        descricao=descricao, contraparte=contraparte, id_externo=id_externo,
        fonte="demo",
    )


def _r(marketplace, dia, liquido, bruto=0, taxas=0, frete=0, id_externo=""):
    return Repasse(
        marketplace=marketplace, data_prevista=date(2026, 10, dia),
        valor_liquido=Decimal(str(liquido)), valor_bruto=Decimal(str(bruto)),
        taxas=Decimal(str(taxas)), frete=Decimal(str(frete)), id_externo=id_externo,
    )


def cenario():
    lancamentos = [
        _l("Inter PJ", 9, "3412.80", "Repasse Shopee", id_externo="L1"),
        _l("Inter PJ", 9, "5000.00", "Transferência recebida Mercado Pago", id_externo="L2"),
        _l("Mercado Pago", 9, "-5000.00", "Saque para conta bancária", id_externo="L3"),
        _l("Inter PJ", 9, "2990.00", "Repasse Mercado Livre", id_externo="L4"),
        _l("Inter PJ", 9, "-32.50", "Débito Uber *trip", id_externo="L5"),
        _l("Inter PJ", 9, "-980.00", "DAS Simples Nacional", id_externo="L6"),
        _l("Inter PJ", 9, "14.22", "Rendimento aplicação automática", id_externo="L7"),
        _l("Inter PJ", 9, "-2400.00", "Pix enviado", "JOAO DA SILVA", id_externo="L8"),
    ]
    repasses = [
        _r("shopee", 9, "3412.80", bruto="4100.00", taxas="600.00", frete="87.20", id_externo="R1"),
        # dois repasses do ML que o banco recebeu somados: 1990 + 1000 = 2990
        _r("mercado_livre", 9, "1990.00", id_externo="R2"),
        _r("mercado_livre", 9, "1000.00", id_externo="R3"),
        # TikTok previsto para o dia 8 e que não caiu em conta nenhuma
        _r("tiktok", 8, "1850.00", id_externo="R4"),
    ]
    return lancamentos, repasses


def main() -> None:
    lancamentos, repasses = cenario()
    resultado = conciliar(lancamentos, repasses, hoje=date(2026, 10, 20))
    print(painel(resultado))


if __name__ == "__main__":
    main()
