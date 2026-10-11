-- =====================================================================
-- 03_analysis_queries.sql  |  Call Center Analytics  |  MySQL 8+ / MariaDB 10.5+
-- Run after loading the data. Run one query at a time and read the result.
--
-- KPI definitions (same as Python + Power BI):
--   Abandon Rate = abandoned / total calls
--   SLA %        = answered within 20 sec / total calls
--   AHT (min)    = average handle time of ANSWERED calls
--   FCR %        = resolved on first call / ANSWERED calls
--   CSAT         = AVG of survey scores (NULLs are ignored automatically)
-- =====================================================================
USE call_center;

-- ---------------------------------------------------------------------
-- Q1. Overall KPIs
-- ---------------------------------------------------------------------
SELECT
    COUNT(*)                                                        AS total_calls,
    ROUND(100 * AVG(is_abandoned), 1)                               AS abandon_rate_pct,
    ROUND(100 * AVG(within_sla), 1)                                 AS sla_pct,
    ROUND(AVG(CASE WHEN call_status = 'Answered' THEN handle_seconds END) / 60, 1) AS aht_min,
    ROUND(AVG(CASE WHEN call_status = 'Answered' THEN wait_seconds END), 0)        AS asa_sec,
    ROUND(100 * AVG(fcr_flag), 1)                                   AS fcr_pct,
    ROUND(AVG(csat_score), 2)                                       AS avg_csat,
    ROUND(100 * AVG(repeat_within_7d), 1)                           AS repeat_call_pct
FROM calls;

-- ---------------------------------------------------------------------
-- Q2. Which hours are the problem? (volume vs abandon vs SLA)
-- ---------------------------------------------------------------------
SELECT
    call_hour,
    COUNT(*)                          AS calls,
    ROUND(100 * AVG(is_abandoned), 1) AS abandon_rate_pct,
    ROUND(100 * AVG(within_sla), 1)   AS sla_pct,
    ROUND(AVG(CASE WHEN call_status = 'Answered' THEN wait_seconds END), 0) AS avg_wait_sec
FROM calls
GROUP BY call_hour
ORDER BY call_hour;

-- ---------------------------------------------------------------------
-- Q3. Weekday pattern
-- ---------------------------------------------------------------------
SELECT
    weekday_num, weekday,
    COUNT(*)                          AS calls,
    ROUND(100 * AVG(is_abandoned), 1) AS abandon_rate_pct,
    ROUND(100 * AVG(within_sla), 1)   AS sla_pct
FROM calls
GROUP BY weekday_num, weekday
ORDER BY weekday_num;

-- ---------------------------------------------------------------------
-- Q4. Queue scorecard
-- ---------------------------------------------------------------------
SELECT
    queue,
    COUNT(*)                                                         AS calls,
    ROUND(100 * AVG(is_abandoned), 1)                                AS abandon_rate_pct,
    ROUND(AVG(CASE WHEN call_status = 'Answered' THEN handle_seconds END) / 60, 1) AS aht_min,
    ROUND(100 * AVG(fcr_flag), 1)                                    AS fcr_pct,
    ROUND(AVG(csat_score), 2)                                        AS avg_csat
FROM calls
WHERE queue <> 'Unknown'
GROUP BY queue
ORDER BY fcr_pct;

-- ---------------------------------------------------------------------
-- Q5. Agent ranking inside each team (JOIN + window function RANK)
--     Only agents with at least 200 answered calls.
-- ---------------------------------------------------------------------
WITH agent_stats AS (
    SELECT
        a.agent_id, a.agent_name, a.team, a.shift, a.tenure_months,
        COUNT(*)                                  AS answered_calls,
        ROUND(AVG(c.handle_seconds) / 60, 1)      AS aht_min,
        ROUND(100 * AVG(c.fcr_flag), 1)           AS fcr_pct,
        ROUND(AVG(c.csat_score), 2)               AS avg_csat
    FROM calls c
    JOIN agents a ON a.agent_id = c.agent_id
    WHERE c.call_status = 'Answered'
    GROUP BY a.agent_id, a.agent_name, a.team, a.shift, a.tenure_months
    HAVING COUNT(*) >= 200
)
SELECT
    team, agent_id, agent_name, tenure_months, answered_calls, aht_min, fcr_pct, avg_csat,
    RANK() OVER (PARTITION BY team ORDER BY fcr_pct DESC) AS fcr_rank_in_team
FROM agent_stats
ORDER BY team, fcr_rank_in_team;

-- ---------------------------------------------------------------------
-- Q6. Does agent tenure matter?
-- ---------------------------------------------------------------------
SELECT
    a.tenure_band,
    COUNT(*)                                  AS answered_calls,
    ROUND(AVG(c.handle_seconds) / 60, 1)      AS aht_min,
    ROUND(100 * AVG(c.fcr_flag), 1)           AS fcr_pct,
    ROUND(AVG(c.csat_score), 2)               AS avg_csat
FROM calls c
JOIN agents a ON a.agent_id = c.agent_id
WHERE c.call_status = 'Answered'
GROUP BY a.tenure_band
ORDER BY MIN(a.tenure_months);

