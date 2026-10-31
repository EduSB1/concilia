#!/usr/bin/env python3
"""
mp_auditoria.py — Protótipo v0.2 de auditoria do Mercado Pago
==============================================================

Objetivo: responder "para onde foi o meu dinheiro?" cruzando
  VENDIDO (bruto) → TAXAS → LÍQUIDO → LIBERADO → SACADO / DEBITADO

Dois modos de uso:

  1) Pela API (pagamentos recebidos no período):
       python mp_auditoria.py api --inicio 2026-09-01 --fim 2026-09-30

  2) Pelo relatório de liberações exportado do Mercado Pago (CSV):
       python mp_auditoria.py csv caminho/relatorio_liberacoes.csv

  O modo "csv" é o que acha dinheiro "sumido", porque o relatório de
  liberações mostra TODOS os movimentos do saldo (saques, débitos de
  frete/tarifa, retenções, chargebacks...), não só os pagamentos.

Saídas na pasta ./saida/:
  resumo_liberacoes.txt   → (modo csv) visão geral com os totais
  resumo_pagamentos.txt   → (modo api) visão geral dos pagamentos
  pagamentos.csv          → (modo api) um pagamento por linha, já classificado
  movimentos.csv          → (modo csv) todos os movimentos normalizados
  suspeitos.csv           → (modo csv) débitos que NÃO são saque: onde investigar
  saques.csv              → (modo csv) saques, para cruzar com o extrato do Inter
  taxas_divergentes.csv   → (modo csv) entradas em que bruto − taxa ≠ creditado

ESBOÇO: nomes de campos e colunas foram escritos a partir da documentação
pública do Mercado Pago e PRECISAM ser conferidos com dados reais.
Procure por "TODO" no código.

Requisitos: Python 3.10+ e `pip install requests` (só para o modo api)
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, asdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

API_BASE = "https://api.mercadopago.com"
PASTA_SAIDA = Path("saida")
FUSO = "-03:00"  # horário de Brasília

ZERO = Decimal("0")
CEM = Decimal("100")
TOLERANCIA = Decimal("0.02")  # centavos de arredondamento aceitos na conferência


# ---------------------------------------------------------------------------
# Problemas encontrados na leitura
# ---------------------------------------------------------------------------
# Numa ferramenta que existe para achar dinheiro sumido, engolir erro em
# silêncio é o pior defeito possível: um valor ilegível viraria R$ 0,00 e
# sumiria do total sem ninguém notar. Tudo que não pôde ser lido com certeza
# entra aqui e aparece em destaque no topo do resumo.

PROBLEMAS: list[str] = []


def avisar(mensagem: str) -> None:
    """Registra algo que o usuário PRECISA ver antes de confiar nos totais."""
    PROBLEMAS.append(mensagem)


def bloco_problemas() -> list[str]:
    if not PROBLEMAS:
        return []
    return [
        "*** ATENÇÃO — PROBLEMAS NA LEITURA ***",
        *(f"  - {p}" for p in PROBLEMAS),
        "  Confira estes pontos antes de confiar nos números abaixo.",
        "",
    ]


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def carregar_env(caminho: str = ".env") -> None:
    """Lê um .env simples (CHAVE=valor) sem depender de biblioteca externa."""
    p = Path(caminho)
    if not p.exists():
        return
    for linha in p.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))


def dinheiro(valor, origem: str = "") -> Decimal:
    """Converte '1.234,56', '1234.56', '(99,90)', 1234.56 ou None em Decimal.

    Nunca usa float. Campo vazio é zero de verdade; campo preenchido mas
    ilegível vira zero para o programa não quebrar, MAS fica registrado em
    PROBLEMAS — senão o valor evaporaria do total sem aviso.
    """
    if valor is None or valor == "":
        return ZERO
    if isinstance(valor, (int, Decimal)):
        return Decimal(valor)
    if isinstance(valor, float):
        return Decimal(str(valor))
    texto = str(valor).strip().replace("R$", "").replace(" ", "")
    if not texto:
        return ZERO
    negativo = texto.startswith("(") and texto.endswith(")")  # (1.234,56) = negativo
    if negativo:
        texto = texto[1:-1]
    if "," in texto and "." in texto:          # 1.234,56
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:                         # 1234,56
        texto = texto.replace(",", ".")
    try:
        convertido = Decimal(texto)
    except InvalidOperation:
        avisar(f"valor ilegível {valor!r}{origem} — contado como R$ 0,00")
        return ZERO
    return -convertido if negativo else convertido


def data_iso(texto: str) -> str:
    """Extrai AAAA-MM-DD de '2026-09-01T10:12:00-03:00' ou de '01/09/2026'."""
    t = (texto or "").strip()
    if not t:
        return ""
    if "/" in t[:10]:                                   # 01/09/2026
        partes = t[:10].split("/")
        if len(partes) == 3 and len(partes[2]) == 4:
            dia, mes, ano = partes
            return f"{ano}-{mes.zfill(2)}-{dia.zfill(2)}"
    return t[:10]


def brl(valor: Decimal) -> str:
    """Formata Decimal como R$ 1.234,56."""
    sinal = "-" if valor < 0 else ""
    inteiro, _, cent = f"{abs(valor):.2f}".partition(".")
    inteiro = f"{int(inteiro):,}".replace(",", ".")
    return f"{sinal}R$ {inteiro},{cent}"


def salvar_csv(caminho: Path, linhas: list[dict]) -> None:
    """Grava CSV com ';' e BOM para abrir direto no Excel em português."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    if not linhas:
        caminho.write_text("(vazio)\n", encoding="utf-8-sig")
        return
    with caminho.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()), delimiter=";")
        w.writeheader()
        for l in linhas:
            w.writerow({k: (str(v).replace(".", ",") if isinstance(v, Decimal) else v)
                        for k, v in l.items()})


