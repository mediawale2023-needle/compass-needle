-- diagnose_case_status_lifecycle.sql
--
-- STRICTLY READ-ONLY lifecycle diagnostic for cases.status vs govt_status.
-- Runs inside a READ ONLY transaction; any write would error out.
-- Output is counts per tenant plus case IDs only: no phone numbers, names,
-- message text, notes, or reference numbers are ever selected.
--
-- Evidence model for an IN PROGRESS case (most specific wins):
--   filed_with_govt       govt_reference_number recorded / govt_status past
--                         pending_staff_submit                     -> supported
--   legacy_escalation     reached via the retired staff escalation workflow
--                         (escalations row or status_change -> 'escalated')
--                                                                  -> supported
--   accept_suggestion_*   the status_change INTO in_progress was written by
--                         the same user <=30s after a category_confirmed row:
--                         the Briefcase "Accept & assign" side effect
--       ..._no_work       and no genuine-work evidence anywhere  -> CONFIRMED INCORRECT
--       ..._with_work     but later genuine work exists           -> potentially incorrect
--   manual_with_work      explicit staff status change + work     -> supported
--   manual_no_work        explicit staff status change, no work   -> potentially incorrect
--   automatic_actor       entered in_progress via a non-human actor -> CONFIRMED INCORRECT
--   no_transition_log     no logged transition into the status    -> insufficient evidence
--
-- "Genuine work" evidence = citizen notification/WhatsApp reply sent by staff,
-- staff notes or citizen response written, complaint added manually, govt
-- filing recorded, govt resolution reviewed. Viewing, filtering, assigning,
-- following, categorising and AI worksheet preparation are NOT work.
--
-- Transitions written by modules/case_lifecycle.py are logged with actor
-- 'system:<evidence>' and are evidence-based by construction;
-- 'system:legacy_status_remap' marks the retired escalated -> in_progress remap.

BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '120s';

-- Transition INTO the current in_progress state (latest one wins).
\echo '== 1. cases by internal status (per tenant) =='
WITH _live_cases AS (
SELECT id, tenant_id, LOWER(COALESCE(status, '')) AS status,
       LOWER(COALESCE(govt_status, 'not_forwarded')) AS govt_status,
       (NULLIF(TRIM(COALESCE(govt_reference_number, '')), '') IS NOT NULL) AS has_ref,
       resolved_at, created_at, govt_status_updated_at
FROM cases
WHERE COALESCE(is_deleted, false) = false
),
_entry AS (
SELECT DISTINCT ON (l.case_id)
       l.case_id, l.tenant_id, COALESCE(l.username, '') AS actor,
       LOWER(COALESCE(l.new_value, '')) AS new_value, l.created_at
FROM case_activity_log l
JOIN _live_cases c ON c.id = l.case_id AND c.tenant_id = l.tenant_id
WHERE l.action = 'status_change'
  AND c.status = 'in_progress'
  AND LOWER(COALESCE(l.new_value, '')) IN ('in_progress', 'escalated')
ORDER BY l.case_id, l.created_at DESC
),
_work AS (
SELECT DISTINCT l.case_id, l.tenant_id
FROM case_activity_log l
WHERE l.action IN ('citizen_notified', 'whatsapp_sent', 'complaint_added_manually',
                   'govt_submitted', 'govt_resolution_reviewed')
   OR (l.action = 'case_updated'
       AND (l.details LIKE '%notes%' OR l.details LIKE '%response%'))
UNION
SELECT DISTINCT g.case_id, g.tenant_id
FROM govt_submission_log g
WHERE g.action = 'staff_submitted'
),
_classified AS (
SELECT c.id, c.tenant_id, c.govt_status, c.has_ref,
       CASE
         WHEN c.has_ref OR c.govt_status NOT IN ('not_forwarded', 'pending_staff_submit')
           THEN 'filed_with_govt'
         WHEN EXISTS (SELECT 1 FROM escalations x WHERE x.case_id = c.id AND x.tenant_id = c.tenant_id)
           OR e.new_value = 'escalated'
           OR e.actor = 'system:legacy_status_remap'
           THEN 'legacy_escalation'
         WHEN e.case_id IS NULL
           THEN 'no_transition_log'
         WHEN e.actor LIKE 'system:govt\_%'
           THEN 'external_evidence'
         WHEN e.actor IN ('', 'ai', 'system', 'buffer_release', 'media_intake', 'thread_reactivate')
           THEN 'automatic_actor'
         WHEN EXISTS (
                SELECT 1 FROM case_activity_log cc
                WHERE cc.case_id = c.id AND cc.tenant_id = c.tenant_id
                  AND cc.action = 'category_confirmed'
                  AND COALESCE(cc.username, '') = e.actor
                  AND cc.created_at BETWEEN e.created_at - INTERVAL '30 seconds' AND e.created_at)
           THEN CASE WHEN w.case_id IS NULL THEN 'accept_suggestion_no_work'
                     ELSE 'accept_suggestion_with_work' END
         WHEN w.case_id IS NULL THEN 'manual_no_work'
         ELSE 'manual_with_work'
       END AS evidence
FROM _live_cases c
LEFT JOIN _entry e ON e.case_id = c.id
LEFT JOIN _work w ON w.case_id = c.id AND w.tenant_id = c.tenant_id
WHERE c.status = 'in_progress'
)
SELECT tenant_id, status, COUNT(*) AS cases
FROM _live_cases GROUP BY 1, 2 ORDER BY 1, 2;

