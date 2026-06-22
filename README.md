# JusVagas

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)
![Render](https://img.shields.io/badge/Deploy-Render-46E3B7?logo=render&logoColor=white)

Agregador de vagas jurídicas para o Brasil. Reúne oportunidades de múltiplas fontes em um só lugar, com filtros, busca automática e rastreamento de candidaturas.

## Funcionalidades

- **Busca automática** a cada 6 horas em 4 fontes (LinkedIn, Infojobs, Vagas.com, TrabalhaBrasil)
- **Filtros** por área, modalidade (remoto/híbrido/presencial), regime (CLT/PJ), fonte e ordenação por data
- **Deduplicação automática** entre fontes via hash SHA256
- **Filtro de relevância jurídica** — descarta vagas sem termos jurídicos no título ou descrição
- **Filtro de prazo** — ignora vagas com mais de 30 dias
- **Rastreamento de candidaturas**: Nova / Favorita / Aplicada / Descartada
- **Notas por vaga** — adicione anotações pessoais a cada oportunidade
- **Badge de aviso** para vagas com mais de 20 dias

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python + FastAPI + SQLModel + APScheduler |
| Frontend | HTML + Vanilla JS + CSS puro |
| Banco de dados | SQLite |
| Scraping | httpx + BeautifulSoup4 |

## Como rodar localmente

```bash
git clone https://github.com/Pedrinhuu/JusVagas
cd JusVagas
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
# Acesse http://localhost:8000
```

## Configuração

### Palavras-chave e cidades

Edite o arquivo `config.py`:

```python
PALAVRAS_CHAVE = [
    "advogada direito imobiliário",
    "advogada direito civil",
    # adicione mais termos...
]
CIDADES = ["Rio de Janeiro", "Niterói"]
BUSCAR_REMOTO = True
DIAS_MAX_VAGA = 30
```

### Variáveis de ambiente

Crie um arquivo `.env` na raiz (opcional):

```
BUSCA_INTERVALO_HORAS=6
DIAS_MAX_VAGA=30
BUSCAR_REMOTO=true
```

## Deploy no Render

1. Fork este repositório
2. Crie um novo **Web Service** em [render.com](https://render.com)
3. Conecte o repositório GitHub
4. O `render.yaml` já configura tudo automaticamente
5. Clique em **Deploy**

## Estrutura do projeto

```
JusVagas/
├── main.py                 # App FastAPI, rotas, scheduler, filtro de relevância
├── config.py               # Palavras-chave, cidades, configurações
├── database.py             # Engine SQLite e session factory
├── models.py               # Modelo Vaga (SQLModel)
├── requirements.txt        # Dependências Python
├── render.yaml             # Configuração de deploy no Render
├── scrapers/
│   ├── __init__.py         # Utilitários: hash, modalidade, prazo, headers
│   ├── linkedin.py         # Scraper LinkedIn Jobs (HTML)
│   ├── infojobs.py         # Scraper Infojobs (HTML)
│   ├── vagas_com.py        # Scraper Vagas.com (HTML)
│   └── trabalha_brasil.py  # Scraper Trabalha Brasil (HTML)
└── static/
    ├── index.html          # SPA — página única
    ├── style.css           # Estilos (CSS variables, responsivo)
    └── app.js              # Lógica frontend (fetch, filtros, cards)
```

## API Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/` | Página principal (SPA) |
| `GET` | `/api/vagas` | Listar vagas com filtros e paginação |
| `GET` | `/api/status` | Status do sistema (última busca, contadores) |
| `POST` | `/api/buscar` | Disparar busca manual em segundo plano |
| `PATCH` | `/api/vagas/{id}/status` | Alterar status de uma vaga |
| `PATCH` | `/api/vagas/{id}/nota` | Salvar nota em uma vaga |
| `DELETE` | `/api/vagas/{id}` | Deletar uma vaga |

## Fontes de vagas

| Fonte | Método | Observações |
|-------|--------|-------------|
| LinkedIn | HTML scraping | Busca por cidade + busca remota (f_WT=2) |
| Infojobs | HTML scraping | Busca com fallback de URL |
| Vagas.com | HTML scraping | Busca padrão + filtro home-office |
| Trabalha Brasil | HTML scraping | Busca padrão + busca home-office |

Todas as fontes usam **httpx + BeautifulSoup** (sem Playwright/Selenium).
