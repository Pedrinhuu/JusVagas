import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import AsyncGenerator, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select, col

from config import PALAVRAS_CHAVE, CIDADES, BUSCA_INTERVALO_HORAS, BUSCAR_REMOTO, DIAS_MAX_VAGA
from database import engine, init_db, get_session
from models import Vaga
from scrapers import vaga_dentro_do_prazo
from scrapers.infojobs import buscar_infojobs
from scrapers.vagas_com import buscar_vagas_com
from scrapers.linkedin import buscar_linkedin
from scrapers.trabalha_brasil import buscar_trabalha_brasil

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("jusvagas")

ultima_busca: Optional[datetime] = None
busca_lock = asyncio.Lock()
scheduler = AsyncIOScheduler()

TERMOS_JURIDICOS = [
    "advogad", "jurídic", "juridic", "direito", "oab",
    "assessor jurídic", "consultor jurídic", "legal",
    "contencioso", "societário", "societario",
    "imobiliário", "imobiliario", "trabalhista",
    "tributário", "tributario", "compliance",
    "contrato", "paralegal", "estágio direito", "estagio direito",
]


def filtrar_relevancia(vaga: Vaga) -> bool:
    texto = f"{vaga.titulo} {vaga.descricao or ''}".lower()
    return any(termo in texto for termo in TERMOS_JURIDICOS)


async def executar_busca():
    global ultima_busca
    if busca_lock.locked():
        logger.info("Busca já em andamento, ignorando.")
        return
    async with busca_lock:
        await _executar_busca()


async def _executar_busca():
    global ultima_busca
    logger.info("Iniciando busca paralela de vagas em todas as fontes...")

    tarefas = []
    for query in PALAVRAS_CHAVE:
        for cidade in CIDADES:
            tarefas.append(buscar_infojobs(query, cidade))
            tarefas.append(buscar_linkedin(query, cidade, incluir_remoto=BUSCAR_REMOTO))
        tarefas.append(buscar_vagas_com(query, incluir_remoto=BUSCAR_REMOTO))
        tarefas.append(buscar_trabalha_brasil(query, incluir_remoto=BUSCAR_REMOTO))

    inicio = datetime.utcnow()
    resultados = await asyncio.gather(*tarefas, return_exceptions=True)

    todas_vagas: list[Vaga] = []
    for r in resultados:
        if isinstance(r, Exception):
            logger.error(f"Erro em tarefa paralela: {r}")
        else:
            todas_vagas.extend(r)

    duracao = (datetime.utcnow() - inicio).total_seconds()
    logger.info(f"Scraping concluído em {duracao:.1f}s — {len(todas_vagas)} vagas brutas de {len(tarefas)} tarefas")

    novas = 0
    duplicatas = 0
    descartadas_prazo = 0
    descartadas_relevancia = 0
    with Session(engine) as session:
        hashes_existentes = set(
            row[0] for row in session.exec(select(Vaga.hash_dedup)).all()
        )
        for vaga in todas_vagas:
            if vaga.hash_dedup in hashes_existentes:
                duplicatas += 1
                continue
            if not vaga_dentro_do_prazo(vaga.data_publicacao):
                descartadas_prazo += 1
                continue
            if not filtrar_relevancia(vaga):
                descartadas_relevancia += 1
                continue
            session.add(vaga)
            hashes_existentes.add(vaga.hash_dedup)
            novas += 1
        session.commit()

    ultima_busca = datetime.utcnow()
    logger.info(
        f"Busca finalizada: {len(todas_vagas)} brutas | "
        f"{novas} inseridas | {duplicatas} duplicatas | "
        f"{descartadas_prazo} fora do prazo | "
        f"{descartadas_relevancia} irrelevantes"
    )


