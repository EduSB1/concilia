# Fase 1.1 — Validação de Acessos ✅ COMPLETA

**Data**: 2026-10-23  
**Status**: Todos os 5 conectores implementados com testes  
**Próxima fase**: 1.2 — Padrão de Normalização e Persistência (1 semana)

## O que foi feito

### 1.1.1 ✅ Banco Inter PJ
- **Arquivo**: `app/conectores/inter.py`
- **Autenticação**: mTLS (certificado + chave privada)
- **Suporte**: Arquivo direto OR base64 (para Render)
- **Métodos**: 
  - `autenticar()` — GET /accounts
  - `listar_contas()` — GET /accounts (retorna contas com saldo)
  - `extrato(data_inicio, data_fim)` — GET /accounts/{id}/transactions
- **Formato de saída**: `Transacao` normalizada
- **Testes**: ✅ 4 testes unitários passam
- **Próximos passos (seu amigo)**:
  1. Login em www.internetbanking.inter.com.br
  2. Integrações > Credenciais de API > Nova integração
  3. Tipo: "Leitura de Extrato", Scopes: `accounts:read`, `transactions:read`
  4. Baixar certificado e chave privada
  5. Converter para base64 e preencher `INTER_CERT_B64` + `INTER_KEY_B64` no Render

### 1.1.2 ✅ Mercado Pago
- **Arquivo**: `app/conectores/mercadopago.py`
- **Autenticação**: Bearer token (OAuth)
- **Métodos**:
  - `autenticar()` — GET /accounts/me
  - `listar_contas()` — GET /accounts/me (retorna usuário/email)
  - `extrato(data_inicio, data_fim)` — GET /payments/search (com paginação)
- **Formato de saída**: `Transacao` normalizada (entrada/saída por operation_type)
- **Testes**: ✅ 4 testes unitários passam
- **Próximos passos (seu amigo)**:
  1. Criar aplicação em developers.mercadopago.com.br
  2. Obter Access Token da app
  3. Preencher `MP_ACCESS_TOKEN` no Render

### 1.1.3 ✅ Shopee Open Platform (template)
- **Arquivo**: `app/conectores/shopee.py`
- **Autenticação**: Partner ID + Partner Key (HMAC-SHA256) + Access Token
- **Métodos**:
  - `autenticar()` — POST /shop/get_shop_info
  - `listar_contas()` — POST /shop/get_shop_info (retorna loja)
  - `extrato(data_inicio, data_fim)` — POST /order/get_order_list (com paginação)
- **Formato de saída**: `Transacao` normalizada (vendas = entrada)
- **Testes**: ✅ 4 testes unitários passam
- **⏳ Aguardando**: Aprovação da aplicação Shopee (2-7 dias)
- **Próximos passos (seu amigo)**:
  1. Solicitar acesso Open Platform em sellers.shopee.com.br > Ferramentas
  2. Criar aplicação e aguardar aprovação
  3. Gerar Access Token da loja
  4. Preencher `SHOPEE_PARTNER_ID`, `SHOPEE_PARTNER_KEY`, `SHOPEE_ACCESS_TOKEN`

### 1.1.4 ✅ TikTok Shop Partner API (template)
- **Arquivo**: `app/conectores/tiktok.py`
- **Autenticação**: Client Key + Client Secret + Access Token (OAuth 2.0) + Shop Cipher
- **Métodos**:
  - `autenticar()` — POST /shop/api/auth/shop/get
  - `listar_contas()` — POST /shop/api/auth/shop/get (retorna loja)
  - `extrato(data_inicio, data_fim)` — POST /shop/api/orders (com paginação)
- **Formato de saída**: `Transacao` normalizada (vendas = entrada)
- **Testes**: ✅ 4 testes unitários passam
- **⏳ Aguardando**: Aprovação da aplicação TikTok (1-14 dias)
- **Próximos passos (seu amigo)**:
  1. Registrar seller em sellers.tiktok.com
  2. Solicitar acesso Partner API
  3. Criar aplicação e aguardar aprovação
  4. Obter OAuth token e Shop Cipher
  5. Preencher `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_ACCESS_TOKEN`, `TIKTOK_SHOP_CIPHER`

