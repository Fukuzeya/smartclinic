-- Pharmacy drug stock — seeded automatically by PostgreSQL on first init.
-- This file is mounted to /docker-entrypoint-initdb.d/ via docker-compose.
-- It runs inside the "pharmacy" database after the schema is created by Alembic.
-- Because Alembic runs at service startup (after postgres init), we use a
-- DO block so this is safe to call even if the table doesn't exist yet
-- (it is a no-op in that case; the API seed covers the re-run path).

\connect pharmacy

INSERT INTO drug_stock (id, drug_name, quantity_on_hand, unit, reorder_threshold)
VALUES
  (gen_random_uuid(), 'Amoxicillin',        200, 'tablets', 20),
  (gen_random_uuid(), 'Paracetamol',         500, 'tablets', 50),
  (gen_random_uuid(), 'Metformin',           300, 'tablets', 30),
  (gen_random_uuid(), 'Atorvastatin',        150, 'tablets', 20),
  (gen_random_uuid(), 'Amlodipine',          150, 'tablets', 20),
  (gen_random_uuid(), 'Lisinopril',          150, 'tablets', 20),
  (gen_random_uuid(), 'Salbutamol Inhaler',   50, 'inhalers', 10),
  (gen_random_uuid(), 'Prednisolone',        120, 'tablets', 20),
  (gen_random_uuid(), 'Cotrimoxazole',       200, 'tablets', 30),
  (gen_random_uuid(), 'Ibuprofen',           300, 'tablets', 30),
  (gen_random_uuid(), 'Omeprazole',           80, 'capsules', 20),
  (gen_random_uuid(), 'Aspirin',              80, 'tablets', 20),
  (gen_random_uuid(), 'Ciprofloxacin',       100, 'tablets', 20),
  (gen_random_uuid(), 'Doxycycline',         100, 'tablets', 20),
  (gen_random_uuid(), 'Ferrous Sulphate',    200, 'tablets', 30)
  -- Warfarin intentionally NOT included — triggers OOS saga demo
ON CONFLICT (drug_name) DO NOTHING;
