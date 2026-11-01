# Candidata funcional de saída — trabalho parcial

**NO-GO para avaliação real e uso externo.** O gate permanece fechado. A projeção anterior em `candidate.py` continua disponível. Esta rodada adiciona apenas dois componentes de admissão para experimentação offline; não existe ainda uma projeção funcional completa nem um novo caminho conectado ao motor.

| Parte | Estado | Evidência / limite |
| --- | --- | --- |
| Perguntas genéricas | Parcial | `admit_generic_message` preserva poucas frases de gramática fechada. Perguntas naturais fora desse conjunto são bloqueadas, inclusive pedidos válidos. |
| Golden set sintético | Parcial | `admit_golden_message` aceita apenas o texto exato e ID do conjunto versionado com hash fixo; alteração do arquivo ou da mensagem falha fechada. Não houve execução de LLM real. |
| Manual | Disponível na candidata anterior | `candidate_prompt` usa a versão exata do manual e mascara contatos institucionais. A conciliação com DEC-03, DEC-06 e AGT-04 permanece pendente. |
| Resultados e argumentos das oito ferramentas | Não implementado na nova candidata | Ainda falta um mecanismo verificável que vincule cada resultado ao despacho real autorizado, sem reexecutar ferramentas com efeitos. Valores textuais do banco não são confiáveis apenas pelo nome da coluna. |
| Correspondência de chamadas e captura | Não implementado na nova candidata | O harness existente usa a projeção anterior que omite argumentos e texto; não constitui demonstração funcional. |
| Segurança e rede | Gate fechado | Nenhum adaptador HTTP foi habilitado; testes de admissão não demonstram privacidade universal. |

Para concluir, é necessário projetar e testar a proveniência de nomes de catálogo e de promoções, estados e datas, resultados de cálculo e políticas, e a associação entre cada `tool_call_id`, argumentos validados e resultado autorizado da mesma sessão. Também faltam os cenários integrados de produto 90, horários, parcelamento, devolução, recusa e escalonamento no JSON serializado. Sem isso, não se deve considerar a candidata pronta nem comunicar que o JSON é funcional para atendimento.
