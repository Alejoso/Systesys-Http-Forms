import io
import json
import mimetypes
from datetime import datetime, timezone, date
from typing import Any, Dict, List, Optional
import re
from urllib.parse import unquote

import requests
import streamlit as st
from verification import six_digit_code_from_fields

# ---------------------------------------------------------
# Utils
# ---------------------------------------------------------
def get_query_params() -> Dict[str, str]:
    """Return query params as a simple dict[str,str]."""
    out: Dict[str, str] = {}
    qp = None

    # Intentar API moderna
    try:
        qp = st.query_params
    except Exception:
        qp = None

    if qp is not None:
        try:
            items = qp.items() if hasattr(qp, "items") else []
            for k, v in items:
                if isinstance(v, list):
                    out[k] = v[0]
                else:
                    out[k] = str(v)
            return out
        except Exception:
            pass

    # Fallback a experimental_get_query_params
    try:
        qp2 = st.experimental_get_query_params()
        for k, v in qp2.items():
            if isinstance(v, list):
                out[k] = v[0]
            else:
                out[k] = str(v)
    except Exception:
        pass

    return out


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_http_url(url: Optional[str]) -> bool:
    if not url:
        return False
    return url.startswith("http://") or url.startswith("https://")


def ensure_session_defaults():
    if "equip_rows" not in st.session_state:
        st.session_state.equip_rows = [0]


def add_equipment_row():
    rows = st.session_state.equip_rows
    new_id = max(rows) + 1 if rows else 0
    rows.append(new_id)


def remove_equipment_row(row_id: int):
    rows = st.session_state.equip_rows
    if len(rows) > 1 and row_id in rows:
        rows.remove(row_id)


def safe_rerun():
    """Compat: Streamlit nuevo tiene st.rerun(), viejo tiene st.experimental_rerun()."""
    try:
        st.rerun()
    except Exception:
        st.experimental_rerun()


def render_equipment_rows() -> List[Dict[str, Any]]:
    """Renderiza los bloques de equipos/materiales y devuelve la lista de ítems."""
    items: List[Dict[str, Any]] = []
    rows = st.session_state.equip_rows
    total = len(rows)

    for idx, row_id in enumerate(rows, start=1):
        with st.expander(f"Equipo/Material #{idx}", expanded=total <= 3):
            cols1 = st.columns([3, 1, 1])
            nombre = cols1[0].text_input("Nombre", key=f"eq_nombre_{row_id}")
            cantidad = cols1[1].number_input(
                "Cantidad",
                min_value=0.0,
                step=1.0,
                format="%g",
                key=f"eq_cantidad_{row_id}",
            )
            unidad = cols1[2].text_input("Unidad", key=f"eq_unidad_{row_id}")

            cols2 = st.columns(3)
            marca = cols2[0].text_input("Marca", key=f"eq_marca_{row_id}")
            modelo = cols2[1].text_input("Modelo", key=f"eq_modelo_{row_id}")
            serial = cols2[2].text_input("Serial", key=f"eq_serial_{row_id}")

            observaciones = st.text_area(
                "Observaciones", key=f"eq_obs_{row_id}", height=80
            )

            remove_clicked = st.button(
                f"{row_id} Quitar este material",
                key=f"rm_{row_id}",
                use_container_width=False,
            )
            if remove_clicked:
                remove_equipment_row(row_id)
                safe_rerun()

            items.append(
                {
                    "nombre": nombre.strip(),
                    "cantidad": cantidad,
                    "unidad": unidad.strip(),
                    "marca": marca.strip(),
                    "modelo": modelo.strip(),
                    "serial": serial.strip(),
                    "observaciones": observaciones.strip(),
                }
            )

    return items


def make_payload(
    meta: Dict[str, Optional[str]],
    descripcion: str,
    equipos: List[Dict[str, Any]],
    trabajo_alturas: Dict[str, Any],
    observaciones: str,
    actividades: str,
    contacto: Dict[str, str],
    horas_visita: Dict[str, str],
) -> Dict[str, Any]:
    """Construye el JSON que se manda a n8n dentro del multipart."""
    return {
        "metadata": {
            "id": meta.get("id") or "",
            "ciudad": meta.get("ciudad") or "",
            "nit": meta.get("nit") or "",
            "nombreEmpresa": meta.get("nombreEmpresa") or "",
            "submittedAt": now_iso(),
        },
        "contactoEnSitio": {
            "nombre": (contacto.get("nombre") or "").strip(),
            "cargo": (contacto.get("cargo") or "").strip(),
        },
        "descripcionServicio": descripcion,
        "equiposMaterialesInstalados": equipos,
        "trabajoEnAlturas": trabajo_alturas,
        "observacionesGenerales": observaciones,
        "actividadesPendientesONovedades": actividades,
        "horasVisita": horas_visita,
    }


