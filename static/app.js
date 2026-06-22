let offset = 0;
const LIMIT = 50;
let debounceTimer = null;
let buscaStreamAtiva = false;
let contadorStream = 0;

document.addEventListener("DOMContentLoaded", async () => {
    const filtros = ["filtro-texto", "filtro-status", "filtro-area", "filtro-regime", "filtro-fonte", "filtro-modalidade", "filtro-ordenar"];
    filtros.forEach(id => {
        const el = document.getElementById(id);
        el.addEventListener(id === "filtro-texto" ? "input" : "change", () => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => { offset = 0; carregarVagas(); }, 300);
        });
    });

    await carregarStatus();
    const resp = await fetch("/api/status");
    const data = await resp.json();

    if (data.total_vagas === 0 && !data.ultima_busca) {
        buscarVagasStream();
    } else {
        carregarVagas();
    }
});

function buscarVagasStream() {
    if (buscaStreamAtiva) return;
    buscaStreamAtiva = true;
    contadorStream = 0;

    const btn = document.getElementById("btn-buscar");
    btn.disabled = true;
    btn.textContent = "Buscando...";

    const grid = document.getElementById("grid-vagas");
    const empty = document.getElementById("empty-state");
    const mais = document.getElementById("carregar-mais");
    empty.style.display = "none";
    mais.style.display = "none";

    const filtroStatus = document.getElementById("filtro-status").value;

    const eventSource = new EventSource("/api/buscar/stream");

    eventSource.onmessage = function(e) {
        const data = JSON.parse(e.data);

        if (data.fim) {
            eventSource.close();
            buscaStreamAtiva = false;
            restaurarBotao(btn);
            carregarStatus();
            mostrarToast(`Busca concluída: ${data.novas} vagas novas de ${data.total_bruto} capturadas`);
            if (contadorStream === 0) {
                carregarVagas();
            }
            return;
        }

        contadorStream++;
        atualizarContadorStream();

        if (!filtroStatus || data.status === filtroStatus) {
            grid.insertBefore(criarCard(data), grid.firstChild);
            empty.style.display = "none";
        }
    };

    eventSource.onerror = function() {
        eventSource.close();
        buscaStreamAtiva = false;
        restaurarBotao(btn);
        carregarVagas();
        carregarStatus();
    };
}

function atualizarContadorStream() {
    document.getElementById("badge-novas").textContent = `${contadorStream} vagas novas hoje`;
}

function restaurarBotao(btn) {
    btn.disabled = false;
    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M7 1a6 6 0 104.32 10.14l3.27 3.27a.75.75 0 001.06-1.06l-3.27-3.27A6 6 0 007 1zM2.5 7a4.5 4.5 0 119 0 4.5 4.5 0 01-9 0z" fill="currentColor"/></svg> Buscar agora`;
}

function getFiltros() {
    const params = new URLSearchParams();
    const texto = document.getElementById("filtro-texto").value.trim();
    const status = document.getElementById("filtro-status").value;
    const area = document.getElementById("filtro-area").value;
    const regime = document.getElementById("filtro-regime").value;
    const fonte = document.getElementById("filtro-fonte").value;
    const modalidade = document.getElementById("filtro-modalidade").value;
    const ordenar = document.getElementById("filtro-ordenar").value;

    if (texto) params.set("q", texto);
    if (status) params.set("status", status);
    if (area) params.set("area", area);
    if (regime) params.set("regime", regime);
    if (fonte) params.set("fonte", fonte);
    if (modalidade) params.set("modalidade", modalidade);
    if (ordenar) params.set("ordenar", ordenar);
    params.set("limit", LIMIT);
    params.set("offset", offset);
    return params;
}

async function carregarVagas(append = false) {
    const params = getFiltros();
    try {
        const resp = await fetch(`/api/vagas?${params}`);
        const vagas = await resp.json();
        const grid = document.getElementById("grid-vagas");
        const empty = document.getElementById("empty-state");
        const mais = document.getElementById("carregar-mais");

        if (!append) grid.innerHTML = "";

        if (vagas.length === 0 && !append) {
            empty.style.display = "block";
            mais.style.display = "none";
        } else {
            empty.style.display = "none";
            vagas.forEach(v => grid.appendChild(criarCard(v)));
            mais.style.display = vagas.length >= LIMIT ? "block" : "none";
        }
    } catch (e) {
        mostrarToast("Erro ao carregar vagas");
    }
}

function carregarMais() {
    offset += LIMIT;
    carregarVagas(true);
}

