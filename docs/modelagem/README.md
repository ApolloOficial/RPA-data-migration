# Modelagem de Dados do Apollo

Arquivos da entrega de Modelagem de Dados do 2º ano. O código do robô de migração (RPA) está na raiz deste repositório.

| Arquivo | Conteúdo |
| --- | --- |
| `Script_SQL_Apollo_2ano.sql` | Script de construção do banco: schemas, 42 tabelas, restrições, funções, procedures, gatilhos, índices, views e comentários. |
| `Dataload_Apollo_Formal_500_Registros.sql` | Massa verossímil e volumosa para testes de volume e para o BI. Executar depois do script de construção, em banco vazio ou descartável. |
| `Dataload_Apollo_Sujo_160_Registros.sql` | Dados legados deliberadamente inválidos, carregados só em staging para análise de qualidade. Executar depois da carga formal, em ambiente de teste. |
| `MODELO_E_CARDINALIDADES.md` | Chaves primárias, as 57 chaves estrangeiras e as cardinalidades. |
| `modelo_logico_apollo.svg` | Diagrama lógico do banco. |
| `evidencia_explain_011126.txt` | Plano de execução (EXPLAIN ANALYZE) da validação dos índices, sem e com índice. |
| `evidencia_explain_analyze.txt` | Planos de execução da rodada anterior. |

Os scripts reiniciam tabelas de domínio: não execute em produção nem em banco com dados a preservar.