\echo ''
\echo '== 2. cases by government status (per tenant) =='
WITH _live_cases AS (
SELECT id, tenant_id, LOWER(COALESCE(status, '')) AS status,
       LOWER(COALESCE(govt_status, 'not_forwarded')) AS govt_status,
       (NULLIF(TRIM(COALESCE(govt_reference_number, '')), '') IS NOT NULL) AS has_ref,
       resolved_at, created_at, govt_status_updated_at
FROM cases
WHERE COALESCE(is_deleted, false) = false
),
_entry AS (
SELECT DISTINCT ON (l.case_id)
       l.case_id, l.tenant_id, COALESCE(l.username, '') AS actor,
       LOWER(COALESCE(l.new_value, '')) AS new_value, l.created_at
FROM case_activity_log l
JOIN _live_cases c ON c.id = l.case_id AND c.tenant_id = l.tenant_id
WHERE l.action = 'status_change'
  AND c.status = 'in_progress'
  AND LOWER(COALESCE(l.new_value, '')) IN ('in_progress', 'escalated')
ORDER BY l.case_id, l.created_at DESC
),
_work AS (
SELECT DISTINCT l.case_id, l.tenant_id
FROM case_activity_log l
WHERE l.action IN ('citizen_notified', 'whatsapp_sent', 'complaint_added_manually',
                   'govt_submitted', 'govt_resolution_reviewed')
   OR (l.action = 'case_updated'
       AND (l.details LIKE '%notes%' OR l.details LIKE '%response%'))
UNION
SELECT DISTINCT g.case_id, g.tenant_id
FROM govt_submission_log g
WHERE g.action = 'staff_submitted'
),
_classified AS (
SELECT c.id, c.tenant_id, c.govt_status, c.has_ref,
       CASE
         WHEN c.has_ref OR c.govt_status NOT IN ('not_forwarded', 'pending_staff_submit')
           THEN 'filed_with_govt'
         WHEN EXISTS (SELECT 1 FROM escalations x WHERE x.case_id = c.id AND x.tenant_id = c.tenant_id)
           OR e.new_value = 'escalated'
           OR e.actor = 'system:legacy_status_remap'
           THEN 'legacy_escalation'
         WHEN e.case_id IS NULL
           THEN 'no_transition_log'
         WHEN e.actor LIKE 'system:govt\_%'
           THEN 'external_evidence'
         WHEN e.actor IN ('', 'ai', 'system', 'buffer_release', 'media_intake', 'thread_reactivate')
           THEN 'automatic_actor'
         WHEN EXISTS (
                SELECT 1 FROM case_activity_log cc
                WHERE cc.case_id = c.id AND cc.tenant_id = c.tenant_id
                  AND cc.action = 'category_confirmed'
                  AND COALESCE(cc.username, '') = e.actor
                  AND cc.created_at BETWEEN e.created_at - INTERVAL '30 seconds' AND e.created_at)
           THEN CASE WHEN w.case_id IS NULL THEN 'accept_suggestion_no_work'
                     ELSE 'accept_suggestion_with_work' END
         WHEN w.case_id IS NULL THEN 'manual_no_work'
         ELSE 'manual_with_work'
       END AS evidence
FROM _live_cases c
LEFT JOIN _entry e ON e.case_id = c.id
LEFT JOIN _work w ON w.case_id = c.id AND w.tenant_id = c.tenant_id
WHERE c.status = 'in_progress'
)
SELECT tenant_id, govt_status, COUNT(*) AS cases
FROM _live_cases GROUP BY 1, 2 ORDER BY 1, 2;

\echo ''
\echo '== 3. IN PROGRESS cases never filed with government (per tenant) =='
WITH _live_cases AS (
SELECT id, tenant_id, LOWER(COALESCE(status, '')) AS status,
       LOWER(COALESCE(govt_status, 'not_forwarded')) AS govt_status,
       (NULLIF(TRIM(COALESCE(govt_reference_number, '')), '') IS NOT NULL) AS has_ref,
       resolved_at, created_at, govt_status_updated_at
FROM cases
WHERE COALESCE(is_deleted, false) = false
),
_entry AS (
SELECT DISTINCT ON (l.case_id)
       l.case_id, l.tenant_id, COALESCE(l.username, '') AS actor,
       LOWER(COALESCE(l.new_value, '')) AS new_value, l.created_at
FROM case_activity_log l
JOIN _live_cases c ON c.id = l.case_id AND c.tenant_id = l.tenant_id
WHERE l.action = 'status_change'
  AND c.status = 'in_progress'
  AND LOWER(COALESCE(l.new_value, '')) IN ('in_progress', 'escalated')
ORDER BY l.case_id, l.created_at DESC
),
_work AS (
SELECT DISTINCT l.case_id, l.tenant_id
FROM case_activity_log l
WHERE l.action IN ('citizen_notified', 'whatsapp_sent', 'complaint_added_manually',
                   'govt_submitted', 'govt_resolution_reviewed')
   OR (l.action = 'case_updated'
       AND (l.details LIKE '%notes%' OR l.details LIKE '%response%'))
UNION
SELECT DISTINCT g.case_id, g.tenant_id
FROM govt_submission_log g
WHERE g.action = 'staff_submitted'
),
_classified AS (
SELECT c.id, c.tenant_id, c.govt_status, c.has_ref,
       CASE
         WHEN c.has_ref OR c.govt_status NOT IN ('not_forwarded', 'pending_staff_submit')
           THEN 'filed_with_govt'
         WHEN EXISTS (SELECT 1 FROM escalations x WHERE x.case_id = c.id AND x.tenant_id = c.tenant_id)
           OR e.new_value = 'escalated'
           OR e.actor = 'system:legacy_status_remap'
           THEN 'legacy_escalation'
         WHEN e.case_id IS NULL
           THEN 'no_transition_log'
         WHEN e.actor LIKE 'system:govt\_%'
           THEN 'external_evidence'
         WHEN e.actor IN ('', 'ai', 'system', 'buffer_release', 'media_intake', 'thread_reactivate')
           THEN 'automatic_actor'
         WHEN EXISTS (
                SELECT 1 FROM case_activity_log cc
                WHERE cc.case_id = c.id AND cc.tenant_id = c.tenant_id
                  AND cc.action = 'category_confirmed'
                  AND COALESCE(cc.username, '') = e.actor
                  AND cc.created_at BETWEEN e.created_at - INTERVAL '30 seconds' AND e.created_at)
           THEN CASE WHEN w.case_id IS NULL THEN 'accept_suggestion_no_work'
                     ELSE 'accept_suggestion_with_work' END
         WHEN w.case_id IS NULL THEN 'manual_no_work'
         ELSE 'manual_with_work'
       END AS evidence
FROM _live_cases c
LEFT JOIN _entry e ON e.case_id = c.id
LEFT JOIN _work w ON w.case_id = c.id AND w.tenant_id = c.tenant_id
WHERE c.status = 'in_progress'
)
SELECT tenant_id, COUNT(*) AS in_progress_total,
       COUNT(*) FILTER (WHERE NOT has_ref AND govt_status IN ('not_forwarded', 'pending_staff_submit'))
         AS never_filed
