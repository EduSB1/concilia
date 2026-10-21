# Concilia

Conciliação bancária para vendedores de marketplace: junta o que o
**marketplace diz que pagou**, o que **caiu no banco** e o que está
**lançado no ERP**, e aponta o que não bate.

Documentos do projeto: [`SPEC.md`](SPEC.md) (o quê) e
[`ROADMAP.md`](ROADMAP.md) (quando).

| Fase | Entrega | Situação |
|---|---|---|
| 0 | Auditoria do Mercado Pago (`prototipo/`) | código pronto; **falta rodar sobre o relatório real do piloto** |
| 1 | Motor de conciliação + modelo de dados (`app/`, `migrations/`) | em andamento — motor e migrations prontos; conectores pendentes |
| 2 | Lançamento automático no Bling | não começou |

---

## Fase 1 — o motor (`app/`)

Só biblioteca padrão do Python 3.11+. Sem banco, sem token, sem rede.

```bash
python3 -m app.demo        # roda um dia fictício e imprime o painel
```

O demo mostra as quatro etapas trabalhando: transferência interna entre
Mercado Pago e Inter, repasse Shopee casado no valor exato, dois repasses
do Mercado Livre que o banco recebeu **somados** num crédito só, despesas
categorizadas por regra, um repasse do TikTok que **não caiu** (alerta) e
um Pix que nenhuma regra cobriu (fila de pendências).

### Como o motor decide

Da ligação mais segura para a mais frouxa, cada uma com sua confiança
(SPEC seção 7). Abaixo de **0,80** o item vai para a fila de pendências —
nunca é decidido sozinho.

| Etapa | O que faz | Confiança |
|---|---|---|
| 1. Transferência interna | saída na conta A = entrada na conta B, D0/D+1 | 0,95 (0,75 sem pista no texto) |
| 2a. Repasse exato | crédito = líquido, dentro de ±2 dias úteis | 0,95 |
| 2b. Repasse agrupado | N repasses somam 1 crédito, ou 1 repasse cai fracionado | 0,80 |
| 2c. Tolerância | diferença de até R$ 0,05 (arredondamento) | 0,70 + sinalização |
| 3. Regra de categoria | padrão de texto, menor prioridade avaliada primeiro | 0,90 |
| 4. Sugestão de IA | ainda não implementada | máx. 0,60 (sempre vai para pendências) |

### Mapa das pastas

| Caminho | Conteúdo |
|---|---|
| `app/dinheiro.py`, `app/datas.py` | Decimal (nunca float) e janela de dias úteis |
| `app/normalizacao/` | formato único de lançamento + idempotência na reimportação |
| `app/motor/` | as etapas acima e o orquestrador |
| `app/relatorios/` | painel de texto (a tela vem depois) |
| `migrations/001_inicial.sql` | esquema PostgreSQL do SPEC seção 6 |
| `prototipo/` | Fase 0: auditoria do Mercado Pago |

O motor **não grava nada**: recebe listas, devolve o que decidiu. É o que
permite rodá-lo inteiro sobre o dataset de teste sem subir banco.

---

## Fase 0 — auditoria do Mercado Pago (`prototipo/`)

Responde: **para onde foi o meu dinheiro no Mercado Pago?**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # cole seu token no .env

# teste com dados de exemplo (não precisa de token):
python prototipo/mp_auditoria.py csv prototipo/exemplo_relatorio_liberacoes.csv

# com o relatório real (Mercado Pago > Relatório de liberações > CSV):
python prototipo/mp_auditoria.py csv meu_relatorio.csv

# pela API (pagamentos recebidos):
python prototipo/mp_auditoria.py api --inicio 2026-09-01 --fim 2026-09-30
```

O exemplo tem R$ 3.000 "sumidos" escondidos — veja se o resumo acha.
Se der erro de coluna, o script mostra as colunas do arquivo → ajuste
`MAPA_COLUNAS` no código.

O resumo traz: totais por tipo de movimento; bruto, taxas e o % efetivo
que o Mercado Pago ficou; conferência entrada a entrada de
`bruto − taxa = creditado`; prova real do saldo; e saques × débitos que
não são saque — onde o dinheiro costuma sumir. Valor que o script não
conseguiu ler aparece **no topo**, antes dos totais: nada é descartado em
silêncio.

Saídas em `saida/`: `resumo_liberacoes.txt`, `resumo_pagamentos.txt`,
`suspeitos.csv`, `saques.csv`, `taxas_divergentes.csv`, `movimentos.csv`
e `pagamentos.csv`.

---

## Testes

Sem dependência nenhuma:

```bash
python3 -m unittest discover -s tests -v
```

Os casos em `tests/dados/` têm um problema plantado de propósito
(relatório invertido, débito negativo, linha faltando, valor ilegível,
taxa errada, relatório sem saldo). Os testes do motor cobrem as formas
conhecidas de o dinheiro não bater: crédito somado, crédito fracionado,
centavo de diferença, repasse que não caiu e dois candidatos idênticos.

## Avisos

- O protótipo é um **esboço**: nomes de campos e colunas precisam ser
  conferidos com dados reais (procure `TODO`).
- A conferência de cobrança só vale para **entradas**. Em débitos a
  composição varia (estorno devolve a taxa, frete tem regra própria).
- Use token **só seu** para testar. Nunca suba o `.env`.
- Extratos reais têm dados pessoais de terceiros (LGPD): o `.gitignore`
  ignora todo `.csv` por padrão.
