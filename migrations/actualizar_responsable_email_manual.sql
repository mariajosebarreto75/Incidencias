-- Correcciones manuales para casos específicos

-- Omar Estupiñán / Estupiñan (sin tilde)
UPDATE compromisos SET responsable_email = 'oestupinan@hesegoingenieria.com'
WHERE (responsable_email IS NULL OR responsable_email = '')
  AND LOWER(responsable) LIKE '%estupi%';

-- Johana Marcela Picón / Johana Marcela / Johanan Marcela
UPDATE compromisos SET responsable_email = 'jpicon@hesegoingenieria.com'
WHERE (responsable_email IS NULL OR responsable_email = '')
  AND LOWER(responsable) LIKE '%johana%' OR LOWER(responsable) LIKE '%johanan%';

-- Jorman Ayala → Jorman Alberto Ayala Holguin
UPDATE compromisos SET responsable_email = 'jayala@hesegoingenieria.com'
WHERE (responsable_email IS NULL OR responsable_email = '')
  AND LOWER(responsable) LIKE '%jorman%';

-- Johan Torres → Johan Rodolfo Torres Rubio
UPDATE compromisos SET responsable_email = 'jtorres@hesegoingenieria.com'
WHERE (responsable_email IS NULL OR responsable_email = '')
  AND LOWER(responsable) LIKE '%johan torres%';

-- Jonathan Vega / Jhonatan Vega → Jhonatan Vega Ramirez
UPDATE compromisos SET responsable_email = 'jvega@hesegoingenieria.com'
WHERE (responsable_email IS NULL OR responsable_email = '')
  AND (LOWER(responsable) LIKE '%jonathan vega%' OR LOWER(responsable) LIKE '%jhonatan vega%');

-- Jhon Cáceres → Jhon Wladimir Camilo Cáceres Sandoval
UPDATE compromisos SET responsable_email = 'jcaceres@hesegoingenieria.com'
WHERE (responsable_email IS NULL OR responsable_email = '')
  AND LOWER(responsable) LIKE '%c%ceres%';

-- Fabian Barrero → Fabian Jair Barrero Suarez
UPDATE compromisos SET responsable_email = 'fbarrero@hesegoingenieria.com'
WHERE (responsable_email IS NULL OR responsable_email = '')
  AND LOWER(responsable) LIKE '%barrero%';

-- Giovanny Cardona → Giovanny Andrés Cardona Espinosa
UPDATE compromisos SET responsable_email = 'gcardona@hesegoingenieria.com'
WHERE (responsable_email IS NULL OR responsable_email = '')
  AND LOWER(responsable) LIKE '%cardona%';

-- Jeison Morales → Jeison Fernando Morales Mendez
UPDATE compromisos SET responsable_email = 'jmorales@hesegoingenieria.com'
WHERE (responsable_email IS NULL OR responsable_email = '')
  AND LOWER(responsable) LIKE '%jeison%';

-- Mauricio Oritz (typo de Ortiz)
UPDATE compromisos SET responsable_email = 'jortiz@hesegoingenieria.com'
WHERE (responsable_email IS NULL OR responsable_email = '')
  AND LOWER(responsable) LIKE '%mauricio or%';

-- Maria José Barreto / Maria José Barreto Castro
UPDATE compromisos SET responsable_email = 'mbarreto@hesegoingenieria.com'
WHERE (responsable_email IS NULL OR responsable_email = '')
  AND LOWER(responsable) LIKE '%barreto%';

-- Andres Peñuela → no existe en personal_hesego, omitir

-- Resultado final
SELECT responsable, COUNT(*) as total
FROM compromisos
WHERE (responsable_email IS NULL OR responsable_email = '')
  AND estado != 'Cerrado'
GROUP BY responsable
ORDER BY total DESC;
