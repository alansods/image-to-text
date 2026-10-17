## Purpose

Mostra o resultado da conversão como o documento que será baixado e faz o usuário conferir, uma a uma, as palavras em que o sistema tem dúvida, antes de liberar a cópia e o download.

## ADDED Requirements

### Requirement: Documento em páginas
A tela de resultado SHALL mostrar o documento em folhas, uma por página do original e na mesma ordem, com o rótulo "Página N de T" acima de cada folha e o número da página no rodapé da folha, preservando títulos, alinhamento, negrito, itálico, listas, colunas, tabelas e imagens como serão exportados. O nome do arquivo enviado e o botão "Converter outro" SHALL aparecer acima do documento.

#### Scenario: PDF de 3 páginas
- **WHEN** a conversão de um PDF de 3 páginas termina
- **THEN** a tela mostra 3 folhas, rotuladas "Página 1 de 3", "Página 2 de 3" e "Página 3 de 3"

#### Scenario: Imagem única
- **WHEN** a conversão de uma única foto termina
- **THEN** a tela mostra 1 folha rotulada "Página 1 de 1"

### Requirement: Aviso de baixa qualidade
Quando alguma página tiver baixa qualidade, a tela de resultado SHALL mostrar, acima das folhas, um aviso de que a imagem tem baixa qualidade e de que o texto e a formatação (negrito, itálico) devem ser conferidos com atenção; em documentos com mais de uma página, o aviso SHALL indicar quais páginas. O aviso MUST NOT bloquear a cópia nem o download.

#### Scenario: Imagem nítida
- **WHEN** nenhuma página do resultado tem baixa qualidade
- **THEN** nenhum aviso de qualidade aparece

#### Scenario: Uma página ruim
- **WHEN** só a página 2 de um PDF de 3 páginas tem baixa qualidade
- **THEN** o aviso de qualidade aparece e cita a página 2

#### Scenario: Não bloqueia
- **WHEN** há aviso de qualidade e nenhuma palavra em dúvida
- **THEN** a tela mostra "Tudo conferido" com "Copiar texto", "Baixar Word" e "Baixar PDF"

### Requirement: Destaque das dúvidas
Palavras "em dúvida" SHALL aparecer destacadas no texto com fundo âmbar e também com sublinhado ondulado, para que o destaque não dependa só de cor, e cada uma MUST ser um controle acionável por clique, toque e teclado.

#### Scenario: Três dúvidas
- **WHEN** o documento tem 3 palavras em dúvida
- **THEN** as 3 palavras aparecem com fundo âmbar e sublinhado ondulado, e cada uma pode receber foco pelo teclado

### Requirement: Conferência obrigatória antes de baixar
Enquanto houver palavras em dúvida, o sistema SHALL mostrar, no lugar dos botões de cópia e download, o aviso "Confira N palavras antes de baixar" (ou "Confira 1 palavra antes de baixar") com o botão "Conferir próxima", e MUST NOT oferecer cópia nem download. Quando não restar nenhuma dúvida, SHALL mostrar "Tudo conferido" e os botões "Copiar texto", "Baixar Word" e "Baixar PDF".

#### Scenario: Dúvidas pendentes
- **WHEN** o resultado abre com 3 palavras em dúvida
- **THEN** a tela mostra "Confira 3 palavras antes de baixar" e "Conferir próxima", e não mostra "Copiar texto", "Baixar Word" nem "Baixar PDF"

#### Scenario: Última dúvida resolvida
- **WHEN** o usuário resolve a última palavra em dúvida
- **THEN** a tela mostra "Tudo conferido" com "Copiar texto", "Baixar Word" e "Baixar PDF"

#### Scenario: Documento sem dúvidas
- **WHEN** a conversão termina sem nenhuma palavra em dúvida
- **THEN** a tela de resultado já abre com "Tudo conferido" e os três botões

### Requirement: Conferir uma palavra
Ao acionar uma palavra em dúvida (ou "Conferir próxima"), o sistema SHALL abrir, junto da palavra (em telas estreitas, como painel na parte de baixo da tela), um quadro com: "Na imagem:" e o recorte ampliado do original com a palavra destacada e um pouco de contexto; a pergunta "Qual está certo?"; uma opção por leitura alternativa, escrita em fonte monoespaçada, com os caracteres que diferem entre as alternativas destacados; a opção "Manter como no original"; e o campo "Ou digite a correta" com um botão de confirmar.

#### Scenario: Abrir sem a página pular
- **WHEN** o usuário aciona uma palavra em dúvida que já está visível na tela
- **THEN** o quadro abre junto da palavra sem a página rolar; só quando a palavra está fora da tela (por exemplo, com "Conferir próxima") a página rola até ela

