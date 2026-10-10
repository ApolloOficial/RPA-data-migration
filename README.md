# RPA Data Migration — Apollo

Transporte de cadastros do PostgreSQL legado do 1º ano para a camada `staging` do PostgreSQL normalizado do 2º ano. O robô lê uma fotografia consistente do legado, trata os campos, registra um lote e aciona `staging.pr_sync_legacy`. Essa procedure do banco final desmembra a filial em `segment`, `address` e `company_unit`, liga as chaves estrangeiras e registra erros por registro. **Nenhum dos três scripts SQL nem o PDF fornecidos é modificado ou versionado aqui.**

## Escopo e mapeamento

| Legado | Staging do 2º ano | Destino normalizado | Tratamento |
| --- | --- | --- | --- |
| `usuario` + `tipo_usuario = ADMINISTRADOR` | `legacy_user` | `administrator` | ID de origem, CPF sem pontuação, e-mail minúsculo, `ativo` em booleano |
| `empresa` | `legacy_company` | `company` | CNPJ sem pontuação; referência ao administrador que cadastrou |
| `filial` + `segmento` + `endereco` | `legacy_company_unit` | `segment`, `address`, `company_unit` | Junção de três tabelas; CEP sem pontuação, UF maiúscula, referências de empresa e administrador |
| `usuario` + `tipo_usuario = GERENTE` | `legacy_user` | `employee` com papel `GERENTE` | Referência à filial e ao administrador; hash bcrypt preservado; e-mail minúsculo |

`ATIVO` vira `true`; `INATIVO` e `CANCELADO` viram `false`. IDs do legado são guardados como `source_id`; os IDs internos do banco novo continuam sendo gerados pelo destino. A procedure usa esses IDs para atualizar um cadastro já sincronizado. O robô nunca lê senhas em texto puro nem altera o hash recebido. Se um hash não for bcrypt, a procedure marca só aquele gerente como `FAILED` e registra o motivo em `staging.rpa_load_error`.

O contrato de RPA embutido no banco final **não recebe** `contrato`, `inversor`, `string`, `painel` ou `manutencao`. Esses registros aparecem nas contagens de cada execução, mas não são migrados silenciosamente. `contrato` não tem tabela correspondente no esquema final. Equipamentos e manutenções exigem campos ausentes no legado, como modelo técnico completo, código de barras real, operador e técnico ativos da filial; os triggers do banco final exigem esses papéis. Inventar esses dados ou criar atores fictícios tornaria a carga incorreta. É preciso definir a origem desses campos e os responsáveis operacionais antes de ampliar o contrato.

## Preparação

Requer Python 3.12+, PostgreSQL compatível com os scripts fornecidos, `psql` e acesso separado aos dois bancos.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Em bancos **novos e isolados**, execute o SQL imutável do 1º ano no banco de origem. O SQL final do 2º ano contém sua própria massa demonstrativa; se executado por inteiro, ela usa `source_id` incompatíveis com os do legado anexado. Para montar um destino limpo com o esquema, procedures, papéis e tabelas de referência do SQL original, derive um arquivo temporário sem a massa demonstrativa:

```powershell
python -m migration.schema_only "C:\caminho\Script_SQL_Apollo_2ano.sql" schema-only.sql
psql -X -v ON_ERROR_STOP=1 -d "postgresql://usuario@host/banco_novo" -f schema-only.sql
```

O utilitário exige o marcador e a procedure esperados e encerra com `COMMIT`; não toca no original. O SQL derivado contém comandos `DROP` do script original: use-o **somente em um banco novo ou descartável**. O dataload do 2º ano é uma demonstração independente, não a fonte da migração. Se o destino já o contém, `--check` detecta colisões de `source_id` antes de gravar.

Defina as URLs fora do repositório. Em serviços remotos, configure TLS na própria URL, conforme o provedor:

```powershell
$env:LEGACY_DATABASE_URL = "postgresql://usuario:senha@host-legado:5432/apollo_1ano?sslmode=require"
$env:TARGET_DATABASE_URL = "postgresql://usuario:senha@host-novo:5432/apollo_2ano?sslmode=require"
python -m migration --check
python -m migration
```

Use uma conta com `SELECT` apenas no legado. No destino, a conta precisa ler as tabelas de preflight, inserir em `staging`, executar a procedure e ter os direitos que essa procedure exige nas tabelas normalizadas, pois ela roda com as permissões de quem a chama. Não versione URLs, `.env`, dumps, logs com dados pessoais ou o SQL derivado. O `.gitignore` cobre os arquivos locais comuns; revise sempre o `git diff --staged`.

## Execução, verificação e recuperação

`--check` lê e valida um snapshot do legado, confere a procedure, o papel `GERENTE` e colisões de IDs no destino, sem gravar. A execução normal usa uma transação no destino e um lock por transação para impedir dois robôs simultâneos. A entrada de staging e a chamada da procedure são confirmadas juntas. Uma falha de conexão ou de SQL fora da procedure desfaz o lote inteiro.

Ao final, a saída mostra ID do lote, estado e contagens. Código de saída `0` significa `COMPLETED`; `2` significa que a procedure confirmou um lote com registros rejeitados; `1` significa que a execução parou antes de confirmar o lote. Consulte os erros sem expor payloads em logs compartilhados:

```sql
SELECT id, status, total_records, processed_records, failed_records
  FROM staging.rpa_load_batch ORDER BY id DESC LIMIT 5;

SELECT source_record_key, error_message
  FROM staging.rpa_load_error WHERE load_batch_id = :batch_id ORDER BY id;
```

Corrija os dados na **fonte operacional**, quando autorizado pelo responsável por ela, ou resolva a divergência de identidade no destino; não edite os scripts de referência. Depois execute novamente. O upsert da procedure usa `source_id`, portanto uma nova execução atualiza os registros já sincronizados. Lotes antigos e erros ficam disponíveis para auditoria. Antes de reprocessar em produção, faça backup do destino conforme o runbook do banco final.

## Qualidade e fluxo de colaboração

```powershell
python -m unittest discover -s tests -v
python -m compileall -q migration tests
```

O CI executa esses checks em pushes de `codex/**` e em PRs para `main`. O desenvolvimento ocorre em branchs de feature com commits em inglês no padrão Conventional Commits, por exemplo `feat: migrate legacy registration data`. Use o template de PR para registrar evidências, impacto nos dados e plano de recuperação; peça revisão e aguarde as aprovações antes do merge. Este repositório não guarda credenciais nem altera as bases de referência.

A auditoria do estado inicial e dos limites da entrega está em [docs/repository-audit.md](docs/repository-audit.md).