# ---------------------------------------------------------------------------
# Cliente da API do Mercado Pago
# ---------------------------------------------------------------------------

class MercadoPago:
    def __init__(self, token: str):
        import requests  # import aqui para o modo csv funcionar sem requests
        self.http = requests.Session()
        self.http.headers.update({"Authorization": f"Bearer {token}"})

    def _get(self, caminho: str, params: dict | None = None) -> dict:
        for tentativa in range(5):
            r = self.http.get(API_BASE + caminho, params=params, timeout=30)
            if r.status_code == 429 or r.status_code >= 500:
                # 429 = limite de requisições; 5xx = instabilidade do lado deles.
                # Nos dois casos, esperar e tentar de novo (RNF-07).
                time.sleep(2 ** tentativa)
                continue
            r.raise_for_status()
            return r.json()
        raise RuntimeError(f"Mercado Pago não respondeu após 5 tentativas em {caminho}")

    def meu_id(self) -> int:
        return self._get("/users/me")["id"]

    def pagamentos(self, inicio: str, fim: str):
        """Itera todos os pagamentos criados no período (paginado)."""
        offset, limite = 0, 100
        while True:
            dados = self._get("/v1/payments/search", {
                "sort": "date_created",
                "criteria": "asc",
                "range": "date_created",
                "begin_date": f"{inicio}T00:00:00.000{FUSO}",
                "end_date": f"{fim}T23:59:59.999{FUSO}",
                "limit": limite,
                "offset": offset,
            })
            resultados = dados.get("results", [])
            yield from resultados
            total = dados.get("paging", {}).get("total", 0)
            offset += limite
            if offset >= total or not resultados:
                break
            if offset >= 1000:
                # A busca tem teto de offset. Avisar em vez de truncar calado.
                avisar(f"período com mais de 1.000 pagamentos ({total}): "
                       "a lista foi truncada — rode semana a semana")
                break
            # TODO: quebrar o período em janelas menores automaticamente.

    # TODO (fase seguinte): baixar o relatório de liberações direto pela API
    # (criar relatório → aguardar ficar pronto → baixar o arquivo), em vez de
    # exportar manualmente. Conferir endpoints em "Relatório de liberações"
    # na documentação do Mercado Pago.


# ---------------------------------------------------------------------------
# MODO API — pagamentos recebidos
# ---------------------------------------------------------------------------

