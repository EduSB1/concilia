"""Serviços de negócio (sincronização, conciliação)."""

from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models import Conta, Transacao, Pendencia
from app.conectores import Transacao as TransacaoConector


class SincronizadorTransacoes:
    """Sincroniza transações dos conectores para o banco."""

    def __init__(self, db: Session):
        self.db = db

    def sincronizar_fonte(self, conector, fonte: str, data_inicio: date, data_fim: date) -> dict:
        """
        Sincronizar transações de um conector.

        Args:
            conector: Instância de ConectorBase
            fonte: Nome da fonte (inter_api, mercadopago_api, etc)
            data_inicio: Data inicial
            data_fim: Data final

        Returns:
            {
                "sucesso": bool,
                "contas_sincronizadas": int,
                "transacoes_inseridas": int,
                "transacoes_atualizadas": int,
                "transacoes_ignoradas": int,  # Já existiam
                "erros": [str]
            }
        """
        resultado = {
            "sucesso": False,
            "contas_sincronizadas": 0,
            "transacoes_inseridas": 0,
            "transacoes_atualizadas": 0,
            "transacoes_ignoradas": 0,
            "erros": [],
        }

        try:
            # 1. Validar autenticação
            if not conector.autenticar():
                resultado["erros"].append(f"Falha na autenticação do {fonte}")
                return resultado

            # 2. Sincronizar contas
            contas_externas = conector.listar_contas()
            for conta_ext in contas_externas:
                try:
                    conta = self._sincronizar_conta(
                        fonte=fonte,
                        conta_ext=conta_ext,
                    )
                    resultado["contas_sincronizadas"] += 1
                except Exception as e:
                    resultado["erros"].append(f"Erro ao sincronizar conta {conta_ext.get('nome')}: {e}")

            # 3. Sincronizar transações de cada conta
            for conta_ext in contas_externas:
                try:
                    # Encontrar conta no BD
                    conta = self.db.query(Conta).filter(
                        Conta.fonte == fonte,
                        Conta.conta_id_externo == conta_ext.get("id", ""),
                    ).first()

                    if not conta:
                        continue

                    # Puxar transações do conector
                    transacoes_ext = conector.extrato(data_inicio, data_fim)

                    for trans_ext in transacoes_ext:
                        stats = self._sincronizar_transacao(conta.id, trans_ext)
                        resultado["transacoes_inseridas"] += stats["inserida"]
                        resultado["transacoes_atualizadas"] += stats["atualizada"]
                        resultado["transacoes_ignoradas"] += stats["ignorada"]

                except Exception as e:
                    resultado["erros"].append(f"Erro ao sincronizar transações da conta {conta_ext.get('nome')}: {e}")

            resultado["sucesso"] = len(resultado["erros"]) == 0
            self.db.commit()
            return resultado

        except Exception as e:
            resultado["erros"].append(f"Erro crítico: {e}")
            self.db.rollback()
            return resultado

    def _sincronizar_conta(self, fonte: str, conta_ext: dict) -> Conta:
        """
        Sincronizar ou criar conta.

        Args:
            fonte: Nome da fonte
            conta_ext: Dict com {id, nome, tipo, ...}

        Returns:
            Conta sincronizada
        """
        # Buscar por unique constraint
        conta = self.db.query(Conta).filter(
            Conta.fonte == fonte,
            Conta.conta_id_externo == conta_ext.get("id", ""),
        ).first()

        if conta:
            # Atualizar
            conta.nome = conta_ext.get("nome", conta.nome)
            conta.tipo = conta_ext.get("tipo", conta.tipo)
            conta.saldo = Decimal(str(conta_ext.get("saldo", 0)))
        else:
            # Criar nova
            conta = Conta(
                fonte=fonte,
                conta_id_externo=conta_ext.get("id", ""),
                nome=conta_ext.get("nome", "Sem nome"),
                tipo=conta_ext.get("tipo", "desconhecido"),
                saldo=Decimal(str(conta_ext.get("saldo", 0))),
            )
            self.db.add(conta)

        self.db.flush()  # Populate ID
        return conta

    def _sincronizar_transacao(self, conta_id: int, trans_ext: TransacaoConector) -> dict:
        """
        Sincronizar ou ignorar transação (idempotência).

        Args:
            conta_id: ID da conta no BD
            trans_ext: Transacao normalizada do conector

        Returns:
            {inserida: 0/1, atualizada: 0/1, ignorada: 0/1}
        """
        resultado = {"inserida": 0, "atualizada": 0, "ignorada": 0}

        # Buscar por unique constraint (conta_id, id_externo)
        trans = self.db.query(Transacao).filter(
            Transacao.conta_id == conta_id,
            Transacao.id_externo == trans_ext.id_externo,
        ).first()

        if trans:
            # Já existe: ignorar (idempotência)
            resultado["ignorada"] = 1
        else:
            # Inserir nova
            trans = Transacao(
                conta_id=conta_id,
                data=trans_ext.data,
                valor=trans_ext.valor,
                descricao=trans_ext.descricao,
                contraparte=trans_ext.contraparte or "",
                id_externo=trans_ext.id_externo,
                fonte=trans_ext.fonte,
                dados_brutos=str(trans_ext.tags or {}),
            )
            self.db.add(trans)
            resultado["inserida"] = 1

        self.db.flush()
        return resultado
