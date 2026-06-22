import asyncio
from datetime import datetime, timedelta
from hashlib import sha256

from config import DIAS_MAX_VAGA

semaforos = {
    "linkedin": asyncio.Semaphore(2),
    "infojobs": asyncio.Semaphore(2),
    "vagas_com": asyncio.Semaphore(2),
    "trabalha_brasil": asyncio.Semaphore(2),
}

HEADERS_BROWSER = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def gerar_hash(titulo: str, empresa: str, url: str) -> str:
    texto = f"{titulo.lower().strip()}{empresa.lower().strip()}{url}"
    return sha256(texto.encode()).hexdigest()


def detectar_modalidade(titulo: str, descricao: str = "") -> str:
    texto = f"{titulo} {descricao}".lower()
    if any(kw in texto for kw in ["remoto", "home office", "trabalho remoto", "remote", "100% remoto"]):
        return "remoto"
    if any(kw in texto for kw in ["híbrido", "hibrido", "hybrid"]):
        return "híbrido"
    return "presencial"


def vaga_dentro_do_prazo(data_publicacao: datetime | None) -> bool:
    if data_publicacao is None:
        return True
    limite = datetime.utcnow() - timedelta(days=DIAS_MAX_VAGA)
    return data_publicacao >= limite
