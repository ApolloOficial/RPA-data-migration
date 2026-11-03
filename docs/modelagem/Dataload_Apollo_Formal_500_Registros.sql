-- CARGA FORMAL DA MASSA DEMONSTRATIVA APOLLO
-- Executar depois de Script_SQL_Apollo_2ano.sql, em banco vazio/descartável.
-- Inclui cadastros de referência e massa operacional superior ao mínimo de 500 registros.
-- A carga reinicia tabelas de domínio; não executar em produção ou em banco com dados a preservar.

BEGIN;

TRUNCATE TABLE access_log, panel_status_history, suggested_external_relocation, suggested_internal_relocation, maintenance_part, maintenance_register, warning, string_health_history, string_performance_measurement, panel, string, inverter, stock, part, inverter_model, panel_model, maintenance_type, employee, company_unit, administrator, address, segment, company, roles, staging.rpa_load_error, staging.legacy_user, staging.legacy_company, staging.legacy_company_unit, staging.rpa_load_batch, audit.audit_panel, audit.audit_maintenance_register RESTART IDENTITY CASCADE;

CREATE OR REPLACE FUNCTION pg_temp.rnd(p text) RETURNS numeric LANGUAGE sql IMMUTABLE AS $$
    SELECT ((('x' || substr(md5(p), 1, 8))::bit(32)::bigint % 1000000)::numeric / 1000000)
$$;