@dataclass
class Pagamento:
    id: str
    data_criacao: str
    data_liberacao: str
    status: str
    status_detalhe: str
    status_liberacao: str
    situacao: str               # nossa classificação
    bruto: Decimal
    taxas: Decimal
    liquido: Decimal
    reembolsado: Decimal
    descricao: str
    referencia_externa: str
    pedido: str


def classificar_pagamento(status: str, status_liberacao: str) -> str:
    if status == "approved":
        return "liberado" if status_liberacao == "released" else "a_liberar"
    return {
        "refunded": "estornado",
        "charged_back": "chargeback",
        "in_mediation": "em_mediacao",
        "cancelled": "cancelado",
        "rejected": "rejeitado",
        "pending": "pendente",
        "in_process": "pendente",
        "authorized": "pendente",
    }.get(status, f"outro:{status}")


def normalizar_pagamento(p: dict) -> Pagamento:
    # Taxas pagas pelo VENDEDOR (collector). TODO: conferir se em pagamentos
    # do Mercado Livre as tarifas vêm aqui ou em "charges_details".
    onde = f" (pagamento {p.get('id')})"
    taxas = sum((dinheiro(f.get("amount"), onde) for f in p.get("fee_details") or []
                 if f.get("fee_payer") == "collector"), ZERO)
    bruto = dinheiro(p.get("transaction_amount"), onde)
    liquido = dinheiro((p.get("transaction_details") or {}).get("net_received_amount"), onde)
    if liquido == ZERO and bruto:
        liquido = bruto - taxas
    status = p.get("status", "")
    status_lib = p.get("money_release_status") or ""
    return Pagamento(
        id=str(p.get("id")),
        data_criacao=data_iso(p.get("date_created") or ""),
        data_liberacao=data_iso(p.get("money_release_date") or ""),
        status=status,
        status_detalhe=p.get("status_detail") or "",
        status_liberacao=status_lib,
        situacao=classificar_pagamento(status, status_lib),
        bruto=bruto,
        taxas=taxas,
        liquido=liquido,
        reembolsado=dinheiro(p.get("transaction_amount_refunded"), onde),
        descricao=(p.get("description") or "")[:80],
        referencia_externa=p.get("external_reference") or "",
        pedido=str((p.get("order") or {}).get("id") or ""),
    )


def modo_api(inicio: str, fim: str) -> None:
    carregar_env()
    token = os.environ.get("MP_ACCESS_TOKEN")
    if not token:
        sys.exit("Defina MP_ACCESS_TOKEN no arquivo .env (veja .env.example).")

    mp = MercadoPago(token)
    eu = mp.meu_id()
    print(f"Conta Mercado Pago: {eu} · período {inicio} a {fim}")

    pagamentos: list[Pagamento] = []
    for bruto in mp.pagamentos(inicio, fim):
        # Mantém só pagamentos que VOCÊ recebeu (não compras que você fez).
        if (bruto.get("collector_id") or (bruto.get("collector") or {}).get("id")) != eu:
            continue
        pagamentos.append(normalizar_pagamento(bruto))

    por_situacao: dict[str, Decimal] = defaultdict(lambda: ZERO)
    qtd: dict[str, int] = defaultdict(int)
    for p in pagamentos:
        por_situacao[p.situacao] += p.liquido
        qtd[p.situacao] += 1

    aprovados = [p for p in pagamentos if p.status == "approved"]
    linhas = [
        f"AUDITORIA MERCADO PAGO (pagamentos) — {inicio} a {fim}",
        "=" * 60,
        f"Pagamentos recebidos no período: {len(pagamentos)}",
        "",
        *bloco_problemas(),
        f"Vendido (bruto, aprovados):  {brl(sum((p.bruto for p in aprovados), ZERO))}",
        f"Taxas pagas por você:       -{brl(sum((p.taxas for p in aprovados), ZERO))}",
        f"Líquido (aprovados):         {brl(sum((p.liquido for p in aprovados), ZERO))}",
        "",
        "Líquido por situação:",
    ]
    for sit in sorted(por_situacao):
        linhas.append(f"  {sit:<15} {qtd[sit]:>5} pgto(s)   {brl(por_situacao[sit])}")
    linhas += [
        "",
        "ATENÇÃO: este modo mostra só PAGAMENTOS. Débitos de frete, tarifas do",
        "Mercado Livre, Mercado Crédito, retenções e saques só aparecem no",
        "relatório de liberações → rode também o modo 'csv'.",
    ]

    PASTA_SAIDA.mkdir(exist_ok=True)
    salvar_csv(PASTA_SAIDA / "pagamentos.csv", [asdict(p) for p in pagamentos])
    (PASTA_SAIDA / "resumo_pagamentos.txt").write_text("\n".join(linhas), encoding="utf-8")
    print("\n".join(linhas))
    print(f"\nArquivos gerados em ./{PASTA_SAIDA}/")


