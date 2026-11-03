# Auditoria e justificativas da migração

## Escopo

O RPA migra administradores, empresas, filiais e gerentes. Esses cadastros formam a base administrativa necessária para relacionar usuários, organizações e unidades no banco normalizado.

Contratos, inversores, strings, painéis e manutenções ficam fora desta carga: pertencem ao fluxo operacional e não têm mapeamento de migração neste RPA. Importá-los sem resolver suas relações e regras próprias poderia criar dados incompletos. Outros tipos de usuário também são excluídos porque não fazem parte do contrato atual de destino. A execução apenas informa as quantidades fora do escopo; não cria dados substitutos.

Filiais são divididas entre unidade, segmento e endereço. O RPA normaliza CPF, CNPJ, e-mail, status, UF e CEP e preserva o ID legado como `source_id`. A procedure do destino resolve os vínculos e grava as entidades normalizadas.

## Decisões de integridade

- A origem é lida em uma transação consistente e somente leitura.
- Cada execução compara os IDs de origem com os do destino e envia apenas os que ainda não existem. Isso permite repetir a carga sem duplicar cadastros. Alterações em registros já migrados não são propagadas para evitar sobrescrever dados do destino sem uma política de atualização definida.
- A gravação no staging e a sincronização ocorrem na mesma transação do destino. Erros de SQL causam rollback; registros recusados pela validação da procedure são identificados no lote e em `staging.rpa_load_error`.
- O `--check` conta os registros ausentes e confere a estrutura necessária, mas não executa a procedure nem garante que todos os vínculos serão aceitos. Um responsável cadastrante nulo, por exemplo, pode ser rejeitado pelo staging ou pela regra do destino durante a execução.
- O lock transacional e `ReservedConcurrentExecutions: 1` evitam sobreposição de cargas no mesmo destino.

## Operação e recuperação

Na AWS, o EventBridge agenda a Lambda a cada cinco minutos. As URIs ficam no Secrets Manager; os logs de execução ficam no CloudWatch. A função precisa de acesso de rede aos dois bancos. A origem deve usar credencial somente leitura.

Para investigar uma execução, consulte `staging.rpa_load_batch` e `staging.rpa_load_error`. Corrija a causa na origem ou resolva o vínculo indicado no destino e execute novamente. O RPA remove o payload bruto de erro antes de confirmar o lote. Em desenvolvimento local, configure `LEGACY_DATABASE_URL` e `TARGET_DATABASE_URL` em `.env`, que não é versionado.

## Evidência de execução

Na execução reportada pela equipe, o lote 4 terminou como `COMPLETED`: 12 registros processados e nenhum erro (5 administradores, 2 empresas, 3 filiais e 2 gerentes).