def to_files_payload(
    payload: Dict[str, Any],
    imgs_antes: List[Any],
    imgs_durante: List[Any],
    imgs_despues: List[Any],
):
    """Construye el multipart/form-data: payload.json + imágenes."""
    files = []

    # Parte JSON
    json_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    files.append(
        ("payload", ("payload.json", io.BytesIO(json_bytes), "application/json"))
    )

    def add_images(field: str, imgs: List[Any]):
        for f in imgs or []:
            fname = getattr(f, "name", "image")
            mt = (
                getattr(f, "type", None)
                or mimetypes.guess_type(fname)[0]
                or "application/octet-stream"
            )
            try:
                content = f.getvalue()
            except Exception:
                content = f.read()
            files.append((field, (fname, content, mt)))

    add_images("imagenesAntes", imgs_antes)
    add_images("imagenesDurante", imgs_durante)
    add_images("imagenesDespues", imgs_despues)

    return files


# ---------------------------------------------------------
# UI – configuración inicial
# ---------------------------------------------------------
st.set_page_config(page_title="Reporte de Servicio Técnico", layout="centered")
ensure_session_defaults()

qp = get_query_params()

# Leer y normalizar POSTURL desde los query params
raw_posturl = (qp.get("POSTURL") or "").strip()
raw_posturl = unquote(raw_posturl)  # http%3A%2F%2F... → http://...

# Forzar https para evitar redirect 301 (POST -> GET) en nginx
if raw_posturl.startswith("http://"):
    raw_posturl = "https://" + raw_posturl[len("http://") :]

meta = {
    "id": (qp.get("id") or "").strip(),
    "ciudad": (qp.get("ciudad") or "").strip(),
    "nit": (qp.get("nit") or "").strip(),
    "nombreEmpresa": (qp.get("nombreEmpresa") or "").strip(),
    "POSTURL": raw_posturl,
}

verification_code = six_digit_code_from_fields(
    id=meta.get("id"),
    ciudad=meta.get("ciudad"),
    nit=meta.get("nit"),
    nombreEmpresa=meta.get("nombreEmpresa"),
)

# ---------------------------------------------------------
# Cabecera con datos de la orden
# ---------------------------------------------------------
st.title("Reporte de Servicio Técnico")

with st.container(border=True):
    st.subheader("Datos del Cliente")
    c1, c2, c3, c4 = st.columns(4)
    c1.write(f"ID: {meta.get('id') or '—'}")
    c2.write(f"Ciudad: {meta.get('ciudad') or '—'}")
    c3.write(f"NIT: {meta.get('nit') or '—'}")
    c4.write(f"Empresa: {meta.get('nombreEmpresa') or '—'}")

    if not is_http_url(meta.get("POSTURL")):
        st.warning(
            "No se recibió una POSTURL válida (?POSTURL=http(s)://...). "
            "El envío estará deshabilitado."
        )

# ---------------------------------------------------------
# Contacto en sitio
# ---------------------------------------------------------
st.subheader("1) Contacto en sitio *")
cA, cB = st.columns(2)
contacto_nombre = cA.text_input(
    "Nombre del contacto en sitio",
    placeholder="Ej: Juan Pérez",
    key="contacto_nombre",
)
contacto_cargo = cB.text_input(
    "Cargo del contacto",
    placeholder="Ej: Coordinador de mantenimiento",
    key="contacto_cargo",
)

# ---------------------------------------------------------
# Formulario principal (SIN st.form para que sea interactivo)
# ---------------------------------------------------------
st.subheader("2) Descripción del servicio técnico realizado *")
descripcion = st.text_area(
    "Descripción",
    placeholder="Detalle las actividades realizadas...",
    height=140,
)

st.subheader("3) Equipos y materiales instalados (Opcional)")
st.caption("Si no se usó materiales, dejar en blanco.")
equipos = render_equipment_rows()

add_clicked = st.button("➕ Agregar material", use_container_width=True, key="add_material")
if add_clicked:
    add_equipment_row()
    safe_rerun()

# -----------------------------------------------------
# Trabajo en alturas (habilita/deshabilita en vivo)
# -----------------------------------------------------
st.subheader("4) Trabajo en alturas *")

alturas_choice = st.selectbox(
    "¿Se realizó trabajo en alturas?",
    options=["Seleccione…", "Sí", "No"],
    index=0,
    key="alturas_choice",
)

requiere_alturas = (alturas_choice == "Sí")

detalles_alturas = st.text_input(
    "Detalles (EPP, permisos, andamios, etc.)",
    placeholder="Opcional (recomendado si selecciona Sí)",
    disabled=not requiere_alturas,
    key="detalles_alturas",
)

