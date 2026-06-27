import asyncio
import logging
from typing import List

import httpx
from bs4 import BeautifulSoup

from models import Vaga
from scrapers import gerar_hash, detectar_modalidade, HEADERS_BROWSER, semaforos

logger = logging.getLogger(__name__)


async def buscar_vagas_com(query: str, incluir_remoto: bool = False) -> List[Vaga]:
    async with semaforos["vagas_com"]:
        return await _buscar_vagas_com(query, incluir_remoto)


async def _buscar_vagas_com(query: str, incluir_remoto: bool) -> List[Vaga]:
    vagas = []
    slug = query.lower().replace(" ", "-")
    urls = [f"https://www.vagas.com.br/vagas-de-{slug}"]

    if incluir_remoto:
        urls.append(f"https://www.vagas.com.br/vagas-de-{slug}?vt=home-office")

    hashes = set()

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=HEADERS_BROWSER) as client:
            for url in urls:
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        logger.warning(f"Vagas.com: status {resp.status_code} para {url}")
                        continue

                    soup = BeautifulSoup(resp.text, "html.parser")
                    cards = soup.select("li.vaga")

                    for card in cards:
                        titulo_el = card.select_one("a.link-detalhes-vaga")
                        empresa_el = card.select_one("span.emprVaga")
                        local_el = card.select_one("div.vaga-local, span.vaga-local")
                        nivel_el = card.select_one("span.nivelVaga")

                        titulo = titulo_el.get_text(strip=True) if titulo_el else ""
                        if not titulo:
                            continue

                        empresa = empresa_el.get_text(strip=True) if empresa_el else "Não informada"
                        local_raw = local_el.get_text(strip=True) if local_el else ""
                        nivel = nivel_el.get_text(strip=True) if nivel_el else ""

                        href = titulo_el.get("href", "") if titulo_el else ""
                        if href and not href.startswith("http"):
                            href = f"https://www.vagas.com.br{href}"

                        cidade = ""
                        estado = ""
                        if " / " in local_raw:
                            partes = local_raw.split(" / ")
                            cidade = partes[0].strip()
                            estado = partes[1][:2].strip() if len(partes) > 1 else ""

                        descricao_el = card.select_one("div.detalhes")
                        descricao = descricao_el.get_text(strip=True)[:500] if descricao_el else ""

                        modalidade = detectar_modalidade(titulo, descricao + " " + local_raw)

                        h = gerar_hash(titulo, empresa, href)
                        if h in hashes:
                            continue
                        hashes.add(h)

                        vagas.append(Vaga(
                            titulo=titulo,
                            empresa=empresa,
                            cidade=cidade or None,
                            estado=estado,
                            regime=nivel if nivel else None,
                            modalidade=modalidade,
                            descricao=descricao[:500] if descricao else None,
                            url=href,
                            fonte="Vagas.com",
                            hash_dedup=h,
                        ))

                    await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"Erro ao buscar Vagas.com ({url}): {e}")

        logger.info(f"Vagas.com: {len(vagas)} vagas encontradas para '{query}'")
    except Exception as e:
        logger.error(f"Erro geral Vagas.com (query={query}): {e}")

    return vagas