async def executar_busca_stream() -> AsyncGenerator[dict, None]:
    global ultima_busca
    if busca_lock.locked():
        logger.info("Busca já em andamento, stream ignorado.")
        yield {"fim": True, "novas": 0, "total_bruto": 0,
               "duplicatas": 0, "descartadas_relevancia": 0, "erro": "busca_em_andamento"}
        return

    await busca_lock.acquire()
    try:
        logger.info("Iniciando busca com streaming...")

        fila: asyncio.Queue = asyncio.Queue()
        sentinel = object()

        async def wrapper_scraper(coro, nome: str):
            try:
                vagas = await coro
                for v in vagas:
                    await fila.put((nome, v))
            except Exception as e:
                logger.error(f"Erro em {nome}: {e}")

        tarefas = []
        for query in PALAVRAS_CHAVE:
            for cidade in CIDADES:
                tarefas.append(wrapper_scraper(
                    buscar_infojobs(query, cidade), f"Infojobs/{query}/{cidade}"))
                tarefas.append(wrapper_scraper(
                    buscar_linkedin(query, cidade, incluir_remoto=BUSCAR_REMOTO), f"LinkedIn/{query}/{cidade}"))
            tarefas.append(wrapper_scraper(
                buscar_vagas_com(query, incluir_remoto=BUSCAR_REMOTO), f"Vagas.com/{query}"))
            tarefas.append(wrapper_scraper(
                buscar_trabalha_brasil(query, incluir_remoto=BUSCAR_REMOTO), f"TrabalhaBrasil/{query}"))

        async def rodar_todas():
            await asyncio.gather(*tarefas)
            await fila.put(sentinel)

        asyncio.create_task(rodar_todas())

        novas = 0
        duplicatas = 0
        descartadas_prazo = 0
        descartadas_relevancia = 0
        total_bruto = 0

        with Session(engine) as session:
            hashes_existentes = set(
                row[0] for row in session.exec(select(Vaga.hash_dedup)).all()
            )

            while True:
                item = await fila.get()
                if item is sentinel:
                    break

                nome, vaga = item
                total_bruto += 1

                if vaga.hash_dedup in hashes_existentes:
                    duplicatas += 1
                    continue
                if not vaga_dentro_do_prazo(vaga.data_publicacao):
                    descartadas_prazo += 1
                    continue
                if not filtrar_relevancia(vaga):
                    descartadas_relevancia += 1
                    continue

                session.add(vaga)
                session.flush()
                session.refresh(vaga)
                hashes_existentes.add(vaga.hash_dedup)
                novas += 1

                yield {
                    "id": vaga.id,
                    "titulo": vaga.titulo,
                    "empresa": vaga.empresa,
                    "cidade": vaga.cidade,
                    "estado": vaga.estado,
                    "regime": vaga.regime,
                    "area": vaga.area,
                    "modalidade": vaga.modalidade,
                    "descricao": vaga.descricao,
                    "url": vaga.url,
                    "fonte": vaga.fonte,
                    "data_publicacao": vaga.data_publicacao.isoformat() if vaga.data_publicacao else None,
                    "data_captura": vaga.data_captura.isoformat() if vaga.data_captura else None,
                    "status": vaga.status,
                    "nota": vaga.nota,
                    "ativa": vaga.ativa,
                }

            session.commit()

        ultima_busca = datetime.utcnow()
        logger.info(
            f"Busca stream finalizada: {total_bruto} brutas | "
            f"{novas} inseridas | {duplicatas} duplicatas | "
            f"{descartadas_prazo} fora do prazo | "
            f"{descartadas_relevancia} irrelevantes"
        )

        yield {"fim": True, "novas": novas, "total_bruto": total_bruto,
               "duplicatas": duplicatas, "descartadas_relevancia": descartadas_relevancia}
    finally:
        busca_lock.release()


