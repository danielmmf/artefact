# Auditoria preliminar de privacidade — fase 4

DEC-06 permanece em vigor. Esta auditoria não aprova exceção nem autoriza envio a provedor externo.

## Contatos no manual processado

O manual interno declara o telefone (67) 3341-4444 na capa e na seção 1.2, o e-mail contato@emporiodamusica.com.br na capa, o e-mail contato@empóriodamusica.com.br na seção 1.2 e o WhatsApp (67) 3321-4500 na seção 7. O prompt atual indica como oficiais o primeiro telefone e o e-mail sem acento e assinala a divergência. O manual, marcado como interno, não comprova por si só que os quatro dados sejam públicos ou corretos; confirmação por fonte institucional confiável está pendente. Nenhum contato de cliente foi identificado no manual. Contatos de mensagens, descrições, observações e resultados dinâmicos têm origem desconhecida e não se tornam públicos por coincidir com um contato institucional.

Proposta pendente para Claude: uma eventual exceção a DEC-06 deve identificar exatamente valores institucionais verificados, origem, finalidade, versão e revogação; só uma projeção confiável do manual poderá expô-los. Nunca aplicar allowlist por correspondência em texto dinâmico. Até decisão explícita, manter tokenização de contatos e não habilitar provedor externo. O prompt atual contém os contatos do manual em claro, portanto não está pronto para transmissão externa sob DEC-06.

## Fronteiras e limitações

O cofre guarda o mapa em memória por sessão; history e o trace existente não guardam esse mapa. A detecção de contatos em texto livre é heurística e não garante cobertura Unicode ou de formas não previstas. O texto livre pode conter outros dados pessoais, segredos, instruções e identificadores. As observações de pedido agora são omitidas na projeção do repositório, sem depender de regex; outras descrições e campos dinâmicos ainda precisam de projeção e validação. O parâmetro de prompt alternativo passa a ser tratado como mensagem de usuário e não substitui o prompt de sistema. Autorização de pedidos permanece determinada pelo contexto e pelo código Python, não pelo texto do modelo.

O tipo exato do simulador é exigido pelo motor, mas isso não constitui uma barreira de rede do processo: objetos Python podem ser alterados em tempo de execução e outros caminhos existem. Não há evidência de isolamento de rede nem gate abrangente. Não se deve interpretar os testes offline como garantia de privacidade em produção.

Antes de qualquer chamada real: aprovar a decisão de contatos, definir projeções restritivas para todos os campos livres e dados de saída, implementar isolamento e teste de rede abrangente, revisar o tratamento de segredos, concluir TRC-02 e o tratamento de falhas, realizar revisão de segurança e testar os artefatos reais. A CLI offline e o conjunto de avaliação rotulado também permanecem pendentes.
