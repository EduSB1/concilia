# Protótipo — Auditoria Mercado Pago

Primeiro passo do projeto (Fase 0 do SPEC.md). Responde: **para onde foi o meu dinheiro no Mercado Pago?**

## Instalar
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env    # depois cole seu token no .env
```

## Usar

**Teste com dados de exemplo** (não precisa de token):
```bash
python mp_auditoria.py csv exemplo_relatorio_liberacoes.csv
```
O exemplo tem R$ 3.000 "sumidos" escondidos — veja se o resumo acha.

**Com o seu relatório real:** no Mercado Pago, exporte o *Relatório de liberações* do período em CSV e rode:
```bash
python mp_auditoria.py csv meu_relatorio.csv
```
Se der erro de coluna, o script mostra as colunas do arquivo → ajuste `MAPA_COLUNAS` no código.

**Pela API (pagamentos recebidos):**
```bash
python mp_auditoria.py api --inicio 2026-09-01 --fim 2026-09-30
```

## O que o resumo mostra

1. **Por tipo de movimento** — para onde o dinheiro foi, agrupado.
2. **O que você vendeu e o que sobrou** — bruto, taxas e o % efetivo que o Mercado Pago ficou. É o número que não aparece quando se lança só o líquido.
3. **Conferência de cobrança** — entrada a entrada, confere se `bruto − taxa = creditado`. Taxa cobrada errada aparece aqui.
4. **Prova real do saldo** — `saldo inicial + créditos − débitos = saldo final`. Se não bater, falta linha no relatório.
5. **Saques × débitos que não são saque** — a segunda lista é onde o dinheiro costuma "sumir".

Qualquer valor que o script **não conseguiu ler** aparece em destaque no topo, antes dos totais. Nada é descartado em silêncio.

## Saídas (pasta `saida/`)
| Arquivo | Conteúdo |
|---|---|
| `resumo_liberacoes.txt` | (modo csv) Totais, taxas, conferência, prova real e maiores suspeitos |
| `resumo_pagamentos.txt` | (modo api) Totais por situação do pagamento |
| `suspeitos.csv` | Débitos que não são saque — onde investigar primeiro |
| `saques.csv` | Saques para conferir no extrato do Inter |
| `taxas_divergentes.csv` | Entradas em que bruto − taxa ≠ creditado |
| `movimentos.csv` / `pagamentos.csv` | Dados normalizados completos |

## Testes

Sem dependência nenhuma:
```bash
python -m unittest discover -s tests -v
```
Cada caso em `tests/dados/` tem um problema plantado de propósito: relatório
em ordem invertida, débito com sinal negativo, linha faltando, valor ilegível,
taxa cobrada errada e relatório sem coluna de saldo.

## Avisos
- É um **esboço**: nomes de campos/colunas precisam ser conferidos com dados reais (procure `TODO`).
- A conferência de cobrança só vale para **entradas**. Em débitos a composição varia (um estorno devolve a taxa, frete tem regra própria).
- Use token **só seu** para testar. Nunca suba o `.env` no Git.
- Extratos reais têm dados pessoais de terceiros (LGPD): o `.gitignore` ignora todo `.csv` por padrão.
