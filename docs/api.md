# Referência da API

**Base URL**: `https://seu-url.onrender.com` (após a implantação)

> Este documento descreve o contrato pretendido da camada HTTP. A implementação em
> `app/api.py` ainda está incompleta — as rotas estão declaradas, mas o módulo não
> instancia a aplicação. Trate as respostas abaixo como especificação, não como
> comportamento já disponível.

---

## Health Check

### GET `/health`
Verificar se servidor está ativo.

**Resposta**:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "environment": "production"
}
```

---

## Sincronização de Dados

### POST `/api/sync/inter`
Sincronizar transações do Banco Inter.

```bash
curl -X POST https://seu-url.onrender.com/api/sync/inter
```

**Resposta**:
```json
{
  "status": "success",
  "data": {
    "sucesso": true,
    "contas_sincronizadas": 1,
    "transacoes_inseridas": 45,
    "transacoes_atualizadas": 0,
    "transacoes_ignoradas": 0,
    "erros": []
  }
}
```

---

### POST `/api/sync/mercadopago`
Sincronizar pagamentos do Mercado Pago.

```bash
curl -X POST https://seu-url.onrender.com/api/sync/mercadopago
```

---

### POST `/api/sync/bling`
Sincronizar notas fiscais do Bling.

```bash
curl -X POST https://seu-url.onrender.com/api/sync/bling
```

---

## Consulta de Dados

### GET `/api/contas`
Listar todas as contas sincronizadas.

```bash
curl https://seu-url.onrender.com/api/contas
```

**Resposta**:
```json
{
  "total": 2,
  "contas": [
    {
      "id": 1,
      "fonte": "inter_api",
      "nome": "Conta Corrente Inter",
      "tipo": "banco",
      "saldo": "15000.00"
    },
    {
      "id": 2,
      "fonte": "mercadopago_api",
      "nome": "Loja Teste MP",
      "tipo": "wallet",
      "saldo": "5000.00"
    }
  ]
}
```

---

### GET `/api/transacoes`
Listar transações com filtro opcional.

**Parâmetros**:
- `conta_id` (optional): Filtrar por conta
- `fonte` (optional): Filtrar por fonte (inter_api, mercadopago_api, etc)

```bash
# Todas as transações
curl https://seu-url.onrender.com/api/transacoes

# Apenas Inter
curl https://seu-url.onrender.com/api/transacoes?fonte=inter_api

# Apenas conta 1
curl https://seu-url.onrender.com/api/transacoes?conta_id=1
```

**Resposta**:
```json
{
  "total": 45,
  "transacoes": [
    {
      "id": 1,
      "data": "2026-10-23",
      "valor": "250.00",
      "descricao": "Recebimento cliente X",
      "contraparte": "Cliente X",
      "fonte": "inter_api",
      "id_externo": "INTER-TRX-001"
    },
    ...
  ]
}
```

---

## Orquestração

### POST `/api/processar-conta`
Processar motor de conciliação para uma conta.

**Parâmetros**:
- `conta_id` (required): ID da conta
- `data_inicio` (optional): Data inicial (YYYY-MM-DD). Default: 30 dias atrás
- `data_fim` (optional): Data final (YYYY-MM-DD). Default: hoje

```bash
curl -X POST "https://seu-url.onrender.com/api/processar-conta?conta_id=1&data_inicio=2026-09-23&data_fim=2026-10-23"
```

**O que faz**:
1. Valida se conta existe
2. Executa motor de conciliação (4 estágios)
3. Retorna estatísticas de processamento

**Resposta**:
```json
{
  "status": "success",
  "conta": {
    "id": 1,
    "fonte": "inter_api",
    "nome": "Conta Corrente Inter",
    "tipo": "banco"
  },
  "periodo": {
    "data_inicio": "2026-09-23",
    "data_fim": "2026-10-23"
  },
  "resultado_motor": {
    "validadas": 45,
    "erros_validacao": 0,
    "normalizadas": 45,
    "pares_encontrados": 12,
    "pendencias_vencidas": 3
  },
  "totais": {
    "transacoes": 45,
    "pendencias_abertas": 3
  }
}
```

---

### POST `/api/sincronizar-e-processar`
Orquestração completa: sincronizar + processar motor em uma única chamada.

**Parâmetros**:
- `fonte` (required): Fonte de dados (inter_api, mercadopago_api, bling_api)
- `data_inicio` (optional): Data inicial. Default: 30 dias atrás
- `data_fim` (optional): Data final. Default: hoje

```bash
# Sincronizar Inter E processar motor
curl -X POST "https://seu-url.onrender.com/api/sincronizar-e-processar?fonte=inter_api"

# Com datas específicas
curl -X POST "https://seu-url.onrender.com/api/sincronizar-e-processar?fonte=mercadopago_api&data_inicio=2026-09-01&data_fim=2026-10-23"
```

**O que faz**:
1. Sincroniza dados do conector
2. Insere no BD (com idempotência)
3. Encontra a conta
4. Processa motor
5. Retorna resultado completo

**Resposta**:
```json
{
  "status": "success",
  "sincronizacao": {
    "fonte": "inter_api",
    "contas_sincronizadas": 1,
    "transacoes_inseridas": 45,
    "transacoes_ignoradas": 0,
    "erros": []
  },
  "processamento": {
    "validadas": 45,
    "erros_validacao": 0,
    "normalizadas": 45,
    "pares_encontrados": 12,
    "pendencias_vencidas": 3
  },
  "conta_id": 1
}
```

---

## Fluxos Recomendados

### Fluxo 1: Sincronizar tudo
```bash
# Executar em sequência ou paralelo
curl -X POST https://seu-url.onrender.com/api/sync/inter
curl -X POST https://seu-url.onrender.com/api/sync/mercadopago
curl -X POST https://seu-url.onrender.com/api/sync/bling

# Ver contas sincronizadas
curl https://seu-url.onrender.com/api/contas

# Ver todas as transações
curl https://seu-url.onrender.com/api/transacoes
```

### Fluxo 2: Sincronizar + processar (recomendado)
```bash
# Tudo em uma chamada por fonte
curl -X POST https://seu-url.onrender.com/api/sincronizar-e-processar?fonte=inter_api
curl -X POST https://seu-url.onrender.com/api/sincronizar-e-processar?fonte=mercadopago_api
curl -X POST https://seu-url.onrender.com/api/sincronizar-e-processar?fonte=bling_api
```

### Fluxo 3: Processar conta já sincronizada
```bash
# Se já sincronizou antes, só processa motor
curl -X POST https://seu-url.onrender.com/api/processar-conta?conta_id=1
```

---

## Status Codes

| Code | Significado |
|------|-------------|
| 200 | Sucesso |
| 400 | Erro de validação |
| 404 | Recurso não encontrado |
| 500 | Erro interno |

---

## Próximos Endpoints

- [ ] GET `/api/pendencias` — listar pendências vencidas
- [ ] POST `/api/reconciliar` — marcar transações como reconciliadas
- [ ] GET `/api/relatorio` — gerar relatório de conciliação
- [ ] DELETE `/api/resetar` — limpar dados (dev only)

---

**Última atualização**: 2026-10-30  
**Versão**: 1.0
