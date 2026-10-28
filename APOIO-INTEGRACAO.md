# Apoio emocional: integração e limites de segurança

## Entregue nesta versão

- Modo Acolhimento no topo, com opções que abrem apenas o recurso escolhido em um painel único; a comunidade aparece logo após as opções.
- Respiração, diário, biblioteca/mensagem, autocuidado, preparação para consulta e orientação urgente não ficam todos abertos ao mesmo tempo.
- Respiração temporizada de 1, 2 ou 5 minutos, com pausa, retomada e encerramento. Não registra se a paciente iniciou ou concluiu o exercício.
- Diário e check-in são escolhas distintas. O diário permite texto sem nota de humor; os registros continuam na tabela existente `humor`, com `nivel` nulo para texto livre. Não houve alteração de `SCHEMA`.
- Leitura e exclusão consultam a sessão autenticada e filtram por `usuario_id`. Exclusão por identificador alheio retorna 404.
- Escritas e exclusões exigem token CSRF. Conteúdo livre é renderizado com escape do Jinja.
- Preparação de perguntas, modelos de mensagem e escolhas de autocuidado são locais; não são enviados nem persistidos pelo servidor.
- O diário oferece navegação mensal, seleção de dia para ler ou escrever, preenchimento retroativo de datas passadas, busca textual e remoção individual de registros. A consulta é filtrada pela sessão autenticada e `usuario_id`; nenhuma tabela nova foi criada.
- Os atalhos de autocuidado conduzem ao recurso correspondente; as perguntas da consulta são geradas apenas a partir de suas opções, sem incorporar as escolhas de autocuidado.
- O guia de emergência informa que a página não monitora risco, diferencia CVV de emergência e orienta buscar ajuda humana urgente.

## Comunidade de apoio: protótipo implementado

A comunidade usa um arquivo SQLite próprio (`nida-community.db`), separado do banco principal; `SCHEMA` e `nida.db` não foram alterados. O caminho pode ser configurado com `NIDA_COMMUNITY_DB`. O módulo implementa:

- Feed por assuntos, publicações, comentários e reações de acolhimento, sem placar ou ordenação por popularidade.
- Pseudônimo escolhido pela participante, sem nome ou e-mail no feed. A conta fica vinculada internamente ao pseudônimo; portanto, isso não é anonimato absoluto.
- Publicações e comentários ficam visíveis imediatamente para participantes autenticadas; não há fila de aprovação. Conteúdo removido por autora ou moderadora autorizada tem o texto apagado.
- Conteúdos que ficaram pendentes numa versão anterior podem ser publicados pela própria autora com ação explícita; eles não são liberados automaticamente para preservar a escolha da participante.
- Denúncia privada de publicações/comentários, com motivo controlado, uma denúncia por pessoa/alvo e acesso somente pela rota de moderação autorizada.
- Autorização por sessão e propriedade para exclusão, CSRF em todas as escritas, conteúdo exibido com escape do Jinja, limites de tamanho e cotas por conta (publicações, comentários, reações e denúncias).
- Auditoria de decisões de moderação. Nenhuma classificação automática é usada para declarar que uma publicação contém risco imediato.

Configure `NIDA_COMMUNITY_MODERATOR_IDS` no servidor com os IDs internos numéricos de contas que receberam autorização operacional (separados por vírgula). O valor nunca é aceito do navegador. Moderadoras autorizadas podem consultar denúncias privadas e remover publicações/comentários. A configuração, por si só, não cria uma equipe, não estabelece prazo de resposta nem garante monitoramento; sem moderadoras configuradas, a conversa continua aberta, mas denúncias não serão tratadas pelo painel. Não anuncie as denúncias como atendimento em tempo real.

O mural avisa que não é canal de emergência e direciona risco imediato a ajuda humana (UPA/pronto-socorro ou SAMU 192; CVV 188 para escuta emocional, não para substituir emergência). Os relatos são experiências pessoais, não orientação clínica; as regras vedam prescrição, alteração de tratamento, promessas, assédio e exposição de dados pessoais.

**Limite importante:** esta é uma implementação de protótipo, não adequada para dados reais de saúde em produção. SQLite não oferece criptografia em repouso por padrão. Antes de uso real, a equipe deve aprovar base e hospedagem gerenciadas, criptografia e chaves, backups protegidos, retenção/exclusão, controle operacional de acesso, resposta a incidentes, proteção adicional contra abuso por IP/rede e processo humano de triagem/recurso. As cotas atuais são por conta, não impedem abuso coordenado ou múltiplas contas.

O banco separado pode ser recriado para remover os dados do protótipo, mas não há política automática de retenção ou exportação nesta versão. A exclusão de publicação própria também exclui comentários, reações e denúncias vinculadas por cascata. Definir uma política aprovada antes de uso real.

## Execução e integração

Executar `py -m unittest discover -s tests` para validar as regras privadas e da comunidade. Em produção, a chave de sessão deve vir de `NIDA_SECRET`, com cookies `HttpOnly`, `SameSite=Lax` e `Secure`.

### Referências de padrões de diário

- [Day One — Calendar View](https://dayoneapp.com/features/calendar-view/): calendário navegável, tocar numa data para abrir os registros e permitir preencher datas passadas sem registro.
- [Day One — Features](https://dayoneapp.com/features/): apresenta pesquisa/filtros para localizar registros e navegação pelo calendário.

O Nida adota esses padrões gerais de interação (calendário → dia → registros e busca), mantendo seu próprio visual e sem adotar streaks, metas ou cobranças de frequência.

### Referências de comunidade e apoio

- [RESOLVE — Find a Support Group](https://resolve.org/get-help/support-groups/): grupos de apoio a pessoas lidando com infertilidade/família, com formatos conduzidos por pares ou profissionais. A organização esclarece que grupos conduzidos por pares não substituem cuidado clínico ou aconselhamento profissional, e que cada pessoa decide quanto quer compartilhar. Isso orientou a escolha de participação voluntária e a mensagem para não tratar relatos como aconselhamento médico.
- [Reddit — Content Policy](https://www.redditinc.com/policies/reddit-rules): descreve expectativas de privacidade e segurança, regras comunitárias e o papel de moderadores. O Nida aplica esses padrões gerais com regras específicas para fertilidade, publicação imediata e denúncia privada.

O diretório de trabalho recebido não contém metadados `.git`; por isso não foi possível criar/confirmar a branch `dev2-apoio` nem abrir um Pull Request a partir deste ambiente. Aplicar os arquivos em uma cópia com Git e revisar junto à Dev 1 antes da integração.
