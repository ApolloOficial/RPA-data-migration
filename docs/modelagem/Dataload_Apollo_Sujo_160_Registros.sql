-- APOLLO | CARGA LEGADA SUJA | 220 REGISTROS
-- Executar DEPOIS do Dataload_Apollo_Formal_500_Registros.sql, em ambiente de teste.
-- Não executa pr_sync_legacy: dados inválidos ficam isolados em staging.
-- 160 usuários + 25 empresas + 35 filiais = 220 registros.
-- Valores malformados permanecem dentro dos limites físicos das colunas de staging; serão rejeitados pelas regras de negócio na etapa de validação.
-- O CNPJ pontuado inválido tem 14 caracteres para caber na coluna varchar(14).
BEGIN;
DO $dirty$
DECLARE
    v_batch bigint;
BEGIN
    INSERT INTO staging.rpa_load_batch (source_system, source_file)
    VALUES ('CRUD_1ANO_SUJO', 'apollo_legacy_sujo_220.csv')
    RETURNING id INTO v_batch;

    INSERT INTO staging.legacy_company
      (load_batch_id, source_id, name, cnpj, contact_email, description, registered_by_source_id)
    SELECT v_batch, 8000 + n,
      CASE WHEN n % 11 = 0 THEN '   ' WHEN n % 7 = 0 THEN 'EMPRESA DUPLICADA'
           ELSE 'Empresa Solar Legada ' || lpad(n::text, 3, '0') END,
      CASE WHEN n % 9 = 0 THEN '00.000.000/000'
           WHEN n % 8 = 0 THEN '123'
           WHEN n % 6 = 0 THEN '11222333000199'
           ELSE lpad((40000000000000::bigint + n)::text, 14, '0') END,
      CASE WHEN n % 5 = 0 THEN 'email-sem-arroba'
           WHEN n % 4 = 0 THEN 'contato@@empresa.demo'
           ELSE 'empresa' || n || '@legado.demo' END,
      CASE WHEN n % 3 = 0 THEN 'Nome, documento ou contato potencialmente inconsistente'
           ELSE 'Importação legada não validada' END,
      CASE WHEN n % 6 = 0 THEN 999999 ELSE 1 END
    FROM generate_series(1, 25) AS n;

    INSERT INTO staging.legacy_company_unit
      (load_batch_id, source_id, company_source_id, segment_source_id, segment_name,
       name, cnpj, email, phone, street_name, number, additional_info,
       neighborhood, city, state, zip_code, registered_by_source_id)
    SELECT v_batch, 9000 + n,
      CASE WHEN n % 8 = 0 THEN 999999 ELSE 8000 + ((n - 1) % 25) + 1 END,
      CASE WHEN n % 9 = 0 THEN 9999 ELSE 1 END,
      CASE WHEN n % 9 = 0 THEN '???' ELSE 'Energia' END,
      CASE WHEN n % 10 = 0 THEN ' ' ELSE 'Unidade Fotovoltaica ' || n END,
      CASE WHEN n % 6 = 0 THEN 'INVALIDO'
           WHEN n % 5 = 0 THEN '00000000000000'
           ELSE (50000000000000::bigint + n)::text END,
      CASE WHEN n % 7 = 0 THEN 'sem-email' ELSE 'filial' || n || '@legado.demo' END,
      CASE WHEN n % 4 = 0 THEN 'ABC-999'
           WHEN n % 3 = 0 THEN '123'
           ELSE '119' || lpad(n::text, 8, '0') END,
      CASE WHEN n % 11 = 0 THEN ' ' ELSE 'Rua da Energia' END,
      CASE WHEN n % 5 = 0 THEN '-50' ELSE n::text END,
      NULL,
      CASE WHEN n % 7 = 0 THEN '' ELSE 'Industrial' END,
      CASE WHEN n % 8 = 0 THEN 'Cidade???' ELSE 'São Paulo' END,
      CASE WHEN n % 6 = 0 THEN 'XX' ELSE 'SP' END,
      CASE WHEN n % 5 = 0 THEN 'ABCDE-00'
           WHEN n % 4 = 0 THEN '00000000'
           ELSE '01001000' END,
      CASE WHEN n % 9 = 0 THEN 999999 ELSE 1 END
    FROM generate_series(1, 35) AS n;

    INSERT INTO staging.legacy_user
      (load_batch_id, source_id, user_type, full_name, email, cpf,
       password_hash, company_unit_source_id, registered_by_source_id)
    SELECT v_batch, 10000 + n,
      CASE WHEN n % 2 = 0 THEN 'GERENTE' ELSE 'ADMINISTRADOR' END,
      CASE WHEN n % 19 = 0 THEN '   '
           WHEN n % 11 = 0 THEN '123456'
           WHEN n % 7 = 0 THEN 'USUARIO DUPLICADO'
           ELSE 'Usuário Legado ' || lpad(n::text, 3, '0') END,
      CASE WHEN n % 16 = 0 THEN 'usuario@@dominio.com'
           WHEN n % 12 = 0 THEN 'sem-arroba.dominio.com'
           WHEN n % 10 = 0 THEN 'duplicado@legado.demo'
           WHEN n % 9 = 0 THEN ' USUARIO' || n || '@LEGADO.DEMO '
           ELSE 'usuario' || n || '@legado.demo' END,
      CASE WHEN n % 15 = 0 THEN '11111111111'
           WHEN n % 11 = 0 THEN '123'
           WHEN n % 8 = 0 THEN 'ABC12345678'
           WHEN n % 7 = 0 THEN '12345678909'
           ELSE lpad((70000000000::bigint + n)::text, 11, '0') END,
      CASE WHEN n % 14 = 0 THEN '123456'
           WHEN n % 9 = 0 THEN 'senha-em-texto-puro'
           ELSE '$2b$10$9w.i.5LbqScZT06ym/WPFOezKVWSa506sHzZNzsD1g5mHkAH6iTpO' END,
      CASE WHEN n % 12 = 0 THEN 999999
           WHEN n % 5 = 0 THEN 101
           ELSE 9000 + ((n - 1) % 35) + 1 END,
      CASE WHEN n % 18 = 0 THEN 999999 ELSE 1 END
    FROM generate_series(1, 160) AS n;

    RAISE NOTICE 'Carga suja criada no batch %: 25 empresas, 35 filiais, 160 usuários', v_batch;
END;
$dirty$;
COMMIT;

-- DIAGNÓSTICO: resumo de registros da carga suja mais recente.
SELECT b.id AS batch_id, b.source_file,
       (SELECT count(*) FROM staging.legacy_company c WHERE c.load_batch_id = b.id) AS empresas,
       (SELECT count(*) FROM staging.legacy_company_unit u WHERE u.load_batch_id = b.id) AS filiais,
       (SELECT count(*) FROM staging.legacy_user x WHERE x.load_batch_id = b.id) AS usuarios
FROM staging.rpa_load_batch b
WHERE b.source_file = 'apollo_legacy_sujo_220.csv'
ORDER BY b.id DESC LIMIT 1;

-- IMPORTANTE: NÃO executar CALL staging.pr_sync_legacy(...) nesta massa
-- sem revisar o comportamento da procedure e as regras de validação.
