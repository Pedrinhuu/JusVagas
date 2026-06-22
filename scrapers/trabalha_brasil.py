import asyncio
import logging
from typing import List

import httpx
from bs4 import BeautifulSoup

from models import Vaga
from scrapers import gerar_hash, detectar_modalidade, HEADERS_BROWSER, semaforos

logger = logging.getLogger(__name__)

BASE_URL = "https://www.trabalhabrasil.com.br/vagas-de-emprego"


async def buscar_trabalha_brasil(query: str, incluir_remoto: bool = False) -> List[Vaga]:
    async with semaforos["trabalha_brasil"]:
        return await _buscar_trabalha_brasil(query, incluir_remoto)


async def _buscar_trabalha_brasil(query: str, incluir_remoto: bool) -> List[Vaga]:
    vagas = []
    slug = query.lower().replace(" ", "-")
    urls = [f"{BASE_URL}/{slug}"]

    if incluir_remoto:
        urls.append(f"{BASE_URL}-home-office/{slug}")

    hashes = set()

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=HEADERS_BROWSER) as client:
            for url in urls:
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        logger.warning(f"TrabalhaBrasil: status {resp.status_code} para {url}")
                        continue

                    soup = BeautifulSoup(resp.text, "html.parser")
                    cards = soup.select("article.job-card")

                    for card in cards:
                        titulo_el = card.select_one("h2.job-title")
                        empresa_el = card.select_one("p.job-company")
                        local_el = card.select_one("p.job-location")
                        tipo_el = card.select_one("li.job-detail--type")
                        regime_el = card.select_one("li.job-detail--employment")
                        link_el = card.select_one("a.job-link")

                        titulo = titulo_el.get_text(strip=True) if titulo_el else ""
                        if titulo.startswith("Vaga de "):
                            titulo = titulo[8:]
                        if not titulo:
                            continue

                        empresa = empresa_el.get_text(strip=True) if empresa_el else "Não informada"
                        local_raw = local_el.get_text(strip=True) if local_el else ""
                        tipo = tipo_el.get_text(strip=True) if tipo_el else ""
                        regime = regime_el.get_text(strip=True) if regime_el else None

                        href = link_el.get("href", "") if link_el else ""
                        if href and not href.startswith("http"):
                            href = f"https://www.trabalhabrasil.com.br{href}"

                        cidade_vaga = ""
                        estado_vaga = ""
                        if "/" in local_raw:
                            partes = local_raw.rsplit("/", 1)
                            cidade_vaga = partes[0].strip()
                            estado_vaga = partes[1].strip()[:2] if len(partes) > 1 else ""

                        modalidade = detectar_modalidade(titulo, tipo)
                        if "home-office" in url or tipo.lower() in ["home office", "remoto"]:
                            modalidade = "remoto"
                        elif tipo.lower() in ["híbrido", "hibrido"]:
                            modalidade = "híbrido"

                        h = gerar_hash(titulo, empresa, href)
                        if h in hashes:
                            continue
                        hashes.add(h)

                        vagas.append(Vaga(
                            titulo=titulo,
                            empresa=empresa,
                            cidade=cidade_vaga or "Não informada",
                            estado=estado_vaga,
                            regime=regime,
                            modalidade=modalidade,
                            url=href,
                            fonte="TrabalhaBrasil",
                            hash_dedup=h,
                        ))

                    await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"Erro ao buscar TrabalhaBrasil ({url}): {e}")

        logger.info(f"TrabalhaBrasil: {len(vagas)} vagas encontradas para '{query}'")
    except Exception as e:
        logger.error(f"Erro geral TrabalhaBrasil (query={query}): {e}")

    return vagas