# ---------------------------------------------------------------------------
# MODO CSV — relatório de liberações (todos os movimentos do saldo)
# ---------------------------------------------------------------------------

# Nomes possíveis de cada coluna. O export pode vir em inglês ou português,
# e o layout muda conforme a configuração do relatório.
# TODO: abrir um relatório real e completar/ajustar esta lista.
MAPA_COLUNAS = {
    "data":        ["DATE", "DATA", "Data", "Fecha"],
    "id_origem":   ["SOURCE_ID", "ID_ORIGEM", "ID da operação", "ID DA OPERAÇÃO"],
    "referencia":  ["EXTERNAL_REFERENCE", "REFERENCIA_EXTERNA", "Referência externa"],
    "tipo":        ["DESCRIPTION", "DESCRICAO", "Descrição", "DESCRIÇÃO"],
    "credito":     ["NET_CREDIT_AMOUNT", "CREDITO_LIQUIDO", "Valor líquido creditado"],
    "debito":      ["NET_DEBIT_AMOUNT", "DEBITO_LIQUIDO", "Valor líquido debitado"],
    "bruto":       ["GROSS_AMOUNT", "VALOR_BRUTO", "Valor bruto"],
    "taxa_mp":     ["MP_FEE_AMOUNT", "TARIFA_MP", "Tarifa do Mercado Pago"],
    "saldo":       ["BALANCE_AMOUNT", "SALDO", "Saldo"],
}
# TODO: o relatório real costuma separar outras deduções em colunas próprias
# (frete, antecipação, impostos, cupom). Enquanto não forem mapeadas, elas
# entram no cálculo apenas pela diferença bruto − creditado, e por isso
# aparecem como divergência na conferência de cobrança.

# Tradução dos tipos de movimento.
# TODO: confirmar a lista com um relatório real; o que não estiver aqui
# aparece como "desconhecido" e vai direto para suspeitos.csv.
TIPOS_MOVIMENTO = {
    "payment":                 "Venda / pagamento recebido",
    "refund":                  "Devolução ao comprador",
    "chargeback":              "Chargeback (contestação no cartão)",
    "mediation":               "Mediação / reclamação",
    "reserve_for_dispute":     "Dinheiro retido por disputa",
    "reserve_for_payout":      "Dinheiro reservado",
    "withdrawal":              "Saque / transferência para banco",
    "withdrawal_cancel":       "Saque cancelado (devolvido ao saldo)",
    "shipping":                "Frete / envio",
    "fee":                     "Tarifa",
    "credit_payment":          "Pagamento de Mercado Crédito",
    "initial_available_balance": "Saldo inicial",
}
TIPO_SAQUE = {"withdrawal"}


@dataclass
class Movimento:
    data: str
    id_origem: str
    referencia: str
    tipo: str
    tipo_pt: str
    credito: Decimal
    debito: Decimal
    liquido: Decimal
    bruto: Decimal
    taxa_mp: Decimal
    saldo: Decimal
    liquido_esperado: Decimal   # bruto − taxa, só em entradas
    diferenca_taxa: Decimal     # creditado − esperado; ≠ 0 = cobrança a conferir


def localizar_colunas(cabecalho: list[str]) -> dict[str, str | None]:
    limpo = {c.strip().lstrip("\ufeff"): c for c in cabecalho}
    achadas = {}
    for campo, candidatos in MAPA_COLUNAS.items():
        achadas[campo] = next((limpo[c] for c in candidatos if c in limpo), None)
    obrigatorias = ["data", "tipo", "credito", "debito"]
    faltando = [c for c in obrigatorias if not achadas[c]]
    if faltando:
        sys.exit(
            f"Não encontrei as colunas {faltando} no CSV.\n"
            f"Colunas do arquivo: {list(limpo)}\n"
            "→ Ajuste MAPA_COLUNAS no topo da seção 'MODO CSV' e rode de novo."
        )
    return achadas


