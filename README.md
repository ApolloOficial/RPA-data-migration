# 🤖 RPA Data Migration — Apollo

Transfere cadastros do PostgreSQL legado do 1º ano para o banco normalizado do 2º ano. O robô extrai uma visão consistente, trata os campos, envia um lote para `staging` e chama a procedure `staging.pr_sync_legacy` do banco final. A procedure resolve os relacionamentos e grava nas tabelas normalizadas. Os SQLs e o PDF fornecidos são referências imutáveis.

## Mapeamento

| Origem legada | Entrada em `staging` | Destino normalizado | Mapeamento e tratamento |
| --- | --- | --- | --- |
| `usuario` com tipo `ADMINISTRADOR` | `legacy_user` | `administrator` | `id` vira `source_id`; CPF perde pontuação, e-mail vai para minúsculas e `ativo` vira booleano. |
| `empresa` | `legacy_company` | `company` | CNPJ perde pontuação; `id_usuario_cadastro` referencia o administrador legado. |
| `filial` + `segmento` + `endereco` | `legacy_company_unit` | `company_unit` + `segment` + `address` | O robô une as três tabelas; a procedure separa unidade, segmento e endereço, resolvendo as chaves da empresa e do administrador. CEP perde pontuação e UF vai para maiúsculas. |
| `usuario` com tipo `GERENTE` | `legacy_user` | `employee` com papel `GERENTE` | `id_filial` liga o gerente à unidade; e-mail vai para minúsculas e o hash da senha é preservado. |

`ATIVO` vira `true`; `INATIVO` e `CANCELADO` viram `false`. O destino gera seus próprios IDs e guarda o ID legado em `source_id`, usado pela procedure para atualizar registros em reexecuções. Um hash que não atenda ao formato esperado pelo destino é rejeitado por registro e aparece em `staging.rpa_load_error`.

O contrato atual da procedure não recebe `contrato`, `inversor`, `string`, `painel` nem `manutencao`. O robô informa suas contagens, mas não inventa os campos e papéis operacionais necessários para inseri-los no banco novo; veja a [decisão de escopo](docs/auditoria.md).

## Início rápido

Requer Python 3.12+, `psql` e acesso aos dois bancos PostgreSQL.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Preencha **`.env` na raiz do repositório** com as URIs reais `LEGACY_DATABASE_URL` e `TARGET_DATABASE_URL`. O arquivo é ignorado pelo Git. Use uma conta somente leitura no legado; a conta de destino precisa executar a procedure e gravar nas tabelas que ela atualiza. Para servidores remotos, inclua `?sslmode=require` na URI quando exigido pelo provedor.

Antes da primeira carga, prepare bancos novos e isolados com os scripts fornecidos. O SQL final contém dados demonstrativos com `source_id` conflitantes; para criar apenas o esquema e os dados de referência, derive um arquivo temporário:

```powershell
python -m app.schema_only "C:\caminho\Script_SQL_Apollo_2ano.sql" schema-only.sql
psql -X -v ON_ERROR_STOP=1 -d "postgresql://usuario@host/banco_novo" -f schema-only.sql
python -m app --check
python -m app
```

**Use o SQL derivado somente em banco novo ou descartável:** ele preserva comandos `DROP` do original. O `--check` valida relações e colisões de identidade sem gravar. Na execução, a origem usa transação somente leitura; o destino confirma ou desfaz a carga como uma transação. Uma validação inválida gera lote `FAILED` e erro sem dados pessoais; `--check` continua sem gravar. Código de saída `0` indica lote concluído, `2` indica registros rejeitados pela procedure e `1` indica falha antes da carga. Consulte `staging.rpa_load_batch` e `staging.rpa_load_error` e reexecute após corrigir a origem ou a colisão.

## Estrutura e qualidade

`app/database.py` conecta e encerra os dois bancos; `app/migration.py` faz o mapeamento e a carga; `app/main.py` executa o fluxo; `app/schema_only.py` prepara o esquema sem os dados de demonstração. Execute `python -m unittest discover -s tests -v`; o CI repete os testes e a verificação de sintaxe em branches `feat/**` e PRs para `main`.

As decisões e os limites da carga estão em [docs/auditoria.md](docs/auditoria.md). O robô pode rodar sob demanda ou agendado em um ambiente com acesso aos dois bancos; a exigência de cloud e containers do interdisciplinar se aplica à infraestrutura do projeto, sem exigir um serviço próprio e permanente para este processo.
