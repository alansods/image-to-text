## Purpose

Combina as leituras de cada bloco em uma única transcrição confiável, decide as divergências de forma rastreável e marca explicitamente o que continua em dúvida, sem nunca inventar ou corrigir texto.

## ADDED Requirements

### Requirement: Transcrição literal
O sistema MUST transcrever exatamente o que está na imagem: não corrigir ortografia, gramática ou pontuação, não completar palavras cortadas e não acrescentar texto que não esteja visível.

#### Scenario: Erro de digitação no original
- **WHEN** o documento original contém a palavra "excessão"
- **THEN** a transcrição final contém "excessão", e não "exceção"

#### Scenario: Trecho ilegível
- **WHEN** nenhuma etapa consegue ler um trecho com segurança
- **THEN** o trecho é transcrito como "[ilegível]" e marcado como "em dúvida"

### Requirement: Concordância aceita
Quando as duas leituras concordam em uma palavra, o sistema SHALL aceitá-la com status "aceita".

#### Scenario: Leituras iguais
- **WHEN** as duas leituras de uma palavra são "contrato"
- **THEN** a palavra final é "contrato" com status "aceita"

### Requirement: Resolução de divergências
Quando as leituras divergem, o sistema SHALL tentar resolver na ordem: (1) aceitar a leitura cuja confiança supere a outra em pelo menos 0,15 e seja ≥ 0,90; (2) reler o trecho ampliado com ambos os mecanismos e aceitar se passarem a concordar, ou aceitar a releitura do mecanismo principal quando ela repete uma das leituras originais com confiança ≥ 0,97 e o segundo mecanismo não consegue ler o trecho (confiança abaixo de 0,90); pontuação no fim da palavra colada por um sublinhado não conta nessas comparações; (3) se o árbitro estiver habilitado, consultá-lo. Uma palavra resolvida SHALL receber status "resolvida" e registrar qual etapa a resolveu.

#### Scenario: Resolvida por confiança
- **WHEN** as leituras são "R$ 150" (0,97) e "R$ 15O" (0,71)
- **THEN** a palavra final é "R$ 150" com status "resolvida" pela etapa "confiança"

#### Scenario: Resolvida por releitura
- **WHEN** as leituras divergem com confianças próximas e a releitura ampliada faz ambas lerem "Silva"
- **THEN** a palavra final é "Silva" com status "resolvida" pela etapa "releitura"

#### Scenario: Segundo leitor não consegue ler
- **WHEN** um título sublinhado é lido "QUARTA" pelo mecanismo principal e o segundo não lê nada, e na releitura ampliada o principal lê "QUARTA" com confiança 0,99 e o segundo lê "_" com confiança 0,18
- **THEN** a palavra final é "QUARTA" com status "resolvida" pela etapa "releitura"

#### Scenario: Os dois leem e discordam
- **WHEN** na releitura ampliada o principal lê "Silva" com 0,99 e o segundo lê "Sllva" com 0,95
- **THEN** a palavra continua divergente e segue para o árbitro ou fica "em dúvida"

#### Scenario: Só o segundo leitor viu a palavra
- **WHEN** o segundo mecanismo leu "CLÁUSULA." num título sublinhado, o principal não leu nada, e na releitura ampliada o principal lê "CLÁUSULA" com 0,99 e o segundo lê "_" com 0,18
- **THEN** a palavra final é "CLÁUSULA" com status "resolvida" pela etapa "releitura"

### Requirement: Sublinhado não é palavra
Um trecho formado só por traços de sublinhado ("_"), lido por um único mecanismo e que a releitura do outro não confirma, SHALL ser descartado como parte da formatação, sem virar palavra nem dúvida.

#### Scenario: Pedaço de sublinhado
- **WHEN** o segundo mecanismo lê "_" entre duas palavras de um título sublinhado e a releitura do principal não reconhece nada com confiança
- **THEN** o título não ganha a palavra "_" nem uma dúvida

### Requirement: Árbitro opcional
O sistema SHALL permitir habilitar ou desabilitar o árbitro por configuração do servidor; o árbitro recebe somente os trechos ainda divergentes, MUST escolher uma das leituras existentes ou responder "[ilegível]", e não pode introduzir texto novo.

#### Scenario: Árbitro desabilitado
- **WHEN** o árbitro está desabilitado e uma divergência persiste após a releitura
- **THEN** a palavra fica com status "em dúvida", mantendo a leitura de maior confiança e as alternativas registradas

#### Scenario: Árbitro tenta texto novo
- **WHEN** o árbitro responde um texto diferente de ambas as leituras e de "[ilegível]"
- **THEN** a resposta é descartada e a palavra fica com status "em dúvida"

### Requirement: Rastreabilidade
Para cada palavra o sistema SHALL guardar as leituras de origem e suas confianças, para que a conferência possa mostrar as alternativas; as alternativas de uma palavra em dúvida MUST ser distintas entre si.

#### Scenario: Alternativas disponíveis
- **WHEN** uma palavra está "em dúvida"
- **THEN** o resultado da conversão inclui as leituras alternativas distintas dessa palavra com suas confianças

### Requirement: Contagem de dúvidas
O sistema SHALL informar, por página e no total, quantas palavras ficaram aceitas, resolvidas e em dúvida.

#### Scenario: Resumo de dúvidas
- **WHEN** a conversão termina
- **THEN** o resultado informa o total de palavras em dúvida por página e no documento
