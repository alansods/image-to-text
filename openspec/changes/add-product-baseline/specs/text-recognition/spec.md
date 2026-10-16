## Purpose

Transcreve o texto de cada bloco com posição, confiança e ênfase (negrito, itálico) por palavra, usando sempre duas leituras independentes para que a reconciliação possa conferi-las.

## ADDED Requirements

### Requirement: Leitura por bloco
O sistema SHALL ler cada bloco de texto a partir do recorte do bloco na página normalizada, e não da página inteira de uma vez.

#### Scenario: Todas as linhas do bloco
- **WHEN** um parágrafo de 12 linhas é lido
- **THEN** o texto reconhecido contém as 12 linhas, na ordem

#### Scenario: Letras grandes no escaneamento
- **WHEN** um parágrafo de 7 linhas foi escaneado com letras maiores que o habitual
- **THEN** as 7 linhas são lidas pelos dois mecanismos, na ordem

#### Scenario: Linha levemente curva
- **WHEN** a primeira linha de um parágrafo sobe para a direita por causa da curvatura do papel no scanner
- **THEN** as palavras dessa linha saem na ordem em que estão escritas, antes das palavras da linha seguinte

### Requirement: Palavras com posição e confiança
Para cada palavra reconhecida o sistema SHALL registrar o texto, a caixa delimitadora na página e uma confiança entre 0 e 1.

#### Scenario: Dados por palavra
- **WHEN** um bloco termina de ser lido
- **THEN** cada palavra do bloco possui texto, caixa e confiança

### Requirement: Leitura dupla
O sistema SHALL fazer duas leituras independentes de cada bloco, por mecanismos de reconhecimento distintos, e entregar ambas à reconciliação. Não existe modo de leitura única.

#### Scenario: Duas leituras
- **WHEN** um bloco é lido
- **THEN** existem duas leituras do bloco, de origens distintas, disponíveis para a reconciliação

### Requirement: Idioma automático
O sistema SHALL reconhecer texto em português e em inglês, inclusive misturados no mesmo documento, sem que o usuário informe o idioma, incluindo todos os acentos e caracteres especiais do português (á, à, â, ã, é, ê, í, ó, ô, õ, ú, ç) e símbolos comuns (R$, %, º, ª, §, @, €).

#### Scenario: Acentuação
- **WHEN** um bloco impresso contém "Ação de cobrança nº 123 — R$ 1.500,00"
- **THEN** a transcrição final é exatamente "Ação de cobrança nº 123 — R$ 1.500,00"

#### Scenario: Documento bilíngue
- **WHEN** uma página tem um parágrafo em português e outro em inglês
- **THEN** ambos os parágrafos são transcritos corretamente, sem o usuário escolher idioma

### Requirement: Negrito e itálico
O sistema SHALL identificar, por palavra, se o texto está em negrito e/ou itálico no original e registrar essa ênfase no resultado.

#### Scenario: Palavra em negrito
- **WHEN** um parágrafo impresso tem a expressão "CONTRATANTE" em negrito e o resto em peso normal
- **THEN** as palavras de "CONTRATANTE" são registradas como negrito e as demais não

#### Scenario: Trecho em itálico
- **WHEN** uma frase impressa está em itálico
- **THEN** as palavras dessa frase são registradas como itálico

### Requirement: Precisão mínima em texto impresso
Em texto impresso do conjunto de teste de referência, o sistema MUST atingir taxa de erro de caracteres (CER) de no máximo 1% e taxa de erro de palavras (WER) de no máximo 2%, antes da conferência humana, e acertar a ênfase (negrito/itálico) em pelo menos 95% das palavras.

#### Scenario: Conjunto de referência
- **WHEN** o conjunto de teste de documentos impressos é processado
- **THEN** o CER médio é ≤ 1%, o WER médio é ≤ 2% e a ênfase está correta em ≥ 95% das palavras, em relação aos gabaritos
