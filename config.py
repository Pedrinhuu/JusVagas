import os
from dotenv import load_dotenv

load_dotenv()

PALAVRAS_CHAVE = [
    "advogada direito imobiliário",
    "advogada direito civil",
    "advogado imobiliário",
    "advogada OAB",
    "assessora jurídica",
    "consultora jurídica imobiliário",
    "advogada home office",
    "advogada remoto",
    "advogado imobiliário remoto",
]

CIDADES = ["Rio de Janeiro", "Niterói"]

MODALIDADES = ["presencial", "híbrido", "remoto"]
BUSCAR_REMOTO = True

DIAS_MAX_VAGA = 30
ORDENACAO_PADRAO = "data_publicacao"

BUSCA_INTERVALO_HORAS = int(os.getenv("BUSCA_INTERVALO_HORAS", "6"))
