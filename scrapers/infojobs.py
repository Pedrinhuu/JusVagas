import logging
from typing import List

import httpx
from bs4 import BeautifulSoup

from models import Vaga
from scrapers import gerar_hash, detectar_modalidade

logger = logging.getLogger(__name__)


def _montar_url(query: str, cidade: str = "") -> str:
    slug = query.lower().replace(" ", "-")
    if cidade:
        cidade_slug = cidade.lower().replace(" ", "-").replace(",", "")
        return f"https://www.infojobs.com.br/vagas-de-{slug}-em-{cidade_slug}.aspx"
    return f"https://www.infojobs.com.br/vagas-de-emprego-{slug}.aspx"


async def buscar_infojobs(query: str, cidade: str = "") -> List[Vaga]:
    vagas = []
    url = _montar_url(query, cidade)

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "pt-BR,pt;q=0.9",
            })
            resp.raise_for_status()

        final_url = str(resp.url)
        if "empregos-em-" in final_url and query.lower() not in final_url.lower():
            url_fallback = f"https://www.infojobs.com.br/vagas-de-emprego-{query.lower().replace(' ', '-')}.aspx"
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(url_fallback, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept-Language": "pt-BR,pt;q=0.9",
                })
                resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        for link in soup.select("a[href*='/vaga-de-']"):
            href = link.get("href", "")
            if "__" not in href:
                continue

            titulo = link.get_text(strip=True)
            if not titulo or len(titulo) < 5:
                continue

            if not href.startswith("http"):
                href = f"https://www.infojobs.com.br{href}"

            empresa = ""
            cidade_vaga = ""
            regime = None
            descricao = ""

            container = link.find_parent("div", recursive=True)
            if not container:
                container = link.find_parent("li")
            if container:
                empresa_el = container.select_one("a[href*='/empresa-']")
                if empresa_el and empresa_el != link:
                    empresa = empresa_el.get_text(strip=True)

                texto_completo = container.get_text(separator="|").lower()
                descricao = container.get_text(separator=" ")[:500]

                if "clt" in texto_completo or "efetivo" in texto_completo:
                    regime = "CLT"
                elif "pj" in texto_completo or "prestador" in texto_completo:
                    regime = "PJ"
                elif "estágio" in texto_completo or "estagiário" in texto_completo:
                    regime = "Estágio"

                for span in container.find_all(string=True):
                    t = span.strip()
                    if " - " in t and any(uf in t for uf in [" SP", " RJ", " MG", " PR", " RS", " SC", " BA", " CE", " GO", " DF", " PE", " ES"]):
                        cidade_vaga = t.split(",")[0].strip()
                        break

            if cidade and cidade_vaga and cidade.lower() not in cidade_vaga.lower():
                continue

            modalidade = detectar_modalidade(titulo, descricao)

            vagas.append(Vaga(
                titulo=titulo,
                empresa=empresa or "Não informada",
                cidade=cidade_vaga or cidade,
                regime=regime,
                modalidade=modalidade,
                descricao=descricao[:500] if descricao else None,
                url=href,
                fonte="Infojobs",
                hash_dedup=gerar_hash(titulo, empresa or "Não informada", href),
            ))

        logger.info(f"Infojobs: {len(vagas)} vagas encontradas para '{query}' (cidade={cidade})")
    except Exception as e:
        logger.error(f"Erro ao buscar Infojobs (query={query}): {e}")

    return vagas
