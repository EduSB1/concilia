# Roteiro de Início de Projeto — Conciliação Bancária por API para Vendedores de Marketplace

> Versão 0.2 · 14/10/2026 — atualizada com as respostas do cliente piloto #1
> Objetivo deste documento: tirar a ideia da conversa e transformar em um plano executável, começando pelo **seu próprio uso diário** (dogfooding) e só depois virando produto.

---

## 1. O problema (em uma frase)

Todo dia o vendedor precisa pegar o que **o marketplace diz que pagou** (Mercado Livre, Shopee, TikTok Shop etc.), o que **caiu de fato no banco** (Inter, Itaú, Mercado Pago…) e o que está **lançado no ERP** (ex.: Bling), e fazer os três baterem — manualmente, linha por linha.

### O que o processo atual mostra (baseado no vídeo)

- Contas em vários lugares: **Banco Inter, Itaú, Mercado Pago, CDB/Porquinho (investimento)**.
- Entradas típicas no extrato: `Repasse Mercado Livre`, `Repasse Mercado Pago`, `Repasse Shopee`, `Repasse TikTok Shop (Bytedance)`, `Pix recebido – vendas parceiros`, `Rendimento aplicação automática`.
- Saídas típicas: `Pix enviado` (fornecedores, pessoas), `Débito – Uber`, `Débito – CPTM`, estacionamento, etc.
- **Transferências internas** entre as próprias contas (Mercado Pago → Inter, Inter → CDB) que **não são receita nem despesa** e bagunçam o fluxo de caixa se não forem identificadas.
- No ERP (Bling), a tela de **Caixa e bancos / Conciliação** é preenchida à mão.
- Já existe um passo usando IA para gerar um PDF de **Entradas e Saídas** e um **Fluxo de caixa** categorizado — ou seja, metade da lógica já está na sua cabeça; falta automatizar a coleta e o casamento.

### As 3 camadas de conciliação (importante separar)

| Camada | Pergunta que responde | Exemplo |
|---|---|---|
| **1. Banco × Banco** | Isso é transferência interna? | Saiu R$ 5.000 do Mercado Pago e entrou R$ 5.000 no Inter no mesmo dia |
| **2. Marketplace × Banco** | O repasse que o marketplace prometeu caiu? Com o valor certo? | Shopee liquidou R$ 3.412,80 dia 09/10 → existe crédito "Repasse Shopee" de R$ 3.412,80? |
| **3. Pedido × Repasse** | Quais pedidos compõem aquele repasse e quanto foi descontado de taxa/frete/estorno? | Repasse de R$ 3.412,80 = 27 pedidos − comissões − frete − 1 devolução |

O MVP deve resolver **1 e 2** muito bem. A camada 3 é onde mora o valor de produto (descobrir taxa cobrada errada, repasse faltando, devolução não reembolsada).

---

## 1.1 Cliente piloto #1 — o que ele respondeu

| Tema | Resposta | O que isso muda no projeto |
|---|---|---|
| Marketplaces | Mercado Livre, Shopee e TikTok Shop (já vendeu em outros) | Os 3 entram no MVP; TikTok deixa de ser "depois" |
| Contas | Inter, Mercado Pago, **Carteira Shopee** | Itaú sai do MVP; Carteira Shopee vira uma "conta" a monitorar |
| Sistema | Só **Bling** (NF + lançamentos de entrada e saída) | O Bling é o **destino** dos dados, não só uma fonte |
| Processo atual | Não concilia; só lança no Bling o que entra e sai do banco. **O bruto não é lançado** | Hoje ele não sabe quanto pagou de taxa e frete; lançar bruto + taxas separadas é um diferencial |
| Maior dor | Digitar à mão no Bling cada linha do extrato | **Feature nº 1: extrato → lançamento automático no Bling** |
| Problema real | R$ 3 mil que não caíram no Mercado Pago, sem rastro no extrato | **Feature nº 2: auditoria de repasses** (venda → liberação → saque) |
| O que quer | Conciliação + automação dos lançamentos a partir do extrato | Confirma o foco no MVP |
| Preço | ~R$ 500/mês para os 3 marketplaces; ~R$ 250/mês para 1 | Sinal forte de disposição a pagar; preço por marketplace conectado |

