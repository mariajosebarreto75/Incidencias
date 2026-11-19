-- Actualiza responsable_email usando coincidencia parcial (nombre corto dentro del nombre completo)
-- Solo afecta registros que aún no tienen correo
UPDATE compromisos c
SET responsable_email = p.correo
FROM personal_hesego p
WHERE (c.responsable_email IS NULL OR c.responsable_email = '')
  AND LOWER(TRIM(p.nombre)) LIKE '%' || LOWER(TRIM(c.responsable)) || '%'
  -- Evitar matches demasiado cortos (menos de 6 caracteres)
  AND LENGTH(TRIM(c.responsable)) >= 6;

-- Ver cuántos siguen sin correo tras la segunda pasada
SELECT responsable, COUNT(*) as total
FROM compromisos
WHERE (responsable_email IS NULL OR responsable_email = '')
  AND estado != 'Cerrado'
GROUP BY responsable
ORDER BY total DESC;
