# Adaptador em preparação — sem conexão externa

`OpenAICompatibleAdapter` mapeia mensagens, schemas e respostas de chat completions ao contrato `AssistantReply` / `FunctionCall`. A configuração chega por `Settings` injetado pelo canal confiável. O único transporte aceito nesta versão é `CaptureTransport`, de tipo exato: ele retorna respostas predefinidas e não implementa HTTP. Não há transporte de rede, ativação por variáveis de ambiente ou integração com `ConversationEngine`; `make chat` permanece offline e `make eval` bloqueado. É uma barreira de implementação para esta versão, não uma sandbox contra código Python modificado ou monkey-patching.

## Inspeção do corpo serializado

A captura acontece imediatamente na entrada do transporte simulado, depois da serialização JSON e antes de qualquer envio. Exemplo local com dados fictícios:

```python
import json
from emporio.config import Settings
from emporio.llm.openai_compat import CaptureTransport, OpenAICompatibleAdapter, SimulatedResponse

response = SimulatedResponse(body=b'{"choices":[{"message":{"role":"assistant","content":"ok"}}]}')
transport = CaptureTransport([response])
adapter = OpenAICompatibleAdapter(Settings('https://example.invalid/v1', 'modelo-teste', 'chave-ficticia'), transport)
adapter.complete([{'role': 'system', 'content': 'manual ficticio'}, {'role': 'user', 'content': 'ola'}])
payload = json.loads(transport.payloads[0])  # somente em memória; inspecionar em ambiente protegido
transport.clear()
```

As entradas podem incluir instruções de sistema, histórico, resultados de ferramentas e schemas. Para revisão futura, forneça ao adaptador exatamente as mensagens e definições que se pretende examinar. **A captura pode conter dados pessoais, contatos e segredos presentes no conteúdo**: não gravá-la em arquivos, logs, tickets ou relatórios; usar dados sintéticos sempre que possível. `clear()` libera as referências mantidas pelo transporte, sem garantir apagamento físico da memória ou de outras cópias. Nenhum header ou chave de configuração é incluído automaticamente na captura. Se um segredo já estiver em uma mensagem, ele estará no corpo capturado.

Erros são códigos estruturados sem corpo, headers ou mensagens remotas. Testes usam somente respostas e timeouts simulados; a ausência de logs ou conexões é verificada nos casos exercitados. Nenhuma sanitização por regex garante privacidade completa, e não foi aprovada exceção para contatos institucionais nem projeção externa do manual. Antes de qualquer implementação e ativação de transporte real: obter parecer do Gemini e revisão de privacidade, reconciliar DEC-06 e o manual, auditar o payload efetivo e os campos livres, definir política de autenticação, limites, observabilidade e timeouts, e revisar o gate de rede e as decisões de modelo. Nenhum smoke test real foi executado.