def ordenar_por_data(movs: list[Movimento]) -> list[Movimento]:
    """Garante a ordem cronológica antes de qualquer cálculo de saldo.

    O export do Mercado Pago costuma vir do mais recente para o mais antigo.
    A prova real lê o saldo inicial na primeira linha e o final na última:
    invertida, ela acusa uma diferença que não existe. Inverter a lista
    inteira preserva a ordem dentro do mesmo dia, que um sort só por
    AAAA-MM-DD perderia.
    """
    datas = [m.data for m in movs if m.data]
    if len(datas) > 1 and datas[0] > datas[-1]:
        movs = list(reversed(movs))
        avisar("relatório veio do mais recente para o mais antigo — "
               "ordem invertida para o cálculo")
        datas = [m.data for m in movs if m.data]
    if datas != sorted(datas):
        avisar("datas fora de ordem no relatório — "
               "a prova real do saldo pode não fechar por causa disso")
    return movs


def ler_relatorio(caminho: Path) -> list[Movimento]:
    texto = caminho.read_text(encoding="utf-8-sig", errors="replace")
    try:
        dialeto = csv.Sniffer().sniff(texto[:5000], delimiters=";,\t")
    except csv.Error:
        dialeto = csv.excel
    leitor = csv.DictReader(texto.splitlines(), dialect=dialeto)
    col = localizar_colunas(leitor.fieldnames or [])

    def pega(linha, campo):
        nome = col.get(campo)
        return linha.get(nome, "") if nome else ""

    movimentos: list[Movimento] = []
    com_sinal_negativo = 0
    for n, linha in enumerate(leitor, start=2):      # 2 = primeira linha de dados
        tipo = (pega(linha, "tipo") or "").strip()
        if not tipo:
            continue
        onde = f" na linha {n}"
        cred_lido = dinheiro(pega(linha, "credito"), onde)
        deb_lido = dinheiro(pega(linha, "debito"), onde)
        # O relatório às vezes traz o débito já com sinal negativo. Sem
        # normalizar, os totais e a prova real do saldo saem invertidos.
        if cred_lido < ZERO or deb_lido < ZERO:
            com_sinal_negativo += 1
        cred, deb = abs(cred_lido), abs(deb_lido)
        bruto = dinheiro(pega(linha, "bruto"), onde)
        taxa = dinheiro(pega(linha, "taxa_mp"), onde)
        liquido = cred - deb

        # Conferência de cobrança: bruto − taxa deveria ser o que foi creditado.
        # Só vale para ENTRADAS: em débitos a composição varia (um estorno
        # devolve a taxa, frete tem regra própria, ajustes não têm bruto).
        # TODO: estender a refunds e chargebacks com um relatório real em mãos.
        if cred > ZERO and bruto != ZERO:
            esperado = abs(bruto) - abs(taxa)
            diferenca = liquido - esperado
        else:
            esperado, diferenca = ZERO, ZERO

        movimentos.append(Movimento(
            data=data_iso(pega(linha, "data")),
            id_origem=pega(linha, "id_origem"),
            referencia=pega(linha, "referencia"),
            tipo=tipo,
            tipo_pt=TIPOS_MOVIMENTO.get(tipo.lower(), f"DESCONHECIDO ({tipo})"),
            credito=cred,
            debito=deb,
            liquido=liquido,
            bruto=bruto,
            taxa_mp=taxa,
            saldo=dinheiro(pega(linha, "saldo"), onde),
            liquido_esperado=esperado,
            diferenca_taxa=diferenca,
        ))

    if com_sinal_negativo:
        avisar(f"{com_sinal_negativo} linha(s) com crédito/débito negativo — "
               "sinal normalizado para o cálculo")
    return ordenar_por_data(movimentos)


