/**
 * Persistencia automática de filtros por página usando sessionStorage.
 * Guarda el valor de todos los <select id="..."> e <input id="..."> (excepto
 * checkbox, button, submit, hidden) cada vez que cambian, y los restaura al cargar.
 *
 * Uso mínimo: incluir este script en la página. No requiere configuración.
 *
 * API expuesta en window.FilterPersist:
 *   .restore()  — restaurar valores (útil después de poblar selects dinámicos)
 *   .save()     — guardar estado actual
 *   .clear()    — borrar filtros guardados para esta página
 */
(function () {
    const KEY = 'fp_' + location.pathname;
    const SKIP_TYPES = new Set(['checkbox', 'radio', 'button', 'submit', 'reset', 'hidden', 'file', 'password']);

    function _inputs() {
        return Array.from(document.querySelectorAll('select[id], input[id]'))
            .filter(el => el.id && !SKIP_TYPES.has(el.type));
    }

    function save() {
        const data = {};
        _inputs().forEach(el => { data[el.id] = el.value; });
        try { sessionStorage.setItem(KEY, JSON.stringify(data)); } catch (e) {}
    }

    function restore() {
        let saved;
        try { saved = JSON.parse(sessionStorage.getItem(KEY) || '{}'); } catch (e) { return; }
        _inputs().forEach(el => {
            if (saved[el.id] !== undefined && saved[el.id] !== null) {
                el.value = saved[el.id];
            }
        });
    }

    function clear() {
        try { sessionStorage.removeItem(KEY); } catch (e) {}
    }

    // Escuchar cambios en cualquier input/select de la página
    document.addEventListener('change', save, true);
    document.addEventListener('input', save, true);

    // Restaurar al cargar
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', restore);
    } else {
        restore();
    }

    window.FilterPersist = { save, restore, clear };
})();
