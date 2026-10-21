# SPEC — Conciliação Bancária para Vendedores de Marketplace

> Nome provisório: **Concilia** · Versão da spec: 0.1 · 14/10/2026
> Status: Fase 1 (MVP interno) em andamento · Documento vivo: atualizar a cada decisão.
>
> Pronto: motor de conciliação (`app/motor/`), formato normalizado
> (`app/normalizacao/`) e esquema do banco (`migrations/001_inicial.sql`).
> Pendente: conectores de API, persistência e tela de pendências.
> A Fase 0 segue aberta: o critério dela é explicar os R$ 3 mil do piloto,
> e isso depende do relatório real.

---

## 1. Visão

Ferramenta que conecta **bancos, carteiras e marketplaces** de um vendedor, descobre automaticamente o que cada movimentação significa e **lança tudo no ERP (Bling)** com o valor bruto, as taxas e o líquido separados. O vendedor não digita nada e vê os números certos.

**Proposta de valor em uma linha:** "Seus números certinhos no Bling, sem digitar nada, e um alerta quando algum dinheiro não cair."

### Problemas que resolve
1. **Trabalho manual:** copiar linha por linha do extrato para o Bling.
2. **Número errado:** só o líquido é lançado, então taxa, frete e devolução ficam invisíveis.
3. **Dinheiro perdido:** repasse que não cai, retenção ou débito sem explicação (ex.: R$ 3 mil sumidos no Mercado Pago).
4. **Transferências internas** contadas como receita ou despesa.

---

## 2. Usuários

| Persona | Perfil | Necessidade principal |
|---|---|---|
| **Fundador (você)** | Vende em marketplaces; contas Inter, Itaú, Mercado Pago, CDB; usa Bling | Parar a conciliação diária manual; fluxo de caixa categorizado |
| **Piloto #1 (amigo)** | ML + Shopee + TikTok; contas Inter, Mercado Pago, Carteira Shopee; Bling para NF e lançamentos | Lançamento automático no Bling + achar dinheiro sumido. Disposto a pagar R$ 250 (1 marketplace) a R$ 500 (3) por mês |
| **Futuro: contador** | Atende vários vendedores | Relatórios padronizados, acesso de leitura |

---

## 3. Escopo por fase

| Fase | Entrega | Critério de pronto |
|---|---|---|
| **0 — Protótipo** | Script de auditoria do Mercado Pago (`prototipo/`) | Explica a diferença de R$ 3 mil do piloto, ou prova onde ela está |
| **1 — MVP interno** | Ingestão Inter + MP + Carteira Shopee; repasses ML/Shopee/TikTok; motor de conciliação; fila de pendências; relatórios | ≥ 85% das transações conciliadas automaticamente nos dados do fundador |
| **2 — Bling** | Lançamentos automáticos no Bling (modo rascunho e depois automático) | Piloto para de digitar lançamentos por 2 semanas seguidas |
| **3 — Piloto pago** | Multiempresa, login, onboarding OAuth, cobrança | 3 clientes pagando |
| **4 — Produto** | Auditoria pedido a pedido, mais marketplaces (Amazon, Magalu), alertas no WhatsApp | — |

**Fora de escopo (por enquanto):** emitir NF, fazer pagamentos, gestão de estoque, conciliação de cartão de crédito empresarial.

---

## 4. Requisitos funcionais

### 4.1 Conexões
- **RF-01:** Conectar conta **Banco Inter PJ** via API oficial (extrato).
- **RF-02:** Conectar **Mercado Pago** via token/OAuth (pagamentos + relatório de liberações).
- **RF-03:** Conectar **Carteira Shopee** e dados de repasse via Shopee Open Platform.
- **RF-04:** Conectar **TikTok Shop** via Partner API (finance/statements).
- **RF-05:** Conectar **Mercado Livre** via API (pedidos, tarifas, envios).
- **RF-06:** Conectar **Bling** via API v3 (OAuth2), para leitura e escrita.
- **RF-07:** Importar **OFX/CSV** manualmente para qualquer banco sem API (ex.: Itaú).
- **RF-08:** Mostrar o status de cada conexão (ok / token expirado / erro) e avisar quando cair.

