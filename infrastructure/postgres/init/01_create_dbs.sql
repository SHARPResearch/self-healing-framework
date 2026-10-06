-- Runs automatically on first Postgres start.
-- Creates the two logical databases we need.

CREATE DATABASE anomaly_db;
CREATE DATABASE telemetry_db;

-- Enable Timescale on the telemetry DB.
\connect telemetry_db
CREATE EXTENSION IF NOT EXISTS timescaledb;