**Frase-chave dele:** "ter os números certinhos é muito importante". O produto vende **confiança no número**, não só economia de tempo.

**Caso de teste nº 1:** os R$ 3 mil sumidos no Mercado Pago. Se a ferramenta conseguir mostrar para onde foi esse dinheiro, vira a melhor demonstração de venda possível.

---

## 2. Dá pra fazer? — Avaliação de viabilidade

**Sim.** Todas as peças têm API ou, no pior caso, exportação de arquivo:

| Fonte | Via preferida | Plano B | Observações |
|---|---|---|---|
| **Banco Inter (PJ)** | API oficial Inter Empresas (extrato) | OFX/CSV | Exige criar integração no Internet Banking PJ, certificado + mTLS, OAuth2 client credentials |
| **Itaú** | Open Finance (via agregador) ou API corporativa | OFX | API direta do Itaú costuma exigir contrato; agregador é mais rápido |
| **Mercado Pago** | API do Mercado Pago (movimentações / relatórios de liberação de dinheiro) | Relatório CSV | É ao mesmo tempo "banco" e "marketplace" — fonte crucial |
| **Mercado Livre** | API do Mercado Livre (pedidos, pagamentos, faturamento) | Relatório de vendas | Pagamentos ML liquidam via Mercado Pago |
| **Shopee** | Shopee Open Platform (escrow / payment details por pedido) | Relatório de receita | Precisa cadastro como parceiro/app e aprovação |
| **TikTok Shop** | TikTok Shop Partner API (finance / statements) | Export do Seller Center | Aprovação de app pode demorar |
| **Bling (ERP)** | API Bling v3 (contas a receber/pagar, pedidos, caixa) | — | OAuth2; serve tanto de fonte quanto de destino (dar baixa) |
| **Agregadores Open Finance** | Ex.: Pluggy, Belvo (avaliar) | — | Um só contrato cobre vários bancos; tem custo por conexão |

**Principais riscos de viabilidade (validar na Semana 1):**
1. Aprovação de apps na Shopee e TikTok Shop (prazo e requisitos).
2. Acesso a extrato do Itaú via API sem contrato corporativo.
3. Custo dos agregadores Open Finance por conta conectada (impacta preço do produto).
4. Limites de requisição (rate limits) e janela de histórico disponível em cada API.

> ⚠️ Documentações, nomes de endpoints e requisitos das APIs mudam com frequência — confirme tudo na documentação oficial de cada plataforma antes de codar.

---

## 3. Escopo

### MVP (uso próprio + cliente piloto, ~6–8 semanas)
- Importar extratos de **Inter + Mercado Pago + Carteira Shopee** automaticamente (API). Itaú via OFX só para o seu uso.
- Importar repasses/liquidações de **Mercado Livre/Mercado Pago, Shopee e TikTok Shop**.
- **Criar os lançamentos automaticamente no Bling** (entrada/saída com categoria), começando em modo "rascunho para aprovar".
- Lançar **bruto, taxas, frete e líquido separados**, para o número bater de verdade.
- **Auditoria de repasses do Mercado Pago:** vendas × liberações × saques, apontando o que não caiu.
- Normalizar tudo num formato único de transação.
- Detectar **transferências internas** automaticamente.
- Casar **repasse do marketplace × crédito no banco**.
- **Categorizar** o resto (regras + IA como sugestão).
- Tela de **pendências** ("não conciliados") para resolver manualmente.
- Exportar **Fluxo de Caixa / Entradas e Saídas** (CSV/PDF) — substitui o processo atual.

### Fora do MVP (depois)
- Camada 3 completa (pedido a pedido, auditoria de taxas).
- Amazon, Magalu e outros.
- Escrita no Bling **sem aprovação humana** (só depois de semanas com alta precisão).
- Multiempresa / multiusuário / cobrança (virar SaaS).
- App mobile, notificações por WhatsApp.

### Precificação inicial (hipótese a validar)
| Plano | Marketplaces | Preço/mês |
|---|---|---|
| Solo | 1 | ~R$ 250 |
| Completo | até 3 | ~R$ 500 |