st.subheader("5) Observaciones generales *")
observaciones = st.text_area("Observaciones", height=120)

st.subheader("6) Actividades pendientes / Novedades *")
actividades = st.text_area("Actividades/Novedades", height=120)

st.subheader("7) Evidencias fotográficas *")
ev_cols = st.columns(3)
imgs_antes = ev_cols[0].file_uploader(
    "Antes", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True
)
imgs_durante = ev_cols[1].file_uploader(
    "Durante", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True
)
imgs_despues = ev_cols[2].file_uploader(
    "Después", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True
)

st.subheader("8) Horas de la visita *")

h1, h2 = st.columns(2)
hora_inicio = h1.time_input("Hora de inicio", key="hora_inicio")
hora_fin = h2.time_input("Hora de fin", key="hora_fin")

st.subheader("9) Verificación de envío *")
entered_code = st.text_input("Ingrese el código de verificación de 6 dígitos", max_chars=6)
entered_digits = re.sub(r"\D", "", entered_code)

submitted = st.button(
    "Enviar reporte",
    use_container_width=True,
    disabled=(not is_http_url(meta.get("POSTURL"))),
    key="send_report",
)

# ---------------------------------------------------------
# Envío del formulario
# ---------------------------------------------------------
if submitted:
    post_url = meta.get("POSTURL") or ""

    errors: List[str] = []

    if not contacto_nombre.strip():
        errors.append("El **nombre del contacto en sitio** es obligatorio.")
    if not contacto_cargo.strip():
        errors.append("El **cargo del contacto** es obligatorio.")

    if not descripcion.strip():
        errors.append("La descripción del servicio es obligatoria.")

    # Required selection
    if alturas_choice not in ("Sí", "No"):
        errors.append("Debe seleccionar **Sí** o **No** en 'Trabajo en alturas'.")

    if not observaciones.strip():
        errors.append("Por favor agregue observaciones. Si no tiene, escriba 'Ninguna'.")

    if not actividades.strip():
        errors.append(
            "Por favor agregue actividades pendientes o novedades. "
            "Si no tiene, escriba 'Ninguna'."
        )

    if not imgs_antes:
        errors.append("Falta al menos una imagen en la sección **Antes**.")
    if not imgs_durante:
        errors.append("Falta al menos una imagen en la sección **Durante**.")
    if not imgs_despues:
        errors.append("Falta al menos una imagen en la sección **Después**.")

    today = date.today()
    dt_inicio = datetime.combine(today, hora_inicio)
    dt_fin = datetime.combine(today, hora_fin)

    if dt_fin <= dt_inicio:
        errors.append("La **hora de fin** debe ser mayor que la **hora de inicio**.")

    if entered_digits != verification_code:
        errors.append("El código de verificación no es válido.")
    if not is_http_url(post_url):
        errors.append("POSTURL inválida o ausente.")

    if errors:
        st.error("\n".join([f"- {e}" for e in errors]))
    else:
        with st.spinner("Enviando reporte..."):
            payload = make_payload(
                meta,
                descripcion=descripcion.strip(),
                equipos=[e for e in equipos if any(str(v).strip() for v in e.values())],
                trabajo_alturas={
                    "requiere": bool(requiere_alturas),
                    "detalles": (detalles_alturas or "").strip(),
                },
                observaciones=observaciones.strip(),
                actividades=actividades.strip(),
                contacto={
                    "nombre": contacto_nombre.strip(),
                    "cargo": contacto_cargo.strip(),
                },
                horas_visita={
                    "inicio": dt_inicio.isoformat(),
                    "fin": dt_fin.isoformat(),
                    "zonaHoraria": "local",
                },
            )


            try:
                files = to_files_payload(payload, imgs_antes, imgs_durante, imgs_despues)

                resp = requests.post(
                    post_url,
                    files=files,
                    timeout=60,
                    verify=False,
                    allow_redirects=False,
                )

                st.success("Envío completado. ¡Muchas gracias por su trabajo!")

            except Exception as ex:
                st.error(f"Error al enviar el reporte: {ex}")

# ---------------------------------------------------------
# Barra lateral – descarga de plantilla JSON
# ---------------------------------------------------------
with st.sidebar:
    st.header("Acciones")
    example_payload = make_payload(
        meta,
        descripcion="",
        equipos=[],
        trabajo_alturas={"requiere": False, "detalles": ""},
        observaciones="",
        actividades="",
        contacto={"nombre": "", "cargo": ""},
        horas_visita={"inicio": "", "fin": "", "zonaHoraria": ""},
    )
    st.download_button(
        label="Descargar plantilla JSON",
        data=json.dumps(example_payload, ensure_ascii=False, indent=2),
        file_name="reporte_servicio.json",
        mime="application/json",
        use_container_width=True,
    )
