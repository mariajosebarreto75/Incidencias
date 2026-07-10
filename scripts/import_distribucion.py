import sys
import os

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

import pandas as pd

from run import app

from app.extensions import db

from app.models.user import User
from app.models.distribucion_operativa import (
    DistribucionOperativa
)
from app.models.recurso import Recurso


BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

ruta_excel = os.path.join(
    BASE_DIR,
    "excels",
    "maestros",
    "plantilla_distribucion.xlsx"
)


df = pd.read_excel(
    ruta_excel
)

with app.app_context():

    for _, row in df.iterrows():

        # ==========================
        # VALIDAR RECURSO
        # ==========================

        recurso_nombre = str(
            row["recurso"]
        ).strip()

        recurso_existe = Recurso.query.filter_by(
            recurso=recurso_nombre
        ).first()

        if not recurso_existe:

            nuevo_recurso = Recurso(

                recurso=recurso_nombre,

                tipo_cuadrilla=str(
                    row["tipo_cuadrilla"]
                ).strip(),

                meta=float(
                    row["meta"]
                )

            )

            db.session.add(
                nuevo_recurso
            )

            print(
                f"Recurso agregado: {recurso_nombre}"
            )

        # ==========================
        # GUARDAR DISTRIBUCIÓN
        # ==========================

        nuevo = DistribucionOperativa(

            fecha=pd.to_datetime(
                row["fecha"]
            ).date(),

            contrato=str(
                row["contrato"]
            ).strip(),

            recurso=recurso_nombre,

            placa=str(
                row["placa"]
            ).strip(),

            orden_trabajo=str(
                row["orden_trabajo"]
            ).strip(),

            tipo_actividad=str(
                row["tipo_actividad"]
            ).strip(),

            tipo_cuadrilla=str(
                row["tipo_cuadrilla"]
            ).strip(),

            hora_salida_sede=pd.to_datetime(
                row["hora_salida_sede"]
            ).time(),

            hora_llegada_sede=pd.to_datetime(
                row["hora_llegada_sede"]
            ).time(),

            cedula_1=str(
                row["cedula _1"]
            ).strip(),

            cedula_2=str(
                row["cedula _2"]
            ).strip(),

            cedula_3=str(
                row["cedula _3"]
            ).strip(),

            cedula_4=str(
                row["cedula _4"]
            ).strip(),

            cedula_5=str(
                row["cedula _5"]
            ).strip(),

            numero_celular=str(
                row["numero__celular"]
            ).strip(),

            latitud=str(
                row["latitud"]
            ).strip(),

            longitud=str(
                row["longitud"]
            ).strip(),

            duracion_actividad=str(
                row["duracion_actividad"]
            ).strip(),

            observacion=str(
                row["observacion"]
            ).strip(),

            meta=float(
                row["meta"]
            )

        )

        db.session.add(
            nuevo
        )

    db.session.commit()

    print(
        "Distribución operativa importada 🚀"
    )