-- Rollback Migration 031: Remove centralized sampling rules

DROP TABLE IF EXISTS sampling_rules;
