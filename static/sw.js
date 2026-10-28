// Evento disparado quando o Service Worker é instalado no navegador
self.addEventListener('install', (event) => {
  console.log('[Service Worker] Instalado com sucesso.');
});

// Evento que intercepta requisições de rede (busca de páginas, CSS, imagens)
self.addEventListener('fetch', (event) => {
  event.respondWith(fetch(event.request));
});