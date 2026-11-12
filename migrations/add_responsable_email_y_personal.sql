-- Migración: responsable_email en compromisos + tabla personal_hesego
-- Ejecutar en producción: docker exec -i postgres psql -U postgres -d neo_incidencias

-- 1. Columna responsable_email en compromisos (si no existe)
ALTER TABLE compromisos
  ADD COLUMN IF NOT EXISTS responsable_email VARCHAR(200);

-- 2. Tabla personal_hesego (si no existe)
CREATE TABLE IF NOT EXISTS personal_hesego (
    id     SERIAL PRIMARY KEY,
    nombre VARCHAR(300) NOT NULL,
    correo VARCHAR(200) NOT NULL UNIQUE
);
CREATE INDEX IF NOT EXISTS ix_personal_hesego_correo ON personal_hesego (correo);
