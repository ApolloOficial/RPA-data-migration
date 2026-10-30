# Auditoria e decisões da migração

O RPA transporta cadastros do legado ao banco Apollo: extrai uma fotografia consistente, normaliza campos, preserva os identificadores de origem, grava um lote auditável em `staging` e solicita a procedure de sincronização. A procedure resolve as referências e grava as entidades normalizadas.

## Mapeamento e limites

- A leitura da origem ocorre em transação `REPEATABLE READ READ ONLY`. São extraídos administradores, empresas, filiais, segmentos, endereços e gerentes.
- O RPA normaliza CPF, CNPJ, e-mail, status e UF. Os identificadores de origem são preservados para permitir reexecuções sem duplicar os mesmos cadastros.
- Filiais são mapeadas para unidade, segmento e endereço no destino. Novos funcionários recebem `is_first_access = true` pelo padrão do banco; a sincronização não altera a flag existente.
- O contrato atual inclui administradores, empresas, unidades e gerentes. Tipos de usuário e dados operacionais fora desse escopo são reportados, sem preenchimento artificial.
- Cada execução compara os `source_id` dessas quatro entidades com o destino. Apenas IDs ausentes são enviados; se não houver novidades, nenhum lote é criado. Edições em registros já sincronizados não são propagadas.
- No Windows, `scripts/install_scheduler.ps1` agenda uma execução a cada cinco minutos enquanto o usuário configurado estiver conectado. Cada execução consulta e fecha as conexões, ignora lotes vazios e registra a saída em `logs/scheduled-migration.log`. O Agendador de Tarefas inicia o Python; `pg_cron` não executa processos externos.
- Antes de gravar, `--check` confere as colunas, a rotina de sincronização, o papel `GERENTE`, o padrão de `employee.is_first_access` e a quantidade de IDs ausentes. Ele não executa a procedure nem valida o resultado de cada referência de negócio.
- O RPA não interrompe a extração por falta de administrador cadastrante ou filial correspondente no snapshot. A procedure do destino valida essas relações durante a sincronização; se algum vínculo obrigatório não puder ser resolvido, o registro é rejeitado e aparece em `staging.rpa_load_error`.

## Integridade e recuperação

Um lock transacional evita cargas simultâneas no mesmo destino. A escrita no staging e a sincronização são confirmadas em uma única transação; erros de SQL ou conexão causam rollback. Erros de validação registrados na execução normal ficam associados ao lote em `staging.rpa_load_error`; o RPA remove o payload bruto desses erros antes do commit. O modo `--check` não grava dados.

Para investigar ou recuperar uma carga, consulte `staging.rpa_load_batch` e `staging.rpa_load_error`, corrija o registro na fonte ou resolva o conflito indicado e execute novamente. As URIs de conexão ficam no `.env` local, ignorado pelo Git. As tabelas de staging contêm dados transportados e devem ter acesso restrito e retenção definida.

## Evidências do RPA

Os testes automatizados cobrem transformação, validação de referências e destino, origem vazia, falhas, limpeza de payload e encerramento das conexões. Em execuções isoladas anteriores, o RPA processou 9 de 9 registros em duas execuções idempotentes; uma cópia de origem com CNPJ inválido gerou lote `FAILED` sem alterar os cadastros carregados.

Em 26/10/2026, uma consulta somente leitura ao ambiente configurado encontrou 0 administradores, 2 empresas, 3 filiais e 2 gerentes na origem. A versão anterior do RPA interrompia a extração por referência de administrador ausente; essa pré-validação foi removida. A verificação atual também deixa a procedure avaliar vínculos com filial ausentes no snapshot. A procedure pode rejeitar individualmente registros sem relações obrigatórias resolvidas. Também foram encontrados três usuários `OPERADOR` e três `TECNICO`, fora do contrato de migração vigente.

Em 28/10/2026, uma tentativa de verificação não chegou aos bancos porque o ambiente não resolveu o host do legado. Em 29/10/2026, `python -m app --check` conectou aos dois bancos e passou sem gravar dados. A origem ainda tinha 0 administradores, 2 empresas, 3 filiais e 2 gerentes. A leitura da procedure confirmou que o destino exige administrador cadastrante para empresas e filiais, e filial válida para gerentes; por isso, o pré-check aprovado não confirma uma carga bem-sucedida. Nenhuma carga de migração foi executada nessa verificação.