FROM _classified GROUP BY 1 ORDER BY 1;

\echo ''
\echo '== 4. IN PROGRESS evidence classification (per tenant) =='
WITH _live_cases AS (
SELECT id, tenant_id, LOWER(COALESCE(status, '')) AS status,
       LOWER(COALESCE(govt_status, 'not_forwarded')) AS govt_status,
       (NULLIF(TRIM(COALESCE(govt_reference_number, '')), '') IS NOT NULL) AS has_ref,
       resolved_at, created_at, govt_status_updated_at
FROM cases
WHERE COALESCE(is_deleted, false) = false
),
_entry AS (
SELECT DISTINCT ON (l.case_id)
       l.case_id, l.tenant_id, COALESCE(l.username, '') AS actor,
       LOWER(COALESCE(l.new_value, '')) AS new_value, l.created_at
FROM case_activity_log l
JOIN _live_cases c ON c.id = l.case_id AND c.tenant_id = l.tenant_id
WHERE l.action = 'status_change'
  AND c.status = 'in_progress'
  AND LOWER(COALESCE(l.new_value, '')) IN ('in_progress', 'escalated')
ORDER BY l.case_id, l.created_at DESC
),
_work AS (
SELECT DISTINCT l.case_id, l.tenant_id
FROM case_activity_log l
WHERE l.action IN ('citizen_notified', 'whatsapp_sent', 'complaint_added_manually',
                   'govt_submitted', 'govt_resolution_reviewed')
   OR (l.action = 'case_updated'
       AND (l.details LIKE '%notes%' OR l.details LIKE '%response%'))
UNION
SELECT DISTINCT g.case_id, g.tenant_id
FROM govt_submission_log g
WHERE g.action = 'staff_submitted'
),
_classified AS (
SELECT c.id, c.tenant_id, c.govt_status, c.has_ref,
       CASE
         WHEN c.has_ref OR c.govt_status NOT IN ('not_forwarded', 'pending_staff_submit')
           THEN 'filed_with_govt'
         WHEN EXISTS (SELECT 1 FROM escalations x WHERE x.case_id = c.id AND x.tenant_id = c.tenant_id)
           OR e.new_value = 'escalated'
           OR e.actor = 'system:legacy_status_remap'
           THEN 'legacy_escalation'
         WHEN e.case_id IS NULL
           THEN 'no_transition_log'
         WHEN e.actor LIKE 'system:govt\_%'
           THEN 'external_evidence'
         WHEN e.actor IN ('', 'ai', 'system', 'buffer_release', 'media_intake', 'thread_reactivate')
           THEN 'automatic_actor'
         WHEN EXISTS (
                SELECT 1 FROM case_activity_log cc
                WHERE cc.case_id = c.id AND cc.tenant_id = c.tenant_id
                  AND cc.action = 'category_confirmed'
                  AND COALESCE(cc.username, '') = e.actor
                  AND cc.created_at BETWEEN e.created_at - INTERVAL '30 seconds' AND e.created_at)
           THEN CASE WHEN w.case_id IS NULL THEN 'accept_suggestion_no_work'
                     ELSE 'accept_suggestion_with_work' END
         WHEN w.case_id IS NULL THEN 'manual_no_work'
         ELSE 'manual_with_work'
       END AS evidence
FROM _live_cases c
LEFT JOIN _entry e ON e.case_id = c.id
LEFT JOIN _work w ON w.case_id = c.id AND w.tenant_id = c.tenant_id
WHERE c.status = 'in_progress'
)
SELECT tenant_id, evidence,
       CASE evidence
         WHEN 'accept_suggestion_no_work'   THEN 'CONFIRMED INCORRECT'
         WHEN 'automatic_actor'             THEN 'CONFIRMED INCORRECT'
         WHEN 'accept_suggestion_with_work' THEN 'potentially incorrect'
         WHEN 'manual_no_work'              THEN 'potentially incorrect'
         WHEN 'no_transition_log'           THEN 'insufficient evidence'
         ELSE 'supported'
       END AS verdict,
       COUNT(*) AS cases
FROM _classified GROUP BY 1, 2 ORDER BY 1, 3, 2;