CREATE OR REPLACE FUNCTION pg_temp.today_sp() RETURNS date LANGUAGE sql STABLE AS $$
    SELECT (CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo')::date
$$;

CREATE OR REPLACE FUNCTION pg_temp.local_ts(p_date date, p_time time) RETURNS timestamptz LANGUAGE sql STABLE AS $$
    SELECT (p_date + p_time) AT TIME ZONE 'America/Sao_Paulo'
$$;

CREATE OR REPLACE FUNCTION pg_temp.mtype(p_name text) RETURNS bigint LANGUAGE sql STABLE AS $$
    SELECT id FROM maintenance_type WHERE name = p_name
$$;

CREATE OR REPLACE FUNCTION pg_temp.ean13(p12 text) RETURNS text LANGUAGE sql IMMUTABLE AS $$
    SELECT p12 || ((10 - (
        (substr(p12,1,1)::int + substr(p12,3,1)::int + substr(p12,5,1)::int + substr(p12,7,1)::int + substr(p12,9,1)::int + substr(p12,11,1)::int)
        + 3 * (substr(p12,2,1)::int + substr(p12,4,1)::int + substr(p12,6,1)::int + substr(p12,8,1)::int + substr(p12,10,1)::int + substr(p12,12,1)::int)
    ) % 10) % 10)::text
$$;

CREATE OR REPLACE FUNCTION pg_temp.emp(p_email text) RETURNS uuid LANGUAGE sql STABLE AS $$
    SELECT id FROM employee WHERE email = p_email
$$;

CREATE OR REPLACE FUNCTION pg_temp.str(p_unit_source integer, p_inverter text, p_code text) RETURNS uuid LANGUAGE sql STABLE AS $$
    SELECT s.id FROM string s JOIN inverter i ON i.id = s.inverter_id JOIN company_unit cu ON cu.id = i.company_unit_id
     WHERE cu.source_id = p_unit_source AND i.code = p_inverter AND s.code = p_code
$$;

INSERT INTO roles (name, description) VALUES
    ('GERENTE', 'Gestão da operação da filial; cadastra analistas, operadores e técnicos'),
    ('ANALISTA', 'Análise de desempenho, alertas e indicadores'),
    ('OPERADOR', 'Cadastro de inversores, strings e placas; abertura e cancelamento de OS; sugestões de realocação'),
    ('TECNICO', 'Ativação de placas pelo bipe, relatos de campo, execução e conclusão de OS');

INSERT INTO panel_model (manufacturer, model, pmax_w) VALUES ('Sunova', 'SS-550-72MDH', 550.00);

INSERT INTO inverter_model (brand, model, rated_power_kw, mppt_count, strings_per_mppt, string_current_monitoring)
VALUES ('Sungrow', 'SG250HX', 250.00, 12, 2, true);

INSERT INTO part (sku, name, manufacturer) VALUES
    ('MC4-STB-PAR', 'Conector MC4 (par macho/fêmea)', 'Stäubli'),
    ('CAB-PRY-6MM', 'Cabo solar 6 mm² (metro)', 'Prysmian'),
    ('FUS-WDM-15A', 'Fusível gPV 15 A 1000 Vcc', 'Weidmüller'),
    ('DPS-CLP-1000', 'DPS CC 1000 V classe II', 'Clamper'),
    ('GRP-ROM-INT', 'Grampo intermediário de fixação', 'Romagnole'),
    ('KIT-LMP-MOD', 'Kit de limpeza de módulos (escova e rodo)', 'Genérico');

INSERT INTO maintenance_type (name, description, default_interval_days) VALUES
    ('Preventiva', 'Inspeção e limpeza programadas', 90),
    ('Corretiva', 'Correção de falha detectada pelo inversor ou em campo', NULL),
    ('Preditiva', 'Intervenção a partir da queda de saúde medida', NULL),
    ('Inspeção', 'Verificação em campo com termografia e bipe de conferência', 180);

INSERT INTO staging.rpa_load_batch (source_system, source_file) VALUES ('CRUD_1ANO', 'rpa_crud_1ano_carga_inicial.json');

-- CPFs sintéticos exclusivos da massa demonstrativa; não representam as pessoas nomeadas.
INSERT INTO staging.legacy_user (load_batch_id, source_id, user_type, full_name, email, cpf) VALUES
    (1, 1, 'ADMINISTRADOR', 'Enzo D''angio Mota', 'enzo.mota@institutojef.org.br', '90000000175'),
    (1, 2, 'ADMINISTRADOR', 'Giovanna Quirino', 'giovanna.quirino@institutojef.org.br', '90000000256'),
    (1, 3, 'ADMINISTRADOR', 'Guilherme Guedes Montoni', 'guilherme.montoni@institutojef.org.br', '90000000337'),
    (1, 4, 'ADMINISTRADOR', 'Matheus Lima Botana Gama', 'matheus.gama@institutojef.org.br', '90000000418'),
    (1, 5, 'ADMINISTRADOR', 'Pedro Henrique de Sena Medeiros', 'pedro.medeiros@institutojef.org.br', '90000000507'),
    (1, 6, 'ADMINISTRADOR', 'Yasmin Benevenuto Holando', 'yasmin.holando@institutojef.org.br', '90000000680');

INSERT INTO staging.legacy_company (load_batch_id, source_id, name, cnpj, contact_email, description, registered_by_source_id) VALUES
    (1, 11, 'Âmbar Energia', '21845301000196', 'contato@ambarenergia.demo', 'Empresa de energia do grupo J&F; tenant de demonstração', 1),
    (1, 12, 'Cooperativa Agroindustrial Vale do Cerrado', '30219877000139', 'contato@valedocerrado.demo', 'Tenant fictício de apoio: destino de realocação externa', 2);

INSERT INTO staging.legacy_company_unit
    (load_batch_id, source_id, company_source_id, segment_source_id, segment_name, name, cnpj, email, phone,
     street_name, number, additional_info, neighborhood, city, state, zip_code, registered_by_source_id) VALUES
    (1, 101, 11, 1, 'Energia', 'UFV Âmbar Saltinho', '21845301000277', 'ufv.saltinho@ambarenergia.demo', '1934560000',
     'Rodovia SP-127', 'km 12', NULL, 'Zona Rural', 'Saltinho', 'SP', '13440000', 1),
    (1, 102, 11, 1, 'Energia', 'Âmbar Micro Usina Rooftop 01', '21845301000358', 'rooftop01@ambarenergia.demo', '1130450000',
     'Rua Guaicurus', '1200', 'Cobertura', 'Água Branca', 'São Paulo', 'SP', '05033002', 1),
    (1, 201, 12, 2, 'Agronegócio', 'Vale do Cerrado - Rio Verde', '30219877000210', 'rioverde@valedocerrado.demo', '6436210000',
     'Rodovia GO-174', 's/n', 'Armazém 3', 'Setor Industrial', 'Rio Verde', 'GO', '75909000', 2);

INSERT INTO staging.legacy_user (load_batch_id, source_id, user_type, full_name, email, cpf, password_hash, company_unit_source_id, registered_by_source_id) VALUES
    (1, 51, 'GERENTE', 'Renata Pinto Moraes', 'renata.moraes@ambarenergia.demo', '41382096542',
     '$2b$10$9w.i.5LbqScZT06ym/WPFOezKVWSa506sHzZNzsD1g5mHkAH6iTpO', 101, 1),
    (1, 52, 'GERENTE', 'Diego Alves Martins', 'diego.martins@ambarenergia.demo', '52931847093',
     '$2b$10$9w.i.5LbqScZT06ym/WPFOezKVWSa506sHzZNzsD1g5mHkAH6iTpO', 102, 1),
    (1, 53, 'GERENTE', 'Tatiane Rocha Dias', 'tatiane.dias@valedocerrado.demo', '63847291058',
     '$2b$10$9w.i.5LbqScZT06ym/WPFOezKVWSa506sHzZNzsD1g5mHkAH6iTpO', 201, 2),
    (1, 54, 'GERENTE', 'Cadastro com filial inexistente', 'teste.falha@valedocerrado.demo', '74102938465',
     '$2b$10$9w.i.5LbqScZT06ym/WPFOezKVWSa506sHzZNzsD1g5mHkAH6iTpO', 999, 2);

CALL staging.pr_sync_legacy(1);

INSERT INTO employee (full_name, email, password_hash, role_id, company_unit_id, created_by)
SELECT v.full_name, v.email, '$2b$10$9w.i.5LbqScZT06ym/WPFOezKVWSa506sHzZNzsD1g5mHkAH6iTpO',
       (SELECT id FROM roles WHERE name = v.role), cu.id, g.id
  FROM (VALUES
        ('Juliana Costa Ribeiro', 'juliana.ribeiro@ambarenergia.demo', 'ANALISTA', 101),
        ('Gabriel Souza Rocha', 'gabriel.rocha@ambarenergia.demo', 'OPERADOR', 101),
        ('Aline Ferreira Lopes', 'aline.lopes@ambarenergia.demo', 'OPERADOR', 101),
        ('Vanessa Lima Mendes', 'vanessa.mendes@ambarenergia.demo', 'TECNICO', 101),
        ('Rodrigo Gomes Teixeira', 'rodrigo.teixeira@ambarenergia.demo', 'TECNICO', 101),
        ('Caio Barbosa Nunes', 'caio.nunes@ambarenergia.demo', 'TECNICO', 101),
        ('Fernanda Dias Cardoso', 'fernanda.cardoso@ambarenergia.demo', 'OPERADOR', 102),
        ('Thiago Moreira Campos', 'thiago.campos@ambarenergia.demo', 'TECNICO', 102),
        ('Letícia Araújo Freitas', 'leticia.freitas@valedocerrado.demo', 'OPERADOR', 201)
       ) AS v(full_name, email, role, unit_source)
  JOIN company_unit cu ON cu.source_id = v.unit_source
  JOIN employee g ON g.company_unit_id = cu.id AND g.role_id = (SELECT id FROM roles WHERE name = 'GERENTE');

INSERT INTO stock (company_unit_id, part_id, available_qtt, minimum_qtt, unit_cost)
SELECT cu.id, p.id,
       CASE WHEN cu.source_id = 101 THEN v.qtd_usina ELSE v.qtd_rooftop END, v.minimo, v.custo
  FROM company_unit cu
  CROSS JOIN (VALUES
        ('MC4-STB-PAR', 60, 12, 20, 18.90),
        ('CAB-PRY-6MM', 400, 80, 100, 9.80),
        ('FUS-WDM-15A', 30, 6, 12, 32.50),
        ('DPS-CLP-1000', 6, 1, 2, 189.00),
        ('GRP-ROM-INT', 120, 20, 40, 7.40),
        ('KIT-LMP-MOD', 4, 1, 1, 145.00)
       ) AS v(sku, qtd_usina, qtd_rooftop, minimo, custo)
  JOIN part p ON p.sku = v.sku
 WHERE cu.source_id IN (101, 102);

DO $$
DECLARE
    v_inverter uuid;
    v_serial   integer := 0;
    v_payload  jsonb;
    v_strings  jsonb;
    v_inv      record;
BEGIN
    FOR v_inv IN
        SELECT * FROM (VALUES
            (101, 'INV-01', 'A2207150101', DATE '2022-07-14', 24, 'gabriel.rocha@ambarenergia.demo', DATE '2022-05-10', 780.00, 'NF-2022-'),
            (101, 'INV-02', 'A2207150102', DATE '2022-07-14', 24, 'aline.lopes@ambarenergia.demo', DATE '2022-05-24', 780.00, 'NF-2022-'),
            (102, 'INV-01', 'A2403200301', DATE '2024-03-20', 6, 'fernanda.cardoso@ambarenergia.demo', DATE '2024-02-15', 690.00, 'NF-2024-')
        ) AS t(unit_source, code, serial, installed, n_strings, operator_email, acq, cost, nf_prefix)
    LOOP
        SELECT jsonb_agg(jsonb_build_object(
                   'mppt_number', (k - 1) / 2 + 1,
                   'entry_number', (k - 1) % 2 + 1,
                   'panel_model_id', (SELECT id FROM panel_model WHERE model = 'SS-550-72MDH'),
                   'invoice_number', v_inv.nf_prefix || lpad((CASE WHEN v_inv.code = 'INV-02' THEN 24 ELSE 0 END + k)::text, 4, '0'),
                   'acquisition_dt', v_inv.acq + ((k - 1) / 12) * 7,
                   'unit_cost', v_inv.cost,
                   'panels', (SELECT jsonb_agg(jsonb_build_object(
                        'serial_number', CASE WHEN v_inv.unit_source = 101 THEN 'SNV22' ELSE 'SNV24' END
                            || lpad((v_serial + (k - 1) * 25 + n)::text, 6, '0'),
                        'barcode', pg_temp.ean13('789' || lpad((v_inv.unit_source * 100000 + v_serial + (k - 1) * 25 + n)::text, 9, '0'))
                        ) ORDER BY n)
                      FROM generate_series(1, CASE WHEN v_inv.unit_source = 102 THEN 20 WHEN k <= 12 THEN 25 ELSE 24 END) n)
               ) ORDER BY k)
          INTO v_strings
          FROM generate_series(1, v_inv.n_strings) k;

        v_payload := jsonb_build_object(
            'inverter_model_id', (SELECT id FROM inverter_model WHERE model = 'SG250HX'),
            'code', v_inv.code, 'serial_number', v_inv.serial, 'installed_at', v_inv.installed, 'strings', v_strings);

        v_inverter := NULL;
        CALL pr_register_inverter(pg_temp.emp(v_inv.operator_email), v_payload, v_inverter);
        v_serial := v_serial + v_inv.n_strings * 25;
    END LOOP;
END;
$$;

UPDATE inverter i SET created_at = (i.installed_at - 20)::timestamptz, updated_at = (i.installed_at - 20)::timestamptz;
UPDATE string s SET created_at = (s.acquisition_dt + 3)::timestamptz, updated_at = (s.acquisition_dt + 3)::timestamptz;
UPDATE panel p SET created_at = (s.acquisition_dt + 3)::timestamptz, updated_at = (s.acquisition_dt + 3)::timestamptz
  FROM string s WHERE s.id = p.string_id;
UPDATE panel_status_history h SET changed_at = p.created_at, changed_by = 'operador@cadastro', reason = 'Cadastro do inversor, strings e placas'
  FROM panel p WHERE p.id = h.panel_id;

DO $$
DECLARE
    v_panel record;
BEGIN
    FOR v_panel IN
        SELECT p.barcode, cu.source_id, i.installed_at, s.code, i.code AS inverter_code,
               row_number() OVER (PARTITION BY cu.id ORDER BY i.code, s.code, p.serial_number) AS rn
          FROM panel p JOIN string s ON s.id = p.string_id JOIN inverter i ON i.id = s.inverter_id
          JOIN company_unit cu ON cu.id = i.company_unit_id
         WHERE NOT (cu.source_id = 102 AND s.code = 'STR-006')
         ORDER BY cu.source_id, i.code, s.code, p.serial_number
    LOOP
        CALL pr_activate_panel(v_panel.barcode,
            pg_temp.emp(CASE WHEN v_panel.source_id = 102 THEN 'thiago.campos@ambarenergia.demo'
                             ELSE (ARRAY['vanessa.mendes@ambarenergia.demo', 'rodrigo.teixeira@ambarenergia.demo',
                                         'caio.nunes@ambarenergia.demo'])[1 + (v_panel.rn % 3)] END),
            v_panel.installed_at + (v_panel.rn / 300)::integer);
    END LOOP;
END;
$$;

UPDATE panel_status_history h SET changed_by = 'tecnico@bipe', reason = 'Ativação pelo bipe de instalação'
 WHERE h.new_status = 'OPERACIONAL';

DO $$
DECLARE
    v_warning bigint;
    v_os      bigint;
    v_child_w bigint;
    v_child   bigint;
    v_str     uuid := pg_temp.str(101, 'INV-02', 'STR-020');
    v_panel   varchar;
    v_d0      date := pg_temp.today_sp();
BEGIN
    INSERT INTO warning (string_id, type, severity, status, message, generation_dt)
    VALUES (v_str, 'FALHA_INVERSOR', 'CRITICA', 'ATIVO', 'Inversor reportou o código de falha F014 (corrente de string nula)',
            pg_temp.local_ts(v_d0 - 40, '10:30'))
    RETURNING id INTO v_warning;

    CALL pr_open_maintenance(v_warning, pg_temp.emp('aline.lopes@ambarenergia.demo'), pg_temp.emp('rodrigo.teixeira@ambarenergia.demo'),
                             pg_temp.mtype('Corretiva'), NULL, 420.00, NULL, v_os);
    CALL pr_start_maintenance(v_os, pg_temp.emp('rodrigo.teixeira@ambarenergia.demo'));
    INSERT INTO maintenance_part (maintenance_id, part_id, quantity)
    SELECT v_os, id, q FROM (VALUES ('FUS-WDM-15A', 2), ('MC4-STB-PAR', 4)) AS v(sku, q) JOIN part ON part.sku = v.sku;
    CALL pr_complete_maintenance(v_os, pg_temp.emp('rodrigo.teixeira@ambarenergia.demo'),
        'Fusível da string queimado e dois conectores MC4 oxidados. Fusíveis e conectores substituídos; corrente da string normalizada.', 260.00);

    UPDATE warning SET generation_dt = pg_temp.local_ts(v_d0 - 40, '10:30'), resolved_at = pg_temp.local_ts(v_d0 - 37, '16:00') WHERE id = v_warning;
    UPDATE maintenance_register SET opening_dt = pg_temp.local_ts(v_d0 - 40, '11:00'), due_date = pg_temp.local_ts(v_d0 - 38, '18:00'),
           concluded_at = pg_temp.local_ts(v_d0 - 37, '16:00'), created_at = pg_temp.local_ts(v_d0 - 40, '11:00')
     WHERE id = v_os;
    UPDATE maintenance_part SET consumed_at = pg_temp.local_ts(v_d0 - 37, '14:00') WHERE maintenance_id = v_os;

    SELECT barcode INTO v_panel FROM panel WHERE string_id = v_str ORDER BY serial_number OFFSET 6 LIMIT 1;
    CALL pr_report_panel_issue(v_panel, pg_temp.emp('rodrigo.teixeira@ambarenergia.demo'), 'PONTO_QUENTE', 'ALTA',
        'Termografia na conclusão da OS mostrou ponto quente de 28 °C acima das vizinhas na célula inferior esquerda', v_child_w);
    CALL pr_open_maintenance(v_child_w, pg_temp.emp('aline.lopes@ambarenergia.demo'), pg_temp.emp('caio.nunes@ambarenergia.demo'),
                             pg_temp.mtype('Inspeção'), NULL, 180.00, v_os, v_child);
    CALL pr_complete_maintenance(v_child, pg_temp.emp('caio.nunes@ambarenergia.demo'),
        'Célula com microfissura confirmada por eletroluminescência. Placa sem reparo viável; desconectada e registrada para garantia.', 150.00);
    CALL pr_deactivate_panel(v_panel, pg_temp.emp('caio.nunes@ambarenergia.demo'), 'Microfissura com ponto quente; acionamento de garantia');

    UPDATE warning SET generation_dt = pg_temp.local_ts(v_d0 - 37, '16:10'), resolved_at = pg_temp.local_ts(v_d0 - 34, '15:00') WHERE id = v_child_w;
    UPDATE maintenance_register SET opening_dt = pg_temp.local_ts(v_d0 - 37, '17:00'), due_date = pg_temp.local_ts(v_d0 - 33, '18:00'),
           concluded_at = pg_temp.local_ts(v_d0 - 34, '15:00'), created_at = pg_temp.local_ts(v_d0 - 37, '17:00')
     WHERE id = v_child;
    UPDATE panel SET deactivated_at = pg_temp.local_ts(v_d0 - 34, '15:30'), updated_at = pg_temp.local_ts(v_d0 - 34, '15:30')
     WHERE barcode = v_panel;
    UPDATE panel_status_history h SET changed_at = pg_temp.local_ts(v_d0 - 34, '15:30')
      FROM panel p WHERE p.id = h.panel_id AND p.barcode = v_panel AND h.new_status = 'INATIVO';
    UPDATE panel_status_history h
       SET changed_at = CASE WHEN h.new_status = 'MANUTENCAO' THEN pg_temp.local_ts(v_d0 - 40, '11:00') ELSE pg_temp.local_ts(v_d0 - 37, '16:00') END,
           changed_by = 'fluxo@os', reason = 'OS corretiva de falha na string'
      FROM panel p WHERE p.id = h.panel_id AND p.string_id = v_str AND h.changed_at >= CURRENT_TIMESTAMP - interval '1 hour'
       AND h.new_status IN ('MANUTENCAO', 'OPERACIONAL');
END;
$$;

INSERT INTO string_performance_measurement (string_id, measured_at, power_w, voltage_v, current_a, generated_energy_kwh, data_source)
SELECT x.string_id, x.measured_at, round(x.p::numeric, 2), round(x.v::numeric, 2), round((x.p / NULLIF(x.v, 0))::numeric, 2), round((x.p * 0.25 / 1000.0)::numeric, 3), 'SIMULATOR'
  FROM (
    SELECT s.id AS string_id,
           pg_temp.local_ts(pg_temp.today_sp() - d, time '06:00' + make_interval(mins => k * 15)) AS measured_at,
           c.nominal_power_wp * 0.86
             * sin(pi() * (k * 15 + 7.5) / 720.0)
             * (0.55 + 0.45 * pg_temp.rnd(cu.source_id || '-' || d))
             * CASE
                   WHEN cu.source_id = 101 AND i.code = 'INV-01' AND s.code = 'STR-007' THEN 0.55
                   WHEN cu.source_id = 102 AND s.code = 'STR-003' THEN 0.64
                   WHEN cu.source_id = 101 AND i.code = 'INV-02' AND s.code = 'STR-011' AND d <= 4 THEN 0.80
                   ELSE 1 END
             * (0.985 + 0.03 * pg_temp.rnd(i.code || s.code || cu.source_id || '-' || d || '-' || k)) AS p,
           c.installed_panels * 41.5 * (0.93 + 0.07 * sin(pi() * (k * 15 + 7.5) / 720.0)) AS v
      FROM string s
      JOIN inverter i ON i.id = s.inverter_id
      JOIN company_unit cu ON cu.id = i.company_unit_id
      JOIN vw_string_capacity c ON c.string_id = s.id
     CROSS JOIN generate_series(1, 14) d
     CROSS JOIN generate_series(0, 47) k
     WHERE s.status = 'ATIVA'
  ) x;

CALL pr_ingest_string_measurement('A2207150101', 8::smallint, 1::smallint, pg_temp.local_ts(pg_temp.today_sp() - 1, '11:15'),
                                  0, 0, 0, 0, 'F021', 'SIMULATOR');

DO $$
DECLARE
    d integer;
BEGIN
    FOR d IN REVERSE 7..1 LOOP
        CALL pr_recalculate_string_health(NULL, 7, 70, pg_temp.local_ts(pg_temp.today_sp() - d, '18:00'));
    END LOOP;
    CALL pr_recalculate_string_health(NULL, 7, 70, CURRENT_TIMESTAMP);
END;
$$;

DO $$
DECLARE
    v_w   bigint;
    v_os  bigint;
    v_d0  date := pg_temp.today_sp();
    v_pnl varchar;
BEGIN
    SELECT w.id INTO v_w FROM warning w WHERE w.string_id = pg_temp.str(101, 'INV-01', 'STR-007') AND w.type = 'EFICIENCIA_BAIXA' AND w.status = 'ATIVO';
    CALL pr_open_maintenance(v_w, pg_temp.emp('gabriel.rocha@ambarenergia.demo'), pg_temp.emp('vanessa.mendes@ambarenergia.demo'),
                             pg_temp.mtype('Preditiva'), CURRENT_TIMESTAMP + interval '3 days', 1200.00, NULL, v_os);
    CALL pr_start_maintenance(v_os, pg_temp.emp('vanessa.mendes@ambarenergia.demo'));

    v_os := NULL;
    SELECT w.id INTO v_w FROM warning w WHERE w.string_id = pg_temp.str(101, 'INV-01', 'STR-015') AND w.type = 'FALHA_INVERSOR' AND w.status = 'ATIVO';
    CALL pr_open_maintenance(v_w, pg_temp.emp('gabriel.rocha@ambarenergia.demo'), pg_temp.emp('rodrigo.teixeira@ambarenergia.demo'),
                             pg_temp.mtype('Corretiva'), CURRENT_TIMESTAMP + interval '1 day', 300.00, NULL, v_os);
    CALL pr_cancel_maintenance(v_os, pg_temp.emp('gabriel.rocha@ambarenergia.demo'),
                               'Falha F021 não se repetiu após religamento remoto do inversor; leituras normais nas horas seguintes');

    v_os := NULL;
    SELECT w.id INTO v_w FROM warning w WHERE w.string_id = pg_temp.str(102, 'INV-01', 'STR-003') AND w.type = 'EFICIENCIA_BAIXA' AND w.status = 'ATIVO';
    CALL pr_open_maintenance(v_w, pg_temp.emp('fernanda.cardoso@ambarenergia.demo'), pg_temp.emp('thiago.campos@ambarenergia.demo'),
                             pg_temp.mtype('Inspeção'), CURRENT_TIMESTAMP + interval '4 days', 250.00, NULL, v_os);
    UPDATE maintenance_register SET opening_dt = pg_temp.local_ts(v_d0 - 6, '09:00'), due_date = pg_temp.local_ts(v_d0 - 2, '18:00'),
           created_at = pg_temp.local_ts(v_d0 - 6, '09:00')
     WHERE id = v_os;

    v_os := NULL;
    SELECT p.barcode INTO v_pnl FROM panel p WHERE p.string_id = pg_temp.str(101, 'INV-01', 'STR-018') ORDER BY p.serial_number OFFSET 11 LIMIT 1;
    CALL pr_report_panel_issue(v_pnl, pg_temp.emp('caio.nunes@ambarenergia.demo'), 'DANO_FISICO', 'CRITICA',
                               'Vidro trincado no canto inferior direito após queda de galho; risco de infiltração', v_w);
    CALL pr_open_maintenance(v_w, pg_temp.emp('aline.lopes@ambarenergia.demo'), pg_temp.emp('caio.nunes@ambarenergia.demo'),
                             pg_temp.mtype('Corretiva'), CURRENT_TIMESTAMP + interval '2 days', 950.00, NULL, v_os);
    CALL pr_start_maintenance(v_os, pg_temp.emp('caio.nunes@ambarenergia.demo'));
    INSERT INTO maintenance_part (maintenance_id, part_id, quantity) SELECT v_os, id, 2 FROM part WHERE sku = 'MC4-STB-PAR';
END;
$$;

INSERT INTO suggested_internal_relocation (string_id, quantity, suggested_unit_id, requested_by, reviewed_by, justification, status, suggested_at, reviewed_at)
VALUES
    (pg_temp.str(102, 'INV-01', 'STR-003'), 20, (SELECT id FROM company_unit WHERE source_id = 101),
     pg_temp.emp('fernanda.cardoso@ambarenergia.demo'), NULL,
     'String com saúde abaixo de 70% por sombreamento da nova casa de máquinas após as 14h; a UFV Saltinho tem estrutura de solo livre sem sombra.',
     'PENDENTE', CURRENT_TIMESTAMP - interval '3 days', NULL),
    (pg_temp.str(101, 'INV-02', 'STR-024'), 4, (SELECT id FROM company_unit WHERE source_id = 102),
     pg_temp.emp('aline.lopes@ambarenergia.demo'), pg_temp.emp('renata.moraes@ambarenergia.demo'),
     'Reposição de placas avariadas no rooftop com placas do mesmo modelo da reserva técnica da usina.',
     'APROVADA', CURRENT_TIMESTAMP - interval '20 days', CURRENT_TIMESTAMP - interval '18 days'),
    (pg_temp.str(101, 'INV-02', 'STR-011'), 24, (SELECT id FROM company_unit WHERE source_id = 102),
     pg_temp.emp('aline.lopes@ambarenergia.demo'), pg_temp.emp('renata.moraes@ambarenergia.demo'),
     'Queda recente de geração da string; mover para o rooftop.',
     'REJEITADA', CURRENT_TIMESTAMP - interval '2 days', CURRENT_TIMESTAMP - interval '1 day');

INSERT INTO suggested_external_relocation (panel_id, destination_company_id, segment_id, requested_by, reviewed_by, justification, status, suggested_at, reviewed_at)
SELECT p.id, (SELECT id FROM company WHERE source_id = 12), (SELECT id FROM segment WHERE source_id = 2),
       pg_temp.emp('gabriel.rocha@ambarenergia.demo'),
       CASE WHEN rn > 3 THEN pg_temp.emp('renata.moraes@ambarenergia.demo') END,
       'Placa da string com saúde de ' || round(h.health_score) || '%, abaixo do limite operacional da usina; adequada para bombeamento em irrigação, que tolera menor rendimento.',
       CASE WHEN rn <= 3 THEN 'PENDENTE' WHEN rn <= 5 THEN 'APROVADA' ELSE 'REJEITADA' END,
       CURRENT_TIMESTAMP - make_interval(days => (10 - rn)::int),
       CASE WHEN rn > 3 THEN CURRENT_TIMESTAMP - make_interval(days => (6 - rn)::int) END
  FROM (SELECT p.*, row_number() OVER (ORDER BY p.serial_number) AS rn FROM panel p
         WHERE p.string_id = pg_temp.str(101, 'INV-01', 'STR-007')) p
  JOIN vw_string_current_health h ON h.string_id = p.string_id
 WHERE p.rn <= 6;

INSERT INTO access_log (employee_id, attempted_email, session_id, login_timestamp, logout_timestamp, ip_address, access_status)
SELECT CASE WHEN x.kind = 'F' AND x.unknown THEN NULL ELSE x.employee_id END,
       CASE WHEN x.kind = 'F' AND x.unknown THEN split_part(x.email, '@', 1) || '@gmail.com' END,
       md5(x.email || x.d || x.kind)::uuid,
       x.login_at,
       CASE WHEN x.kind = 'S' THEN x.login_at + make_interval(mins => 15 + (pg_temp.rnd(x.email || x.d || 'dur') * 100)::int) END,
       ('10.' || x.net || '.' || (1 + abs(hashtext(x.email)) % 3) || '.' || (20 + abs(hashtext(x.email)) % 200))::inet,
       CASE WHEN x.kind = 'S' THEN 'SUCESSO' ELSE 'FALHA' END
  FROM (
    SELECT e.id AS employee_id, e.email, d, k.kind, cu.source_id % 100 AS net,
           pg_temp.rnd(e.email || d || 'u') < 0.5 AS unknown,
           pg_temp.local_ts(pg_temp.today_sp() - d, time '07:30' + make_interval(mins => (pg_temp.rnd(e.email || d || 'h') * 600)::int))
             - CASE WHEN k.kind = 'F' THEN interval '2 minutes' ELSE interval '0' END AS login_at
      FROM employee e
      JOIN roles r ON r.id = e.role_id
      JOIN company_unit cu ON cu.id = e.company_unit_id
     CROSS JOIN generate_series(1, 21) d
     CROSS JOIN (VALUES ('S'), ('F')) k(kind)
     WHERE e.is_active
       AND extract(isodow FROM pg_temp.today_sp() - d) < 6
       AND pg_temp.rnd(e.email || d) < CASE r.name WHEN 'GERENTE' THEN 0.85 WHEN 'ANALISTA' THEN 0.90 WHEN 'OPERADOR' THEN 0.80 ELSE 0.60 END
       AND (k.kind = 'S' OR pg_temp.rnd(e.email || d || 'f') < 0.05)
  ) x;

CALL governance.pr_reserve_demo_source_ids();
INSERT INTO governance.operational_runbook
    (procedure_name, objective, execution_steps, validation_steps, recommended_frequency, responsible_role)
VALUES
    ('Backup lógico completo', 'Gerar cópia lógica portátil do banco Apollo.',
     'Executar pg_dump em formato customizado, com SSL, credenciais em segredo e destino criptografado. Registrar horário, tamanho e hash do arquivo.',
     'Executar pg_restore --list, conferir o código de saída e realizar restauração mensal em ambiente isolado.',
     'Diário, com retenção definida pela organização', 'Administrador de Banco de Dados'),
    ('Recuperação de falha', 'Restaurar o serviço após perda lógica ou indisponibilidade.',
     'Criar banco ou branch isolada, restaurar o último backup válido e redirecionar a aplicação somente após homologação.',
     'Validar contagens, PKs/FKs, funções, views, auditorias e consultas críticas; registrar RPO e RTO observados.',
     'Teste trimestral e sempre após mudança estrutural', 'Administrador de Banco de Dados'),
    ('Recuperação no Neon', 'Usar branch e point-in-time recovery do Neon.',
     'Criar uma branch no ponto anterior ao incidente, validar os dados e promover a recuperação conforme o plano aprovado.',
     'Comparar indicadores antes/depois, validar autenticação da API e preservar a branch anterior para investigação.',
     'Conforme incidente', 'Responsável por Infraestrutura'),
    ('Sincronização RPA com o 1º ano', 'Trazer administradores, empresas, filiais e gerentes do CRUD do 1º ano.',
     'O RPA grava uma linha em staging.rpa_load_batch, preenche staging.legacy_user, legacy_company e legacy_company_unit e executa CALL staging.pr_sync_legacy(<id da carga>).',
     'Conferir o status da carga (COMPLETED ou COMPLETED_WITH_ERRORS) e tratar cada linha de staging.rpa_load_error.',
     'A cada hora ou sob demanda', 'Responsável pelo RPA'),
    ('Job de saúde das strings', 'Recalcular a saúde de todas as strings ativas e abrir ou resolver alertas de eficiência baixa.',
     'CALL pr_recalculate_string_health(); agendar via pg_cron, job do Databricks ou scheduler do Spring.',
     'Conferir string_health_history crescendo e alertas coerentes com as leituras.',
     'A cada hora ou após cada lote de leituras', 'Backend')
ON CONFLICT (procedure_name) DO UPDATE
SET objective = EXCLUDED.objective, execution_steps = EXCLUDED.execution_steps,
    validation_steps = EXCLUDED.validation_steps, recommended_frequency = EXCLUDED.recommended_frequency,
    responsible_role = EXCLUDED.responsible_role;
CREATE OR REPLACE FUNCTION pg_temp.rnd(p text) RETURNS numeric LANGUAGE sql IMMUTABLE AS $$
    SELECT ((('x' || substr(md5(p), 1, 8))::bit(32)::bigint % 1000000)::numeric / 1000000)
$$;

CREATE OR REPLACE FUNCTION pg_temp.today_sp() RETURNS date LANGUAGE sql STABLE AS $$
    SELECT (CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo')::date
$$;

CREATE OR REPLACE FUNCTION pg_temp.local_ts(p_date date, p_time time) RETURNS timestamptz LANGUAGE sql STABLE AS $$
    SELECT (p_date + p_time) AT TIME ZONE 'America/Sao_Paulo'
$$;

CREATE OR REPLACE FUNCTION pg_temp.mtype(p_name text) RETURNS bigint LANGUAGE sql STABLE AS $$
    SELECT id FROM maintenance_type WHERE name = p_name
$$;

CREATE OR REPLACE FUNCTION pg_temp.ean13(p12 text) RETURNS text LANGUAGE sql IMMUTABLE AS $$
    SELECT p12 || ((10 - (
        (substr(p12,1,1)::int + substr(p12,3,1)::int + substr(p12,5,1)::int + substr(p12,7,1)::int + substr(p12,9,1)::int + substr(p12,11,1)::int)
        + 3 * (substr(p12,2,1)::int + substr(p12,4,1)::int + substr(p12,6,1)::int + substr(p12,8,1)::int + substr(p12,10,1)::int + substr(p12,12,1)::int)
    ) % 10) % 10)::text
$$;

CREATE OR REPLACE FUNCTION pg_temp.emp(p_email text) RETURNS uuid LANGUAGE sql STABLE AS $$
    SELECT id FROM employee WHERE email = p_email
$$;

CREATE OR REPLACE FUNCTION pg_temp.str(p_unit_source integer, p_inverter text, p_code text) RETURNS uuid LANGUAGE sql STABLE AS $$
    SELECT s.id FROM string s JOIN inverter i ON i.id = s.inverter_id JOIN company_unit cu ON cu.id = i.company_unit_id
     WHERE cu.source_id = p_unit_source AND i.code = p_inverter AND s.code = p_code
$$;

CALL governance.pr_refresh_data_catalog();

ANALYZE;

COMMIT;