Validar com pelo menos mais 5 vendedores antes de fixar. Lembrar do custo de APIs/agregadores por conta conectada.

### Critério de sucesso do MVP
- Você para de fazer a conciliação manual diária.
- **≥ 85% das transações conciliadas automaticamente**, o resto em fila de pendências.
- Tempo diário gasto com conciliação cai de X min para < 10 min (meça o X agora!).

---

## 4. Arquitetura proposta

```
 ┌───────────────┐   ┌──────────────────┐   ┌────────────┐
 │ Bancos        │   │ Marketplaces     │   │ ERP (Bling)│
 │ Inter/Itaú/MP │   │ ML / Shopee / TT │   │            │
 └──────┬────────┘   └────────┬─────────┘   └─────┬──────┘
        │ conectores (1 por fonte, agendados)       │
        ▼                     ▼                     ▼
 ┌─────────────────────────────────────────────────────┐
 │  INGESTÃO  → guarda payload bruto (raw)             │
 │  NORMALIZAÇÃO → tabela única de "lançamentos"       │
 └──────────────────────────┬──────────────────────────┘
                            ▼
 ┌─────────────────────────────────────────────────────┐
 │  MOTOR DE CONCILIAÇÃO                               │
 │  1. transferências internas                         │
 │  2. repasse marketplace × crédito bancário          │
 │  3. regras de categorização (+ sugestão por IA)     │
 └──────────────────────────┬──────────────────────────┘
                            ▼
 ┌─────────────────────────────────────────────────────┐
 │  PAINEL: conciliados · pendências · fluxo de caixa  │
 │  EXPORTS: CSV / PDF / (futuro) baixa no Bling       │
 └─────────────────────────────────────────────────────┘
```

### Stack sugerida (simples e barata)
- **Backend:** Python + FastAPI (ou Node/NestJS, se preferir JS).
- **Banco de dados:** PostgreSQL (Supabase ou Neon pra começar sem servidor).
- **Jobs agendados:** cron / APScheduler / Celery + Redis (quando crescer).
- **Frontend:** Next.js ou até uma planilha/Retool/Streamlit no começo — o valor está no motor, não na tela.
- **Segredos:** variáveis de ambiente + cofre (Doppler, AWS Secrets Manager, etc.). **Nunca** tokens e certificados no repositório.
- **IA:** API de LLM só para *sugerir* categoria e descrever pendências — a decisão final é regra determinística ou humano.

---

## 5. Modelo de dados (primeira versão)

