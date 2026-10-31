# Concilia

Motor de conciliação financeira para operações de e-commerce. Sincroniza extratos
bancários, repasses de marketplace e lançamentos de ERP a partir de múltiplas fontes,
cruza entradas e saídas e aponta pendências de cobrança.

## Problema

Quem vende em mais de um canal recebe o dinheiro em lugares diferentes e em prazos
diferentes: o marketplace retém, o adquirente repassa em D+N, o ERP registra o pedido.
Conferir se todo pedido faturado virou dinheiro em conta é trabalho manual e propenso a
erro. O Concilia automatiza essa conferência.

## Estado atual

O núcleo — conectores, persistência e motor de conciliação — está implementado e coberto
por testes. A camada HTTP (`app/api.py`) ainda **não** está operacional: o módulo declara
rotas no estilo FastAPI sem importar o framework nem definir a aplicação, portanto não
sobe como serviço. Até que seja concluída, o motor é acionado programaticamente conforme
o exemplo abaixo.

| Camada | Situação |
| --- | --- |
| Conectores (Inter, Mercado Pago, Bling) | Implementados e testados |
| Conectores (Shopee, TikTok Shop) | Implementados, pendentes de validação com credenciais reais |
| Persistência e migrações | Implementadas |
| Motor de conciliação | Implementado e testado |
| API HTTP | Incompleta — ver `app/api.py` |

## Fontes suportadas

| Fonte | Protocolo | Dados consumidos |
| --- | --- | --- |
| Banco Inter PJ | REST + mTLS | Extrato e saldo de conta corrente |
| Mercado Pago | REST (OAuth) | Liberações, repasses e taxas |
| Bling | REST v3 (OAuth) | Contas a pagar, a receber e pedidos |
| Shopee | Open Platform | Repasses |
| TikTok Shop | Partner API | Repasses |

## Motor de conciliação

O processamento de uma conta percorre quatro estágios em sequência:

1. **Validação** — descarta lançamentos com data, valor ou identificador inconsistentes.
2. **Normalização** — padroniza valores monetários em `Decimal` com `ROUND_HALF_UP` e
   limpa descrições.
3. **Matching** — pareia entradas e saídas correspondentes dentro da janela configurada.
4. **Conferência de cobrança** — sinaliza repasses não recebidos após o prazo em dias
   úteis previsto para a fonte.

A ingestão é idempotente: a chave composta `(conta_id, id_externo)` é única, de modo que
reprocessar o mesmo período não duplica lançamentos.

## Stack

- Python 3.11
- SQLAlchemy com migrações via Alembic
- SQLite para desenvolvimento e testes; PostgreSQL em produção

## Estrutura

```
app/
  models.py           Modelos SQLAlchemy
  db.py               Sessão e inicialização do banco
  services.py         Sincronização das fontes
  motor.py            Os quatro estágios de conciliação
  dinheiro.py         Aritmética monetária
  datas.py            Cálculo de dias úteis
  normalizacao/       Normalização de lançamentos
  relatorios/         Geração de relatórios
  conectores/         Um módulo por fonte de dados
  api.py              Camada HTTP (incompleta)
alembic/              Migrações de banco
prototipo/            Script de auditoria que originou o projeto
tests/                Suíte de testes
docs/                 Documentação de implantação e da API pretendida
```

## Como rodar

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env    # preencha as credenciais
alembic upgrade head
```

Com o banco migrado, o fluxo de sincronização e conciliação é acionado em código:

```python
from datetime import date, timedelta

from app.db import SessionLocal
from app.services import SincronizadorTransacoes
from app.motor import MotorConciliacao
from app.conectores.inter import InterAPI

db = SessionLocal()
fim, inicio = date.today(), date.today() - timedelta(days=30)

SincronizadorTransacoes(db).sincronizar_fonte(
    conector=InterAPI(), fonte="inter_api", data_inicio=inicio, data_fim=fim
)
MotorConciliacao(db).processar_conta(conta_id=1, data_inicio=inicio, data_fim=fim)
```

## Testes

```bash
python -m pytest tests/
```

A suíte cobre os conectores, os quatro estágios do motor, a aritmética monetária e o
fluxo ponta a ponta. Os conectores de teste são simulados, portanto nenhum teste exige
credenciais reais ou acesso de rede.

## Documentação

- [`docs/deploy.md`](docs/deploy.md) — implantação em Render com PostgreSQL
- [`docs/api.md`](docs/api.md) — contrato pretendido da API HTTP
- [`SPEC.md`](SPEC.md) — especificação funcional
- [`ROADMAP.md`](ROADMAP.md) — escopo e fases

## Credenciais

Nenhuma credencial é versionada. O arquivo `.env.example` lista as variáveis necessárias
com valores de exemplo; em produção elas são definidas como variáveis de ambiente no
provedor de hospedagem. Certificados e chaves do Inter são informados em Base64.
