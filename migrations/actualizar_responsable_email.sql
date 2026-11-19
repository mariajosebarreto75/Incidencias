-- Actualiza responsable_email en compromisos cruzando por nombre exacto con personal_hesego
UPDATE compromisos c
SET responsable_email = p.correo
FROM personal_hesego p
WHERE LOWER(TRIM(c.responsable)) = LOWER(TRIM(p.nombre))
  AND (c.responsable_email IS NULL OR c.responsable_email = '');

-- Ver cuántos quedaron sin correo (nombres que no coincidieron)
SELECT responsable, COUNT(*) as total
FROM compromisos
WHERE (responsable_email IS NULL OR responsable_email = '')
  AND estado != 'Cerrado'
GROUP BY responsable
ORDER BY total DESC;