```sql
-- Contas da empresa (bancos e carteiras de marketplace)
CREATE TABLE contas (
  id            SERIAL PRIMARY KEY,
  nome          TEXT NOT NULL,            -- "Inter PJ", "Mercado Pago", "Itaú"
  tipo          TEXT NOT NULL,            -- banco | carteira_marketplace | investimento
  instituicao   TEXT NOT NULL,
  ativa         BOOLEAN DEFAULT TRUE
);

-- Todo dado bruto recebido, para auditoria e reprocessamento
CREATE TABLE ingestoes_raw (
  id            BIGSERIAL PRIMARY KEY,
  fonte         TEXT NOT NULL,            -- inter_api | ofx_itau | shopee_api ...
  recebido_em   TIMESTAMPTZ DEFAULT now(),
  payload       JSONB NOT NULL
);

-- Lançamentos normalizados (extrato de banco)
CREATE TABLE lancamentos (
  id             BIGSERIAL PRIMARY KEY,
  conta_id       INT REFERENCES contas(id),
  data           DATE NOT NULL,
  valor          NUMERIC(14,2) NOT NULL,  -- + entrada, − saída
  descricao      TEXT,
  contraparte    TEXT,                    -- nome/CPF/CNPJ quando houver
  id_externo     TEXT,                    -- id da transação na fonte (endToEndId do Pix etc.)
  categoria      TEXT,
  status         TEXT DEFAULT 'pendente', -- pendente | conciliado | ignorado
  raw_id         BIGINT REFERENCES ingestoes_raw(id),
  UNIQUE (conta_id, id_externo)           -- evita duplicar ao reimportar
);

-- Repasses/liquidações informados pelos marketplaces
CREATE TABLE repasses (
  id               BIGSERIAL PRIMARY KEY,
  marketplace      TEXT NOT NULL,         -- mercado_livre | shopee | tiktok
  loja             TEXT,                  -- se tiver mais de uma loja
  data_prevista    DATE,
  valor_bruto      NUMERIC(14,2),
  taxas            NUMERIC(14,2),
  frete            NUMERIC(14,2),
  estornos         NUMERIC(14,2),
  valor_liquido    NUMERIC(14,2) NOT NULL,
  id_externo       TEXT,
  status           TEXT DEFAULT 'aguardando', -- aguardando | recebido | divergente
  UNIQUE (marketplace, id_externo)
);

-- Ligações feitas pelo motor (N:N para suportar agrupamentos)
CREATE TABLE conciliacoes (
  id             BIGSERIAL PRIMARY KEY,
  tipo           TEXT NOT NULL,           -- transferencia_interna | repasse | regra | manual
  lancamento_id  BIGINT REFERENCES lancamentos(id),
  par_lancamento_id BIGINT REFERENCES lancamentos(id), -- p/ transferência interna
  repasse_id     BIGINT REFERENCES repasses(id),
  confianca      NUMERIC(3,2),            -- 0.00 a 1.00
  criado_por     TEXT DEFAULT 'motor',    -- motor | usuario
  criado_em      TIMESTAMPTZ DEFAULT now()
);

-- Regras de categorização editáveis
CREATE TABLE regras_categoria (
  id          SERIAL PRIMARY KEY,
  padrao      TEXT NOT NULL,              -- regex ou "contém" na descrição/contraparte
  categoria   TEXT NOT NULL,              -- "Transporte", "Fornecedor", "Receita Marketplace"...
  prioridade  INT DEFAULT 100
);
```

**Regras de ouro do modelo:**
- Dinheiro sempre em `NUMERIC`/centavos inteiros — **nunca float**.
- Guardar sempre o **payload bruto**; você vai reprocessar muitas vezes enquanto ajusta o motor.
- Chave única por `id_externo` para importar de novo sem duplicar (idempotência).

---

## 6. O motor de conciliação (lógica)

Rodar em etapas, das mais certas para as mais incertas:

### Etapa 1 — Transferências internas
Para cada saída em conta A, procurar entrada em conta B (também sua) com:
- mesmo valor absoluto,
- data igual ou até D+1,
- descrição contendo nome da própria empresa/CNPJ ou termos como "Transferência", "Resgate", "Aplicação".

→ Marca as duas como `transferencia_interna`, categoria neutra (não entra em receita/despesa).

### Etapa 2 — Repasse × crédito bancário
Para cada `repasse` aguardando:
1. **Match exato:** crédito com mesmo `valor_liquido`, data dentro de `data_prevista ± 2 dias úteis`, descrição compatível (`Repasse Shopee`, `Mercado Livre`, `Bytedance`…). → confiança 0,95+
2. **Match agrupado (N:1):** o banco às vezes recebe **um crédito somando vários repasses** (ou o contrário). Testar combinações de repasses do mesmo marketplace e janela de datas cuja soma = crédito. → confiança 0,80
3. **Match com tolerância:** diferença de centavos (arredondamento) → confiança 0,70 e sinaliza.
4. Sem match → repasse fica `aguardando`; se passou da data prevista + 3 dias úteis → **alerta "repasse não recebido"**.

### Etapa 3 — Categorização por regras
- Aplicar `regras_categoria` por prioridade (ex.: `Uber` → Transporte; `CPTM` → Transporte; `Rendimento` → Receita Financeira).
- O que sobrar: **IA sugere** categoria com base em descrição + contraparte + histórico, mas fica como *sugestão* até confirmar.
- Toda correção manual vira **nova regra** (o sistema aprende com você).

### Etapa 4 — Fila de pendências
Tudo com confiança < 0,80 ou sem match vai para uma tela com: lançamento, melhores candidatos, botão **Confirmar / Escolher outro / Ignorar / Criar regra**.

