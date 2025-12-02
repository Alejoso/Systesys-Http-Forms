import io
import json
import mimetypes
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import re

import requests
import streamlit as st
from verification import six_digit_code_from_fields


# ---------- Utils ----------
def get_query_params() -> Dict[str, str]:
	"""Return query params as a simple dict[str,str].
	Supports both st.query_params (QueryParams) and experimental_get_query_params().
	"""
	out: Dict[str, str] = {}
	qp = None
	# Try modern API
	try:
		qp = st.query_params  # type: ignore[attr-defined]
	except Exception:
		qp = None
	# Attempt to read qp if available
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
	# Fallback to experimental
	try:
		qp2 = st.experimental_get_query_params()  # type: ignore[attr-defined]
		for k, v in qp2.items():
			if isinstance(v, list):
				out[k] = v[0]
			else:
				out[k] = str(v)
	except Exception:
		pass
	return out


def is_http_url(url: Optional[str]) -> bool:
	if not url:
		return False
	return url.startswith("http://") or url.startswith("https://")


def now_iso() -> str:
	return datetime.now(timezone.utc).isoformat()


def ensure_session_defaults():
    if "equip_rows" not in st.session_state:
        st.session_state.equip_rows = [0]


def add_equipment_row():
    rows = st.session_state.equip_rows
    new_id = (max(rows) + 1) if rows else 0
    rows.append(new_id)


def remove_equipment_row(row_id: int):
    rows = st.session_state.equip_rows
    if len(rows) > 1 and row_id in rows:
        rows.remove(row_id)

def render_equipment_rows() -> List[Dict[str, Any]]:
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
                "Observaciones", key=f"eq_observaciones_{row_id}", height=80
            )

            remove_clicked = st.form_submit_button(
                f"🗑 Quitar este material #{idx}"
            )
            if remove_clicked:
                remove_equipment_row(row_id)
                st.experimental_rerun()

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
) -> Dict[str, Any]:
	return {
		"metadata": {
			"id": meta.get("id") or "",
			"ciudad": meta.get("ciudad") or "",
			"nit": meta.get("nit") or "",
			"nombreEmpresa": meta.get("nombreEmpresa") or "",
			"submittedAt": now_iso(),
		},
		"descripcionServicio": descripcion,
		"equiposMaterialesInstalados": equipos,
		"trabajoEnAlturas": trabajo_alturas,
		"observacionesGenerales": observaciones,
		"actividadesPendientesONovedades": actividades,
	}


def to_files_payload(
	payload: Dict[str, Any],
	imgs_antes: List[Any],
	imgs_durante: List[Any],
	imgs_despues: List[Any],
):
	files = []
	# JSON part
	json_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
	files.append(("payload", ("payload.json", io.BytesIO(json_bytes), "application/json")))

	def add_images(field_name: str, files_list: List[Any]):
		for f in files_list or []:
			# f is st.uploadedfile.UploadedFile
			fname = getattr(f, "name", "image")
			mt = getattr(f, "type", None) or mimetypes.guess_type(fname)[0] or "application/octet-stream"
			try:
				content = f.getvalue()  # bytes
			except Exception:
				content = f.read()
			files.append((field_name, (fname, content, mt)))

	add_images("imagenesAntes", imgs_antes)
	add_images("imagenesDurante", imgs_durante)
	add_images("imagenesDespues", imgs_despues)
	return files


# ---------- UI ----------
st.set_page_config(page_title="Orden de Servicio - Reporte Técnico", layout="wide")
ensure_session_defaults()

qp = get_query_params()
meta = {
	"id": (qp.get("id") or "").strip(),
	"ciudad": (qp.get("ciudad") or "").strip(),
	"nit": (qp.get("nit") or "").strip(),
	"nombreEmpresa": (qp.get("nombreEmpresa") or "").strip(),
	"POSTURL": (qp.get("POSTURL") or "").strip(),
}

# Compute deterministic verification code from URL fields
verification_code = six_digit_code_from_fields(
	id=meta.get("id"),
	ciudad=meta.get("ciudad"),
	nit=meta.get("nit"),
	nombreEmpresa=meta.get("nombreEmpresa"),
)

st.title("Reporte de Servicio Técnico")

