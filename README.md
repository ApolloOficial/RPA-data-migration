# 🤖 RPA Data Migration — Apollo

Transfere cadastros do PostgreSQL legado do 1º ano para o banco normalizado do 2º ano. O robô extrai uma visão consistente, trata os campos, envia um lote para `staging` e chama a procedure `staging.pr_sync_legacy` do banco final. Os SQLs e o PDF fornecidos são referências imutáveis.

## Mapeamento

| Origem legada | Destino normalizado | Tratamento |
| --- | --- | --- |
| `usuario` administrador | `administrator` | CPF sem pontuação, e-mail minúsculo, status booleano |
| `empresa` | `company` | CNPJ sem pontuação e vínculo ao administrador |
| `filial` + `segmento` + `endereco` | `company_unit` + `segment` + `address` | Junção, CEP sem pontuação, UF maiúscula e chaves relacionadas |
| `usuario` gerente | `employee` com papel `GERENTE` | Vínculo à unidade e hash preservado |

O destino gera seus próprios IDs e guarda o ID legado em `source_id` para permitir reexecução. O contrato atual da procedure não recebe contratos, equipamentos nem manutenções: o robô informa suas contagens e não inventa campos ausentes.

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