Pseudocódigo da etapa 2 (match exato):

```python
for rep in repasses_aguardando():
    candidatos = lancamentos_pendentes(
        valor=rep.valor_liquido,
        data_entre=(rep.data_prevista - 2 dias_uteis, rep.data_prevista + 2 dias_uteis),
        entrada=True,
    )
    candidatos = [c for c in candidatos if descricao_compativel(c.descricao, rep.marketplace)]
    if len(candidatos) == 1:
        conciliar(rep, candidatos[0], tipo="repasse", confianca=0.95)
    elif len(candidatos) > 1:
        enviar_para_pendencias(rep, candidatos)  # ambíguo: humano decide
```

---

## 7. Plano de execução (semana a semana)

### Semana 0 — Preparação (2–3 dias)
- [ ] **Medir o processo atual:** cronometrar a conciliação de 3 dias diferentes; anotar onde trava.
- [ ] Juntar **1 mês de dados reais** exportados manualmente (OFX/CSV de cada banco + relatórios de cada marketplace). Isso vira o **dataset de teste**.
- [ ] Listar todas as contas, lojas e marketplaces usados.
- [ ] Criar repositório, README, `.env.example`, estrutura de pastas.

### Semana 1 — Validação de acessos (o maior risco)
- [ ] Criar integração na API do **Banco Inter PJ** e conseguir puxar 1 extrato.
- [ ] Criar app no **Mercado Pago/Mercado Livre** e puxar movimentações/liberações.
- [ ] Solicitar acesso à **Shopee Open Platform** e **TikTok Shop Partner** (aprovação pode levar dias/semanas — pedir já).
- [ ] Testar **Itaú**: OFX manual agora; cotar um agregador Open Finance.
- [ ] Testar **API do Bling v3** (leitura de contas a receber e caixa).
- [ ] Documentar para cada fonte: autenticação, limites, histórico disponível, formato de valores e datas.

### Semana 2 — Ingestão + normalização
- [ ] Criar o banco de dados (seção 5).
- [ ] Conectores: Inter (API), Mercado Pago (API), Itaú (importador OFX).
- [ ] Normalizador → tabela `lancamentos`, com deduplicação.
- [ ] Job agendado diário (ex.: 6h da manhã).

### Semana 3 — Marketplaces
- [ ] Conector de repasses/liquidações Mercado Livre/Mercado Pago.
- [ ] Conector Shopee (se aprovado) — senão, importador do relatório exportado.
- [ ] Tabela `repasses` preenchida com bruto, taxas, frete, estornos e líquido.

### Semana 4 — Motor de conciliação
- [ ] Etapas 1 e 2 (transferências + repasses).
- [ ] Etapa 3 com regras iniciais (extrair do seu histórico: Uber, CPTM, fornecedores recorrentes…).
- [ ] **Testes automatizados com o dataset da Semana 0** — medir % de conciliação automática.

### Semana 5 — Interface + relatórios
- [ ] Tela de pendências (pode ser Streamlit/Retool no começo).
- [ ] Relatório **Entradas e Saídas** e **Fluxo de Caixa** (substituindo o PDF atual).
- [ ] Alerta de "repasse não recebido".

### Semana 6 — Uso real e ajuste
- [ ] Usar **todo dia** no lugar do processo manual.
- [ ] Registrar cada caso que o motor errou → nova regra ou ajuste.
- [ ] Comparar tempo gasto vs. medição da Semana 0.
- [ ] Decidir: continua ferramenta interna ou vira produto? (ver seção 9)

---

## 8. Segurança, LGPD e boas práticas

- Extratos têm **dados pessoais de terceiros** (nomes e CPFs em Pix) → LGPD se aplica, principalmente se virar produto para outras empresas.
- Credenciais e certificados bancários: cofre de segredos, acesso mínimo, rotação.
- Usar sempre **escopo de leitura** nas APIs de banco (nunca permissão de pagamento no MVP).
- Logs **sem** dados sensíveis (mascarar CPF, tokens).
- Backups do Postgres ativados.
- Se usar IA para categorizar: enviar só o necessário (descrição + valor), mascarar documentos, e verificar a política de dados do provedor.
- Trilha de auditoria: toda conciliação registra quem/qual regra decidiu.