### 4.2 Ingestão
- **RF-10:** Sincronização automática diária (padrão 6h) e botão "sincronizar agora".
- **RF-11:** Guardar o payload bruto de toda ingestão (auditoria e reprocessamento).
- **RF-12:** Reimportar sem duplicar (idempotência por `id_externo`).
- **RF-13:** Normalizar tudo para o formato único de **Lançamento** (seção 6).

### 4.3 Motor de conciliação
- **RF-20:** Detectar **transferências internas** entre contas do mesmo dono (ex.: MP → Inter, Carteira Shopee → Inter, Inter → CDB).
- **RF-21:** Casar **repasse do marketplace × crédito no banco**, nesta ordem:
  - match exato;
  - match agrupado (N:1 e 1:N);
  - match com tolerância de centavos.
- **RF-22:** Decompor cada repasse em **bruto, taxas, frete, estornos e líquido**.
- **RF-23:** Categorizar por **regras** (descrição, contraparte, valor) com prioridade.
- **RF-24:** A IA **sugere** categoria para o que nenhuma regra cobriu. Nunca decide sozinha.
- **RF-25:** Toda correção manual pode virar **regra nova** com 1 clique.
- **RF-26:** Atribuir uma **confiança** (0–1) a cada conciliação. Abaixo de 0,80, o item vai para pendências.

### 4.4 Auditoria e alertas
- **RF-30:** Alertar **repasse não recebido** quando passar a data prevista + 3 dias úteis.
- **RF-31:** Fazer a **prova real do saldo** por conta (saldo inicial + créditos − débitos = saldo final).
- **RF-32:** Listar **débitos sem explicação** (não são saque, nem taxa conhecida, nem estorno vinculado).
- **RF-33:** Mostrar **retenções, disputas e mediações** em aberto, com o valor e a data prevista de liberação.

### 4.5 Integração Bling (escrita)
- **RF-40:** Criar lançamentos de **contas a receber/pagar** (ou movimentação de caixa, conforme a configuração do cliente), já com categoria.
- **RF-41:** **Modo rascunho:** o usuário aprova em lote antes de enviar ao Bling.
- **RF-42:** **Modo automático:** liberado por conta, após a precisão ficar ≥ 98% por 2 semanas.
- **RF-43:** Lançar a venda pelo **bruto** e as taxas e o frete como despesas separadas (configurável: bruto separado ou só líquido).
- **RF-44:** Nunca lançar duas vezes. Guardar o id do Bling em cada lançamento enviado.
- **RF-45:** Mapear as categorias internas para o **plano de contas do Bling** do cliente.

### 4.6 Interface e relatórios
- **RF-50:** Painel com saldo por conta, conciliados hoje, pendências e alertas.
- **RF-51:** Fila de pendências com as ações Confirmar / Escolher outro / Ignorar / Criar regra.
- **RF-52:** Relatórios: Entradas e Saídas, Fluxo de Caixa, **Lucro real por marketplace** (bruto − taxas − frete − estornos), Recebíveis futuros.
- **RF-53:** Exportar em CSV e PDF.
- **RF-54 (fase 4):** Resumo diário pelo WhatsApp.

---

## 5. Requisitos não funcionais

