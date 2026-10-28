// Mapa de clínicas (Leaflet + OpenStreetMap) e lista ordenada pela distância da usuária.

// ATENÇÃO: coordenadas aproximadas. Confirmar endereço, telefone e posição no mapa antes do pitch.
// Para adicionar uma clínica, copie um bloco e ajuste. tipo: "SUS" ou "Particular".
const CLINICAS = [
  {
    nome: "Hospital das Clínicas da UFG — Laboratório de Reprodução Humana",
    endereco: "Primeira Avenida, s/n, Setor Leste Universitário",
    tipo: "SUS",
    lat: -16.6797, lng: -49.2466,
  },
  {
    nome: "Humana Medicina Reprodutiva",
    endereco: "Rua 1129, 751, Setor Marista",
    tipo: "Particular",
    lat: -16.7060, lng: -49.2600,
  },
  {
    nome: "Clínica Essência",
    endereco: "Avenida T-1, 1315, Setor Bueno",
    tipo: "Particular",
    lat: -16.7040, lng: -49.2700,
  },
];

const CENTRO_GOIANIA = [-16.6869, -49.2648];

// Abre o Google Maps em modo rota (no celular abre o app com GPS). Não precisa de chave de API.
function linkRota(c) {
  return "https://www.google.com/maps/dir/?api=1&destination=" + c.lat + "," + c.lng;
}

// Distância em km entre dois pontos (fórmula de Haversine).
function distanciaKm(a, b) {
  const rad = (g) => (g * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat), dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(h));
}

document.addEventListener("DOMContentLoaded", () => {
  const mapa = L.map("mapa-clinicas").setView(CENTRO_GOIANIA, 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  }).addTo(mapa);

  const marcadores = CLINICAS.map((c) =>
    L.marker([c.lat, c.lng]).addTo(mapa)
      .bindPopup("<strong>" + c.nome + "</strong><br>" + c.endereco + "<br><em>" + c.tipo + "</em>")
  );

  const lista = document.getElementById("lista-clinicas");
  const status = document.getElementById("status-local");
  const botao = document.getElementById("btn-local");
  let marcadorUsuaria = null;

  function desenharLista(origem) {
    const itens = CLINICAS.map((c, i) => ({ c, i, km: origem ? distanciaKm(origem, c) : null }));
    if (origem) itens.sort((x, y) => x.km - y.km);
    lista.innerHTML = "";
    itens.forEach(({ c, i, km }) => {
      const li = document.createElement("li");
      li.innerHTML =
        '<span class="cresce"><strong></strong><span class="mini endereco"></span></span>' +
        '<span class="selo ' + (c.tipo === "SUS" ? "verde" : "") + '"></span>' +
        '<span class="mini km"></span>' +
        '<a class="mini" target="_blank" rel="noopener">Rota</a>';
      li.querySelector("strong").textContent = c.nome;
      li.querySelector(".endereco").textContent = c.endereco;
      li.querySelector(".selo").textContent = c.tipo;
      li.querySelector(".km").textContent = km === null ? "" : km.toFixed(1).replace(".", ",") + " km";
      li.querySelector("a").href = linkRota(c);
      li.querySelector("strong").addEventListener("click", () => {
        mapa.setView([c.lat, c.lng], 15);
        marcadores[i].openPopup();
      });
      lista.appendChild(li);
    });
  }

  desenharLista(null);

  botao.addEventListener("click", () => {
    if (!navigator.geolocation) {
      status.textContent = "Seu navegador não permite localização. A lista segue sem distância.";
      return;
    }
    status.textContent = "Buscando sua localização...";
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const origem = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        if (marcadorUsuaria) marcadorUsuaria.remove();
        marcadorUsuaria = L.circleMarker([origem.lat, origem.lng], {
          radius: 9, color: "#173d32", fillColor: "#2b6b54", fillOpacity: 0.9,
        }).addTo(mapa).bindPopup("Você está aqui");
        mapa.fitBounds(L.latLngBounds([[origem.lat, origem.lng], ...CLINICAS.map((c) => [c.lat, c.lng])]).pad(0.15));
        desenharLista(origem);
        status.textContent = "Clínicas ordenadas da mais próxima para a mais distante.";
      },
      () => {
        status.textContent = "Não foi possível pegar sua localização. A lista segue sem distância.";
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  });
});
