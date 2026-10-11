# Auditoria e decisões da migração

O fluxo é `legado → app → staging → staging.pr_sync_legacy → tabelas normalizadas`. A documentação dos scripts finais, modelo e testes fica no diretório de entrega de Modelagem de Dados.

## Decisões de mapeamento

- O robô lê administradores, empresas, filiais e gerentes em uma transação `REPEATABLE READ READ ONLY`. Ele valida documentos, e-mails, status e referências antes de abrir o lote.
- A procedure do banco final separa os dados da filial em `segment`, `address` e `company_unit`. `source_id` preserva a identidade do legado para reexecução sem duplicar entidades.
- Os cadastros demonstrativos do SQL final usam `source_id` negativos, reservando IDs positivos para o legado. O `--check` continua detectando colisões reais de identidade. O utilitário `app.schema_only` permanece disponível para testes de esquema vazio, mas não é necessário no fluxo de entrega.
- O contrato da procedure não recebe `contrato`, `inversor`, `string`, `painel` nem `manutencao`. O esquema final não possui tabela de contrato; equipamentos e manutenções requerem atributos e papéis operacionais que o legado não fornece. O robô mostra essas contagens e não fabrica dados para preencher lacunas.

## Carga e recuperação

Um lock transacional impede duas cargas simultâneas no mesmo destino. Staging e procedure são confirmados na mesma transação; erro de conexão ou SQL desfaz essa transação. Falhas de validação na execução normal geram lote `FAILED` e registro em `staging.rpa_load_error`, sem guardar o conteúdo do registro. O modo `--check` não grava. Se a conexão falhar ou a transação do destino ficar inválida, não é possível registrar o lote ali; consulte a saída de erro do processo.

Para recuperar uma carga, consulte `staging.rpa_load_batch` e `staging.rpa_load_error`, corrija o dado na fonte operacional ou a colisão no destino e execute novamente. As conexões são encerradas em ordem inversa; a origem permanece somente leitura. As URIs ficam no `.env` local, ignorado pelo Git.

## Verificação realizada

Em PostgreSQL 16 isolado, o SQL final, o dataload e a migração foram executados nessa ordem. O RPA processou 9/9 cadastros em duas execuções, mantendo as mesmas contagens no destino. Um CNPJ inválido em uma cópia descartável do legado gerou lote `FAILED` (1/1), sem payload e sem alterar os cadastros já carregados. Também foram verificados hash inválido com erro por registro e colisão de administrador barrada pelo `--check`. Os testes automatizados cobrem transformação, preparação do esquema, colisão, falha de validação e encerramento das conexões; o CI executa esses testes e a verificação de sintaxe, sem provisionar PostgreSQL.
