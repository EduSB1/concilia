# Implantação em Render

**Plataforma**: Render.com (gratuita, auto-deploy)  
**Tempo estimado**: 1-2 horas  
**Requisitos**: Ter credenciais das APIs (Inter, MP, Bling)

---

## Parte 1: Preparar Credenciais

### Passo 1.1: Obter Certificado Inter PJ

1. Acesse: www.internetbanking.inter.com.br (conta PJ)
2. Integrações > Credenciais de API > Nova Integração
3. Nome: "Concilia MVP"
4. Tipo: "Leitura de Extrato"
5. Scopes: `accounts:read`, `transactions:read`
6. Gerar certificado mTLS (cert.pem + key.pem)
7. **Converter para Base64**:
   ```bash
   base64 -w 0 cert.pem > cert.b64
   base64 -w 0 key.pem > key.b64
   ```
8. Copiar conteúdo dos arquivos .b64

**Resultado**:
- `INTER_CERT_B64` = conteúdo do cert.b64
- `INTER_KEY_B64` = conteúdo do key.b64

---

### Passo 1.2: Obter Token Mercado Pago

1. Acesse: https://www.mercadopago.com.br
2. Criar conta de vendedor (ou logar)
3. Configurações > Credenciais
4. Copiar **Access Token** (começa com `APP_USR-` ou `TEST_`)

**Resultado**:
- `MP_ACCESS_TOKEN` = seu token

---

### Passo 1.3: Obter Token Bling

1. Acesse: https://bling.com.br (sua conta)
2. Configurações > API
3. Gerar OAuth Token
4. Copiar token

**Resultado**:
- `BLING_ACCESS_TOKEN` = seu token

---

### Passo 1.4: Shopee e TikTok (OPCIONAL - aguarda aprovação)

Se já tiver aprovação Shopee:
- `SHOPEE_PARTNER_ID`
- `SHOPEE_PARTNER_KEY`
- `SHOPEE_ACCESS_TOKEN`

Se já tiver aprovação TikTok:
- `TIKTOK_CLIENT_KEY`
- `TIKTOK_CLIENT_SECRET`
- `TIKTOK_ACCESS_TOKEN`
- `TIKTOK_SHOP_CIPHER`

---

## Parte 2: Preparar Render.com

### Passo 2.1: Criar Conta Render

1. Vá para: https://render.com
2. Sign up com GitHub ou email
3. Conectar conta GitHub (opcional, mas facilita deploy automático)

---

### Passo 2.2: Criar PostgreSQL

1. Dashboard Render → New → PostgreSQL
2. Name: `concilia-db`
3. Database: `concilia_prod`
4. User: `concilia_user`
5. Region: São Paulo (sa-east-1) se disponível
6. Pricing: Free tier
7. Criar

**Resultado**: Você recebe `DATABASE_URL` (copie e guarde)

Exemplo:
```
postgresql://concilia_user:senha@dpg-xxx.render.internal:5432/concilia_prod
```

---

### Passo 2.3: Criar Web Service

1. Dashboard Render → New → Web Service
2. Conectar repositório: `https://github.com/EduSB1/concilia.git`
3. Name: `concilia-api`
4. Environment: `Python 3.11`
5. Build Command:
   ```bash
   pip install -r requirements.txt && alembic upgrade head
   ```
6. Start Command:
   ```bash
   gunicorn -w 2 -b 0.0.0.0:$PORT app.api:app
   ```
7. Region: São Paulo
8. Pricing: Free tier

---

### Passo 2.4: Adicionar Variáveis de Ambiente

Na página do Web Service, vá para **Environment**:

```
DATABASE_URL=postgresql://... (da Parte 2.2)
INTER_CERT_B64=seu_cert_aqui
INTER_KEY_B64=sua_key_aqui
MP_ACCESS_TOKEN=seu_token_mp
BLING_ACCESS_TOKEN=seu_token_bling
SHOPEE_PARTNER_ID=seu_id (se tiver)
SHOPEE_PARTNER_KEY=sua_key (se tiver)
SHOPEE_ACCESS_TOKEN=seu_token (se tiver)
TIKTOK_CLIENT_KEY=sua_key (se tiver)
TIKTOK_CLIENT_SECRET=seu_secret (se tiver)
TIKTOK_ACCESS_TOKEN=seu_token (se tiver)
TIKTOK_SHOP_CIPHER=seu_cipher (se tiver)
FLASK_ENV=production
SECRET_KEY=seu_secret_aleatorio_bem_longo
```

**Importante**: Use valores seguros para `SECRET_KEY` (pode gerar com `python -c "import secrets; print(secrets.token_hex(32))"`)

---

## Parte 3: Validar Deploy

### Passo 3.1: Esperar Deploy

Render vai:
1. Clonar repositório
2. Instalar dependências
3. Rodar migrations Alembic
4. Iniciar servidor Gunicorn

**Tempo**: ~5-10 minutos

Você verá um link como: `https://concilia-api.onrender.com`

---

### Passo 3.2: Testar Health Check

```bash
curl https://concilia-api.onrender.com/health
```

**Resposta esperada**:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "environment": "production"
}
```

---

### Passo 3.3: Testar Sincronização Inter

```bash
curl -X POST https://concilia-api.onrender.com/api/sync/inter
```

**Resposta esperada**:
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

### Passo 3.4: Testar Mercado Pago

```bash
curl -X POST https://concilia-api.onrender.com/api/sync/mercadopago
```

---

### Passo 3.5: Listar Contas

```bash
curl https://concilia-api.onrender.com/api/contas
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

## Troubleshooting

### Database connection error

**Erro**: `could not connect to server`

**Solução**:
1. Verificar `DATABASE_URL` está correto (copiar novamente de Render)
2. Aguardar 2-3 minutos (DB pode estar iniciando)
3. Reiniciar Web Service (Render Dashboard → Restart)

---

### Inter authentication failed

**Erro**: `Falha na autenticação do inter_api`

**Solução**:
1. Verificar `INTER_CERT_B64` e `INTER_KEY_B64` estão corretos
2. Testar certificado localmente:
   ```bash
   base64 -d <<< $INTER_CERT_B64 | openssl x509 -text -noout
   ```
3. Regenerar certificado no Inter Banking

---

### Mercado Pago 404 error

**Erro**: `404 Client Error: Not Found for url: https://api.mercadopago.com/v1/accounts/me`

**Solução**:
1. Token pode estar expirado
2. Usar token de usuário, não de app
3. Regenerar token em Mercado Pago

---

### Migrations failed

**Erro**: `alembic upgrade head` falhou

**Solução**:
1. Verificar se PostgreSQL está rodando
2. Verificar `DATABASE_URL`
3. Fazer rollback:
   ```bash
   alembic downgrade -1
   alembic upgrade head
   ```

---

## Parte 4: Usar em Produção

### Sincronizar Dados

```bash
# Inter
curl -X POST https://seu-url.onrender.com/api/sync/inter

# Mercado Pago
curl -X POST https://seu-url.onrender.com/api/sync/mercadopago

# Bling
curl -X POST https://seu-url.onrender.com/api/sync/bling
```

### Ver Transações

```bash
curl "https://seu-url.onrender.com/api/transacoes?fonte=inter_api"
```

### Processar Conciliação

```bash
# Via motor (manual por enquanto)
# Endpoint ainda em desenvolvimento
```

---

## Próximas Melhorias

- [ ] Endpoint `/api/processar-conta` para rodar motor manual
- [ ] Webhook de sincronização automática
- [ ] Dashboard web para visualizar dados
- [ ] Alertas de pendências vencidas
- [ ] Exportar relatórios

---

## Suporte

Se algo não funcionar:
1. Verificar logs em Render Dashboard
2. Testar endpoints localmente
3. Abrir issue no repositório

**Repositório**: https://github.com/EduSB1/concilia

---

**Último atualizado**: 2026-10-30  
**Versão**: MVP 1.0
