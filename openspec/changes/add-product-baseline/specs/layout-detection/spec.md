## Purpose

Identifica a estrutura de cada página — que elementos existem, onde estão, como estão alinhados e em que ordem devem ser lidos — para que nada seja perdido e o documento gerado repita a organização original.

## ADDED Requirements

### Requirement: Blocos tipados
O sistema SHALL dividir cada página em blocos, cada um com tipo (título, parágrafo, lista, tabela, figura, fórmula, cabeçalho, rodapé), caixa delimitadora em coordenadas da página e identificador único na conversão.

#### Scenario: Página com título, texto e tabela
- **WHEN** uma página com um título, dois parágrafos e uma tabela é processada
- **THEN** o resultado contém um bloco "título", dois blocos "parágrafo" e um bloco "tabela", cada um com sua caixa

### Requirement: Ordem de leitura e colunas
O sistema SHALL atribuir a cada bloco uma posição na ordem de leitura natural da página e registrar em quantas colunas o texto da página está, incluindo layouts em múltiplas colunas (coluna da esquerda inteira antes da direita), com cabeçalho no início e rodapé no fim.

#### Scenario: Duas colunas
- **WHEN** uma página de revista em duas colunas é processada
- **THEN** a página é registrada com 2 colunas e todos os blocos da coluna esquerda vêm antes dos da coluna direita na ordem de leitura

### Requirement: Alinhamento e tamanho relativo
Para cada bloco de texto o sistema SHALL registrar o alinhamento (esquerda, centro, direita, justificado), o tamanho da letra em pontos, medido no original, e o tamanho relativo em relação ao texto principal do documento.

#### Scenario: Título centralizado
- **WHEN** uma página tem um título centralizado em letra maior acima de parágrafos justificados
- **THEN** o bloco título é registrado como centralizado e maior, e os parágrafos como justificados

#### Scenario: Mesmo corpo, palavras diferentes
- **WHEN** dois parágrafos com a mesma fonte de 11 pt têm, um, palavras com letras como "p" e "g" e, outro, títulos em maiúsculas
- **THEN** os dois são registrados com tamanho de cerca de 11 pt

#### Scenario: Sujeira do scanner
- **WHEN** há um ponto de sujeira menor que uma letra no topo da página
- **THEN** nenhum bloco de texto é criado para ele

### Requirement: Elementos não-texto preservados
O sistema MUST classificar capas, figuras, fotos, logotipos, ilustrações, gráficos, assinaturas e carimbos como blocos "figura" e guardar o recorte do original de cada um, com sua caixa; nenhum desses elementos pode ser descartado.

#### Scenario: Documento com logo e assinatura
- **WHEN** uma página com logotipo no topo e assinatura no fim é processada
- **THEN** o resultado contém dois blocos "figura" com seus recortes, nas posições de leitura correspondentes

#### Scenario: Assinatura e rubrica sobre a página
- **WHEN** uma página tem uma rubrica no canto e uma assinatura cursiva que o detector marcou como texto
- **THEN** ambas entram como blocos "figura" com o recorte do original e não geram palavras nem dúvidas

#### Scenario: Preenchimento à mão
- **WHEN** um campo "Nome:" foi preenchido à mão com letra cursiva que não pode ser lida com segurança
- **THEN** a região entra como figura, preservando a escrita do original, sem gerar dúvidas

#### Scenario: Figura com legenda
- **WHEN** uma figura possui legenda em texto abaixo dela
- **THEN** a figura vira um bloco "figura" e a legenda vira um bloco de texto separado, logo após a figura na ordem de leitura

### Requirement: Texto não vira imagem
O sistema MUST NOT entregar como figura ou fórmula uma região que contém linhas de texto corrido: quando um bloco detectado como figura ou fórmula contém linhas de texto, essas linhas SHALL ser lidas como texto.

#### Scenario: Foto levemente desfocada
- **WHEN** uma foto de contrato levemente desfocada é processada e o detector classifica a página inteira como uma única figura ou fórmula
- **THEN** os parágrafos da página são lidos como texto, e não entregues como imagem

### Requirement: Fórmulas como imagem
O sistema SHALL tratar fórmulas matemáticas como blocos "fórmula" com recorte do original, sem tentar transcrevê-las.

#### Scenario: Equação no texto
- **WHEN** uma página contém uma equação em destaque
- **THEN** o resultado contém um bloco "fórmula" com o recorte da equação

### Requirement: Listas
O sistema SHALL reconhecer listas com marcadores ou numeração, preservando o marcador original de cada item e o nível de aninhamento.

#### Scenario: Lista numerada aninhada
- **WHEN** uma página tem itens "1.", "2." e subitens "a)", "b)"
- **THEN** o bloco "lista" preserva os marcadores e indica que "a)" e "b)" são subitens
