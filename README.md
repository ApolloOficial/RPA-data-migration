# 🤖 RPA Data Migration — Apollo

<p align="center">
  <strong>Migração auditável dos cadastros legados para o banco normalizado Apollo</strong>
</p>

<p align="center">
  <img alt="Python 3.12+" src="https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white">
</p>

O RPA transfere cadastros do PostgreSQL legado do 1º ano para o banco normalizado do 2º ano. Ele trata os dados antes de enviá-los à área de `staging`; a procedure do banco final resolve as relações e grava nas tabelas normalizadas.

## Como funciona

- **Origem:** uma conexão somente leitura obtém uma visão consistente do legado.
- **Tratamento:** o robô reúne tabelas, normaliza campos e valida referências.
- **Destino:** o RPA registra o lote em `staging` e chama `staging.pr_sync_legacy(id_do_lote)`; a procedure distribui os registros pelas tabelas finais.
- **Auditoria:** lote e erros ficam em `staging.rpa_load_batch` e `staging.rpa_load_error`. A carga é transacional e pode ser reexecutada.

```text
Legado → extração e tratamento → staging → pr_sync_legacy → tabelas normalizadas
```

## Mapeamento

| Origem legada | Entrada em `staging` | Destino normalizado | Mapeamento e tratamento |
| --- | --- | --- | --- |
| `usuario` com tipo `ADMINISTRADOR` | `legacy_user` | `administrator` | `id` vira `source_id`; CPF perde pontuação, e-mail vai para minúsculas e `ativo` vira booleano. |
| `empresa` | `legacy_company` | `company` | CNPJ perde pontuação; `id_usuario_cadastro` referencia o administrador legado. |
| `filial` + `segmento` + `endereco` | `legacy_company_unit` | `company_unit` + `segment` + `address` | O robô une as três tabelas; a procedure separa unidade, segmento e endereço, resolvendo as chaves da empresa e do administrador. CEP perde pontuação e UF vai para maiúsculas. |
| `usuario` com tipo `GERENTE` | `legacy_user` | `employee` com papel `GERENTE` | `id_filial` liga o gerente à unidade; e-mail vai para minúsculas e o hash da senha é preservado. |

`Ativo` vira `true`; `Inativo` e `Cancelado` viram `false`, independentemente das maiúsculas. O destino gera seus próprios IDs e guarda o ID legado em `source_id`, usado pela procedure para atualizar registros em reexecuções. Um hash que não atenda ao formato esperado pelo destino é rejeitado por registro e aparece em `staging.rpa_load_error`.

Novos registros de `employee` começam com `is_first_access = true` pelo padrão do banco. O RPA não redefine essa flag em reexecuções; a aplicação deve marcá-la como `false` após concluir o primeiro acesso. O SQL demonstrativo inclui seis administradores da equipe com CPFs sintéticos, distintos dos cadastros reais do legado.

O contrato atual da procedure não recebe `contrato`, `inversor`, `string`, `painel` nem `manutencao`. Quando a origem passa pela validação, o robô informa as contagens dessas tabelas, mas não inventa os campos e papéis operacionais necessários para inseri-las no banco novo; veja a [decisão de escopo](docs/auditoria.md).

## Início rápido

Requer Python 3.12+, `psql` e acesso aos dois bancos PostgreSQL.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Preencha **`.env` na raiz do repositório** com as URIs reais `LEGACY_DATABASE_URL` e `TARGET_DATABASE_URL`. O arquivo é ignorado pelo Git. Use uma conta somente leitura no legado; a conta de destino precisa executar a procedure e gravar nas tabelas que ela atualiza. Para servidores remotos, inclua `?sslmode=require` na URI quando exigido pelo provedor.

Antes da migração, o legado precisa ter ao menos um usuário `ADMINISTRADOR`, e as empresas, filiais e gerentes precisam referenciar um administrador existente. `--check` valida essa condição sem gravar; se ela falhar, a execução normal também não deve ser iniciada. A [auditoria](docs/auditoria.md) registra o resultado da última verificação do ambiente configurado.

Antes da primeira carga, prepare bancos novos e isolados com os scripts da entrega de Modelagem de Dados. O SQL final reserva `source_id` negativos para os cadastros demonstrativos; os IDs positivos ficam disponíveis para o legado. Execute o dataload **antes** do RPA: ele reinicia tabelas e apagaria uma migração anterior.

```powershell
psql -X -v ON_ERROR_STOP=1 -d "postgresql://usuario@host/banco_legado" -f "C:\caminho\script-primeiro-ano.sql"
psql -X -v ON_ERROR_STOP=1 -d "postgresql://usuario@host/banco_novo" -f "C:\caminho\Script_SQL_Apollo_2ano.sql"
psql -X -v ON_ERROR_STOP=1 -d "postgresql://usuario@host/banco_novo" -f "C:\caminho\Dataload_Apollo_Formal_500_Registros.sql"
python -m app --check
python -m app
```

`Dataload_Apollo_Sujo_160_Registros.sql` é uma massa separada para analisar dados inválidos no staging: gera 220 linhas (160 usuários, 25 empresas e 35 filiais) e não chama a procedure. Ela não exercita a extração ou a validação do RPA. Para testar falhas do RPA, use um banco legado descartável com registros inválidos e execute `python -m app` contra um destino de teste.

**O script de construção recria o schema e a carga formal reinicia as tabelas de domínio:** execute-os apenas na preparação de um ambiente novo ou descartável. A carga suja apenas acrescenta registros a staging e não executa a sincronização. O `--check` valida relações e rejeita uma origem sem cadastros no contrato, sem gravar. Na execução, a origem usa transação somente leitura; o destino confirma ou desfaz a carga como uma transação. Uma validação inválida gera lote `FAILED` e erro sem cópia do registro. Código de saída `0` indica lote concluído, `2` indica registros rejeitados pela procedure e `1` indica falha antes da carga. Consulte `staging.rpa_load_batch` e `staging.rpa_load_error` e reexecute após corrigir a origem ou a restrição apontada. O mesmo `source_id` atualiza o cadastro já migrado.

## Testes

```powershell
python -m unittest discover -s tests -v
```

## Documentação

Veja as [decisões de mapeamento, evidências e limites da carga](docs/auditoria.md). O robô pode rodar sob demanda ou agendado em um ambiente com acesso aos dois bancos; não exige um serviço permanente próprio na cloud.