#### Scenario: Letras parecidas
- **WHEN** as alternativas de uma palavra são "SILVA" e "SlLVA"
- **THEN** as duas opções aparecem em fonte monoespaçada e o segundo caractere de cada uma ("I" e "l") aparece destacado

#### Scenario: Nenhuma alternativa certa
- **WHEN** o usuário digita "SILVEIRA" no campo "Ou digite a correta" e confirma
- **THEN** a palavra passa a "SILVEIRA" e deixa de estar em dúvida

#### Scenario: Trecho ilegível
- **WHEN** a palavra em dúvida é "[ilegível]"
- **THEN** o quadro mostra o recorte, a opção "[ilegível]" e o campo "Ou digite a correta"

### Requirement: Resolver e ver a correção
Ao escolher uma opção, confirmar um texto digitado ou escolher "Manter como no original", a palavra SHALL passar a ter essa forma com status "editada", o quadro SHALL fechar mantendo o foco na própria palavra, o contador de dúvidas MUST diminuir em 1, e a palavra SHALL aparecer marcada em verde na tela para o usuário ver como ficou; a marca verde MUST NOT aparecer na cópia nem nos documentos baixados. O sistema MUST NOT pular sozinho para a próxima dúvida: o usuário avança com "Conferir próxima", que leva à próxima palavra em dúvida na ordem de leitura do documento (atravessando páginas). A palavra corrigida SHALL continuar acionável: acioná-la reabre o mesmo quadro, com as mesmas opções e a escolha atual indicada, e uma nova escolha substitui a anterior sem mudar o contador de dúvidas. Uma palavra corrigida para "(nenhuma palavra)" SHALL aparecer na tela como uma pequena marca verde acionável no lugar dela; essa marca MUST NOT aparecer na cópia nem nos documentos baixados.

#### Scenario: Trocar a escolha
- **WHEN** o usuário escolheu "SlLVA" por engano e aciona de novo a palavra verde
- **THEN** o quadro reabre com "SlLVA" indicada como escolha atual; ao escolher "SILVA", a palavra passa a "SILVA", continua verde, e o contador de dúvidas não muda

#### Scenario: Desfazer remoção
- **WHEN** o usuário escolheu "(nenhuma palavra)" e depois quer a palavra de volta
- **THEN** a marca verde no lugar dela reabre o quadro, e a cópia do texto não contém a marca

#### Scenario: Escolher alternativa
- **WHEN** há 3 dúvidas e o usuário escolhe "SILVA" na primeira
- **THEN** a palavra fica "SILVA" marcada em verde, o quadro fecha com o foco nela e o aviso passa a "Confira 2 palavras antes de baixar"

#### Scenario: Dúvida na página seguinte
- **WHEN** o usuário resolveu a última dúvida da página 1, a página 2 tem dúvidas e ele clica em "Conferir próxima"
- **THEN** a tela rola até a primeira dúvida da página 2 e abre o quadro nela

#### Scenario: Marca só na tela
- **WHEN** o usuário corrigiu palavras e baixa o Word
- **THEN** as palavras corrigidas aparecem no Word sem nenhuma cor ou marca

### Requirement: Manter como no original
O quadro de conferência SHALL oferecer a opção "Manter como no original"; escolhida, a palavra passa a ser mostrada, copiada como seu texto lido e exportada no Word e no PDF como o recorte da imagem original naquele ponto do texto, na mesma linha e com a altura da linha.

#### Scenario: Símbolo que ninguém leu
- **WHEN** as leituras de um travessão são "|}~°£" e "(nenhuma palavra)" e o usuário escolhe "Manter como no original"
- **THEN** no Word e no PDF aparece, naquele ponto da linha, o recorte do original com o travessão

### Requirement: Fechar sem resolver
O usuário SHALL poder fechar o quadro (botão fechar, tecla Esc ou clique fora) sem resolver a palavra, que continua em dúvida.

#### Scenario: Fechar com Esc
- **WHEN** o quadro está aberto e o usuário pressiona Esc
- **THEN** o quadro fecha, a palavra continua destacada e o contador não muda

### Requirement: Escolhas preservadas
As palavras resolvidas SHALL ser enviadas ao servidor, e a cópia e os documentos baixados MUST conter os textos escolhidos ou digitados pelo usuário.

#### Scenario: Escolha refletida no download
- **WHEN** o usuário escolheu "SILVA" no lugar de "SlLVA" e baixa o Word
- **THEN** o Word contém "SILVA" e não contém "SlLVA"