function criarCard(vaga) {
    const card = document.createElement("div");
    card.className = "card";
    card.dataset.id = vaga.id;

    const dataRel = vaga.data_publicacao ? tempoRelativo(vaga.data_publicacao) : "Data não informada";
    const diasVaga = vaga.data_publicacao ? diasDesde(vaga.data_publicacao) : null;
    const avisoAntiga = diasVaga !== null && diasVaga > 20
        ? `<span class="badge badge-aviso">Vaga antiga (${diasVaga} dias)</span>`
        : "";

    const modalidadeLabel = vaga.modalidade
        ? `<span class="badge badge-modalidade-${vaga.modalidade}">${capitalizar(vaga.modalidade)}</span>`
        : "";

    card.innerHTML = `
        <div class="card-header">
            <span class="card-titulo">${esc(vaga.titulo)}</span>
        </div>
        <div class="card-meta">
            <span>${esc(vaga.empresa)}</span>
            <span>&middot;</span>
            <span>${esc(vaga.cidade || "")}${vaga.estado ? ", " + esc(vaga.estado) : ""}</span>
            <span>&middot;</span>
            <span>${dataRel}</span>
        </div>
        <div class="card-meta">
            <span class="badge badge-fonte-${vaga.fonte}">${esc(vaga.fonte)}</span>
            <span class="badge badge-status-${vaga.status}">${capitalizar(vaga.status)}</span>
            ${modalidadeLabel}
            ${vaga.regime ? `<span class="badge badge-regime">${esc(vaga.regime)}</span>` : ""}
            ${vaga.area ? `<span class="badge badge-regime">${esc(vaga.area)}</span>` : ""}
            ${avisoAntiga}
        </div>
        <div class="card-acoes">
            ${vaga.url ? `<a href="${esc(vaga.url)}" target="_blank" rel="noopener" class="btn-ver">Ver vaga</a>` : ""}
            <button class="btn-fav ${vaga.status === "favorita" ? "ativo" : ""}" onclick="toggleFavorita(${vaga.id}, '${vaga.status}')">
                ${vaga.status === "favorita" ? "★" : "☆"}
            </button>
            <select class="select-status" onchange="mudarStatus(${vaga.id}, this.value)">
                <option value="nova" ${vaga.status === "nova" ? "selected" : ""}>Nova</option>
                <option value="favorita" ${vaga.status === "favorita" ? "selected" : ""}>Favorita</option>
                <option value="aplicada" ${vaga.status === "aplicada" ? "selected" : ""}>Aplicada</option>
                <option value="descartada" ${vaga.status === "descartada" ? "selected" : ""}>Descartada</option>
            </select>
        </div>
        <div class="nota-container">
            <button class="nota-toggle" onclick="toggleNota(this)">${vaga.nota ? "Editar nota" : "Adicionar nota"}</button>
            <textarea class="nota-campo" style="display:none" onblur="salvarNota(${vaga.id}, this)">${esc(vaga.nota || "")}</textarea>
        </div>
    `;
    return card;
}

async function mudarStatus(id, status) {
    try {
        await fetch(`/api/vagas/${id}/status`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status }),
        });
        mostrarToast(`Status alterado para "${capitalizar(status)}"`);
        offset = 0;
        carregarVagas();
    } catch (e) {
        mostrarToast("Erro ao alterar status");
    }
}

async function toggleFavorita(id, statusAtual) {
    const novoStatus = statusAtual === "favorita" ? "nova" : "favorita";
    await mudarStatus(id, novoStatus);
}

async function salvarNota(id, textarea) {
    try {
        await fetch(`/api/vagas/${id}/nota`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ nota: textarea.value }),
        });
        mostrarToast("Nota salva");
    } catch (e) {
        mostrarToast("Erro ao salvar nota");
    }
}

function toggleNota(btn) {
    const campo = btn.nextElementSibling;
    campo.style.display = campo.style.display === "none" ? "block" : "none";
    if (campo.style.display === "block") campo.focus();
}

function dispararBusca() {
    buscarVagasStream();
}

async function carregarStatus() {
    try {
        const resp = await fetch("/api/status");
        const data = await resp.json();
        if (!buscaStreamAtiva) {
            document.getElementById("badge-novas").textContent = `${data.vagas_novas_hoje} vagas novas hoje`;
        }
        if (data.ultima_busca) {
            document.getElementById("ultima-atualizacao").textContent = `Última busca: ${tempoRelativo(data.ultima_busca)}`;
        }
    } catch (e) { /* silencioso */ }
}

function limparFiltros() {
    document.getElementById("filtro-texto").value = "";
    document.getElementById("filtro-status").value = "";
    document.getElementById("filtro-area").value = "";
    document.getElementById("filtro-regime").value = "";
    document.getElementById("filtro-fonte").value = "";
    document.getElementById("filtro-modalidade").value = "";
    document.getElementById("filtro-ordenar").value = "recentes";
    offset = 0;
    carregarVagas();
}

function diasDesde(dataStr) {
    const data = new Date(dataStr);
    const agora = new Date();
    return Math.floor((agora - data) / 86400000);
}

function tempoRelativo(dataStr) {
    const data = new Date(dataStr);
    const agora = new Date();
    const diff = Math.floor((agora - data) / 1000);
    const dataFormatada = data.toLocaleDateString("pt-BR");

    if (diff < 60) return "agora";
    if (diff < 3600) return `há ${Math.floor(diff / 60)} min`;
    if (diff < 86400) return `há ${Math.floor(diff / 3600)} horas`;
    const dias = Math.floor(diff / 86400);
    if (dias === 1) return `há 1 dia (${dataFormatada})`;
    if (dias < 30) return `há ${dias} dias (${dataFormatada})`;
    return dataFormatada;
}

function capitalizar(s) {
    return s.charAt(0).toUpperCase() + s.slice(1);
}

function esc(s) {
    if (!s) return "";
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
}

function mostrarToast(msg) {
    const toast = document.getElementById("toast");
    toast.textContent = msg;
    toast.classList.add("visivel");
    setTimeout(() => toast.classList.remove("visivel"), 3000);
}