---

## 9. Se for virar produto (SaaS) — perguntas para validar

- [ ] Conversar com **10 vendedores** de marketplace: como conciliam hoje? quanto tempo gastam? quanto pagariam?
- [ ] Mapear concorrentes e o que já fazem: módulos de conciliação de ERPs (Bling, Olist/Tiny, Conta Azul, Omie etc.) e ferramentas específicas de marketplace. Onde eles falham? (provável diferencial: **auditoria de repasse pedido a pedido** e multi-marketplace + multi-banco num só lugar).
- [ ] Modelo de preço: por faixa de faturamento? por número de contas/marketplaces conectados? Lembrar do custo do agregador Open Finance por conexão.
- [ ] Requisitos extras: multi-tenant, onboarding OAuth self-service, termos de uso, política de privacidade, DPO/LGPD, suporte.
- [ ] Parceria com contadores: eles atendem muitos vendedores e sofrem com a mesma dor — ótimo canal de vendas.

---

## 10. Riscos e mitigação

| Risco | Impacto | Mitigação |
|---|---|---|
| Marketplace demora a aprovar app | Atrasa camada 2 | Importador de relatório CSV como plano B |
| API muda formato/endpoint | Conector quebra | Guardar raw, testes de contrato, alertas de falha no job |
| Repasses agrupados/fracionados | Match falha | Algoritmo N:1 e fila de pendências |
| Estornos, chargebacks e devoluções | Valores não batem | Campo `estornos` no repasse; camada 3 depois |
| Custo do Open Finance | Margem do produto | Começar com APIs diretas (Inter, MP) + OFX |
| IA categorizar errado | Relatório errado | IA só sugere; regra/humano confirma |

---

## 10.1 Próximas perguntas para o cliente piloto

1. Quantas movimentações aparecem por dia no extrato, somando as 3 contas?
2. No Bling, você lança em **Contas a pagar/receber** ou direto no **Caixa e bancos**? Usa plano de contas/categorias?
3. O repasse do TikTok cai em qual conta? O saldo da Carteira Shopee é sacado manual ou automático para o Inter?
4. Já testou a importação de OFX ou a conciliação que o próprio Bling tem? Por que não serviu?
5. Sobre os R$ 3 mil: em que período e de quais vendas eram? (vai ser nosso primeiro caso de teste)
6. Toparia gerar um token de API **só leitura** do Mercado Pago para o teste?
7. Seu contador recebe algum relatório seu hoje? Qual formato ajudaria ele?

---

## 11. Checklist de amanhã de manhã ☕

1. [ ] Cronometrar a conciliação de hoje.
2. [ ] Exportar os extratos e relatórios do último mês e salvar numa pasta `dataset/`.
3. [ ] Entrar no Internet Banking PJ do Inter e procurar a área de **integrações/API**.
4. [ ] Criar conta de desenvolvedor no **Mercado Livre/Mercado Pago**.
5. [ ] Pedir acesso de desenvolvedor na **Shopee** e **TikTok Shop**.
6. [ ] Criar o repositório e colar este roteiro como `ROADMAP.md`.

---

## Anexo A — Categorias iniciais sugeridas

**Entradas:** Receita Mercado Livre · Receita Shopee · Receita TikTok Shop · Vendas Parceiros (Pix) · Receita Financeira (rendimentos) · Outras Entradas
**Saídas:** Fornecedores/Mercadoria · Frete/Envios · Taxas de Marketplace · Transporte (Uber, CPTM, estacionamento) · Alimentação · Impostos (DAS, DARE) · Serviços/Software · Pró-labore/Retiradas · Outras Saídas
**Neutras:** Transferência Interna · Aplicação/Resgate de Investimento

## Anexo B — Formato normalizado de lançamento (JSON)

```json
{
  "conta": "Inter PJ",
  "data": "2026-10-09",
  "valor": 3412.80,
  "descricao": "Repasse Shopee",
  "contraparte": "Shopee",
  "id_externo": "E1234567820261009...",
  "fonte": "inter_api"
}
```
