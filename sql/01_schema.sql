-- =====================================================================
-- 01_schema.sql  |  Call Center Analytics  |  MySQL 8+ (also works on MariaDB 10.5+)
-- Run first. Creates the database, tables and indexes.
-- =====================================================================
CREATE DATABASE IF NOT EXISTS call_center CHARACTER SET utf8mb4;
USE call_center;

DROP TABLE IF EXISTS calls;
DROP TABLE IF EXISTS agents;

CREATE TABLE agents (
    agent_id       VARCHAR(10)  NOT NULL PRIMARY KEY,
    agent_name     VARCHAR(60)  NOT NULL,
    team           VARCHAR(30)  NOT NULL,
    shift          VARCHAR(10)  NOT NULL,
    tenure_months  INT          NOT NULL,
    tenure_band    VARCHAR(20)  NOT NULL
);

CREATE TABLE calls (
    call_id             VARCHAR(10)  NOT NULL PRIMARY KEY,
    call_datetime       DATETIME     NOT NULL,
    call_date           DATE         NOT NULL,
    call_hour           TINYINT      NOT NULL,
    weekday             VARCHAR(10)  NOT NULL,
    weekday_num         TINYINT      NOT NULL,   -- Monday = 1 ... Sunday = 7
    month               CHAR(7)      NOT NULL,   -- e.g. 2026-04
    customer_id         VARCHAR(10)  NOT NULL,
    queue               VARCHAR(30)  NOT NULL,
    agent_id            VARCHAR(10)  NULL,       -- NULL for abandoned calls
    wait_seconds        INT          NOT NULL,
    handle_seconds      INT          NOT NULL,
    call_status         VARCHAR(10)  NOT NULL,   -- Answered / Abandoned
    is_abandoned        TINYINT      NOT NULL,
    within_sla          TINYINT      NOT NULL,   -- answered within 20 sec
    resolved_first_call CHAR(1)      NULL,       -- Y / N, NULL when abandoned
    fcr_flag            TINYINT      NULL,
    csat_score          TINYINT      NULL,       -- 1-5, NULL when no survey
    repeat_within_7d    TINYINT      NOT NULL,
    CONSTRAINT fk_calls_agent FOREIGN KEY (agent_id) REFERENCES agents(agent_id),
    CONSTRAINT chk_csat CHECK (csat_score IS NULL OR csat_score BETWEEN 1 AND 5)
);

CREATE INDEX idx_calls_date     ON calls (call_date);
CREATE INDEX idx_calls_hour     ON calls (call_hour);
CREATE INDEX idx_calls_queue    ON calls (queue);
CREATE INDEX idx_calls_agent    ON calls (agent_id);
CREATE INDEX idx_calls_customer ON calls (customer_id, call_datetime);
