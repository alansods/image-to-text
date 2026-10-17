## Purpose

Define a moldura do site — barra de navegação, idioma da interface, rodapé, aparência, uso no celular e acessibilidade — comum a todas as telas da conversão.

## ADDED Requirements

### Requirement: Uma página, três telas
O site SHALL funcionar em um único endereço (`/`) com três telas que se substituem: envio, progresso e resultado. Qualquer outro endereço SHALL mostrar "Página não encontrada" com o link "Voltar ao início".

#### Scenario: Endereço inexistente
- **WHEN** o usuário abre `/qualquer-coisa`
- **THEN** a tela mostra "Página não encontrada" e o link "Voltar ao início", que leva a `/`

### Requirement: Barra de navegação
Todas as telas SHALL ter uma barra superior com o logotipo "image-to-text" à esquerda e o seletor de idioma "PT | EN" à direita. Clicar no logotipo durante o progresso ou o resultado SHALL voltar à tela de envio.

#### Scenario: Logotipo no resultado
- **WHEN** o usuário está na tela de resultado e clica no logotipo
- **THEN** a tela de envio aparece e os arquivos da conversão são apagados como em "Converter outro"

### Requirement: Idioma da interface
O seletor "PT | EN" SHALL trocar imediatamente todos os textos da interface entre português do Brasil e inglês, sem recarregar a página e sem alterar o texto do documento convertido. O idioma inicial SHALL ser inglês quando o idioma preferido do navegador for inglês, e português em qualquer outro caso. A escolha MUST NOT ser guardada no navegador.

#### Scenario: Trocar para inglês
- **WHEN** o usuário está na tela de envio em português e clica em "EN"
- **THEN** o título passa a "Turn images into text" e o botão a "Choose file"

#### Scenario: Documento não é traduzido
- **WHEN** o usuário troca para "EN" na tela de resultado de um contrato em português
- **THEN** os botões e avisos ficam em inglês e o texto do contrato continua em português

#### Scenario: Navegador em inglês
- **WHEN** o idioma preferido do navegador é "en-US" e o usuário abre o site
- **THEN** a interface aparece em inglês

### Requirement: Rodapé
Todas as telas SHALL ter um rodapé com o logotipo e "© <ano atual> image-to-text", sem outros textos ou links.

#### Scenario: Rodapé
- **WHEN** qualquer tela é exibida
- **THEN** o rodapé mostra o logotipo e "© <ano atual> image-to-text"

### Requirement: Aparência única
O site SHALL ter um único tema claro, sem opção de tema escuro: toda tela começa com uma faixa azul-escura (barra superior e título da tela) e o conteúdo principal num cartão branco que avança sobre a faixa. O âmbar MUST ser usado apenas para o que pede atenção: palavras em dúvida, a contagem de dúvidas e o aviso de baixa qualidade.

#### Scenario: Sistema em modo escuro
- **WHEN** o sistema operacional do usuário está em modo escuro
- **THEN** o site aparece no tema claro

### Requirement: Página inicial ensina a usar
A tela de envio SHALL ser a página inicial: título, subtítulo e a etiqueta "Grátis · sem cadastro · nada fica guardado" na faixa; a área de envio no cartão; abaixo, "Como funciona" com quatro passos em ordem (envie o arquivo; a leitura começa sozinha; confira as dúvidas; baixe ou copie), cada um com ícone, título e uma frase; e, por fim, a chamada "Pronto para começar?" com um botão que abre a escolha de arquivo. Os textos MUST descrever só o que o produto faz.

#### Scenario: Primeira visita
- **WHEN** o usuário abre `/`
- **THEN** vê a área de envio no topo e, rolando, os quatro passos de "Como funciona" e a chamada "Pronto para começar?"

#### Scenario: Botão da chamada final
- **WHEN** o usuário clica em "Escolher arquivo" na chamada "Pronto para começar?"
- **THEN** abre a mesma escolha de arquivo da área de envio

### Requirement: Celular
Todas as telas SHALL funcionar em telas a partir de 360 px de largura sem rolagem horizontal da página, com alvos de toque de pelo menos 44 px.

#### Scenario: Resultado no celular
- **WHEN** a tela de resultado é aberta em um celular de 390 px de largura
- **THEN** a página não tem rolagem horizontal e os botões têm pelo menos 44 px de altura

### Requirement: Acessibilidade
O site SHALL atender WCAG 2.1 AA: todo controle operável por teclado com foco visível, textos com contraste mínimo de 4,5:1, imagens com texto alternativo e mensagens de estado (progresso, contagem de dúvidas, "Copiado") anunciadas a leitores de tela.

#### Scenario: Só teclado
- **WHEN** o usuário usa apenas o teclado
- **THEN** consegue escolher o arquivo, cancelar, conferir todas as dúvidas, copiar e baixar
