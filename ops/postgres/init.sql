-- SmartClinic — per-context PostgreSQL bootstrap.
--
-- Creates one database per bounded context and a dedicated role for each
-- (principle of least privilege). Every service connects as its own role
-- and sees only its own database. Cross-context reads and joins are
-- impossible by construction — the only way to share state is via domain
-- events on RabbitMQ.
--
-- This file is run exactly once, as the Postgres superuser, on volume
-- initialisation (see `docker-entrypoint-initdb.d` in the docker-compose).

-- ---- roles ------------------------------------------------------------

CREATE ROLE patient_identity WITH LOGIN PASSWORD 'patient_identity';
CREATE ROLE scheduling       WITH LOGIN PASSWORD 'scheduling';
CREATE ROLE clinical         WITH LOGIN PASSWORD 'clinical';
CREATE ROLE pharmacy         WITH LOGIN PASSWORD 'pharmacy';
CREATE ROLE laboratory       WITH LOGIN PASSWORD 'laboratory';
CREATE ROLE billing          WITH LOGIN PASSWORD 'billing';
CREATE ROLE saga             WITH LOGIN PASSWORD 'saga';
CREATE ROLE keycloak         WITH LOGIN PASSWORD 'keycloak';

-- ---- databases --------------------------------------------------------

CREATE DATABASE patient_identity OWNER patient_identity;
CREATE DATABASE scheduling       OWNER scheduling;
CREATE DATABASE clinical_write   OWNER clinical;
CREATE DATABASE clinical_read    OWNER clinical;
CREATE DATABASE pharmacy         OWNER pharmacy;
CREATE DATABASE laboratory       OWNER laboratory;
CREATE DATABASE billing          OWNER billing;
CREATE DATABASE saga             OWNER saga;
CREATE DATABASE keycloak         OWNER keycloak;

-- ---- extensions (created inside each DB by connecting via \c) ---------

\c patient_identity
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

\c scheduling
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

\c clinical_write
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

\c clinical_read
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

\c pharmacy
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

\c laboratory
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

\c billing
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

\c saga
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
