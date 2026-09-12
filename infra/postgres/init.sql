-- Local/CI separation between migration ownership and the runtime application role.
-- These are development-only credentials from compose.yaml, never production defaults.
CREATE ROLE conformly_app LOGIN PASSWORD 'conformly_app' NOSUPERUSER NOCREATEDB NOCREATEROLE;
GRANT CONNECT ON DATABASE conformly TO conformly_app;
GRANT USAGE ON SCHEMA public TO conformly_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO conformly_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO conformly_app;
