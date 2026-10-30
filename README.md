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
- O RPA normaliza documentos, e-mails e status e preserva os identificadores do legado em `staging`.
- A procedure do destino resolve as referências entre registros e grava as entidades normalizadas.
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

Valide as conexões e o contrato esperado sem gravar dados:

```powershell
python -m app --check
```

Se a validação passar, execute a migração:

```powershell
python -m app
```

O RPA compara os identificadores de origem (`source_id`) com os já sincronizados. Ele envia apenas novos administradores, empresas, filiais e gerentes; se não houver registros novos, não abre um lote. Alterações em registros já sincronizados não são propagadas por esse fluxo.

O `--check` confere as conexões, os pré-requisitos estruturais e quantos registros estão ausentes no destino, sem executar a procedure. A execução normal retorna `0` para lote concluído ou sem novidades, `2` quando há registros rejeitados e `1` para falha anterior à conclusão. Consulte `staging.rpa_load_batch` e `staging.rpa_load_error` para auditar lotes e corrigir rejeições.

### Execução automática no Windows

Com `.env` e `.venv` configurados, instale a tarefa que executa o RPA a cada cinco minutos:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_scheduler.ps1
```

Cada execução consulta os bancos, grava a saída em `logs/scheduled-migration.log` e só cria um lote quando encontra IDs ausentes. A tarefa roda enquanto o usuário configurado estiver conectado. Para removê-la:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\uninstall_scheduler.ps1
```

O agendamento usa o Agendador de Tarefas local porque `pg_cron` executa comandos SQL dentro do PostgreSQL e não inicia o processo Python do RPA. O computador precisa estar ligado e o usuário configurado precisa estar conectado para o monitoramento operar.

## Escopo do mapeamento

| Dados legados | Transformação | Destino |
| --- | --- | --- |
| Usuários administradores | Normalização de CPF, e-mail e status | `administrator` |
| Empresas | Normalização de CNPJ; a procedure resolve o identificador do administrador cadastrante | `company` |
| Filiais, segmentos e endereços | Consolidação dos dados legados; a procedure resolve os vínculos e separa as entidades | `company_unit`, `segment`, `address` |
| Usuários gerentes | Normalização de CPF, e-mail e status; preservação do hash de senha; a procedure resolve filial e cadastrante | `employee` com papel `GERENTE` |

O banco define `employee.is_first_access = true` para novos funcionários. O RPA não redefine essa marca em sincronizações posteriores. Tipos de usuário e entidades fora do contrato atual da migração são reportados, mas não são convertidos em dados inventados.

## Testes e documentação

```powershell
python -m unittest discover -s tests -v
```

As regras de mapeamento, tratamento de falhas e histórico das verificações do RPA estão em [docs/auditoria.md](docs/auditoria.md). A automação pode ser executada sob demanda ou no computador que tenha acesso aos bancos; não requer serviço permanente na cloud.
