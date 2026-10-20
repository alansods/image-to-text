## Purpose

Garante que nenhum conteúdo da imagem fique de fora do resultado, detectando e reprocessando regiões com conteúdo que não foram cobertas por nenhum bloco ou linhas que não foram transcritas.

## ADDED Requirements

### Requirement: Regiões órfãs
O sistema SHALL detectar regiões da página com conteúdo visível (texto, traços, imagens) que não estão dentro de nenhum bloco e reprocessá-las como novos blocos, na posição de leitura correspondente.

#### Scenario: Nota de rodapé esquecida
- **WHEN** a detecção de layout não cria bloco para uma nota pequena no canto inferior
- **THEN** a checagem de completude cria um bloco para a nota, lido e incluído no fim da página

#### Scenario: Ruído ignorado
- **WHEN** uma região órfã é apenas uma mancha menor que o menor caractere da página
- **THEN** nenhum bloco é criado para ela

#### Scenario: Borda do papel escaneado
- **WHEN** a página tem a borda e a sombra do papel escaneado em volta do texto já lido
- **THEN** nenhum texto já lido é lido de novo nem aparece duplicado, o contorno do papel em volta da página é ignorado (não é conteúdo do documento) e traços soltos compridos (borda lateral, régua, dobra) entram como figura, sem gerar palavras nem dúvidas

### Requirement: Linhas por bloco
O sistema SHALL comparar o número de linhas de texto visíveis em cada bloco com o número de linhas transcritas e, havendo diferença, reler o bloco; persistindo a diferença, cada linha não transcrita MUST entrar no resultado como um trecho "[ilegível]" em dúvida, na posição da linha, com o recorte da linha original para o usuário conferir.

#### Scenario: Linha pulada
- **WHEN** um bloco tem 8 linhas visíveis e a transcrição tem 7 linhas, mesmo após a releitura
- **THEN** o bloco passa a ter um trecho "[ilegível]" em dúvida no lugar da linha faltante, que conta para a conferência obrigatória
