"""
Servicio GPS Monitor — cliente para sincronización del plan operativo.
"""

import requests

BASE_URL = "http://178.219.0.123/api/distributor"
API_KEY  = "gps_CRfC_rpCOihAanlm5xdMCen8G0K3NNA5zsorERZ90_I"

_HEADERS = {"X-Api-Key": API_KEY}
_TIMEOUT = 15


def obtener_plan_del_dia(from_date, to_date=None):
    """
    Descarga el plan operativo diario y lo devuelve como pandas.DataFrame.
    Columnas: plan_id, plan_date, contract_code, contract_group, resource_code,
              brigade_type, plan_centroid_code, tech1_doc..tech5_doc, plan_status,
              plate, plan_item_id, order_number, order_type, duration_min,
              estado, item_centroid_code, client_lat, client_lon, observation.
    Si no hay datos devuelve DataFrame vacío (verificar con df.empty).
    """
    import pandas as pd

    def _to_str(d):
        if d is None:
            return None
        if isinstance(d, str):
            return d
        return d.strftime("%Y-%m-%d")

    from_str = _to_str(from_date)
    to_str   = _to_str(to_date) if to_date is not None else from_str

    resp = requests.get(
        f"{BASE_URL}/plan/items",
        headers=_HEADERS,
        params={"from": from_str, "to": to_str},
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()

    text = resp.text.strip()
    print(f"[Plan GPS] status={resp.status_code} body={repr(text[:120])}")

    content_type = resp.headers.get("Content-Type", "")
    if not text or text.startswith("<") or "text/html" in content_type:
        return pd.DataFrame()

    data = resp.json()
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    if "plan_date" in df.columns:
        df["plan_date"] = pd.to_datetime(df["plan_date"]).dt.date
    return df
