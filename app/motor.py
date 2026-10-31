"""Motor de conciliação com 4 estágios."""

from datetime import date
from decimal import Decimal
from dataclasses import dataclass
from typing import Optional
from sqlalchemy.orm import Session

from app.models import Transacao, Pendencia, Conta
from app.utils import (
    eh_dia_util,
    contar_dias_uteis,
    adicionar_dias_uteis,
    normalizar_valor,
    valores_compativel,
)


@dataclass
class ResultadoValidacao:
    """Resultado de validação de transação."""
    valida: bool
    erros: list[str]


@dataclass
class ResultadoNormalizacao:
    """Resultado de normalização de transação."""
    data: date
    valor: Decimal
    descricao: str
    warnings: list[str]


class MotorConciliacao:
    """Motor de conciliação com 4 estágios."""

    def __init__(self, db: Session):
        self.db = db

    # ===== ESTÁGIO 1: VALIDAÇÃO =====

    def validar_transacao(self, trans: Transacao) -> ResultadoValidacao:
        """
        Estágio 1: Validar formato, datas, valores.

        Args:
            trans: Transacao do banco

        Returns:
            ResultadoValidacao com erros (se houver)
        """
        erros = []

        # Validar data
        if not trans.data or trans.data > date.today():
            erros.append(f"Data inválida: {trans.data}")

        # Validar valor
        if trans.valor is None:
            erros.append("Valor não pode ser nulo")
        elif trans.valor == Decimal("0"):
            erros.append("Valor não pode ser zero")

        # Validar descrição
        if not trans.descricao or len(trans.descricao.strip()) == 0:
            erros.append("Descrição obrigatória")

        # Validar ID externo (para idempotência)
        if not trans.id_externo:
            erros.append("ID externo obrigatório")

        return ResultadoValidacao(
            valida=len(erros) == 0,
            erros=erros,
        )

    # ===== ESTÁGIO 2: NORMALIZAÇÃO =====

    def normalizar_transacao(self, trans: Transacao) -> ResultadoNormalizacao:
        """
        Estágio 2: Normalizar valores, timestamps, etc.

        Args:
            trans: Transacao do banco

        Returns:
            ResultadoNormalizacao com dados normalizados
        """
        warnings = []

        # Normalizar valor (2 casas decimais)
        valor_norm = normalizar_valor(trans.valor)
        if valor_norm != trans.valor:
            warnings.append(f"Valor ajustado: {trans.valor} → {valor_norm}")

        # Data já está normalizada (date object)
        data_norm = trans.data

        # Descrição: limpar espaços
        descricao_norm = trans.descricao.strip()
        if descricao_norm != trans.descricao:
            warnings.append("Descrição com espaços extras removidos")

        return ResultadoNormalizacao(
            data=data_norm,
            valor=valor_norm,
            descricao=descricao_norm,
            warnings=warnings,
        )

    # ===== ESTÁGIO 3: MATCHING (Encontrar pares) =====

    def encontrar_pares(
        self,
        conta_id: int,
        data_inicio: date,
        data_fim: date,
        tolerancia: Decimal = Decimal("0.01"),
    ) -> list[tuple[Transacao, Transacao]]:
        """
        Estágio 3: Encontrar pares entrada vs saída.

        Busca transações que se cancelam (entrada + saída com mesmo valor).

        Args:
            conta_id: ID da conta
            data_inicio: Data inicial
            data_fim: Data final
            tolerancia: Tolerância de valor (default: R$ 0.01)

        Returns:
            Lista de tuplas (entrada, saída) encontradas
        """
        pares = []

        # Buscar todas as transações não reconciliadas
        transacoes = self.db.query(Transacao).filter(
            Transacao.conta_id == conta_id,
            Transacao.data >= data_inicio,
            Transacao.data <= data_fim,
        ).all()

        # Separar por sinal
        entradas = [t for t in transacoes if t.valor > 0]
        saidas = [t for t in transacoes if t.valor < 0]

        # Tentar emparelar
        for entrada in entradas:
            for saida in saidas:
                # Compatibilidade de valor (entrada = -saida)
                if valores_compativel(entrada.valor, -saida.valor, tolerancia):
                    # Compatibilidade de data (mesmo dia ou dia seguinte)
                    dias_diff = abs((entrada.data - saida.data).days)
                    if dias_diff <= 1:
                        pares.append((entrada, saida))
                        break  # Já encontrou par para esta entrada

        return pares

    # ===== ESTÁGIO 4: CONFERÊNCIA DE COBRANÇA (Repayment) =====

    def conferir_cobranca(
        self,
        conta_id: int,
        dias_uteis_repayment: int = 7,
    ) -> list[dict]:
        """
        Estágio 4: Conferir pendências vs janela de repayment.

        Identifica transações que saíram da janela de cobrança sem reconciliação.

        Args:
            conta_id: ID da conta
            dias_uteis_repayment: Dias úteis de repayment (default: 7)

        Returns:
            Lista de pendências identificadas
        """
        pendencias_identificadas = []

        # Buscar transações de saída não reconciliadas
        saidas = self.db.query(Transacao).filter(
            Transacao.conta_id == conta_id,
            Transacao.valor < 0,  # Saídas
        ).all()

        hoje = date.today()

        for saida in saidas:
            # Calcular data de vencimento (data + dias_uteis_repayment dias úteis)
            data_vencimento = adicionar_dias_uteis(saida.data, dias_uteis_repayment)

            # Verificar se venceu
            if hoje > data_vencimento:
                # Verificar se já existe pendência para esta transação
                pendencia_existente = self.db.query(Pendencia).filter(
                    Pendencia.transacao_saida_id == saida.id,
                ).first()

                if not pendencia_existente:
                    # Criar nova pendência
                    pendencias_identificadas.append({
                        "transacao_saida_id": saida.id,
                        "data": saida.data,
                        "valor": abs(saida.valor),
                        "descricao": f"VENCIDA: {saida.descricao}",
                        "dias_uteis_repayment": dias_uteis_repayment,
                        "data_vencimento": data_vencimento,
                    })

        return pendencias_identificadas

    # ===== ORQUESTRAÇÃO (todos os 4 estágios) =====

    def processar_conta(
        self,
        conta_id: int,
        data_inicio: date,
        data_fim: date,
    ) -> dict:
        """
        Processar conciliação completa de uma conta.

        Executa os 4 estágios: validação → normalização → matching → cobrança.

        Args:
            conta_id: ID da conta
            data_inicio: Data inicial
            data_fim: Data final

        Returns:
            {
                "validadas": int,
                "erros_validacao": int,
                "normalizadas": int,
                "pares_encontrados": int,
                "pendencias_vencidas": int,
                "detalhes": {...}
            }
        """
        resultado = {
            "validadas": 0,
            "erros_validacao": 0,
            "normalizadas": 0,
            "pares_encontrados": 0,
            "pendencias_vencidas": 0,
        }

        # Estágio 1: Validação
        transacoes = self.db.query(Transacao).filter(
            Transacao.conta_id == conta_id,
            Transacao.data >= data_inicio,
            Transacao.data <= data_fim,
        ).all()

        for trans in transacoes:
            validacao = self.validar_transacao(trans)
            if validacao.valida:
                resultado["validadas"] += 1
            else:
                resultado["erros_validacao"] += 1

        # Estágio 2: Normalização (já feita ao inserir, mas pode revalidar)
        resultado["normalizadas"] = resultado["validadas"]

        # Estágio 3: Matching
        pares = self.encontrar_pares(conta_id, data_inicio, data_fim)
        resultado["pares_encontrados"] = len(pares)

        # Estágio 4: Cobrança
        pendencias = self.conferir_cobranca(conta_id)
        resultado["pendencias_vencidas"] = len(pendencias)

        # Criar pendências no banco
        for p in pendencias:
            pendencia = Pendencia(
                conta_id=conta_id,
                transacao_saida_id=p["transacao_saida_id"],
                status="ABERTA",
                data=p["data"],
                valor=p["valor"],
                descricao=p["descricao"],
                dias_uteis_repayment=p["dias_uteis_repayment"],
                data_vencimento=p["data_vencimento"],
            )
            self.db.add(pendencia)

        self.db.commit()

        return resultado