### 1.1.5 ✅ Bling v3 API
- **Arquivo**: `app/conectores/bling.py`
- **Autenticação**: Bearer token (OAuth 2.0)
- **Métodos**:
  - `autenticar()` — GET /empresa
  - `listar_contas()` — GET /empresa (retorna empresa com CNPJ)
  - `extrato(data_inicio, data_fim)` — GET /notasfiscais (com paginação)
- **Formato de saída**: `Transacao` normalizada (NF venda = entrada)
- **Testes**: ✅ 4 testes unitários passam
- **Próximos passos (seu amigo)**:
  1. Login em bling.com.br > Configurações > API
  2. Gerar OAuth token
  3. Preencher `BLING_ACCESS_TOKEN` no Render

## Estrutura de código

```
app/
  conectores/
    __init__.py      # ConectorBase (interface) + Transacao (dataclass)
    inter.py         # InterAPI
    mercadopago.py   # MercadoPagoAPI
    shopee.py        # ShopeeAPI
    tiktok.py        # TikTokShopAPI
    bling.py         # BlingAPI

tests/
  conectores/
    __init__.py
  test_conectores_inter.py
  test_conectores_mercadopago.py
  test_conectores_shopee.py
  test_conectores_tiktok.py
  test_conectores_bling.py
```

## Interface padrão (ConectorBase)

Todos os conectores herdam de `ConectorBase` e implementam:

```python
class ConectorBase(ABC):
    def autenticar(self) -> bool: pass
    def extrato(self, data_inicio: date, data_fim: date) -> list[Transacao]: pass
    def listar_contas(self) -> list[dict]: pass
```

Formato de saída normalizado:

```python
@dataclass
class Transacao:
    data: date
    valor: Decimal        # + entrada / - saída
    descricao: str
    contraparte: str = ""
    id_externo: str = ""  # chave única por fonte (idempotência)
    fonte: str = ""       # inter_api, mercadopago_api, shopee_api, tiktok_api, bling_api
    tags: dict = None     # dados brutos da API
```

## Variáveis de ambiente esperadas

```bash
# Inter (mTLS)
INTER_CERT_B64="base64 do certificado"
INTER_KEY_B64="base64 da chave privada"

# Mercado Pago
MP_ACCESS_TOKEN="token"

# Shopee (após aprovação)
SHOPEE_PARTNER_ID="id"
SHOPEE_PARTNER_KEY="key"
SHOPEE_ACCESS_TOKEN="token"

# TikTok (após aprovação)
TIKTOK_CLIENT_KEY="id"
TIKTOK_CLIENT_SECRET="secret"
TIKTOK_ACCESS_TOKEN="token"
TIKTOK_SHOP_CIPHER="cipher"

# Bling
BLING_ACCESS_TOKEN="token"
```

## Próximas fases

| Fase | Objetivo | Duração | Status |
|------|----------|---------|--------|
| 1.1 | ✅ Validação de acessos (5 conectores) | 1 semana | COMPLETA |
| **1.2** | Padrão de normalização e persistência | 1 semana | ⏳ PRÓXIMA |
| 1.3 | Validação com dados reais | 1 semana | ⏳ |
| 1.4 | Motor de conciliação (PENDENCIAS_DETALHADO) | 2 semanas | ⏳ |
| 1.5 | Testes E2E + ajustes | 1 semana | ⏳ |

---

**Commits da Fase 1.1**:
- c8f7450: feat(conectores): inter.py + testes
- 79a0652: feat(conectores): mercadopago.py + testes
- 50b230d: feat(conectores): shopee.py + testes
- fea73c1: feat(conectores): tiktok.py + testes
- 7c81ab7: feat(conectores): bling.py + testes
