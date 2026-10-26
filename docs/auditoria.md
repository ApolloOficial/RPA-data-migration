# Auditoria e decisões da migração

O fluxo é `legado → app → staging → staging.pr_sync_legacy → tabelas normalizadas`. A documentação dos scripts finais, modelo e testes fica no diretório de entrega de Modelagem de Dados.

## Decisões de mapeamento

- O robô lê administradores, empresas, filiais e gerentes em uma transação `REPEATABLE READ READ ONLY`. Ele valida documentos, e-mails, status e referências antes de abrir o lote.
- A procedure do banco final separa os dados da filial em `segment`, `address` e `company_unit`. `source_id` preserva a identidade do legado para reexecução sem duplicar entidades.
- O legado usa valores como `Ativo`, `Administrador` e `Gerente`; o robô compara status e tipos sem depender de maiúsculas. A coluna `employee.is_first_access` recebe `true` do banco para novos funcionários e permanece inalterada na sincronização seguinte.
- Empresas, filiais e gerentes precisam apontar para um administrador presente no snapshot legado. Sem essa referência válida, `--check` interrompe a migração antes de abrir um lote; não se deve substituir o responsável por um cadastro demonstrativo.
- Os cadastros demonstrativos do SQL final usam `source_id` negativos, reservando IDs positivos para o legado. Reexecuções atualizam o mesmo `source_id`, inclusive quando CPF, CNPJ ou e-mail mudam. Conflitos com outras entidades ficam sujeitos às restrições únicas do banco e aparecem como falhas por registro. O utilitário `app.schema_only` permanece disponível para testes de esquema vazio, mas não é necessário no fluxo de entrega.
- O contrato da procedure não recebe `contrato`, `inversor`, `string`, `painel` nem `manutencao`. O esquema final não possui tabela de contrato; equipamentos e manutenções requerem atributos e papéis operacionais que o legado não fornece. O robô mostra essas contagens e não fabrica dados para preencher lacunas.

## Carga e recuperação

Um lock transacional impede duas cargas simultâneas no mesmo destino. Uma origem sem cadastros no contrato é recusada antes da carga em staging; na execução normal, a falha gera um lote `FAILED` para auditoria. Staging e procedure são confirmados na mesma transação; erro de conexão ou SQL desfaz essa transação. Falhas de validação na execução normal geram lote `FAILED` e registro em `staging.rpa_load_error`. Após a procedure, o RPA limpa `source_payload` dos erros do próprio lote antes do commit. O modo `--check` não grava. As tabelas de staging ainda contêm os dados transportados e exigem acesso restrito e política de retenção. Se a conexão falhar ou a transação do destino ficar inválida, não é possível registrar o lote ali; consulte a saída de erro do processo.

Para recuperar uma carga, consulte `staging.rpa_load_batch` e `staging.rpa_load_error`, corrija o dado na fonte operacional ou a colisão no destino e execute novamente. As conexões são encerradas em ordem inversa; a origem permanece somente leitura. As URIs ficam no `.env` local, ignorado pelo Git.

## Verificação realizada

Em PostgreSQL 16 isolado, o SQL final, o dataload e a migração foram executados nessa ordem. O RPA processou 9/9 cadastros em duas execuções, mantendo as mesmas contagens no destino. Um CNPJ inválido em uma cópia descartável do legado gerou lote `FAILED` (1/1), sem payload e sem alterar os cadastros já carregados. Em nova verificação isolada, a procedure aceitou mudança de CPF e e-mail para o mesmo `source_id`; uma falha por CPF duplicado teve o payload limpo antes do commit. Os testes automatizados cobrem transformação, preparação do esquema, origem vazia, limpeza do erro, falha de validação e encerramento das conexões.

Em 26/10/2026, a consulta somente leitura ao ambiente configurado encontrou 0 administradores, 2 empresas, 3 filiais e 2 gerentes no legado. As 7 empresas, filiais e gerentes referenciam administradores ausentes; por isso `python -m app --check` para em `manager:1 has no registering administrator`. Nenhum desses 7 registros tem `source_id` positivo nas tabelas normalizadas do destino. Há também 3 usuários `OPERADOR` e 3 `TECNICO`, fora do contrato atual do RPA. O destino mantém um lote `CRUD_1ANO` com 14 de 15 registros marcados como processados e 1 falha, mas atualmente só contém os cadastros demonstrativos com `source_id` negativo; esse histórico não comprova que a carga esteja presente no estado atual. O lote `CRUD_1ANO_SUJO` está em `RECEIVED` com 160 usuários, 25 empresas e 35 filiais pendentes, conforme esperado para a massa de análise que não chama a procedure.