def bloco_vendas_e_taxas(movs: list[Movimento]) -> list[str]:
    """Mostra quanto foi vendido, quanto o MP ficou e o que sobrou.

    É a resposta à pergunta que o relatório sozinho não responde: lançar só o
    líquido esconde a taxa. Aqui ela fica visível e vira um percentual que dá
    para comparar mês a mês.
    """
    entradas = [m for m in movs if m.credito > ZERO and m.bruto != ZERO]
    if not entradas:
        return []
    bruto = sum((abs(m.bruto) for m in entradas), ZERO)
    taxas = sum((abs(m.taxa_mp) for m in entradas), ZERO)
    creditado = sum((m.credito for m in entradas), ZERO)
    pct = (taxas / bruto * CEM).quantize(Decimal("0.01")) if bruto else ZERO
    pct_br = f"{pct}".replace(".", ",")
    return [
        "O QUE VOCÊ VENDEU E O QUE SOBROU",
        f"  Vendido (bruto):        {brl(bruto):>16}   em {len(entradas)} entrada(s)",
        f"  Taxas do Mercado Pago:  {brl(-taxas):>16}   ({pct_br}% do bruto)",
        f"  Creditado no saldo:     {brl(creditado):>16}",
        "",
    ]


def bloco_conferencia_taxas(movs: list[Movimento]) -> tuple[list[str], list[Movimento]]:
    """Confere, entrada a entrada, se bruto − taxa = o que foi creditado.

    Sem isto, uma taxa cobrada a mais passa despercebida: o relatório fecha
    certinho com ela, porque o saldo acompanha o que o MP cobrou.
    """
    conferidas = [m for m in movs if m.credito > ZERO and m.bruto != ZERO]
    if not conferidas:
        return [], []
    divergentes = sorted(
        (m for m in conferidas if abs(m.diferenca_taxa) > TOLERANCIA),
        key=lambda m: abs(m.diferenca_taxa), reverse=True,
    )
    linhas = [
        "CONFERÊNCIA DE COBRANÇA  (bruto − taxa = creditado?)",
        f"  {len(conferidas)} entrada(s) conferida(s)",
    ]
    if not divergentes:
        linhas.append("  ✅ todas batem")
    else:
        total = sum((m.diferenca_taxa for m in divergentes), ZERO)
        verbo = "NÃO bate" if len(divergentes) == 1 else "NÃO batem"
        linhas += [
            f"  ⚠️  {len(divergentes)} {verbo} · diferença total {brl(total)}",
            "  → cobrança a conferir com o Mercado Pago (taxas_divergentes.csv):",
        ]
        for m in divergentes[:10]:
            linhas.append(
                f"    {m.data}  esperado {brl(m.liquido_esperado):>14}  "
                f"creditado {brl(m.credito):>14}  "
                f"dif {brl(m.diferenca_taxa):>12}  (id {m.id_origem})"
            )
    linhas.append("")
    return linhas, divergentes


def bloco_prova_real(movs: list[Movimento], total_cred: Decimal,
                     total_deb: Decimal) -> list[str]:
    """saldo inicial + créditos − débitos deve ser igual ao saldo final."""
    if not any(m.saldo for m in movs):
        # Não dá para fazer a prova — e isso precisa ser dito, não omitido.
        return [
            "PROVA REAL DO SALDO",
            "  não foi possível: o relatório não trouxe a coluna de saldo",
            "  → exporte de novo incluindo o saldo para conferir se falta linha",
            "",
        ]
    saldo_ini = movs[0].saldo - movs[0].liquido
    saldo_fim = movs[-1].saldo
    esperado = saldo_ini + total_cred - total_deb
    diferenca = saldo_fim - esperado
    return [
        "PROVA REAL DO SALDO",
        f"  Saldo inicial (calculado): {brl(saldo_ini)}",
        f"  + Créditos:                {brl(total_cred)}",
        f"  − Débitos:                 {brl(total_deb)}",
        f"  = Saldo esperado:          {brl(esperado)}",
        f"  Saldo final no relatório:  {brl(saldo_fim)}",
        f"  DIFERENÇA:                 {brl(diferenca)}"
        + ("   ✅ bate" if diferenca == ZERO else "   ⚠️  NÃO BATE — investigar"),
        "",
    ]


