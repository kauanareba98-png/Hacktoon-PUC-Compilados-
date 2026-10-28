# Nida — Gestão e orientação para pacientes em FIV

Plataforma que acompanha a mulher em cada etapa da fertilização in vitro: organiza o tratamento, orienta com informação de fontes médicas confiáveis, oferece apoio emocional e avisa quando é hora de procurar ajuda.

Projeto da equipe [nome da equipe] para o **IV CodeCraft — Ciência e Tecnologia para a Saúde Delas** (PUC Goiás, 2026).

> O Nida orienta, não diagnostica e nunca sugere dose. Não substitui a equipe médica.

## Como rodar

1. Instale o Python 3 (no Windows, marque "Add python.exe to PATH").
2. No terminal, dentro da pasta do projeto:
   ```
   py -m pip install -r requirements.txt
   py app.py
   ```
   (No Linux/Mac: `python3 -m pip install -r requirements.txt` e `python3 app.py`.)
3. Abra http://127.0.0.1:5000

**Conta de demonstração:** `juliana@demo.com` · senha `nida2026`
Também dá para criar uma conta nova na tela de entrada.

O banco `nida.db` (SQLite) é criado sozinho na primeira execução. Ele **não vai para o Git** (cada pessoa tem o seu). Para voltar aos dados de exemplo, apague `nida.db` e rode de novo.

## Estrutura

| Arquivo | O que tem |
|---|---|
| `app.py` | Banco de dados, login, regras e todas as rotas |
| `conteudo.py` | Base de conhecimento: etapas, exames, medicamentos, sintomas, caminhos e apoio emocional, com fontes |
| `templates/` | Uma página HTML por tela (`base.html` é o layout comum; `_icones.html` tem os ícones) |
| `static/style.css` | Todo o visual |
| `tests/test_apoio.py`, `tests/test_comunidade.py` | Testes de privacidade do diário, autenticação, CSRF, comunidade e moderação |

Regra importante: **toda tabela tem `usuario_id`** e toda consulta filtra por `uid()`. Ao criar uma tabela ou consulta nova, mantenha esse filtro, senão uma usuária pode ver dados de outra.

## Telas

Entrar/Criar conta · Painel · Linha do tempo · Exames · Agenda · Medicação · Sintomas · Apoio emocional · Clínicas · Relatório · Minha conta

## Divisão de tarefas

| Quem | Tarefa | Arquivos principais |
|---|---|---|
| Dev 1 | Integração e revisão: juntar as branches, testar login e separação de contas, conta demo final, preparar o notebook do pitch | `app.py` |
| Dev 2 | Apoio emocional e comunidade de conversa (banco separado, sem alterar `SCHEMA`) | `templates/apoio.html`, `templates/comunidade*.html`, rotas de apoio em `app.py`, `static/style.css` |
| Dev 3 | Clínicas: mapa com Leaflet + OpenStreetMap e localização da usuária, lista de clínicas de Goiânia (nome, endereço, tipo, coordenadas), ordenar por distância | `templates/clinicas.html`, `static/` |
| Dev 4 | Celular e app: transformar em PWA (manifest + service worker), testar todas as telas no celular; se der tempo, leitura de lista de exames por foto (OCR) com confirmação antes de salvar | `static/`, `templates/base.html`, `templates/exames.html` |
| Pitch | Slides, roteiro da demo, ensaio | — |

Combinados para não dar conflito:
- Cada pessoa trabalha na **sua branch** (`dev2-apoio`, `dev3-clinicas`...) e abre um Pull Request para a `main`.
- Só a Dev 1 muda a **estrutura do banco** (`SCHEMA` em `app.py`). Precisa de tabela nova? Peça.
- `base.html` e `style.css` são de todo mundo: avise no grupo antes de mexer e acrescente CSS **no fim** do arquivo.
- **Às 15h do dia do pitch o código congela.** O que não estiver funcionando sai da demo e vira "próximos passos".

### Apoio emocional

O Modo Acolhimento oferece respiração sem exigir check-in emocional, diário privado, conteúdos relacionados à etapa, preparação local de perguntas e orientação para buscar ajuda. Os registros do diário reutilizam a tabela `humor`, filtrada pela sessão autenticada; textos livres ficam com `nivel` nulo e não são publicados. As operações de escrita e exclusão usam token CSRF e verificam a propriedade no backend.

A comunidade tem feed por assunto, pseudônimos, publicações e comentários visíveis imediatamente, reações e denúncias privadas. Usa um SQLite separado (`nida-community.db`) e não altera o esquema `SCHEMA` compartilhado. Configure `NIDA_COMMUNITY_DB` para definir o caminho do arquivo e `NIDA_COMMUNITY_MODERATOR_IDS` com os IDs internos autorizados a acessar denúncias e remover conteúdo (separados por vírgula). A ausência de moderadoras não impede a conversa, mas denúncias não serão tratadas pelo painel. Pseudônimo não significa anonimato; o mural não é canal de emergência nem é monitorado em tempo real. O SQLite deste protótipo não tem criptografia em repouso e não deve guardar dados reais de saúde em produção sem controles adicionais. Consulte [APOIO-INTEGRACAO.md](./APOIO-INTEGRACAO.md) para detalhes de privacidade, segurança, limites e referências.

Para executar os testes: `py -m unittest discover -s tests`. Em produção, configure `NIDA_ENV=production` e uma chave secreta forte em `NIDA_SECRET`; sem ela, a aplicação recusa iniciar. A chave aleatória usada no desenvolvimento não deve ser compartilhada entre processos.

## Fontes do conteúdo

ASRM, ESHRE, NICE, NHS, HFEA, Resolução CFM 2.320/2022, Anvisa RDC 771/2022, STJ (Tema 1.067) e reportagem da Tribuna de Minas (2024). Os links estão em `conteudo.py` e aparecem no próprio site.
