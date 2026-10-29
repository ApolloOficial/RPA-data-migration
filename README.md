# 🤖 RPA Data Migration — Apollo

<p align="center">
  <strong>Migração auditável de cadastros legados para o banco normalizado Apollo</strong>
</p>

<p align="center">
  <img alt="Python 3.12+" src="https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white">
</p>

O robô extrai cadastros do PostgreSQL legado, trata e valida os dados e os envia para a área de `staging` do banco Apollo. A procedure de sincronização do destino distribui os registros nas tabelas normalizadas.

## Fluxo

```text
Banco legado → extração e tratamento → staging → sincronização → tabelas normalizadas
```

- A origem é lida em uma transação consistente e somente leitura.
- O RPA normaliza documentos, e-mails, status e referências entre registros.
- O destino recebe lotes auditáveis; erros de validação são registrados por lote e por registro.
- A carga no destino é transacional e pode ser repetida usando os identificadores de origem.

## Configuração e execução

Requer Python 3.12+ e acesso aos dois bancos PostgreSQL.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Preencha `LEGACY_DATABASE_URL` e `TARGET_DATABASE_URL` no `.env` da raiz. O arquivo é ignorado pelo Git. Use credenciais somente leitura para a origem e uma conta com permissão para executar a sincronização e gravar no staging do destino. Para conexões remotas, configure SSL conforme exigido pelo provedor.

Se uma empresa, filial ou gerente não tiver administrador cadastrante válido na origem, informe `MIGRATION_ADMIN_SOURCE_ID` com o `source_id` de um administrador já existente no destino. Essa conta será registrada como responsável técnico pela migração nesses cadastros. O pré-check confirma que o administrador configurado existe; sem referência ausente, a variável é opcional. Consulte os `source_id` disponíveis no destino com `SELECT source_id FROM administrator ORDER BY source_id`.

Valide as conexões e o contrato esperado sem gravar dados:

```powershell
python -m app --check
```

Se a validação passar, execute a migração:

```powershell
python -m app
```

O `--check` identifica vínculos estruturais ausentes, referências de administrador sem substituto e incompatibilidades no destino antes da carga. A execução normal retorna `0` para lote concluído, `2` quando há registros rejeitados pela sincronização e `1` para falha anterior à conclusão. Consulte `staging.rpa_load_batch` e `staging.rpa_load_error` para auditar o resultado e corrigir os dados antes de uma nova execução.

## Escopo do mapeamento

| Dados legados | Transformação | Destino |
| --- | --- | --- |
| Usuários administradores | Normalização de CPF, e-mail e status | `administrator` |
| Empresas | Normalização de CNPJ e vínculo com administrador | `company` |
| Filiais, segmentos e endereços | Consolidação da origem e separação das entidades no destino | `company_unit`, `segment`, `address` |
| Usuários gerentes | Normalização de CPF, e-mail e status; preservação do hash de senha | `employee` com papel `GERENTE` |

O banco define `employee.is_first_access = true` para novos funcionários. O RPA não redefine essa marca em sincronizações posteriores. Tipos de usuário e entidades fora do contrato atual da migração são reportados, mas não são convertidos em dados inventados.

## Testes e documentação

```powershell
python -m unittest discover -s tests -v
```

As regras de mapeamento, tratamento de falhas e histórico das verificações do RPA estão em [docs/auditoria.md](docs/auditoria.md). A automação pode ser executada sob demanda ou agendada em um ambiente com acesso aos bancos; não requer serviço permanente próprio na cloud.
