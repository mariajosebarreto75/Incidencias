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
