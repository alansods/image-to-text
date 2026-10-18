## Purpose

Define como o usuário envia a imagem ou o PDF a converter, quais formatos e limites são aceitos e como a conversão começa, sem nenhuma escolha prévia.

## ADDED Requirements

### Requirement: Formas de envio
O sistema SHALL aceitar um arquivo por clique em "Escolher arquivo", por arrastar e soltar na área de envio e por colar da área de transferência (Ctrl+V / Cmd+V). Em dispositivos móveis SHALL oferecer também "Tirar foto", que abre a câmera.

#### Scenario: Escolher arquivo
- **WHEN** o usuário clica em "Escolher arquivo" e seleciona uma imagem PNG
- **THEN** a conversão dessa imagem começa

#### Scenario: Arrastar e soltar
- **WHEN** o usuário solta um PDF na área de envio
- **THEN** a conversão desse PDF começa

#### Scenario: Colar imagem
- **WHEN** o usuário cola uma imagem copiada com a página inicial aberta
- **THEN** a conversão dessa imagem começa

#### Scenario: Câmera no celular
- **WHEN** o usuário toca em "Tirar foto" em um celular e confirma a foto
- **THEN** a conversão da foto começa

### Requirement: Um arquivo por conversão
Cada conversão SHALL ter exatamente um arquivo de origem: uma imagem ou um PDF. Se mais de um arquivo for solto ou selecionado de uma vez, o sistema MUST recusar o envio com a mensagem "Envie um arquivo por vez."

#### Scenario: Dois arquivos soltos
- **WHEN** o usuário solta duas imagens ao mesmo tempo na área de envio
- **THEN** nenhuma conversão começa e o sistema mostra "Envie um arquivo por vez."

### Requirement: Início sem opções
A conversão SHALL começar assim que um arquivo válido é recebido, sem botão de confirmação e sem pedir modo, idioma ou qualquer outra opção ao usuário.

#### Scenario: Nenhuma pergunta
- **WHEN** o usuário escolhe um arquivo válido
- **THEN** a tela passa direto para o progresso da conversão, sem exibir opções

### Requirement: Formatos aceitos
O sistema SHALL aceitar JPG, PNG, WEBP, HEIC e PDF, identificando o formato pelo conteúdo do arquivo e não apenas pela extensão, e MUST recusar qualquer outro formato com a mensagem "Esse arquivo não é uma imagem nem PDF. Tente JPG, PNG, HEIC ou PDF."

#### Scenario: Formato não suportado
- **WHEN** o usuário envia um arquivo .gif
- **THEN** a conversão não começa e o sistema mostra "Esse arquivo não é uma imagem nem PDF. Tente JPG, PNG, HEIC ou PDF."

#### Scenario: Extensão enganosa
- **WHEN** o usuário envia um arquivo .png cujo conteúdo é um executável
- **THEN** o arquivo é recusado como formato não suportado

### Requirement: Limites de envio
O sistema MUST recusar arquivos acima de 20 MB e PDFs com mais de 4 páginas, informando o limite excedido, e MUST recusar PDFs protegidos por senha.

#### Scenario: Arquivo grande demais
- **WHEN** o usuário envia um arquivo de 25 MB
- **THEN** a conversão não começa e o sistema informa o limite de 20 MB

#### Scenario: PDF com páginas demais
- **WHEN** o usuário envia um PDF de 6 páginas
- **THEN** a conversão não começa e o sistema informa o limite de 4 páginas

#### Scenario: PDF protegido por senha
- **WHEN** o usuário envia um PDF protegido por senha
- **THEN** a conversão não começa e o sistema mostra "PDF protegido por senha não é suportado"

### Requirement: Limites visíveis antes do envio
A área de envio SHALL mostrar os limites de tamanho (20 MB) e de páginas (4) antes da escolha do arquivo.

#### Scenario: Limites na página inicial
- **WHEN** o usuário abre a página inicial
- **THEN** a área de envio mostra "até 20 MB" e "até 4 páginas"

### Requirement: Falha no envio
Se o envio do arquivo ao servidor falhar, o sistema SHALL voltar à tela de envio informando o problema, para que o usuário tente de novo.

#### Scenario: Conexão cai durante o envio
- **WHEN** a conexão cai enquanto o arquivo é enviado
- **THEN** o usuário volta à tela de envio com a mensagem "Não foi possível enviar. Verifique sua conexão."