def modo_csv(caminho: str) -> None:
    arquivo = Path(caminho)
    if not arquivo.exists():
        sys.exit(f"Arquivo não encontrado: {arquivo}")
    movs = ler_relatorio(arquivo)
    if not movs:
        sys.exit("Nenhum movimento lido. Confira o arquivo e o MAPA_COLUNAS.")

    # Totais por tipo de movimento
    grupos: dict[str, dict] = defaultdict(lambda: {"qtd": 0, "credito": ZERO, "debito": ZERO})
    for m in movs:
        g = grupos[m.tipo_pt]
        g["qtd"] += 1
        g["credito"] += m.credito
        g["debito"] += m.debito

    total_cred = sum((m.credito for m in movs), ZERO)
    total_deb = sum((m.debito for m in movs), ZERO)
    saques = [m for m in movs if m.tipo.lower() in TIPO_SAQUE]
    suspeitos = sorted(
        (m for m in movs if m.debito > 0 and m.tipo.lower() not in TIPO_SAQUE),
        key=lambda m: m.debito, reverse=True,
    )
    linhas_taxas, divergentes = bloco_conferencia_taxas(movs)

    linhas = [
        f"AUDITORIA MERCADO PAGO (relatório de liberações) — {arquivo.name}",
        "=" * 60,
        f"Movimentos lidos: {len(movs)}  ·  de {movs[0].data} a {movs[-1].data}",
        "",
        *bloco_problemas(),
        "POR TIPO DE MOVIMENTO",
        f"  {'Tipo':<38}{'Qtd':>5}{'Créditos':>16}{'Débitos':>16}",
    ]
    for nome, g in sorted(grupos.items(), key=lambda kv: -(kv[1]["credito"] + kv[1]["debito"])):
        linhas.append(f"  {nome[:37]:<38}{g['qtd']:>5}{brl(g['credito']):>16}{brl(g['debito']):>16}")
    linhas += [
        f"  {'TOTAL':<38}{len(movs):>5}{brl(total_cred):>16}{brl(total_deb):>16}",
        "",
        *bloco_vendas_e_taxas(movs),
        *linhas_taxas,
        *bloco_prova_real(movs, total_cred, total_deb),
        f"SAQUES PARA BANCO: {len(saques)} · {brl(sum((m.debito for m in saques), ZERO))}",
        "  → conferir cada um no extrato do Inter (saques.csv)",
        "",
        f"DÉBITOS QUE NÃO SÃO SAQUE: {len(suspeitos)} · "
        f"{brl(sum((m.debito for m in suspeitos), ZERO))}",
        "  → é aqui que dinheiro 'some'. Maiores primeiro:",
    ]
    for m in suspeitos[:10]:
        linhas.append(f"    {m.data}  {brl(m.debito):>14}  {m.tipo_pt}  (id {m.id_origem})")

    PASTA_SAIDA.mkdir(exist_ok=True)
    salvar_csv(PASTA_SAIDA / "movimentos.csv", [asdict(m) for m in movs])
    salvar_csv(PASTA_SAIDA / "suspeitos.csv", [asdict(m) for m in suspeitos])
    salvar_csv(PASTA_SAIDA / "saques.csv", [asdict(m) for m in saques])
    salvar_csv(PASTA_SAIDA / "taxas_divergentes.csv", [asdict(m) for m in divergentes])
    (PASTA_SAIDA / "resumo_liberacoes.txt").write_text("\n".join(linhas), encoding="utf-8")
    print("\n".join(linhas))
    print(f"\nArquivos gerados em ./{PASTA_SAIDA}/")


# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Auditoria do Mercado Pago (protótipo)")
    sub = ap.add_subparsers(dest="modo", required=True)

    a = sub.add_parser("api", help="Busca pagamentos recebidos pela API")
    a.add_argument("--inicio", required=True, help="AAAA-MM-DD")
    a.add_argument("--fim", required=True, help="AAAA-MM-DD")

    c = sub.add_parser("csv", help="Analisa o relatório de liberações exportado")
    c.add_argument("arquivo")

    args = ap.parse_args()
    if args.modo == "api":
        modo_api(args.inicio, args.fim)
    else:
        modo_csv(args.arquivo)


if __name__ == "__main__":
    main()
