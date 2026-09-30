-- Runs once, when the postgres volume is first initialised. Dagster creates its own
-- tables but not the database that holds them, and a restore needs it to exist too
CREATE DATABASE dagster;
