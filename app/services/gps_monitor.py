"""
Servicio GPS Monitor — cliente oficial del desarrollador (adaptado).
"""

import requests

BASE_URL = "http://143.20.129.195/api/distributor"
API_KEY  = "gps_4ych-cC4_5LaMMBQO3JEfsMGxY36dIQPRnj3_KWwx4U"

_HEADERS = {"X-Api-Key": API_KEY}
_TIMEOUT = 15


def obtener_alertas_pendientes():
    """
    Devuelve lista de diccionarios con todas las alertas pendientes.
    Lista vacía = sin alertas (no es error).
    """
    resp = requests.get(
        f"{BASE_URL}/alerts/pending",
        headers=_HEADERS,
        timeout=_TIMEOUT
    )
    resp.raise_for_status()
    return resp.json()["alerts"]


def responder_alertas(respuestas):
    """
    Informa a GPS Monitor qué se hizo con cada alerta.

    respuestas: [{"alert_id": 123, "accion": "resolver" | "liberar"}, ...]

    "resolver" → alerta atendida, se cierra
    "liberar"  → no se pudo atender, vuelve a pending
    """
    resultados = []
    for item in respuestas:
        alert_id = item["alert_id"]
        accion   = item["accion"]

        try:
            # Primero reclamar (requisito de la API)
            claim = requests.post(
                f"{BASE_URL}/alerts/{alert_id}/claim",
                headers=_HEADERS,
                timeout=_TIMEOUT
            )
            if claim.status_code != 200:
                resultados.append({
                    "alert_id": alert_id, "ok": False,
                    "detalle": f"No se pudo reclamar: {claim.text}"
                })
                continue

            # Luego resolver o liberar
            endpoint = "resolve" if accion == "resolver" else "release"
            paso2 = requests.post(
                f"{BASE_URL}/alerts/{alert_id}/{endpoint}",
                headers=_HEADERS,
                timeout=_TIMEOUT
            )

            if paso2.status_code == 200:
                resultados.append({"alert_id": alert_id, "ok": True, "detalle": "ok"})
            else:
                resultados.append({
                    "alert_id": alert_id, "ok": False,
                    "detalle": f"Error al {accion}: {paso2.text}"
                })

        except requests.exceptions.RequestException as e:
            resultados.append({"alert_id": alert_id, "ok": False, "detalle": str(e)})

    return resultados


def obtener_plan_del_dia(from_date, to_date=None):
    """
    Descarga el plan operativo diario del API GPS Monitor.
    from_date / to_date: str "YYYY-MM-DD" o datetime.date
    Devuelve lista de dicts (un dict por OT/plan_item).
    """
    def _str(d):
        if d is None:
            return None
        return d if isinstance(d, str) else d.strftime("%Y-%m-%d")

    from_str = _str(from_date)
    to_str   = _str(to_date) if to_date is not None else from_str

    resp = requests.get(
        f"{BASE_URL}/plan/items",
        headers=_HEADERS,
        params={"from": from_str, "to": to_str},
        timeout=_TIMEOUT
    )
    resp.raise_for_status()
    text = resp.text.strip()
    print(f"[Plan GPS] status={resp.status_code} body={repr(text[:120])}")
    if not text:
        return []
    content_type = resp.headers.get("Content-Type", "")
    if text.startswith("<") or "text/html" in content_type:
        raise ValueError(
            "El endpoint /plan/items devolvió HTML en vez de JSON. "
            "El endpoint aún no está disponible en GPS Monitor."
        )
    data = resp.json()
    return data if isinstance(data, list) else []