\echo ''
\echo '== 5. IN PROGRESS with vs without staff-work evidence (per tenant) =='
WITH _live_cases AS (
SELECT id, tenant_id, LOWER(COALESCE(status, '')) AS status,
       LOWER(COALESCE(govt_status, 'not_forwarded')) AS govt_status,
       (NULLIF(TRIM(COALESCE(govt_reference_number, '')), '') IS NOT NULL) AS has_ref,
       resolved_at, created_at, govt_status_updated_at
FROM cases
WHERE COALESCE(is_deleted, false) = false
),
_entry AS (
SELECT DISTINCT ON (l.case_id)
       l.case_id, l.tenant_id, COALESCE(l.username, '') AS actor,
       LOWER(COALESCE(l.new_value, '')) AS new_value, l.created_at
FROM case_activity_log l
JOIN _live_cases c ON c.id = l.case_id AND c.tenant_id = l.tenant_id
WHERE l.action = 'status_change'
  AND c.status = 'in_progress'
  AND LOWER(COALESCE(l.new_value, '')) IN ('in_progress', 'escalated')
ORDER BY l.case_id, l.created_at DESC
),
_work AS (
SELECT DISTINCT l.case_id, l.tenant_id
FROM case_activity_log l
WHERE l.action IN ('citizen_notified', 'whatsapp_sent', 'complaint_added_manually',
                   'govt_submitted', 'govt_resolution_reviewed')
   OR (l.action = 'case_updated'
       AND (l.details LIKE '%notes%' OR l.details LIKE '%response%'))
UNION
SELECT DISTINCT g.case_id, g.tenant_id
FROM govt_submission_log g
WHERE g.action = 'staff_submitted'
),
_classified AS (
SELECT c.id, c.tenant_id, c.govt_status, c.has_ref,
       CASE
         WHEN c.has_ref OR c.govt_status NOT IN ('not_forwarded', 'pending_staff_submit')
           THEN 'filed_with_govt'
         WHEN EXISTS (SELECT 1 FROM escalations x WHERE x.case_id = c.id AND x.tenant_id = c.tenant_id)
           OR e.new_value = 'escalated'
           OR e.actor = 'system:legacy_status_remap'
           THEN 'legacy_escalation'
         WHEN e.case_id IS NULL
           THEN 'no_transition_log'
         WHEN e.actor LIKE 'system:govt\_%'
           THEN 'external_evidence'
         WHEN e.actor IN ('', 'ai', 'system', 'buffer_release', 'media_intake', 'thread_reactivate')
           THEN 'automatic_actor'
         WHEN EXISTS (
                SELECT 1 FROM case_activity_log cc
                WHERE cc.case_id = c.id AND cc.tenant_id = c.tenant_id
                  AND cc.action = 'category_confirmed'
                  AND COALESCE(cc.username, '') = e.actor
                  AND cc.created_at BETWEEN e.created_at - INTERVAL '30 seconds' AND e.created_at)
           THEN CASE WHEN w.case_id IS NULL THEN 'accept_suggestion_no_work'
                     ELSE 'accept_suggestion_with_work' END
         WHEN w.case_id IS NULL THEN 'manual_no_work'
         ELSE 'manual_with_work'
       END AS evidence
FROM _live_cases c
LEFT JOIN _entry e ON e.case_id = c.id
LEFT JOIN _work w ON w.case_id = c.id AND w.tenant_id = c.tenant_id
WHERE c.status = 'in_progress'
)
SELECT c.tenant_id,
       COUNT(*) FILTER (WHERE w.case_id IS NOT NULL) AS with_staff_work,
       COUNT(*) FILTER (WHERE w.case_id IS NULL)     AS no_staff_work_evidence
FROM _classified c
LEFT JOIN _work w ON w.case_id = c.id AND w.tenant_id = c.tenant_id
GROUP BY 1 ORDER BY 1;

\echo ''
\echo '== 6. logged status transitions by non-human actors (per tenant) =='
WITH _live_cases AS (
SELECT id, tenant_id, LOWER(COALESCE(status, '')) AS status,
       LOWER(COALESCE(govt_status, 'not_forwarded')) AS govt_status,
       (NULLIF(TRIM(COALESCE(govt_reference_number, '')), '') IS NOT NULL) AS has_ref,
       resolved_at, created_at, govt_status_updated_at
FROM cases
WHERE COALESCE(is_deleted, false) = false
),
_entry AS (
SELECT DISTINCT ON (l.case_id)
       l.case_id, l.tenant_id, COALESCE(l.username, '') AS actor,
       LOWER(COALESCE(l.new_value, '')) AS new_value, l.created_at
FROM case_activity_log l
JOIN _live_cases c ON c.id = l.case_id AND c.tenant_id = l.tenant_id
WHERE l.action = 'status_change'
  AND c.status = 'in_progress'
  AND LOWER(COALESCE(l.new_value, '')) IN ('in_progress', 'escalated')
ORDER BY l.case_id, l.created_at DESC
),
_work AS (
SELECT DISTINCT l.case_id, l.tenant_id
FROM case_activity_log l
WHERE l.action IN ('citizen_notified', 'whatsapp_sent', 'complaint_added_manually',
                   'govt_submitted', 'govt_resolution_reviewed')
   OR (l.action = 'case_updated'
       AND (l.details LIKE '%notes%' OR l.details LIKE '%response%'))
UNION
SELECT DISTINCT g.case_id, g.tenant_id
FROM govt_submission_log g
WHERE g.action = 'staff_submitted'
),
_classified AS (
SELECT c.id, c.tenant_id, c.govt_status, c.has_ref,
       CASE
         WHEN c.has_ref OR c.govt_status NOT IN ('not_forwarded', 'pending_staff_submit')
           THEN 'filed_with_govt'
         WHEN EXISTS (SELECT 1 FROM escalations x WHERE x.case_id = c.id AND x.tenant_id = c.tenant_id)
           OR e.new_value = 'escalated'
           OR e.actor = 'system:legacy_status_remap'
           THEN 'legacy_escalation'
         WHEN e.case_id IS NULL
           THEN 'no_transition_log'
         WHEN e.actor LIKE 'system:govt\_%'
           THEN 'external_evidence'
         WHEN e.actor IN ('', 'ai', 'system', 'buffer_release', 'media_intake', 'thread_reactivate')
           THEN 'automatic_actor'
         WHEN EXISTS (
                SELECT 1 FROM case_activity_log cc
                WHERE cc.case_id = c.id AND cc.tenant_id = c.tenant_id
                  AND cc.action = 'category_confirmed'
                  AND COALESCE(cc.username, '') = e.actor
                  AND cc.created_at BETWEEN e.created_at - INTERVAL '30 seconds' AND e.created_at)
           THEN CASE WHEN w.case_id IS NULL THEN 'accept_suggestion_no_work'
                     ELSE 'accept_suggestion_with_work' END
         WHEN w.case_id IS NULL THEN 'manual_no_work'
         ELSE 'manual_with_work'
       END AS evidence
FROM _live_cases c
LEFT JOIN _entry e ON e.case_id = c.id
LEFT JOIN _work w ON w.case_id = c.id AND w.tenant_id = c.tenant_id
WHERE c.status = 'in_progress'
)
SELECT l.tenant_id, COALESCE(NULLIF(l.username, ''), '(blank)') AS actor,
       LOWER(COALESCE(l.new_value, '')) AS new_status, COUNT(*) AS transitions
FROM case_activity_log l
WHERE l.action = 'status_change'
  AND COALESCE(l.username, '') IN ('', 'ai', 'system', 'buffer_release', 'media_intake', 'thread_reactivate')
GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;

