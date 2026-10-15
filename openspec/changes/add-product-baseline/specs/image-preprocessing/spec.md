## Purpose

Normaliza cada página antes da leitura para maximizar a precisão do reconhecimento, sem nunca alterar ou descartar a imagem original enviada, de onde saem os recortes de imagens do documento gerado.

## ADDED Requirements

### Requirement: Preservação do original
O sistema MUST guardar cada página original sem modificação, durante a vida da conversão; recortes de imagens (figuras, logotipos, assinaturas, trechos para conferência) MUST vir do original alinhado, nunca da versão contrastada para leitura.

#### Scenario: Original disponível
- **WHEN** uma página termina o pré-processamento
- **THEN** a versão original alinhada e a versão normalizada da página estão disponíveis para a conversão

### Requirement: Rasterização de PDF
O sistema SHALL converter cada página de PDF em imagem com resolução equivalente a pelo menos 300 DPI e registrar o tamanho de folha de cada página.

#### Scenario: PDF de 3 páginas
- **WHEN** um PDF de 3 páginas A4 é processado
- **THEN** o documento resultante tem 3 páginas A4, na mesma ordem do PDF

### Requirement: Correção de orientação e inclinação
O sistema SHALL detectar páginas giradas (90°, 180°, 270°) e inclinadas e endireitá-las antes da leitura.

#### Scenario: Página de cabeça para baixo
- **WHEN** uma página escaneada de cabeça para baixo é processada
- **THEN** o texto reconhecido sai na orientação correta de leitura

#### Scenario: Página inclinada
- **WHEN** uma página inclinada em 7° é processada
- **THEN** a página normalizada fica com inclinação residual de no máximo 0,5°

### Requirement: Correção de perspectiva
O sistema SHALL detectar o contorno da folha em fotos e corrigir a perspectiva, de modo que a página normalizada fique retangular e frontal; quando o contorno não for detectado com segurança, a imagem segue sem essa correção.

#### Scenario: Foto de celular em ângulo
- **WHEN** uma foto de folha tirada em ângulo, com fundo de mesa visível, é processada
- **THEN** a página normalizada contém apenas a folha, retificada, sem o fundo

#### Scenario: Contorno não encontrado
- **WHEN** o contorno da folha não é detectado com segurança
- **THEN** a imagem é lida sem correção de perspectiva e a conversão continua normalmente

### Requirement: Limpeza e resolução
O sistema SHALL reduzir ruído, sombras e baixo contraste e ampliar páginas cujo texto esteja abaixo da resolução mínima de leitura.

#### Scenario: Print pequeno
- **WHEN** uma captura de tela de 600 px de largura com fonte pequena é processada
- **THEN** a página é ampliada antes da leitura e o texto é reconhecido

### Requirement: Página sem conteúdo
O sistema SHALL identificar páginas em branco e mantê-las no resultado como páginas em branco, sem blocos.

#### Scenario: Página em branco
- **WHEN** uma página totalmente branca é processada
- **THEN** a página aparece no resultado, na mesma posição, sem blocos