with st.container(border=True):
	st.subheader("Datos del Cliente")
	c1, c2, c3, c4 = st.columns(4)
	c1.write(f"ID: {meta.get('id') or '—'}")
	c2.write(f"Ciudad: {meta.get('ciudad') or '—'}")
	c3.write(f"NIT: {meta.get('nit') or '—'}")
	c4.write(f"Empresa: {meta.get('nombreEmpresa') or '—'}")

	# Admin/testing: toggle to show the generated code
	if not is_http_url(meta.get("POSTURL")):
		st.warning(
			"No se recibió una POSTURL válida en la URL (?POSTURL=http(s)://...). El envío estará deshabilitado.")

with st.form("service_form"):
	st.subheader("1) Descripción del servicio técnico realizado *")
	descripcion = st.text_area(
		"Descripción", placeholder="Detalle las actividades realizadas...", height=140
	)

	st.subheader("2) Equipos y materiales instalados *")
	equipos = render_equipment_rows()

	add_clicked = st.form_submit_button(
		"➕ Agregar material",
		use_container_width=True,
	)
	if add_clicked:
		add_equipment_row()
		st.experimental_rerun()
	
	st.subheader("3) Trabajo en alturas")
	col_a, col_b = st.columns([1, 3])
	requiere_alturas = col_a.checkbox("¿Se realizó trabajo en alturas?", value=False)
	detalles_alturas = col_b.text_input(
		"Detalles (EPP utilizado, permisos, andamios, etc.)",
		placeholder="Opcional",
	)

	st.subheader("4) Observaciones generales")
	observaciones = st.text_area("Observaciones", height=120)

	st.subheader("5) Actividades pendientes / Novedades")
	actividades = st.text_area("Actividades/Novedades", height=120)

	st.subheader("6) Evidencias fotográficas *")
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

	st.subheader("7) Verificación de envío *")
	entered_code = st.text_input("Ingrese el código de verificación de 6 dígitos", max_chars=6)
	entered_digits = re.sub(r"\D", "", entered_code)
	codes_match = entered_digits == verification_code

	submitted = st.form_submit_button(
		"Enviar reporte",
		use_container_width=True,
		disabled=(not is_http_url(meta.get("POSTURL"))),
	)

if submitted:
	# Minimal validation
	errors = []
	if not descripcion.strip():
		errors.append("La descripción del servicio es obligatoria.")
	if not observaciones.strip():
		errors.append("Por favor agregue observaciones. Si no tiene, escriba 'Ninguna'.")
	if not actividades.strip():
		errors.append("Por favor agregue actividades pendientes o novedades. Si no tiene, escriba 'Ninguna'.")
	if not imgs_antes:
		errors.append("Falta al menos una imagen en la sección **Antes**.")
	if not imgs_durante:
		errors.append("Falta al menos una imagen en la sección **Durante**.")
	if not imgs_despues:
		errors.append("Falta al menos una imagen en la sección **Después**.")
	if not is_http_url(meta.get("POSTURL")):
		errors.append("POSTURL inválida o ausente.")
	if not codes_match:
		errors.append("El código de verificación no es válido.")

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
					"detalles": detalles_alturas.strip(),
				},
				observaciones=observaciones.strip(),
				actividades=actividades.strip(),
			)

			post_url = meta.get("POSTURL") or ""

			try:
				files = to_files_payload(payload, imgs_antes, imgs_durante, imgs_despues)
				# Siempre enviar multipart con archivo JSON (payload.json); incluir imágenes si existen
				resp = requests.post(post_url, files=files, timeout=60)

				st.success(f"Envío completado. Código de estado: {resp.status_code}")
				with st.expander("Respuesta del servidor"):
					st.code(resp.text or "<sin contenido>", language="json")
			except requests.RequestException as ex:
				st.error(f"Error al enviar el reporte: {ex}")

# Download JSON utility (even if not submitted)
with st.sidebar:
	st.header("Acciones")
	example_payload = make_payload(
		meta,
		descripcion="",
		equipos=[],
		trabajo_alturas={"requiere": False, "detalles": ""},
		observaciones="",
		actividades="",
	)
	st.download_button(
		label="Descargar plantilla JSON",
		data=json.dumps(example_payload, ensure_ascii=False, indent=2),
		file_name="reporte_servicio.json",
		mime="application/json",
		use_container_width=True,
	)

