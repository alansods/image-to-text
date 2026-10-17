## Purpose

Define o ciclo de vida da conversão no servidor — fila, progresso, cancelamento, falhas e descarte dos arquivos — para que documentos longos sejam processados sem travar a interface e sem guardar nada além do necessário.

## ADDED Requirements

### Requirement: Estados da conversão
Cada conversão SHALL passar pelos estados "na fila", "processando", "concluída", "falhou", "cancelada" e "expirada", e o estado atual MUST ser consultável pelo identificador da conversão.

#### Scenario: Consulta de estado
- **WHEN** o cliente consulta uma conversão recém-criada
- **THEN** o estado retornado é "na fila" ou "processando"

#### Scenario: Conversão inexistente
- **WHEN** o cliente consulta um identificador que não existe
- **THEN** o sistema responde "não encontrado"

### Requirement: Progresso
Enquanto a conversão não termina, a tela SHALL mostrar "Lendo seu documento…", o nome do arquivo, uma barra com o percentual geral (0 a 100) e o botão "Cancelar". O percentual MUST nunca diminuir. Enquanto a conversão aguarda na fila, o percentual é 0.

#### Scenario: Documento de 5 páginas
- **WHEN** o servidor terminou 2 das 5 páginas
- **THEN** a tela mostra um percentual entre 40% e 60%

#### Scenario: Aguardando na fila
- **WHEN** há outras conversões à frente
- **THEN** a tela mostra "Lendo seu documento…" com 0%

### Requirement: O que está acontecendo
Durante o progresso, a tela SHALL mostrar uma ilustração animada de uma folha sendo lida e uma frase sobre a etapa real da conversão, informada pelo servidor junto com a página atual: na fila, preparando a página, encontrando a estrutura, lendo o texto ou montando o documento. Enquanto o texto é lido, uma segunda frase SHALL alternar dicas verdadeiras sobre o produto. Com "reduzir movimento" ativado no sistema, a ilustração MUST ficar parada e as dicas MUST NOT trocar sozinhas.

#### Scenario: Lendo a segunda página
- **WHEN** o servidor está lendo o texto da página 2 de 5
- **THEN** a tela mostra "Lendo o texto da página 2 de 5" e uma dica abaixo, que troca depois de alguns segundos

#### Scenario: Na fila
- **WHEN** a conversão aguarda na fila
- **THEN** a tela mostra "Na fila, já vai começar…"

#### Scenario: Reduzir movimento
- **WHEN** o sistema do usuário pede movimento reduzido
- **THEN** a ilustração fica parada e a dica não troca sozinha

### Requirement: Conclusão
Quando todas as páginas terminam, o sistema SHALL levar o usuário automaticamente à tela de resultado, sem ação dele.

#### Scenario: Conversão concluída
- **WHEN** a última página termina de ser processada
- **THEN** a tela de progresso é substituída pela tela de resultado

### Requirement: Cancelamento
O usuário SHALL poder cancelar a conversão durante o progresso; o processamento é interrompido em até 10 segundos, a conversão vai para "cancelada", seus arquivos são apagados e o usuário volta à tela de envio.

#### Scenario: Cancelar
- **WHEN** o usuário clica em "Cancelar" durante o progresso
- **THEN** o usuário volta à tela de envio e, em até 10 segundos, nenhum arquivo da conversão existe mais no servidor

### Requirement: Falhas
Se uma página falhar, o sistema SHALL continuar as demais e incluir a página que falhou no resultado como a imagem original da página, com um trecho "[ilegível]" em dúvida; se todas as páginas falharem, a conversão vai para "falhou" e o usuário volta à tela de envio com a mensagem "Não foi possível ler esse arquivo."

#### Scenario: Página corrompida
- **WHEN** a página 2 de 4 não pode ser lida
- **THEN** o resultado tem 4 páginas, e a página 2 contém a imagem original e uma dúvida "[ilegível]"

#### Scenario: Nada pôde ser lido
- **WHEN** nenhuma página do arquivo pode ser lida
- **THEN** o usuário volta à tela de envio com a mensagem "Não foi possível ler esse arquivo."

### Requirement: Nada guardado
O sistema MUST apagar o arquivo enviado, as imagens intermediárias, o resultado e os documentos gerados quando o usuário clica em "Converter outro" ou cancela, e em qualquer caso no máximo 1 hora após o envio; depois disso a conversão fica "expirada". O sistema MUST NOT guardar dados da conversão no navegador além da sessão aberta, MUST NOT exigir conta e MUST NOT enviar imagens ou texto a serviços de terceiros.

#### Scenario: Converter outro
- **WHEN** o usuário clica em "Converter outro" na tela de resultado
- **THEN** a tela volta ao envio e os arquivos da conversão anterior deixam de existir no servidor

#### Scenario: Aba fechada
- **WHEN** o usuário fecha a aba sem clicar em nada e passa 1 hora desde o envio
- **THEN** a conversão está "expirada" e nenhum arquivo dela pode ser baixado

#### Scenario: Página recarregada
- **WHEN** o usuário recarrega a página durante ou depois da conversão
- **THEN** a tela de envio aparece vazia, sem resultado anterior

### Requirement: Limite de uso
O sistema SHALL limitar a 3 conversões ativas simultâneas por endereço de origem, recusando novas acima disso com a mensagem "Aguarde a conclusão de uma conversão em andamento."

#### Scenario: Quarta conversão simultânea
- **WHEN** um mesmo endereço já tem 3 conversões ativas e envia um quarto arquivo
- **THEN** a conversão não começa e o sistema mostra "Aguarde a conclusão de uma conversão em andamento."
