import asyncio
import logging
from datetime import datetime
from typing import List

import httpx
from bs4 import BeautifulSoup

from models import Vaga
from scrapers import gerar_hash, detectar_modalidade, HEADERS_BROWSER, semaforos

logger = logging.getLogger(__name__)

BASE_URL = "https://www.linkedin.com/jobs/search/"

PAISES_INVALIDOS = [
    "estados unidos", "united states", "argentina", "chile",
    "colombia", "mexico", "méxico", "portugal", "espanha", "spain",
    "united kingdom", "canada", "france", "germany", "italy",
    "australia", "india", "peru", "uruguay", "paraguai",
]


def eh_localizacao_valida(cidade: str) -> bool:
    if not cidade:
        return True
    cidade_lower = cidade.lower()
    return not any(pais in cidade_lower for pais in PAISES_INVALIDOS)


async def buscar_linkedin(query: str, cidade: str = "Rio de Janeiro", incluir_remoto: bool = False) -> List[Vaga]:
    async with semaforos["linkedin"]:
        return await _buscar_linkedin(query, cidade, incluir_remoto)


async def _buscar_linkedin(query: str, cidade: str, incluir_remoto: bool) -> List[Vaga]:
    vagas = []
    hashes = set()

    params_list = [
        {"keywords": query, "location": cidade, "f_TPR": "r2592000", "position": "1", "pageNum": "0"},
    ]

    if incluir_remoto:
        params_list.append(
            {"keywords": query, "location": "Brasil", "f_WT": "2", "f_TPR": "r2592000", "position": "1", "pageNum": "0"}
        )

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=HEADERS_BROWSER) as client:
            for params in params_list:
                try:
                    resp = await client.get(BASE_URL, params=params)

                    if resp.status_code == 403:
                        logger.warning(f"LinkedIn: 403 Forbidden para query='{query}'")
                        continue
                    if resp.status_code != 200:
                        logger.warning(f"LinkedIn: status {resp.status_code} para query='{query}'")
                        continue

                    soup = BeautifulSoup(resp.text, "html.parser")
                    cards = soup.select("div.job-search-card")

                    for card in cards:
                        titulo_el = card.select_one("h3.base-search-card__title")
                        empresa_el = card.select_one("h4.base-search-card__subtitle")
                        local_el = card.select_one("span.job-search-card__location")
                        data_el = card.select_one("time.job-search-card__listdate, time.job-search-card__listdate--new")
                        link_el = card.select_one("a.base-card__full-link")

                        titulo = titulo_el.get_text(strip=True) if titulo_el else ""
                        if not titulo:
                            continue

                        empresa = empresa_el.get_text(strip=True) if empresa_el else "Não informada"
                        local = local_el.get_text(strip=True) if local_el else cidade

                        data_pub = None
                        if data_el and data_el.get("datetime"):
                            try:
                                data_pub = datetime.fromisoformat(data_el["datetime"])
                            except (ValueError, TypeError):
                                pass

                        href = link_el.get("href", "").split("?")[0] if link_el else ""

                        is_remoto = "f_WT" in str(params.get("f_WT", ""))
                        modalidade = "remoto" if is_remoto else detectar_modalidade(titulo, local)

                        cidade_vaga = local.replace(" e Região", "").strip()
                        estado_vaga = ""
                        if ", " in cidade_vaga:
                            partes = cidade_vaga.rsplit(", ", 1)
                            cidade_vaga = partes[0]
                            estado_vaga = partes[1][:2] if len(partes) > 1 else ""

                        if not eh_localizacao_valida(cidade_vaga):
                            continue

                        h = gerar_hash(titulo, empresa, href)
                        if h in hashes:
                            continue
                        hashes.add(h)

                        vagas.append(Vaga(
                            titulo=titulo,
                            empresa=empresa,
                            cidade=cidade_vaga,
                            estado=estado_vaga or "RJ",
                            modalidade=modalidade,
                            url=href,
                            fonte="LinkedIn",
                            data_publicacao=data_pub,
                            hash_dedup=h,
                        ))

                    await asyncio.sleep(3)
                except Exception as e:
                    logger.error(f"Erro ao buscar LinkedIn (query={query}): {e}")

        logger.info(f"LinkedIn: {len(vagas)} vagas encontradas para '{query}'")
    except Exception as e:
        logger.error(f"Erro geral LinkedIn (query={query}): {e}")

    return vagas
