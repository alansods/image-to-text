## Purpose

Converte tabelas da imagem em tabelas estruturadas (linhas, colunas e células mescladas) com o conteúdo de cada célula conferido com o mesmo rigor do texto corrido.

## ADDED Requirements

### Requirement: Estrutura da tabela
Para cada bloco "tabela" o sistema SHALL identificar linhas, colunas e células, incluindo células mescladas (com extensão em linhas e colunas) e linhas de cabeçalho.

#### Scenario: Tabela simples
- **WHEN** uma tabela de 4 linhas por 3 colunas é processada
- **THEN** o bloco contém 12 células, cada uma com linha e coluna corretas

#### Scenario: Célula mesclada
- **WHEN** uma célula de cabeçalho ocupa 2 colunas
- **THEN** a célula é registrada com extensão de 2 colunas e não há célula duplicada na posição coberta

#### Scenario: Tabela sem bordas
- **WHEN** uma tabela sem linhas de grade, alinhada apenas por espaços, é processada
- **THEN** linhas e colunas são identificadas pelo alinhamento do conteúdo

### Requirement: Conteúdo das células
O conteúdo de cada célula SHALL passar pelo mesmo reconhecimento e reconciliação do texto corrido, com status por palavra; palavras em dúvida dentro de células entram na conferência obrigatória como qualquer outra.

#### Scenario: Número em célula
- **WHEN** uma célula contém "1.234,56"
- **THEN** a célula final contém exatamente "1.234,56"

#### Scenario: Célula vazia
- **WHEN** uma célula não tem conteúdo
- **THEN** a célula é registrada como vazia, sem deslocar as demais

### Requirement: Tabela não estruturável
Quando a estrutura não puder ser identificada com segurança, o sistema SHALL manter o bloco como imagem recortada do original, na mesma posição, para que nada da tabela se perca.

#### Scenario: Tabela muito irregular
- **WHEN** uma tabela desenhada à mão não tem estrutura identificável
- **THEN** o resultado contém a tabela como imagem do original, na posição em que ela estava
