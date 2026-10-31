
# ===== ENDPOINTS DE SINCRONIZAÇÃO =====
from app.services import SincronizadorTransacoes
from app.conectores.inter import InterAPI
from app.conectores.mercadopago import MercadoPagoAPI
from app.conectores.bling import BlingAPI


@app.post("/api/sync/inter")
def sync_inter(db: Session = Depends(get_db)):
    """Sincronizar transações do Inter."""
    try:
        from datetime import date, timedelta
        
        conector = InterAPI()
        sincronizador = SincronizadorTransacoes(db)
        
        # Puxar últimos 30 dias
        data_fim = date.today()
        data_inicio = data_fim - timedelta(days=30)
        
        resultado = sincronizador.sincronizar_fonte(
            conector=conector,
            fonte="inter_api",
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        return {"status": "success", "data": resultado}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 400


@app.post("/api/sync/mercadopago")
def sync_mercadopago(db: Session = Depends(get_db)):
    """Sincronizar transações do Mercado Pago."""
    try:
        from datetime import date, timedelta
        
        conector = MercadoPagoAPI()
        sincronizador = SincronizadorTransacoes(db)
        
        data_fim = date.today()
        data_inicio = data_fim - timedelta(days=30)
        
        resultado = sincronizador.sincronizar_fonte(
            conector=conector,
            fonte="mercadopago_api",
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        return {"status": "success", "data": resultado}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 400


@app.post("/api/sync/bling")
def sync_bling(db: Session = Depends(get_db)):
    """Sincronizar notas fiscais do Bling."""
    try:
        from datetime import date, timedelta
        
        conector = BlingAPI()
        sincronizador = SincronizadorTransacoes(db)
        
        data_fim = date.today()
        data_inicio = data_fim - timedelta(days=30)
        
        resultado = sincronizador.sincronizar_fonte(
            conector=conector,
            fonte="bling_api",
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        return {"status": "success", "data": resultado}
    except Exception as e:
        return {"status": "error", "message": str(e)}, 400


@app.get("/api/contas")
def listar_contas(db: Session = Depends(get_db)):
    """Listar todas as contas sincronizadas."""
    contas = db.query(Conta).all()
    return {
        "total": len(contas),
        "contas": [
            {
                "id": c.id,
                "fonte": c.fonte,
                "nome": c.nome,
                "tipo": c.tipo,
                "saldo": str(c.saldo),
            }
            for c in contas
        ],
    }


@app.get("/api/transacoes")
def listar_transacoes(conta_id: int = None, fonte: str = None, db: Session = Depends(get_db)):
    """Listar transações com filtro opcional."""
    query = db.query(Transacao)
    
    if conta_id:
        query = query.filter(Transacao.conta_id == conta_id)
    if fonte:
        query = query.filter(Transacao.fonte == fonte)
    
    transacoes = query.order_by(Transacao.data.desc()).limit(100).all()
    return {
        "total": len(transacoes),
        "transacoes": [
            {
                "id": t.id,
                "data": t.data.isoformat(),
                "valor": str(t.valor),
                "descricao": t.descricao,
                "contraparte": t.contraparte,
                "fonte": t.fonte,
                "id_externo": t.id_externo,
            }
            for t in transacoes
        ],
    }


# Importar modelos para Depends
from app.models import Conta, Transacao


# ===== ENDPOINT DE ORQUESTRAÇÃO =====

@app.post("/api/processar-conta")
def processar_conta(
    conta_id: int,
    data_inicio: str = None,
    data_fim: str = None,
    db: Session = Depends(get_db)
):
    """
    Orquestrar sincronizador + motor para uma conta.

    Fluxo completo:
    1. Validar se conta existe
    2. Processar motor (validação, normalização, matching, cobrança)
    3. Retornar resultado

    Args:
        conta_id: ID da conta (do BD)
        data_inicio: Data inicial (YYYY-MM-DD). Default: 30 dias atrás
        data_fim: Data final (YYYY-MM-DD). Default: hoje

    Returns:
        {
            "status": "success",
            "conta": {...},
            "resultado_motor": {
                "validadas": int,
                "erros_validacao": int,
                "normalizadas": int,
                "pares_encontrados": int,
                "pendencias_vencidas": int,
            },
            "transacoes_totais": int,
            "pendencias_abertas": int,
        }
    """
    try:
        from datetime import date, timedelta
        
        # Validar conta
        conta = db.query(Conta).filter(Conta.id == conta_id).first()
        if not conta:
            return {"status": "error", "message": f"Conta {conta_id} não encontrada"}, 404
        
        # Parser datas
        if not data_fim:
            data_fim = date.today()
        else:
            data_fim = date.fromisoformat(data_fim)
        
        if not data_inicio:
            data_inicio = data_fim - timedelta(days=30)
        else:
            data_inicio = date.fromisoformat(data_inicio)
        
        # Processar motor
        from app.motor import MotorConciliacao
        motor = MotorConciliacao(db)
        
        resultado_motor = motor.processar_conta(
            conta_id=conta_id,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        
        # Contar resultados
        transacoes_totais = db.query(Transacao).filter(
            Transacao.conta_id == conta_id
        ).count()
        
        pendencias_abertas = db.query(Pendencia).filter(
            Pendencia.conta_id == conta_id,
            Pendencia.status == "ABERTA",
        ).count()
        
        return {
            "status": "success",
            "conta": {
                "id": conta.id,
                "fonte": conta.fonte,
                "nome": conta.nome,
                "tipo": conta.tipo,
            },
            "periodo": {
                "data_inicio": data_inicio.isoformat(),
                "data_fim": data_fim.isoformat(),
            },
            "resultado_motor": resultado_motor,
            "totais": {
                "transacoes": transacoes_totais,
                "pendencias_abertas": pendencias_abertas,
            },
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}, 400


@app.post("/api/sincronizar-e-processar")
def sincronizar_e_processar(
    fonte: str,
    data_inicio: str = None,
    data_fim: str = None,
    db: Session = Depends(get_db),
):
    """
    Sincronizar uma fonte E DEPOIS processar o motor automaticamente.

    Fluxo:
    1. Puxar dados do conector
    2. Sincronizar no BD
    3. Processar motor
    4. Retornar resultado completo

    Args:
        fonte: "inter_api", "mercadopago_api", "bling_api", "shopee_api", "tiktok_api"
        data_inicio: Data inicial. Default: 30 dias atrás
        data_fim: Data final. Default: hoje

    Returns:
        {
            "status": "success",
            "sincronizacao": {...},
            "processamento": {...},
        }
    """
    try:
        from datetime import date, timedelta
        from app.conectores.inter import InterAPI
        from app.conectores.mercadopago import MercadoPagoAPI
        from app.conectores.bling import BlingAPI
        
        # Parser datas
        if not data_fim:
            data_fim = date.today()
        else:
            data_fim = date.fromisoformat(data_fim)
        
        if not data_inicio:
            data_inicio = data_fim - timedelta(days=30)
        else:
            data_inicio = date.fromisoformat(data_inicio)
        
        # Selecionar conector
        conectores = {
            "inter_api": InterAPI(),
            "mercadopago_api": MercadoPagoAPI(),
            "bling_api": BlingAPI(),
        }
        
        if fonte not in conectores:
            return {
                "status": "error",
                "message": f"Fonte '{fonte}' não suportada. Use: {', '.join(conectores.keys())}",
            }, 400
        
        conector = conectores[fonte]
        
        # PASSO 1: Sincronizar
        sincronizador = SincronizadorTransacoes(db)
        sync_result = sincronizador.sincronizar_fonte(
            conector=conector,
            fonte=fonte,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        
        if not sync_result["sucesso"]:
            return {
                "status": "error",
                "message": "Sincronização falhou",
                "detalhes": sync_result["erros"],
            }, 400
        
        # PASSO 2: Encontrar conta sincronizada
        conta = db.query(Conta).filter(Conta.fonte == fonte).first()
        if not conta:
            return {
                "status": "error",
                "message": "Conta não encontrada após sincronização",
            }, 400
        
        # PASSO 3: Processar motor
        from app.motor import MotorConciliacao
        motor = MotorConciliacao(db)
        
        motor_result = motor.processar_conta(
            conta_id=conta.id,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        
        return {
            "status": "success",
            "sincronizacao": {
                "fonte": fonte,
                "contas_sincronizadas": sync_result["contas_sincronizadas"],
                "transacoes_inseridas": sync_result["transacoes_inseridas"],
                "transacoes_ignoradas": sync_result["transacoes_ignoradas"],
                "erros": sync_result["erros"],
            },
            "processamento": motor_result,
            "conta_id": conta.id,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}, 400