\echo ''
\echo '== 7. Accept & assign side effect: category_confirmed followed by in_progress within 30s (per tenant, all time) =='
WITH _live_cases AS (
SELECT id, tenant_id, LOWER(COALESCE(status, '')) AS status,
       LOWER(COALESCE(govt_status, 'not_forwarded')) AS govt_status,
       (NULLIF(TRIM(COALESCE(govt_reference_number, '')), '') IS NOT NULL) AS has_ref,
       resolved_at, created_at, govt_status_updated_at
FROM cases
WHERE COALESCE(is_deleted, false) = false
),
_entry AS (
SELECT DISTINCT ON (l.case_id)
       l.case_id, l.tenant_id, COALESCE(l.username, '') AS actor,
       LOWER(COALESCE(l.new_value, '')) AS new_value, l.created_at
FROM case_activity_log l
JOIN _live_cases c ON c.id = l.case_id AND c.tenant_id = l.tenant_id
WHERE l.action = 'status_change'
  AND c.status = 'in_progress'
  AND LOWER(COALESCE(l.new_value, '')) IN ('in_progress', 'escalated')
ORDER BY l.case_id, l.created_at DESC
),
_work AS (
SELECT DISTINCT l.case_id, l.tenant_id
FROM case_activity_log l
WHERE l.action IN ('citizen_notified', 'whatsapp_sent', 'complaint_added_manually',
                   'govt_submitted', 'govt_resolution_reviewed')
   OR (l.action = 'case_updated'
       AND (l.details LIKE '%notes%' OR l.details LIKE '%response%'))
UNION
SELECT DISTINCT g.case_id, g.tenant_id
FROM govt_submission_log g
WHERE g.action = 'staff_submitted'
),
_classified AS (
SELECT c.id, c.tenant_id, c.govt_status, c.has_ref,
       CASE
         WHEN c.has_ref OR c.govt_status NOT IN ('not_forwarded', 'pending_staff_submit')
           THEN 'filed_with_govt'
         WHEN EXISTS (SELECT 1 FROM escalations x WHERE x.case_id = c.id AND x.tenant_id = c.tenant_id)
           OR e.new_value = 'escalated'
           OR e.actor = 'system:legacy_status_remap'
           THEN 'legacy_escalation'
         WHEN e.case_id IS NULL
           THEN 'no_transition_log'
         WHEN e.actor LIKE 'system:govt\_%'
           THEN 'external_evidence'
         WHEN e.actor IN ('', 'ai', 'system', 'buffer_release', 'media_intake', 'thread_reactivate')
           THEN 'automatic_actor'
         WHEN EXISTS (
                SELECT 1 FROM case_activity_log cc
                WHERE cc.case_id = c.id AND cc.tenant_id = c.tenant_id
                  AND cc.action = 'category_confirmed'
                  AND COALESCE(cc.username, '') = e.actor
                  AND cc.created_at BETWEEN e.created_at - INTERVAL '30 seconds' AND e.created_at)
           THEN CASE WHEN w.case_id IS NULL THEN 'accept_suggestion_no_work'
                     ELSE 'accept_suggestion_with_work' END
         WHEN w.case_id IS NULL THEN 'manual_no_work'
         ELSE 'manual_with_work'
       END AS evidence
FROM _live_cases c
LEFT JOIN _entry e ON e.case_id = c.id
LEFT JOIN _work w ON w.case_id = c.id AND w.tenant_id = c.tenant_id
WHERE c.status = 'in_progress'
)
SELECT s.tenant_id, COUNT(DISTINCT s.case_id) AS cases_affected_ever
FROM case_activity_log s
JOIN case_activity_log cc
  ON cc.case_id = s.case_id AND cc.tenant_id = s.tenant_id
 AND cc.action = 'category_confirmed'
 AND COALESCE(cc.username, '') = COALESCE(s.username, '')
 AND cc.created_at BETWEEN s.created_at - INTERVAL '30 seconds' AND s.created_at
WHERE s.action = 'status_change' AND LOWER(COALESCE(s.new_value, '')) = 'in_progress'
GROUP BY 1 ORDER BY 1;

