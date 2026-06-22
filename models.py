from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class Vaga(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    titulo: str
    empresa: str
    cidade: str
    estado: str = "RJ"
    regime: Optional[str] = None
    area: Optional[str] = None
    modalidade: Optional[str] = None
    descricao: Optional[str] = None
    url: str
    fonte: str
    data_publicacao: Optional[datetime] = None
    data_captura: datetime = Field(default_factory=datetime.utcnow)
    hash_dedup: str = Field(index=True)
    status: str = "nova"
    nota: Optional[str] = None
    ativa: bool = True