| ID | Requisito |
|---|---|
| RNF-01 | Valores sempre em `NUMERIC(14,2)` ou centavos inteiros. **Nunca float** |
| RNF-02 | Datas armazenadas em UTC e exibidas em America/Sao_Paulo |
| RNF-03 | Credenciais em cofre de segredos, criptografadas em repouso; nunca no código ou em logs |
| RNF-04 | Escopo **somente leitura** em bancos e marketplaces; escrita apenas no Bling |
| RNF-05 | Logs sem dados pessoais (mascarar CPF/CNPJ, nomes de contraparte e tokens) |
| RNF-06 | Sincronização diária concluída em < 10 min para até 5.000 movimentações/mês |
| RNF-07 | Tratar limites de requisição (retry com backoff) e tokens expirados (refresh automático) |
| RNF-08 | Trilha de auditoria: toda conciliação e todo lançamento registram quem decidiu (regra, IA, usuário) |
| RNF-09 | Backup diário do banco de dados |
| RNF-10 | Conformidade com a **LGPD**: base legal, termo de uso, política de privacidade, exclusão de dados a pedido |

---

## 6. Modelo de dados

```sql
CREATE TABLE empresas (
  id SERIAL PRIMARY KEY, nome TEXT NOT NULL, cnpj TEXT, criado_em TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE conexoes (                          -- uma por fonte conectada
  id SERIAL PRIMARY KEY, empresa_id INT REFERENCES empresas(id),
  fonte TEXT NOT NULL,                           -- inter | mercadopago | shopee | tiktok | mercadolivre | bling | ofx
  status TEXT DEFAULT 'ok',                      -- ok | expirada | erro
  segredo_ref TEXT,                              -- referência ao cofre, nunca o token em si
  ultima_sync TIMESTAMPTZ
);

CREATE TABLE contas (                            -- bancos e carteiras
  id SERIAL PRIMARY KEY, empresa_id INT REFERENCES empresas(id),
  conexao_id INT REFERENCES conexoes(id),
  nome TEXT NOT NULL,                            -- "Inter PJ", "Mercado Pago", "Carteira Shopee"
  tipo TEXT NOT NULL                             -- banco | carteira_marketplace | investimento
);

CREATE TABLE ingestoes_raw (
  id BIGSERIAL PRIMARY KEY, conexao_id INT REFERENCES conexoes(id),
  recebido_em TIMESTAMPTZ DEFAULT now(), payload JSONB NOT NULL
);

CREATE TABLE lancamentos (                       -- movimento de dinheiro numa conta
  id BIGSERIAL PRIMARY KEY, conta_id INT REFERENCES contas(id),
  data DATE NOT NULL, valor NUMERIC(14,2) NOT NULL,   -- + entrada / − saída
  descricao TEXT, contraparte TEXT, id_externo TEXT,
  categoria TEXT, status TEXT DEFAULT 'pendente',     -- pendente | conciliado | ignorado
  bling_id TEXT,                                       -- preenchido após enviar ao Bling
  raw_id BIGINT REFERENCES ingestoes_raw(id),
  UNIQUE (conta_id, id_externo)
);

CREATE TABLE repasses (                          -- o que o marketplace diz que pagou
  id BIGSERIAL PRIMARY KEY, empresa_id INT REFERENCES empresas(id),
  marketplace TEXT NOT NULL, data_prevista DATE,
  valor_bruto NUMERIC(14,2), taxas NUMERIC(14,2), frete NUMERIC(14,2),
  estornos NUMERIC(14,2), valor_liquido NUMERIC(14,2) NOT NULL,
  id_externo TEXT, status TEXT DEFAULT 'aguardando',   -- aguardando | recebido | divergente | retido
  UNIQUE (marketplace, id_externo)
);

CREATE TABLE repasse_itens (                     -- fase 4: pedido a pedido
  id BIGSERIAL PRIMARY KEY, repasse_id BIGINT REFERENCES repasses(id),
  pedido_id TEXT, tipo TEXT,                     -- venda | comissao | frete | estorno | ajuste
  valor NUMERIC(14,2)
);

CREATE TABLE conciliacoes (
  id BIGSERIAL PRIMARY KEY,
  tipo TEXT NOT NULL,                            -- transferencia_interna | repasse | regra | manual
  lancamento_id BIGINT REFERENCES lancamentos(id),
  par_lancamento_id BIGINT REFERENCES lancamentos(id),
  repasse_id BIGINT REFERENCES repasses(id),
  confianca NUMERIC(3,2), decidido_por TEXT,     -- motor | ia | usuario:<id>
  criado_em TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE regras_categoria (
  id SERIAL PRIMARY KEY, empresa_id INT REFERENCES empresas(id),
  campo TEXT DEFAULT 'descricao',                -- descricao | contraparte
  padrao TEXT NOT NULL, categoria TEXT NOT NULL, prioridade INT DEFAULT 100
);

CREATE TABLE mapa_bling (                        -- categoria interna → plano de contas Bling
  empresa_id INT REFERENCES empresas(id), categoria TEXT, bling_categoria_id TEXT,
  PRIMARY KEY (empresa_id, categoria)
);
```