\echo ''
\echo '== 8. inconsistent status combinations (per tenant) =='
WITH _live_cases AS (
SELECT id, tenant_id, LOWER(COALESCE(status, '')) AS status,
       LOWER(COALESCE(govt_status, 'not_forwarded')) AS govt_status,
       (NULLIF(TRIM(COALESCE(govt_reference_number, '')), '') IS NOT NULL) AS has_ref,
       resolved_at, created_at, govt_status_updated_at
FROM cases
WHERE COALESCE(is_deleted, false) = false
),
_entry AS (
SELECT DISTINCT ON (l.case_id)
       l.case_id, l.tenant_id, COALESCE(l.username, '') AS actor,
       LOWER(COALESCE(l.new_value, '')) AS new_value, l.created_at
FROM case_activity_log l
JOIN _live_cases c ON c.id = l.case_id AND c.tenant_id = l.tenant_id
WHERE l.action = 'status_change'
  AND c.status = 'in_progress'
  AND LOWER(COALESCE(l.new_value, '')) IN ('in_progress', 'escalated')
ORDER BY l.case_id, l.created_at DESC
),
_work AS (
SELECT DISTINCT l.case_id, l.tenant_id
FROM case_activity_log l
WHERE l.action IN ('citizen_notified', 'whatsapp_sent', 'complaint_added_manually',
                   'govt_submitted', 'govt_resolution_reviewed')
   OR (l.action = 'case_updated'
       AND (l.details LIKE '%notes%' OR l.details LIKE '%response%'))
UNION
SELECT DISTINCT g.case_id, g.tenant_id
FROM govt_submission_log g
WHERE g.action = 'staff_submitted'
),
_classified AS (
SELECT c.id, c.tenant_id, c.govt_status, c.has_ref,
       CASE
         WHEN c.has_ref OR c.govt_status NOT IN ('not_forwarded', 'pending_staff_submit')
           THEN 'filed_with_govt'
         WHEN EXISTS (SELECT 1 FROM escalations x WHERE x.case_id = c.id AND x.tenant_id = c.tenant_id)
           OR e.new_value = 'escalated'
           OR e.actor = 'system:legacy_status_remap'
           THEN 'legacy_escalation'
         WHEN e.case_id IS NULL
           THEN 'no_transition_log'
         WHEN e.actor LIKE 'system:govt\_%'
           THEN 'external_evidence'
         WHEN e.actor IN ('', 'ai', 'system', 'buffer_release', 'media_intake', 'thread_reactivate')
           THEN 'automatic_actor'
         WHEN EXISTS (
                SELECT 1 FROM case_activity_log cc
                WHERE cc.case_id = c.id AND cc.tenant_id = c.tenant_id
                  AND cc.action = 'category_confirmed'
                  AND COALESCE(cc.username, '') = e.actor
                  AND cc.created_at BETWEEN e.created_at - INTERVAL '30 seconds' AND e.created_at)
           THEN CASE WHEN w.case_id IS NULL THEN 'accept_suggestion_no_work'
                     ELSE 'accept_suggestion_with_work' END
         WHEN w.case_id IS NULL THEN 'manual_no_work'
         ELSE 'manual_with_work'
       END AS evidence
FROM _live_cases c
LEFT JOIN _entry e ON e.case_id = c.id
LEFT JOIN _work w ON w.case_id = c.id AND w.tenant_id = c.tenant_id
WHERE c.status = 'in_progress'
)
SELECT tenant_id, issue, COUNT(*) AS cases FROM (
  SELECT tenant_id, 'filed_but_internal_status_untriaged' AS issue FROM _live_cases
   WHERE (has_ref OR govt_status NOT IN ('not_forwarded', 'pending_staff_submit'))
     AND status IN ('new', 'pending', 'pending_review', 'awaiting_location', 'incomplete')
  UNION ALL
  SELECT tenant_id, 'reference_recorded_but_govt_status_unfiled' FROM _live_cases
   WHERE has_ref AND govt_status IN ('not_forwarded', 'pending_staff_submit')
  UNION ALL
  SELECT tenant_id, 'govt_submitted_without_reference' FROM _live_cases
   WHERE NOT has_ref AND govt_status = 'submitted'
  UNION ALL
  SELECT tenant_id, 'resolved_without_resolved_at' FROM _live_cases
   WHERE status IN ('resolved', 'completed') AND resolved_at IS NULL
  UNION ALL
  SELECT tenant_id, 'resolved_at_set_on_unresolved_case' FROM _live_cases
   WHERE status NOT IN ('resolved', 'completed') AND resolved_at IS NOT NULL
  UNION ALL
  SELECT tenant_id, 'legacy_or_unknown_status:' || status FROM _live_cases
   WHERE status NOT IN ('new', 'pending', 'pending_review', 'awaiting_location', 'in_progress',
                        'resolved', 'closed', 'incomplete', 'emergency', 'offensive',
                        'irrelevant', 'case_comment', 'contact_buffered')
) x GROUP BY 1, 2 ORDER BY 1, 2;

\echo ''
\echo '== 9. CONFIRMED INCORRECT case IDs (ids only, max 200 per tenant) =='
WITH _live_cases AS (
SELECT id, tenant_id, LOWER(COALESCE(status, '')) AS status,
       LOWER(COALESCE(govt_status, 'not_forwarded')) AS govt_status,
       (NULLIF(TRIM(COALESCE(govt_reference_number, '')), '') IS NOT NULL) AS has_ref,
       resolved_at, created_at, govt_status_updated_at
FROM cases
WHERE COALESCE(is_deleted, false) = false
),
_entry AS (
SELECT DISTINCT ON (l.case_id)
       l.case_id, l.tenant_id, COALESCE(l.username, '') AS actor,
       LOWER(COALESCE(l.new_value, '')) AS new_value, l.created_at
FROM case_activity_log l
JOIN _live_cases c ON c.id = l.case_id AND c.tenant_id = l.tenant_id
WHERE l.action = 'status_change'
  AND c.status = 'in_progress'
  AND LOWER(COALESCE(l.new_value, '')) IN ('in_progress', 'escalated')
ORDER BY l.case_id, l.created_at DESC
),
_work AS (
SELECT DISTINCT l.case_id, l.tenant_id
FROM case_activity_log l
WHERE l.action IN ('citizen_notified', 'whatsapp_sent', 'complaint_added_manually',
                   'govt_submitted', 'govt_resolution_reviewed')
   OR (l.action = 'case_updated'
       AND (l.details LIKE '%notes%' OR l.details LIKE '%response%'))
UNION
SELECT DISTINCT g.case_id, g.tenant_id
FROM govt_submission_log g
WHERE g.action = 'staff_submitted'
),
_classified AS (
SELECT c.id, c.tenant_id, c.govt_status, c.has_ref,
       CASE
         WHEN c.has_ref OR c.govt_status NOT IN ('not_forwarded', 'pending_staff_submit')
           THEN 'filed_with_govt'
         WHEN EXISTS (SELECT 1 FROM escalations x WHERE x.case_id = c.id AND x.tenant_id = c.tenant_id)
           OR e.new_value = 'escalated'
           OR e.actor = 'system:legacy_status_remap'
           THEN 'legacy_escalation'
         WHEN e.case_id IS NULL
           THEN 'no_transition_log'
         WHEN e.actor LIKE 'system:govt\_%'
           THEN 'external_evidence'
         WHEN e.actor IN ('', 'ai', 'system', 'buffer_release', 'media_intake', 'thread_reactivate')
           THEN 'automatic_actor'
         WHEN EXISTS (
                SELECT 1 FROM case_activity_log cc
                WHERE cc.case_id = c.id AND cc.tenant_id = c.tenant_id
                  AND cc.action = 'category_confirmed'
                  AND COALESCE(cc.username, '') = e.actor
                  AND cc.created_at BETWEEN e.created_at - INTERVAL '30 seconds' AND e.created_at)
           THEN CASE WHEN w.case_id IS NULL THEN 'accept_suggestion_no_work'
                     ELSE 'accept_suggestion_with_work' END
         WHEN w.case_id IS NULL THEN 'manual_no_work'
         ELSE 'manual_with_work'
       END AS evidence
FROM _live_cases c
LEFT JOIN _entry e ON e.case_id = c.id
LEFT JOIN _work w ON w.case_id = c.id AND w.tenant_id = c.tenant_id
WHERE c.status = 'in_progress'
)
SELECT tenant_id, evidence, id AS case_id
FROM (
  SELECT tenant_id, evidence, id,
         ROW_NUMBER() OVER (PARTITION BY tenant_id ORDER BY id) AS rn
  FROM _classified
  WHERE evidence IN ('accept_suggestion_no_work', 'automatic_actor')
) t WHERE rn <= 200 ORDER BY tenant_id, id;

