-- 001_inicial.sql — esquema da Fase 1 (SPEC seção 6)
-- PostgreSQL. Dinheiro sempre NUMERIC(14,2), nunca float (RNF-01).
-- Datas de evento em DATE; carimbos de sistema em TIMESTAMPTZ/UTC (RNF-02).

BEGIN;

CREATE TABLE empresas (
  id         SERIAL PRIMARY KEY,
  nome       TEXT NOT NULL,
  cnpj       TEXT,
  criado_em  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Uma linha por fonte conectada. O token NUNCA mora aqui: só a
-- referência ao cofre de segredos (RNF-03).
CREATE TABLE conexoes (
  id           SERIAL PRIMARY KEY,
  empresa_id   INT NOT NULL REFERENCES empresas(id),
  fonte        TEXT NOT NULL
               CHECK (fonte IN ('inter', 'mercadopago', 'mercadolivre',
                                'shopee', 'tiktok', 'bling', 'ofx')),
  status       TEXT NOT NULL DEFAULT 'ok'
               CHECK (status IN ('ok', 'expirada', 'erro')),
  segredo_ref  TEXT,
  ultima_sync  TIMESTAMPTZ
);

CREATE TABLE contas (
  id          SERIAL PRIMARY KEY,
  empresa_id  INT NOT NULL REFERENCES empresas(id),
  conexao_id  INT REFERENCES conexoes(id),
  nome        TEXT NOT NULL,
  tipo        TEXT NOT NULL
              CHECK (tipo IN ('banco', 'carteira_marketplace', 'investimento')),
  UNIQUE (empresa_id, nome)
);

-- Payload bruto de toda ingestão: sem ele não dá para reprocessar quando
-- o motor melhorar nem para provar de onde veio um número (RF-11).
CREATE TABLE ingestoes_raw (
  id           BIGSERIAL PRIMARY KEY,
  conexao_id   INT REFERENCES conexoes(id),
  recebido_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
  payload      JSONB NOT NULL
);

CREATE TABLE lancamentos (
  id          BIGSERIAL PRIMARY KEY,
  conta_id    INT NOT NULL REFERENCES contas(id),
  data        DATE NOT NULL,
  valor       NUMERIC(14,2) NOT NULL,          -- + entrada / - saída
  descricao   TEXT,
  contraparte TEXT,
  id_externo  TEXT,
  categoria   TEXT,
  status      TEXT NOT NULL DEFAULT 'pendente'
              CHECK (status IN ('pendente', 'conciliado', 'ignorado')),
  confianca   NUMERIC(3,2) CHECK (confianca IS NULL OR confianca BETWEEN 0 AND 1),
  bling_id    TEXT,
  raw_id      BIGINT REFERENCES ingestoes_raw(id),
  criado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT valor_nao_zero CHECK (valor <> 0)
);

-- Reimportar o mesmo extrato não pode duplicar (RF-12). O índice é
-- parcial porque nem toda fonte entrega id: sem id_externo, não há como
-- afirmar que duas linhas iguais são o mesmo movimento.
CREATE UNIQUE INDEX lancamentos_idempotencia
  ON lancamentos (conta_id, id_externo)
  WHERE id_externo IS NOT NULL AND id_externo <> '';

CREATE INDEX lancamentos_busca_motor ON lancamentos (data, valor)
  WHERE status = 'pendente';

CREATE TABLE repasses (
  id             BIGSERIAL PRIMARY KEY,
  empresa_id     INT NOT NULL REFERENCES empresas(id),
  marketplace    TEXT NOT NULL
                 CHECK (marketplace IN ('mercado_livre', 'mercado_pago',
                                        'shopee', 'tiktok')),
  data_prevista  DATE,
  valor_bruto    NUMERIC(14,2) NOT NULL DEFAULT 0,
  taxas          NUMERIC(14,2) NOT NULL DEFAULT 0,
  frete          NUMERIC(14,2) NOT NULL DEFAULT 0,
  estornos       NUMERIC(14,2) NOT NULL DEFAULT 0,
  valor_liquido  NUMERIC(14,2) NOT NULL,
  id_externo     TEXT,
  status         TEXT NOT NULL DEFAULT 'aguardando'
                 CHECK (status IN ('aguardando', 'recebido', 'divergente', 'retido')),
  criado_em      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (marketplace, id_externo)
);

CREATE INDEX repasses_aguardando ON repasses (data_prevista)
  WHERE status = 'aguardando';

-- Fase 4: a decomposição pedido a pedido. A tabela entra agora porque o
-- conector que trouxer o repasse já conhece os itens; preenchê-la cedo
-- custa pouco e evita refazer a ingestão depois.
CREATE TABLE repasse_itens (
  id          BIGSERIAL PRIMARY KEY,
  repasse_id  BIGINT NOT NULL REFERENCES repasses(id) ON DELETE CASCADE,
  pedido_id   TEXT,
  tipo        TEXT CHECK (tipo IN ('venda', 'comissao', 'frete', 'estorno', 'ajuste')),
  valor       NUMERIC(14,2) NOT NULL
);

-- Quem decidiu o quê (RNF-08). Um crédito pode fechar vários repasses e
-- um repasse pode cair fracionado, por isso as pontas vão em tabela
-- própria em vez de uma coluna só.
CREATE TABLE conciliacoes (
  id           BIGSERIAL PRIMARY KEY,
  tipo         TEXT NOT NULL
               CHECK (tipo IN ('transferencia_interna', 'repasse', 'regra', 'manual')),
  confianca    NUMERIC(3,2) NOT NULL CHECK (confianca BETWEEN 0 AND 1),
  decidido_por TEXT NOT NULL DEFAULT 'motor',   -- motor | ia | usuario:<id>
  observacao   TEXT,
  criado_em    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE conciliacao_lancamentos (
  conciliacao_id BIGINT NOT NULL REFERENCES conciliacoes(id) ON DELETE CASCADE,
  lancamento_id  BIGINT NOT NULL REFERENCES lancamentos(id),
  papel          TEXT NOT NULL DEFAULT 'principal'
                 CHECK (papel IN ('principal', 'par')),   -- 'par' = outra ponta da transferência
  PRIMARY KEY (conciliacao_id, lancamento_id)
);

CREATE TABLE conciliacao_repasses (
  conciliacao_id BIGINT NOT NULL REFERENCES conciliacoes(id) ON DELETE CASCADE,
  repasse_id     BIGINT NOT NULL REFERENCES repasses(id),
  PRIMARY KEY (conciliacao_id, repasse_id)
);

-- Menor prioridade é avaliada primeiro; a primeira que casar vence.
CREATE TABLE regras_categoria (
  id          SERIAL PRIMARY KEY,
  empresa_id  INT NOT NULL REFERENCES empresas(id),
  campo       TEXT NOT NULL DEFAULT 'descricao'
              CHECK (campo IN ('descricao', 'contraparte', 'ambos')),
  padrao      TEXT NOT NULL,
  categoria   TEXT NOT NULL,
  prioridade  INT NOT NULL DEFAULT 100,
  criado_por  TEXT NOT NULL DEFAULT 'sistema'
);

CREATE TABLE mapa_bling (
  empresa_id         INT NOT NULL REFERENCES empresas(id),
  categoria          TEXT NOT NULL,
  bling_categoria_id TEXT NOT NULL,
  PRIMARY KEY (empresa_id, categoria)
);

COMMIT;