### Formato normalizado de lançamento (contrato entre conectores e motor)
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

---

## 7. Regras do motor (detalhe)

| Etapa | Regra | Confiança |
|---|---|---|
| 1. Transferência interna | Saída na conta A e entrada na conta B (mesmo dono), mesmo valor, D0 ou D+1, descrição de transferência/saque/resgate | 0,95 |
| 2a. Repasse exato | Crédito = `valor_liquido`, data entre a data prevista e ±2 dias úteis, descrição compatível com o marketplace | 0,95 |
| 2b. Repasse agrupado | Soma de N repasses do mesmo marketplace na janela = 1 crédito (ou o inverso) | 0,80 |
| 2c. Tolerância | Diferença ≤ R$ 0,05 | 0,70 + sinalização |
| 3. Regra de categoria | Padrão da `regras_categoria` com maior prioridade | 0,90 |
| 4. Sugestão IA | Descrição + contraparte + histórico | máx. 0,60 (sempre vai para pendências) |

**Palavras-chave iniciais de descrição por marketplace:** Mercado Livre / Mercado Pago, Shopee, TikTok / Bytedance.

---

## 8. Integrações: pontos de atenção

| Fonte | Autenticação | Atenção |
|---|---|---|
| Inter PJ | OAuth2 client credentials + certificado (mTLS) | Criar a integração no Internet Banking PJ; certificado expira |
| Mercado Pago | Access token / OAuth | Pagamentos ≠ movimentos do saldo. Para débitos, saques e retenções, usar o **relatório de liberações** |
| Mercado Livre | OAuth2 | Tarifas e fretes podem ser debitados do saldo MP, fora do pagamento |
| Shopee | Partner ID + assinatura HMAC | Exige app aprovado; Carteira Shopee tem saque separado |
| TikTok Shop | App key/secret + OAuth do vendedor | Aprovação do app pode demorar; repasse vem como "Bytedance" no banco |
| Bling v3 | OAuth2 (refresh token) | Respeitar limites de requisição; confirmar endpoints de contas a pagar/receber e categorias |
| Itaú | OFX (MVP) / Open Finance via agregador | Avaliar o custo do agregador por conexão |

> Toda informação de API acima deve ser confirmada na documentação oficial antes da implementação. Elas mudam.

---

## 9. Categorias padrão

- **Entradas:** Receita Mercado Livre · Receita Shopee · Receita TikTok Shop · Vendas Parceiros (Pix) · Receita Financeira · Outras Entradas
- **Saídas:** Taxas de Marketplace · Frete/Envios · Devoluções/Estornos · Fornecedores/Mercadoria · Transporte · Alimentação · Impostos (DAS, DARE) · Software/Serviços · Pró-labore/Retiradas · Outras Saídas
- **Neutras:** Transferência Interna · Aplicação/Resgate

---

## 10. Arquitetura e stack

```
Conectores (1 por fonte, agendados) → ingestoes_raw → normalizador → lancamentos / repasses
→ motor de conciliação → conciliacoes → [painel + relatórios] → escritor Bling
```