\echo ''
\echo '== 10. revised rules: filed cases NOT in progress that the next verified govt event would move (per tenant) =='
WITH _live_cases AS (
SELECT id, tenant_id, LOWER(COALESCE(status, '')) AS status,
       LOWER(COALESCE(govt_status, 'not_forwarded')) AS govt_status,
       (NULLIF(TRIM(COALESCE(govt_reference_number, '')), '') IS NOT NULL) AS has_ref,
       resolved_at, created_at, govt_status_updated_at
FROM cases
WHERE COALESCE(is_deleted, false) = false
),
_entry AS (
SELECT DISTINCT ON (l.case_id)
       l.case_id, l.tenant_id, COALESCE(l.username, '') AS actor,
       LOWER(COALESCE(l.new_value, '')) AS new_value, l.created_at
FROM case_activity_log l
JOIN _live_cases c ON c.id = l.case_id AND c.tenant_id = l.tenant_id
WHERE l.action = 'status_change'
  AND c.status = 'in_progress'
  AND LOWER(COALESCE(l.new_value, '')) IN ('in_progress', 'escalated')
ORDER BY l.case_id, l.created_at DESC
),
_work AS (
SELECT DISTINCT l.case_id, l.tenant_id
FROM case_activity_log l
WHERE l.action IN ('citizen_notified', 'whatsapp_sent', 'complaint_added_manually',
                   'govt_submitted', 'govt_resolution_reviewed')
   OR (l.action = 'case_updated'
       AND (l.details LIKE '%notes%' OR l.details LIKE '%response%'))
UNION
SELECT DISTINCT g.case_id, g.tenant_id
FROM govt_submission_log g
WHERE g.action = 'staff_submitted'
),
_classified AS (
SELECT c.id, c.tenant_id, c.govt_status, c.has_ref,
       CASE
         WHEN c.has_ref OR c.govt_status NOT IN ('not_forwarded', 'pending_staff_submit')
           THEN 'filed_with_govt'
         WHEN EXISTS (SELECT 1 FROM escalations x WHERE x.case_id = c.id AND x.tenant_id = c.tenant_id)
           OR e.new_value = 'escalated'
           OR e.actor = 'system:legacy_status_remap'
           THEN 'legacy_escalation'
         WHEN e.case_id IS NULL
           THEN 'no_transition_log'
         WHEN e.actor LIKE 'system:govt\_%'
           THEN 'external_evidence'
         WHEN e.actor IN ('', 'ai', 'system', 'buffer_release', 'media_intake', 'thread_reactivate')
           THEN 'automatic_actor'
         WHEN EXISTS (
                SELECT 1 FROM case_activity_log cc
                WHERE cc.case_id = c.id AND cc.tenant_id = c.tenant_id
                  AND cc.action = 'category_confirmed'
                  AND COALESCE(cc.username, '') = e.actor
                  AND cc.created_at BETWEEN e.created_at - INTERVAL '30 seconds' AND e.created_at)
           THEN CASE WHEN w.case_id IS NULL THEN 'accept_suggestion_no_work'
                     ELSE 'accept_suggestion_with_work' END
         WHEN w.case_id IS NULL THEN 'manual_no_work'
         ELSE 'manual_with_work'
       END AS evidence
FROM _live_cases c
LEFT JOIN _entry e ON e.case_id = c.id
LEFT JOIN _work w ON w.case_id = c.id AND w.tenant_id = c.tenant_id
WHERE c.status = 'in_progress'
)
SELECT tenant_id, status, COUNT(*) AS cases
FROM _live_cases
WHERE (has_ref OR govt_status IN ('submitted', 'registered', 'under_review', 'forwarded', 'escalated'))
  AND status IN ('new', 'pending', 'pending_review', 'awaiting_location', 'incomplete', 'emergency')
GROUP BY 1, 2 ORDER BY 1, 2;

