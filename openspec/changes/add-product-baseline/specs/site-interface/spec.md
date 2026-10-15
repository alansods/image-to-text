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
O site SHALL ter um único tema claro, sem opção de tema escuro, e o âmbar MUST ser usado apenas para indicar palavras em dúvida.

#### Scenario: Sistema em modo escuro
- **WHEN** o sistema operacional do usuário está em modo escuro
- **THEN** o site aparece no tema claro

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