-- ---------------------------------------------------------------------
-- Q7. Month-over-month change (CTE + LAG)
-- ---------------------------------------------------------------------
WITH monthly AS (
    SELECT
        month,
        COUNT(*)                          AS calls,
        ROUND(100 * AVG(is_abandoned), 2) AS abandon_rate_pct,
        ROUND(AVG(csat_score), 2)         AS avg_csat
    FROM calls
    GROUP BY month
)
SELECT
    month, calls,
    LAG(calls) OVER (ORDER BY month)                                         AS prev_month_calls,
    ROUND(100 * (calls - LAG(calls) OVER (ORDER BY month))
          / LAG(calls) OVER (ORDER BY month), 1)                             AS mom_change_pct,
    abandon_rate_pct, avg_csat
FROM monthly
ORDER BY month;

-- ---------------------------------------------------------------------
-- Q8. Cumulative calls per month (running total)
-- ---------------------------------------------------------------------
SELECT
    month,
    COUNT(*)                                  AS calls,
    SUM(COUNT(*)) OVER (ORDER BY month)       AS cumulative_calls
FROM calls
GROUP BY month
ORDER BY month;

-- ---------------------------------------------------------------------
-- Q9. Does waiting hurt? Wait-time bucket vs abandonment and CSAT
-- ---------------------------------------------------------------------
SELECT
    CASE
        WHEN wait_seconds <= 20  THEN '1) 0-20 sec'
        WHEN wait_seconds <= 60  THEN '2) 21-60 sec'
        WHEN wait_seconds <= 120 THEN '3) 61-120 sec'
        ELSE                          '4) 120+ sec'
    END                                       AS wait_bucket,
    COUNT(*)                                  AS calls,
    ROUND(100 * AVG(is_abandoned), 1)         AS abandon_rate_pct,
    ROUND(AVG(csat_score), 2)                 AS avg_csat
FROM calls
GROUP BY wait_bucket
ORDER BY wait_bucket;

-- ---------------------------------------------------------------------
-- Q10. Staffing gap: calls per rostered agent by hour and shift
--      (a shift with very few agents but heavy calls = understaffed)
-- ---------------------------------------------------------------------
WITH shift_staff AS (
    SELECT shift, COUNT(*) AS agents_in_shift FROM agents GROUP BY shift
),
hourly AS (
    SELECT
        call_hour,
        CASE WHEN call_hour BETWEEN 6  AND 13 THEN 'Morning'
             WHEN call_hour BETWEEN 14 AND 21 THEN 'Evening'
             ELSE 'Night' END AS shift,
        COUNT(*) AS calls,
        ROUND(100 * AVG(is_abandoned), 1) AS abandon_rate_pct
    FROM calls
    GROUP BY call_hour
)
SELECT
    h.call_hour, h.shift, s.agents_in_shift, h.calls,
    ROUND(h.calls / s.agents_in_shift, 0) AS calls_per_agent,
    h.abandon_rate_pct
FROM hourly h
JOIN shift_staff s ON s.shift = h.shift
ORDER BY h.call_hour;

-- ---------------------------------------------------------------------
-- Q11. Repeat-call analysis: top 10 customers by number of calls
-- ---------------------------------------------------------------------
SELECT
    customer_id,
    COUNT(*)                                   AS total_calls,
    SUM(repeat_within_7d)                      AS repeat_calls,
    ROUND(AVG(csat_score), 2)                  AS avg_csat
FROM calls
GROUP BY customer_id
ORDER BY total_calls DESC, customer_id
LIMIT 10;

-- ---------------------------------------------------------------------
-- Q12. Billing bill-cycle effect: first 7 days of month vs rest
-- ---------------------------------------------------------------------
WITH billing_daily AS (
    SELECT call_date, COUNT(*) AS billing_calls
    FROM calls
    WHERE queue = 'Billing'
    GROUP BY call_date
)
SELECT
    CASE WHEN DAY(call_date) <= 7 THEN 'Days 1-7' ELSE 'Days 8-31' END AS period,
    COUNT(*)                          AS days_counted,
    ROUND(AVG(billing_calls), 0)      AS avg_billing_calls_per_day
FROM billing_daily
GROUP BY period
ORDER BY period;

-- ---------------------------------------------------------------------
-- Q13. Worst 3 agents by CSAT in every team (ROW_NUMBER) -> coaching list
-- ---------------------------------------------------------------------
WITH agent_csat AS (
    SELECT
        a.team, a.agent_id, a.agent_name, a.tenure_months,
        COUNT(c.csat_score)               AS survey_count,
        ROUND(AVG(c.csat_score), 2)       AS avg_csat
    FROM agents a
    JOIN calls c ON c.agent_id = a.agent_id
    GROUP BY a.team, a.agent_id, a.agent_name, a.tenure_months
    HAVING COUNT(c.csat_score) >= 100
),
ranked AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY team ORDER BY avg_csat ASC) AS rn
    FROM agent_csat
)
SELECT team, agent_id, agent_name, tenure_months, survey_count, avg_csat
FROM ranked
WHERE rn <= 3
ORDER BY team, rn;
