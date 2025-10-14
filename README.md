# Syntesys Service Order – Streamlit App

Aplicación Streamlit para diligenciar un reporte de servicio técnico. Se activa con parámetros en la URL y al enviar hace POST a la URL indicada.

## Requisitos

- Python 3.9+
- Paquetes: ver `requirements.txt`

## Instalación

```bash
# Activar el entorno (opcional si ya usa venv en este repo)
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

## Ejecutar

```bash
streamlit run app.py
```

Luego abra el navegador con una URL incluyendo los parámetros requeridos:

```
http://localhost:8501/?id=123&ciudad=Bogota&nit=900123456&nombreEmpresa=EmpresaXYZ&POSTURL=https://tu-api/endpoint
```

Parámetros soportados por URL:

- id: Identificador de la orden o cliente
- ciudad
- nit
- nombreEmpresa
- POSTURL: Endpoint al que se enviará el formulario

## Campos del formulario

- Descripción del servicio técnico realizado
- Equipos & materiales instalados (múltiples ítems):
  - nombre, cantidad, unidad, marca, modelo, serial, observaciones
- Trabajo en alturas (checkbox + detalles)
- Observaciones generales
- Actividades pendientes / Novedades
- Evidencias fotográficas: Antes, Durante, Después (múltiples imágenes por sección)

## Envío de datos

Al presionar “Enviar reporte” se realiza un POST a `POSTURL` con `multipart/form-data`:

- Parte `payload` (archivo `payload.json` con el JSON)
- Partes `imagenesAntes`, `imagenesDurante`, `imagenesDespues` (0..n archivos)

### Estructura del JSON

```json
{
  "metadata": {
    "id": "...",
    "ciudad": "...",
    "nit": "...",
    "nombreEmpresa": "...",
    "submittedAt": "2025-10-04T00:00:00Z"
  },
  "descripcionServicio": "...",
  "equiposMaterialesInstalados": [
    {
      "nombre": "...",
      "cantidad": 1,
      "unidad": "...",
      "marca": "...",
      "modelo": "...",
      "serial": "...",
      "observaciones": "..."
    }
  ],
  "trabajoEnAlturas": { "requiere": false, "detalles": "..." },
  "observacionesGenerales": "...",
  "actividadesPendientesONovedades": "..."
}
```

## Notas

- Si `POSTURL` no es un `http(s)://` válido, el botón de envío queda deshabilitado.
- Puede descargar un ejemplo de plantilla JSON desde la barra lateral.
- Timeout del POST: 60s para multipart.

## Pruebas rápidas del receptor (opcional)

- Puede usar un endpoint temporal (por ejemplo https://webhook.site/) en `POSTURL` para ver el contenido recibido.