| Camada | Escolha inicial | Motivo |
|---|---|---|
| Linguagem | Python 3.11+ | Protótipo já em Python; ótimo para dados |
| API | FastAPI | Simples, tipado |
| Banco | PostgreSQL (Supabase/Neon) | Gerenciado, barato no início |
| Jobs | APScheduler, depois Celery + Redis | Começar simples |
| Front | Streamlit (MVP interno), depois Next.js | O valor está no motor |
| Segredos | Doppler / AWS Secrets Manager | RNF-03 |
| IA | API de LLM apenas para sugestões | RF-24 |

### Estrutura do repositório
```
concilia/
├── SPEC.md
├── ROADMAP.md
├── prototipo/            # Fase 0 — scripts soltos
├── app/
│   ├── conectores/       # inter.py, mercadopago.py, shopee.py, tiktok.py, mercadolivre.py, bling.py, ofx.py
│   ├── normalizacao/
│   ├── motor/            # transferencias.py, repasses.py, categorias.py
│   ├── bling_writer/
│   ├── api/
│   └── relatorios/
├── migrations/
└── tests/
    └── dados/            # extratos reais anonimizados = casos de teste
```

---

## 11. Métricas de sucesso

| Métrica | Meta MVP |
|---|---|
| % de lançamentos conciliados automaticamente | ≥ 85% (meta fase 2: ≥ 95%) |
| Precisão das conciliações automáticas | ≥ 98% |
| Tempo diário gasto pelo usuário | < 10 min (medir a linha de base antes!) |
| Repasses não recebidos detectados | 100% dos que passarem do prazo |
| Diferença na prova real do saldo | R$ 0,00 ou explicada |

---

## 12. Modelo de negócio (hipótese)

| Plano | Inclui | Preço/mês |
|---|---|---|
| Solo | 1 marketplace + contas ligadas a ele + Bling | ~R$ 250 |
| Completo | Até 3 marketplaces + contas + Bling | ~R$ 500 |

Validar com ≥ 5 vendedores além do piloto. Canal promissor: **contadores** que atendem vendedores de marketplace.

---

## 13. Riscos

| Risco | Mitigação |
|---|---|
| Aprovação de apps Shopee/TikTok demorar | Importador de relatório CSV como plano B |
| Bling já ter conciliação "boa o suficiente" | Perguntar ao piloto; diferencial = multi-marketplace + bruto/taxas + auditoria |
| APIs mudarem | Payload bruto guardado, testes de contrato, alerta de falha |
| Lançamento errado no Bling | Modo rascunho, idempotência, botão de desfazer |
| Vazamento de dados financeiros | Somente leitura, cofre, criptografia, LGPD |

---

## 14. Perguntas em aberto

1. O piloto lança no Bling em contas a pagar/receber ou em caixa e bancos? Usa plano de contas?
2. O repasse do TikTok cai em qual conta? O saque da Carteira Shopee é manual ou automático?
3. O piloto já testou a importação OFX e a conciliação nativa do Bling? Por que não serviu?
4. Quantas movimentações por dia ele tem, somando as contas?
5. O que explica os R$ 3 mil? (resposta esperada da Fase 0)
6. Qual agregador Open Finance usar, e quanto custa por conexão?

---

## 15. Glossário

- **Repasse / liquidação:** valor que o marketplace transfere ao vendedor.
- **Liberação:** quando o dinheiro de uma venda fica disponível no saldo (MP/Shopee).
- **Bruto / líquido:** valor da venda antes e depois de taxas, frete e estornos.
- **Conciliação:** ligar um movimento a sua origem (repasse, transferência, despesa) e confirmar que os valores batem.
- **Transferência interna:** dinheiro entre contas do mesmo dono. Não é receita nem despesa.
- **Prova real do saldo:** saldo inicial + créditos − débitos deve ser igual ao saldo final.
