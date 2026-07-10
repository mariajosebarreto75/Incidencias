from app.extensions import db


class DistribucionOperativa(
    db.Model
):

    __tablename__ = (
        "distribucion_operativa"
    )

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    fecha = db.Column(
        db.Date,
        nullable=False
    )

    contrato = db.Column(
        db.Text,
        nullable=False
    )

    # Sede donde opera esta cuadrilla (informativo; la sede oficial viene del Contrato)
    sede = db.Column(db.String(150), nullable=True)

    recurso = db.Column(
        db.String(200),
        nullable=False
    )

    placa = db.Column(
        db.String(50)
    )

    orden_trabajo = db.Column(
        db.String(100)
    )

    tipo_actividad = db.Column(
        db.Text
    )

    tipo_cuadrilla = db.Column(
        db.Text
    )

    hora_salida_sede = db.Column(
        db.Time
    )

    hora_llegada_sede = db.Column(
        db.Time
    )

    cedula_1 = db.Column(
        db.String(50)
    )

    cedula_2 = db.Column(
        db.String(50)
    )

    cedula_3 = db.Column(
        db.String(50)
    )

    cedula_4 = db.Column(
        db.String(50)
    )

    cedula_5 = db.Column(
        db.String(50)
    )

    numero_celular = db.Column(
        db.String(50)
    )

    latitud = db.Column(
        db.String(100)
    )

    longitud = db.Column(
        db.String(100)
    )

    duracion_actividad = db.Column(
        db.String(50)
    )

    observacion = db.Column(
        db.Text
    )

    meta = db.Column(
        db.Float
    )