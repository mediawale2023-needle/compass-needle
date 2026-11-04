-- diagnose_delhi_geography.sql
--
-- STRICTLY READ-ONLY. Runs inside a READ ONLY transaction that ends in ROLLBACK;
-- any write would error out. Answers one question: why does Tenant 9's
-- synthetic-case dry run find none of the ten New Delhi assembly segments in
-- tenant_overrides.geography_data?
--
-- Output is public (this repository's workflow logs are world-readable), so it is
-- limited to geography and seat names, counts and booleans. It never selects
-- citizen data, phone numbers, message text, tenant/MP names or station payloads
-- (only counts and yes/no matches derived from them).
--
-- Reference (authoritative, not a new dataset): needle-india-geography-master
-- release 0.2.1, ECI PC 4 "New Delhi" = AC 23, 24, 25, 38, 39, 40, 42, 43, 44, 50
-- (2008 Delimitation Order). The VALUES list below only repeats those ten
-- numbers and names so the diagnostic can match them under spelling variants.
--
-- Shape of a geography row (sansadx_backend/db.py):
--   tenant_overrides.override_type = 'geography_data'
--   tenant_overrides.key           = '<mp|mla>:<seat name>/<assembly name>'
--   tenant_overrides.value         = JSON array of polling-station rows (text)
BEGIN TRANSACTION READ ONLY;

\pset pager off
\pset null '-'

\echo
\echo '=== 0. Environment (read-only check)'
SELECT current_setting('transaction_read_only') AS read_only,
       current_setting('server_version_num')::int / 10000 AS pg_major;

\echo
\echo '=== 1. What geography state exists at all? (counts by override type)'
SELECT override_type, COUNT(*) AS rows, COUNT(*) FILTER (WHERE tenant_id IS NULL) AS shared_rows
FROM tenant_overrides
WHERE override_type IN ('geography_data', 'geo_seat_manual_override', 'geo_manual_override', 'geo_override', 'geo_alias')
GROUP BY 1 ORDER BY 1;

\echo
\echo '=== 2. Geography reset markers (the one-time 2026-06 wipe)'
SELECT key AS migration_key, created_at::date AS applied_on
FROM tenant_overrides
WHERE override_type = 'system_migration' AND (key ILIKE '%geograph%' OR key ILIKE '%reset%' OR key ILIKE '%alias%')
ORDER BY created_at;

\echo
\echo '=== 3. Platform-wide geography shape (AGGREGATE ONLY - no seat names are listed)'
SELECT COUNT(DISTINCT split_part(key, '/', 1))                              AS seats_with_geography,
       COUNT(*)                                                             AS assembly_rows,
       COUNT(*) FILTER (WHERE key LIKE 'mp:%')                              AS keyed_mp,
       COUNT(*) FILTER (WHERE key LIKE 'mla:%')                             AS keyed_mla,
       COUNT(*) FILTER (WHERE key NOT LIKE 'mp:%' AND key NOT LIKE 'mla:%') AS keyed_legacy_no_prefix,
       COUNT(*) FILTER (WHERE split_part(key, '/', 2) ~ '\((SC|ST)\)')       AS names_with_reservation_suffix,
       COUNT(*) FILTER (WHERE split_part(key, '/', 2) ~ '\.')                AS names_with_dots,
       COUNT(*) FILTER (WHERE value !~ '^\s*\[')                              AS non_list_payloads
FROM tenant_overrides
WHERE override_type = 'geography_data' AND position('/' IN key) > 0;

\echo
\echo '=== 4. Any Delhi-looking geography row, under ANY seat key (mis-keyed rows would show here)'
SELECT key,
       tenant_id IS NULL AS shared,
       (value ~ '^\s*\[') AS payload_is_list,
       (length(value) - length(replace(value, '"station_number"', ''))) / length('"station_number"') AS station_rows
FROM tenant_overrides
WHERE override_type = 'geography_data'
  AND (key ILIKE '%delhi%'
       OR lower(regexp_replace(split_part(key, '/', 2), '\(.*\)|[^a-zA-Z0-9]', '', 'g'))
          IN ('karolbagh','patelnagar','motinagar','delhicantt','delhicantonment','rajindernagar','newdelhi',
              'kasturbanagar','malviyanagar','rkpuram','greaterkailash'))
ORDER BY key;

\echo
\echo '=== 5. The ten New Delhi segments: found anywhere? (match ignores (SC), dots, spaces, case)'
WITH ref(ac_no, ac_name, norm) AS (VALUES
  (23,'Karol Bagh','karolbagh'),(24,'Patel Nagar','patelnagar'),(25,'Moti Nagar','motinagar'),
  (38,'Delhi Cantt','delhicantt'),(39,'Rajinder Nagar','rajindernagar'),(40,'New Delhi','newdelhi'),
  (42,'Kasturba Nagar','kasturbanagar'),(43,'Malviya Nagar','malviyanagar'),(44,'R.K. Puram','rkpuram'),
  (50,'Greater Kailash','greaterkailash')),
geo AS (
  SELECT key, split_part(key, '/', 1) AS seat_key, split_part(key, '/', 2) AS asm,
         lower(regexp_replace(split_part(key, '/', 2), '\(.*\)|[^a-zA-Z0-9]', '', 'g')) AS asm_norm
  FROM tenant_overrides WHERE override_type = 'geography_data')
SELECT ref.ac_no, ref.ac_name,
       COUNT(geo.key)                                                  AS rows_found_any_seat,
       COUNT(geo.key) FILTER (WHERE lower(geo.seat_key) = 'mp:new delhi') AS under_mp_new_delhi,
       COALESCE(string_agg(DISTINCT geo.key, ' | '), '-')              AS keys_found
FROM ref LEFT JOIN geo ON geo.asm_norm = ref.norm OR (ref.norm = 'delhicantt' AND geo.asm_norm = 'delhicantonment')
GROUP BY ref.ac_no, ref.ac_name ORDER BY ref.ac_no;

\echo
\echo '=== 6. Manifest localities present in any Delhi-looking row? (yes/no only)'
WITH locs(name) AS (VALUES ('Connaught Place'),('Delhi Cantonment'),('Dev Nagar'),('East Patel Nagar'),('Gole Market'),
  ('Greater Kailash-I'),('Greater Kailash-II'),('Hauz Rani'),('Karol Bagh'),('Kasturba Nagar'),('Malviya Nagar'),
  ('Moti Nagar'),('Munirka Village'),('Old Rajinder Nagar'),('Rajinder Nagar'),('Vasant Vihar'),('West Patel Nagar')),
delhi_rows AS (SELECT value FROM tenant_overrides WHERE override_type = 'geography_data' AND key ILIKE '%delhi%')
SELECT locs.name AS locality,
       EXISTS (SELECT 1 FROM delhi_rows WHERE delhi_rows.value ILIKE '%' || locs.name || '%') AS in_a_delhi_row
FROM locs ORDER BY 1;

\echo
\echo '=== 7. Delhi-related tenants (id, seat and yes/no flags only; no names, no phone numbers)'
SELECT id, constituency, seat_type, tenant_type, is_active,
       whatsapp_number IS NOT NULL                 AS has_whatsapp_number,
       onboarding_state->>'geography'              AS onboarding_geography_flag,
       onboarding_state->>'live'                   AS onboarding_live_flag
FROM tenants WHERE constituency ILIKE '%delhi%' ORDER BY id;

\echo
\echo '=== 8. Seat-map manifests mentioning Delhi (if the table exists)'
SELECT to_regclass('public.seat_map_manifests') IS NOT NULL AS has_seat_maps \gset
\if :has_seat_maps
SELECT seat_type, seat_name, state FROM seat_map_manifests
WHERE seat_name ILIKE '%delhi%' OR state ILIKE '%delhi%' ORDER BY seat_type, seat_name;
\else
\echo 'seat_map_manifests does not exist'
\endif

\echo
\echo '=== 9. Gazetteer places for Delhi seats (if the table exists)'
SELECT to_regclass('public.geo_places') IS NOT NULL AS has_gazetteer \gset
\if :has_gazetteer
SELECT seat_type, seat_name, COUNT(DISTINCT assembly) AS assemblies, COUNT(*) AS places
FROM geo_places WHERE seat_name ILIKE '%delhi%' OR parliamentary_constituency ILIKE '%delhi%'
GROUP BY 1, 2 ORDER BY 1, 2;
\else
\echo 'geo_places does not exist'
\endif

\echo
\echo '=== 10. Collision preview (the dry run stopped before this): Tenant 9 synthetic cases already present?'
SELECT COUNT(*) AS rows_with_syn_t9_refs,
       COUNT(*) FILTER (WHERE tenant_id = 9) AS in_tenant_9
FROM cases WHERE case_ref LIKE 'SYN-T9-DL-%';

ROLLBACK;