async def manutencao_vagas():
    logger.info("Executando manutenção de vagas...")
    agora = datetime.utcnow()
    limite_publicacao = agora - timedelta(days=DIAS_MAX_VAGA)
    limite_captura_sem_data = agora - timedelta(days=15)

    with Session(engine) as session:
        vagas_antigas = session.exec(
            select(Vaga).where(
                Vaga.ativa == True,  # noqa: E712
                Vaga.data_publicacao != None,  # noqa: E711
                Vaga.data_publicacao < limite_publicacao,
            )
        ).all()

        vagas_sem_data = session.exec(
            select(Vaga).where(
                Vaga.ativa == True,  # noqa: E712
                Vaga.data_publicacao == None,  # noqa: E711
                Vaga.data_captura < limite_captura_sem_data,
            )
        ).all()

        total = 0
        for vaga in vagas_antigas + vagas_sem_data:
            vaga.ativa = False
            session.add(vaga)
            total += 1
        session.commit()

    logger.info(f"Manutenção: {total} vagas marcadas como inativas.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.add_job(executar_busca, "interval", hours=BUSCA_INTERVALO_HORAS, id="busca_periodica")
    scheduler.add_job(manutencao_vagas, "cron", hour=0, minute=0, id="manutencao_diaria")
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="JusVagas", version="2.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    return FileResponse("static/index.html")


class StatusUpdate(BaseModel):
    status: str

class NotaUpdate(BaseModel):
    nota: str


@app.get("/api/vagas")
async def listar_vagas(
    status: Optional[str] = None,
    area: Optional[str] = None,
    regime: Optional[str] = None,
    fonte: Optional[str] = None,
    modalidade: Optional[str] = None,
    q: Optional[str] = None,
    cidade: Optional[str] = None,
    incluir_inativas: bool = Query(default=False),
    ordenar: str = Query(default="recentes"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    query = select(Vaga)

    if not incluir_inativas:
        query = query.where(Vaga.ativa == True)  # noqa: E712

    if status:
        query = query.where(Vaga.status == status)
    if area:
        query = query.where(Vaga.area == area)
    if regime:
        query = query.where(Vaga.regime == regime)
    if fonte:
        query = query.where(Vaga.fonte == fonte)
    if modalidade:
        query = query.where(Vaga.modalidade == modalidade)
    if cidade:
        query = query.where(col(Vaga.cidade).contains(cidade))
    if q:
        query = query.where(
            col(Vaga.titulo).contains(q) | col(Vaga.descricao).contains(q)
        )

    if ordenar == "antigas":
        query = query.order_by(
            col(Vaga.data_publicacao).asc().nulls_last()
        )
    else:
        query = query.order_by(
            col(Vaga.data_publicacao).desc().nulls_last()
        )

    query = query.offset(offset).limit(limit)
    vagas = session.exec(query).all()
    return vagas


@app.patch("/api/vagas/{vaga_id}/status")
async def atualizar_status(vaga_id: int, body: StatusUpdate, session: Session = Depends(get_session)):
    vaga = session.get(Vaga, vaga_id)
    if not vaga:
        raise HTTPException(status_code=404, detail="Vaga não encontrada")
    if body.status not in ("nova", "favorita", "aplicada", "descartada"):
        raise HTTPException(status_code=400, detail="Status inválido")
    vaga.status = body.status
    session.add(vaga)
    session.commit()
    session.refresh(vaga)
    return vaga


@app.patch("/api/vagas/{vaga_id}/nota")
async def atualizar_nota(vaga_id: int, body: NotaUpdate, session: Session = Depends(get_session)):
    vaga = session.get(Vaga, vaga_id)
    if not vaga:
        raise HTTPException(status_code=404, detail="Vaga não encontrada")
    vaga.nota = body.nota
    session.add(vaga)
    session.commit()
    session.refresh(vaga)
    return vaga


@app.delete("/api/vagas/{vaga_id}")
async def deletar_vaga(vaga_id: int, session: Session = Depends(get_session)):
    vaga = session.get(Vaga, vaga_id)
    if not vaga:
        raise HTTPException(status_code=404, detail="Vaga não encontrada")
    session.delete(vaga)
    session.commit()
    return {"ok": True}


@app.get("/api/buscar/stream")
async def buscar_stream():
    async def gerador():
        async for vaga_dict in executar_busca_stream():
            yield f"data: {json.dumps(vaga_dict, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        gerador(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/buscar")
async def buscar_manual():
    asyncio.create_task(executar_busca())
    return {"mensagem": "Busca iniciada em segundo plano"}


@app.get("/api/status")
async def status_sistema(session: Session = Depends(get_session)):
    total = len(session.exec(select(Vaga).where(Vaga.ativa == True)).all())  # noqa: E712
    hoje = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    novas_hoje = len(session.exec(
        select(Vaga).where(Vaga.data_captura >= hoje, Vaga.ativa == True)  # noqa: E712
    ).all())
    return {
        "ultima_busca": ultima_busca.isoformat() if ultima_busca else None,
        "total_vagas": total,
        "vagas_novas_hoje": novas_hoje,
        "intervalo_horas": BUSCA_INTERVALO_HORAS,
    }
