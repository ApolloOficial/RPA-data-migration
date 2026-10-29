# Auditoria e decisões da migração

O RPA transporta cadastros do legado ao banco Apollo: extrai uma fotografia consistente, transforma os campos e referências, grava um lote auditável em `staging` e solicita a sincronização para as entidades normalizadas.

## Mapeamento e limites

- A leitura da origem ocorre em transação `REPEATABLE READ READ ONLY`. São extraídos administradores, empresas, filiais, segmentos, endereços e gerentes.
- O RPA normaliza CPF, CNPJ, e-mail, status e UF. Os identificadores de origem são preservados para permitir reexecuções sem duplicar os mesmos cadastros.
- Filiais são mapeadas para unidade, segmento e endereço no destino. Novos funcionários recebem `is_first_access = true` pelo padrão do banco; a sincronização não altera a flag existente.
- O contrato atual inclui administradores, empresas, unidades e gerentes. Tipos de usuário e dados operacionais fora desse escopo são reportados, sem preenchimento artificial.
- Antes de gravar, `--check` confere as colunas, a rotina de sincronização, o papel `GERENTE`, o padrão de `employee.is_first_access` e as referências estruturais necessárias.
- O RPA não interrompe a extração por `id_usuario_cadastro` nulo ou sem administrador correspondente. A procedure do destino valida essa regra durante a sincronização; se o vínculo for obrigatório e não puder ser resolvido, o registro é marcado como rejeitado e aparece em `staging.rpa_load_error`.

## Integridade e recuperação

Um lock transacional evita cargas simultâneas no mesmo destino. A escrita no staging e a sincronização são confirmadas em uma única transação; erros de SQL ou conexão causam rollback. Erros de validação registrados na execução normal ficam associados ao lote em `staging.rpa_load_error`; o RPA remove o payload bruto desses erros antes do commit. O modo `--check` não grava dados.

Para investigar ou recuperar uma carga, consulte `staging.rpa_load_batch` e `staging.rpa_load_error`, corrija o registro na fonte ou resolva o conflito indicado e execute novamente. As URIs de conexão ficam no `.env` local, ignorado pelo Git. As tabelas de staging contêm dados transportados e devem ter acesso restrito e retenção definida.

## Evidências do RPA

Os testes automatizados cobrem transformação, validação de referências e destino, origem vazia, falhas, limpeza de payload e encerramento das conexões. Em execuções isoladas anteriores, o RPA processou 9 de 9 registros em duas execuções idempotentes; uma cópia de origem com CNPJ inválido gerou lote `FAILED` sem alterar os cadastros carregados.

Em 26/10/2026, uma consulta somente leitura ao ambiente configurado encontrou 0 administradores, 2 empresas, 3 filiais e 2 gerentes na origem. A versão do RPA naquela data interrompia a extração com `manager:1 has no registering administrator`; essa pré-validação foi removida. A procedure do destino ainda pode rejeitar individualmente os registros sem administrador cadastrante válido. Também foram encontrados três usuários `OPERADOR` e três `TECNICO`, fora do contrato de migração vigente.

Em 28/10/2026, a verificação remota não chegou a consultar os bancos porque o DNS não resolveu o host do legado. Nenhuma alteração remota foi feita nessa tentativa. Os resultados acima são históricos; o estado remoto atual requer nova execução de `python -m app --check` com conectividade disponível.
