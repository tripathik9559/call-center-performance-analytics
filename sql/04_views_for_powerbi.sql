-- =====================================================================
-- 04_views_for_powerbi.sql  |  Views that Power BI can connect to directly
-- Run after loading the data.
-- =====================================================================
USE call_center;

-- One row per call, with agent details joined in (main fact table for Power BI)
CREATE OR REPLACE VIEW vw_call_facts AS
SELECT
    c.call_id, c.call_datetime, c.call_date, c.call_hour, c.weekday, c.weekday_num, c.month,
    c.customer_id, c.queue, c.agent_id,
    COALESCE(a.agent_name, 'Abandoned (no agent)') AS agent_name,
    a.team, a.shift, a.tenure_months, a.tenure_band,
    c.wait_seconds, c.handle_seconds, ROUND(c.handle_seconds / 60, 2) AS handle_minutes,
    c.call_status, c.is_abandoned, c.within_sla,
    c.resolved_first_call, c.fcr_flag, c.csat_score, c.repeat_within_7d
FROM calls c
LEFT JOIN agents a ON a.agent_id = c.agent_id;

-- Hourly KPI summary
CREATE OR REPLACE VIEW vw_hourly_kpis AS
SELECT
    call_hour,
    COUNT(*)                          AS calls,
    ROUND(100 * AVG(is_abandoned), 2) AS abandon_rate_pct,
    ROUND(100 * AVG(within_sla), 2)   AS sla_pct,
    ROUND(AVG(csat_score), 2)         AS avg_csat
FROM calls
GROUP BY call_hour;

-- Agent scorecard
CREATE OR REPLACE VIEW vw_agent_scorecard AS
SELECT
    a.agent_id, a.agent_name, a.team, a.shift, a.tenure_months, a.tenure_band,
    COUNT(c.call_id)                       AS answered_calls,
    ROUND(AVG(c.handle_seconds) / 60, 2)   AS aht_min,
    ROUND(100 * AVG(c.fcr_flag), 2)        AS fcr_pct,
    ROUND(AVG(c.csat_score), 2)            AS avg_csat
FROM agents a
LEFT JOIN calls c ON c.agent_id = a.agent_id AND c.call_status = 'Answered'
GROUP BY a.agent_id, a.agent_name, a.team, a.shift, a.tenure_months, a.tenure_band;