\echo ''
\echo '== 11. revised rules: portal reports resolution, internal case still open, no review this cycle (per tenant) =='
WITH _live_cases AS (
SELECT id, tenant_id, LOWER(COALESCE(status, '')) AS status,
       LOWER(COALESCE(govt_status, 'not_forwarded')) AS govt_status,
       (NULLIF(TRIM(COALESCE(govt_reference_number, '')), '') IS NOT NULL) AS has_ref,
       resolved_at, created_at, govt_status_updated_at
FROM cases
WHERE COALESCE(is_deleted, false) = false
),
_entry AS (
SELECT DISTINCT ON (l.case_id)
       l.case_id, l.tenant_id, COALESCE(l.username, '') AS actor,
       LOWER(COALESCE(l.new_value, '')) AS new_value, l.created_at
FROM case_activity_log l
JOIN _live_cases c ON c.id = l.case_id AND c.tenant_id = l.tenant_id
WHERE l.action = 'status_change'
  AND c.status = 'in_progress'
  AND LOWER(COALESCE(l.new_value, '')) IN ('in_progress', 'escalated')
ORDER BY l.case_id, l.created_at DESC
),
_work AS (
SELECT DISTINCT l.case_id, l.tenant_id
FROM case_activity_log l
WHERE l.action IN ('citizen_notified', 'whatsapp_sent', 'complaint_added_manually',
                   'govt_submitted', 'govt_resolution_reviewed')
   OR (l.action = 'case_updated'
       AND (l.details LIKE '%notes%' OR l.details LIKE '%response%'))
UNION
SELECT DISTINCT g.case_id, g.tenant_id
FROM govt_submission_log g
WHERE g.action = 'staff_submitted'
),
_classified AS (
SELECT c.id, c.tenant_id, c.govt_status, c.has_ref,
       CASE
         WHEN c.has_ref OR c.govt_status NOT IN ('not_forwarded', 'pending_staff_submit')
           THEN 'filed_with_govt'
         WHEN EXISTS (SELECT 1 FROM escalations x WHERE x.case_id = c.id AND x.tenant_id = c.tenant_id)
           OR e.new_value = 'escalated'
           OR e.actor = 'system:legacy_status_remap'
           THEN 'legacy_escalation'
         WHEN e.case_id IS NULL
           THEN 'no_transition_log'
         WHEN e.actor LIKE 'system:govt\_%'
           THEN 'external_evidence'
         WHEN e.actor IN ('', 'ai', 'system', 'buffer_release', 'media_intake', 'thread_reactivate')
           THEN 'automatic_actor'
         WHEN EXISTS (
                SELECT 1 FROM case_activity_log cc
                WHERE cc.case_id = c.id AND cc.tenant_id = c.tenant_id
                  AND cc.action = 'category_confirmed'
                  AND COALESCE(cc.username, '') = e.actor
                  AND cc.created_at BETWEEN e.created_at - INTERVAL '30 seconds' AND e.created_at)
           THEN CASE WHEN w.case_id IS NULL THEN 'accept_suggestion_no_work'
                     ELSE 'accept_suggestion_with_work' END
         WHEN w.case_id IS NULL THEN 'manual_no_work'
         ELSE 'manual_with_work'
       END AS evidence
FROM _live_cases c
LEFT JOIN _entry e ON e.case_id = c.id
LEFT JOIN _work w ON w.case_id = c.id AND w.tenant_id = c.tenant_id
WHERE c.status = 'in_progress'
)
SELECT c.tenant_id, c.govt_status, COUNT(*) AS awaiting_resolution_verification
FROM _live_cases c
WHERE c.govt_status IN ('resolved', 'disposed')
  AND c.status NOT IN ('resolved', 'completed', 'closed', 'irrelevant', 'offensive')
  AND NOT EXISTS (
        SELECT 1 FROM case_activity_log r
        WHERE r.case_id = c.id AND r.tenant_id = c.tenant_id
          AND r.action = 'govt_resolution_reviewed'
          AND (c.govt_status_updated_at IS NULL OR r.created_at >= c.govt_status_updated_at))
GROUP BY 1, 2 ORDER BY 1, 2;

\echo ''
\echo '== 12. govt-rejected cases still open internally (per tenant) =='
WITH _live_cases AS (
SELECT id, tenant_id, LOWER(COALESCE(status, '')) AS status,
       LOWER(COALESCE(govt_status, 'not_forwarded')) AS govt_status,
       (NULLIF(TRIM(COALESCE(govt_reference_number, '')), '') IS NOT NULL) AS has_ref,
       resolved_at, created_at, govt_status_updated_at
FROM cases
WHERE COALESCE(is_deleted, false) = false
),
_entry AS (
SELECT DISTINCT ON (l.case_id)
       l.case_id, l.tenant_id, COALESCE(l.username, '') AS actor,
       LOWER(COALESCE(l.new_value, '')) AS new_value, l.created_at
FROM case_activity_log l
JOIN _live_cases c ON c.id = l.case_id AND c.tenant_id = l.tenant_id
WHERE l.action = 'status_change'
  AND c.status = 'in_progress'
  AND LOWER(COALESCE(l.new_value, '')) IN ('in_progress', 'escalated')
ORDER BY l.case_id, l.created_at DESC
),
_work AS (
SELECT DISTINCT l.case_id, l.tenant_id
FROM case_activity_log l
WHERE l.action IN ('citizen_notified', 'whatsapp_sent', 'complaint_added_manually',
                   'govt_submitted', 'govt_resolution_reviewed')
   OR (l.action = 'case_updated'
       AND (l.details LIKE '%notes%' OR l.details LIKE '%response%'))
UNION
SELECT DISTINCT g.case_id, g.tenant_id
FROM govt_submission_log g
WHERE g.action = 'staff_submitted'
),
_classified AS (
SELECT c.id, c.tenant_id, c.govt_status, c.has_ref,
       CASE
         WHEN c.has_ref OR c.govt_status NOT IN ('not_forwarded', 'pending_staff_submit')
           THEN 'filed_with_govt'
         WHEN EXISTS (SELECT 1 FROM escalations x WHERE x.case_id = c.id AND x.tenant_id = c.tenant_id)
           OR e.new_value = 'escalated'
           OR e.actor = 'system:legacy_status_remap'
           THEN 'legacy_escalation'
         WHEN e.case_id IS NULL
           THEN 'no_transition_log'
         WHEN e.actor LIKE 'system:govt\_%'
           THEN 'external_evidence'
         WHEN e.actor IN ('', 'ai', 'system', 'buffer_release', 'media_intake', 'thread_reactivate')
           THEN 'automatic_actor'
         WHEN EXISTS (
                SELECT 1 FROM case_activity_log cc
                WHERE cc.case_id = c.id AND cc.tenant_id = c.tenant_id
                  AND cc.action = 'category_confirmed'
                  AND COALESCE(cc.username, '') = e.actor
                  AND cc.created_at BETWEEN e.created_at - INTERVAL '30 seconds' AND e.created_at)
           THEN CASE WHEN w.case_id IS NULL THEN 'accept_suggestion_no_work'
                     ELSE 'accept_suggestion_with_work' END
         WHEN w.case_id IS NULL THEN 'manual_no_work'
         ELSE 'manual_with_work'
       END AS evidence
FROM _live_cases c
LEFT JOIN _entry e ON e.case_id = c.id
LEFT JOIN _work w ON w.case_id = c.id AND w.tenant_id = c.tenant_id
WHERE c.status = 'in_progress'
)
SELECT tenant_id, status, COUNT(*) AS cases
FROM _live_cases
WHERE govt_status = 'rejected'
  AND status NOT IN ('resolved', 'completed', 'closed', 'irrelevant', 'offensive')
GROUP BY 1, 2 ORDER BY 1, 2;

ROLLBACK;
