-- Dijalankan sekali saat container PostgreSQL pertama kali dibuat.
-- Password di sini hanya untuk development lokal.
CREATE ROLE spe_owner LOGIN PASSWORD 'spe_owner_dev';
CREATE ROLE spe_app LOGIN PASSWORD 'spe_app_dev' NOSUPERUSER NOBYPASSRLS;
CREATE DATABASE spe_dev OWNER spe_owner;
\connect spe_dev
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS citext;
GRANT CONNECT ON DATABASE spe_dev TO spe_app;
