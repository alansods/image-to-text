## Purpose

Entrega o resultado conferido como texto copiável e como documento novo, em Word ou PDF, com o texto editável e a mesma paginação, organização, formatação e imagens do original.

## ADDED Requirements

### Requirement: Saídas disponíveis
Depois da conferência, o sistema SHALL oferecer exatamente três saídas: "Copiar texto", "Baixar Word" (.docx) e "Baixar PDF" (.pdf). Os arquivos baixados MUST ter o nome base do arquivo enviado.

#### Scenario: Nome do arquivo
- **WHEN** o arquivo enviado foi "contrato.pdf" e o usuário clica em "Baixar Word"
- **THEN** o navegador baixa "contrato.docx"

#### Scenario: Foto enviada
- **WHEN** o arquivo enviado foi "foto.jpg" e o usuário clica em "Baixar PDF"
- **THEN** o navegador baixa "foto.pdf"

### Requirement: Copiar texto
"Copiar texto" SHALL copiar para a área de transferência todo o texto do documento, em ordem de leitura, com uma linha em branco entre blocos e células de tabela separadas por tabulação, e o botão SHALL mudar para "Copiado" como confirmação.

#### Scenario: Cópia
- **WHEN** o usuário clica em "Copiar texto"
- **THEN** a área de transferência contém o texto do documento em ordem de leitura e o botão mostra "Copiado"

### Requirement: Documento novo com texto
Word e PDF SHALL ser documentos novos com o texto como texto editável e selecionável (não a imagem escaneada da página), contendo as escolhas feitas na conferência.

#### Scenario: Texto selecionável no PDF
- **WHEN** o usuário abre o PDF baixado e busca uma palavra presente no documento
- **THEN** o leitor de PDF encontra a palavra como texto

### Requirement: Mesma paginação
Word e PDF MUST ter o mesmo número de páginas do original, com o mesmo tamanho de folha, e cada bloco MUST ficar na mesma página em que estava no original. Páginas em branco do original SHALL ser mantidas como páginas em branco. Quando a entrada é uma imagem, o documento SHALL ter uma página A4, em retrato ou paisagem conforme a proporção da imagem.

#### Scenario: PDF de 5 páginas
- **WHEN** um PDF escaneado de 5 páginas A4 é convertido e baixado em Word
- **THEN** o Word tem 5 páginas A4 e o conteúdo da página 3 do original está na página 3 do Word

#### Scenario: Página em branco
- **WHEN** a página 2 de 3 do original está em branco
- **THEN** o documento baixado tem 3 páginas e a página 2 está em branco

#### Scenario: Foto deitada
- **WHEN** a entrada é uma foto mais larga do que alta
- **THEN** o documento baixado tem 1 página A4 em paisagem

### Requirement: Organização e formatação
Word e PDF SHALL preservar a ordem de leitura; títulos como títulos, com tamanho relativo maior que o texto; o tamanho da letra de cada bloco medido no original; o alinhamento de cada bloco (esquerda, centro, direita, justificado); negrito e itálico por palavra; listas com os marcadores originais e níveis; texto em múltiplas colunas como colunas; cabeçalhos e rodapés repetidos de página; e tabelas como tabelas reais, com células mescladas.

#### Scenario: Título centralizado
- **WHEN** o original tem um título centralizado acima de parágrafos justificados
- **THEN** o documento baixado tem o título centralizado, maior que o texto, e os parágrafos justificados

#### Scenario: Negrito preservado
- **WHEN** o original tem a palavra "CONTRATANTE" em negrito no meio de um parágrafo
- **THEN** no documento baixado essa palavra está em negrito e as vizinhas não

#### Scenario: Tabela
- **WHEN** o original tem uma tabela de 4×3 com uma célula mesclada
- **THEN** o documento baixado contém uma tabela real de 4×3 com a mesma mescla

#### Scenario: Duas colunas
- **WHEN** a página original tem texto em duas colunas
- **THEN** a página correspondente do documento baixado tem o texto em duas colunas, na mesma ordem

### Requirement: Imagens do original
Todo elemento que não é texto — capa, logotipo, foto, ilustração, gráfico, assinatura, carimbo, fórmula — MUST entrar no Word e no PDF como imagem recortada do original, na mesma página, na mesma posição relativa no fluxo do texto e com tamanho proporcional ao original. Texto que faz parte de uma imagem (como o nome dentro de um logotipo) SHALL continuar como parte da imagem.

#### Scenario: Logotipo e assinatura
- **WHEN** a página 1 tem um logotipo no topo e a página 2 tem uma assinatura no fim
- **THEN** o documento baixado tem o logotipo no topo da página 1 e a assinatura no fim da página 2

#### Scenario: Capa só com imagem
- **WHEN** a página 1 do original é uma capa formada por uma ilustração
- **THEN** a página 1 do documento baixado contém essa ilustração, ocupando a página na mesma proporção

#### Scenario: Texto dentro de uma assinatura
- **WHEN** uma assinatura foi feita sobre o nome impresso "EMPRESA EXEMPLO" e encosta na linha da data
- **THEN** o nome aparece uma vez só (dentro da imagem da assinatura) e a data aparece uma vez só, como texto

#### Scenario: Rubrica à direita
- **WHEN** a página tem uma rubrica no canto inferior direito
- **THEN** no documento baixado a rubrica aparece no canto inferior direito daquela página

#### Scenario: Nenhuma figura perdida
- **WHEN** o original tem 4 elementos que não são texto
- **THEN** o documento baixado contém as 4 imagens

### Requirement: Falha ao gerar
Se a geração do Word ou do PDF falhar, o sistema SHALL informar "Não foi possível gerar o arquivo. Tente de novo." sem perder as escolhas da conferência, e o botão continua disponível para nova tentativa.

#### Scenario: Erro ao gerar
- **WHEN** a geração do PDF falha
- **THEN** o usuário vê "Não foi possível gerar o arquivo. Tente de novo." e as palavras conferidas continuam como estavam
