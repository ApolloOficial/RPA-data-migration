# Auditoria do repositório

Antes desta entrega, o repositório tinha apenas README e licença. A revisão da PR contra `main` verificou código, testes, CI, segurança das conexões e aderência aos SQLs e ao PDF fornecidos.

| Risco encontrado | Tratamento |
| --- | --- |
| Cópia literal não atenderia ao banco normalizado | Junções e tratamento de documentos, status e relacionamentos antes da carga; a procedure desmembra filial em segmento, endereço e unidade. |
| IDs da massa demonstrativa conflitam com os do legado | `--check` e a validação do destino impedem sobrescrever uma identidade diferente. |
| Falhas ou reexecuções poderiam duplicar dados | Lote transacional, `source_id` para atualização e erros em `staging.rpa_load_error`, inclusive antes da carga. |
| Duas conexões sem responsável explícito | `DatabaseConnections` abre a origem somente leitura e encerra o destino primeiro, com rollback em exceções. |
| Ausência de revisão reproduzível | Testes, CI, template de PR e commits por responsabilidade. |

**Limite do contrato:** a procedure de destino não recebe contratos, equipamentos nem manutenções. O banco final não tem tabela de contrato; os demais objetos exigem campos e papéis operacionais ausentes no legado. O robô informa as contagens e não cria dados fictícios.

**Evidência:** em PostgreSQL 16 isolado, os SQLs imutáveis resultaram em 9/9 cadastros processados; uma segunda execução não duplicou entidades. Um hash inválido gerou 1 erro por registro, e uma colisão de administrador foi barrada pelo `--check`. O CI executa testes sem provisionar os bancos de referência.

**Limite operacional:** falhas de validação em execução normal geram um lote `FAILED` com erro sem payload; o modo `--check` informa o problema sem gravar. Falhas de conexão ou SQL que invalidem a transação impedem registrar o lote e precisam ser consultadas no stderr.
