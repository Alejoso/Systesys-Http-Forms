import re
import unicodedata
from typing import Optional


def normalize(value: Optional[str]) -> str:
    if value is None:
        return ""
    s = str(value)
    s = unicodedata.normalize("NFD", s)
    s = re.sub(r"[\u0300-\u036f]", "", s)  # quita diacríticos
    s = " ".join(s.strip().split())  # colapsa espacios
    return s.upper()


def fnv1a32(input_str: str) -> int:
    """FNV-1a 32-bit con mezcla estilo JS y procesando code units UTF-16
    para emular charCodeAt de JavaScript.
    """
    h = 0x811C9DC5
    b = input_str.encode("utf-16le", errors="surrogatepass")
    for i in range(0, len(b), 2):
        cu = b[i] | (b[i + 1] << 8)  # code unit (0..65535)
        h ^= cu
        # h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) >>> 0 en JS
        h = (h + ((h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24))) & 0xFFFFFFFF
    return h & 0xFFFFFFFF


def six_digit_code_from_fields(*, id: Optional[str], ciudad: Optional[str], nit: Optional[str], nombreEmpresa: Optional[str]) -> str:
    n_id = normalize(id)
    n_city = normalize(ciudad)
    n_company = normalize(nombreEmpresa)
    n_nit = re.sub(r"\D", "", str(nit or ""))  # solo dígitos

    sep = "\u241F"  # separador para mantener paridad con JS (carácter U+241F)
    payload = sep.join([n_id, n_city, n_nit, n_company])

    h = fnv1a32(payload)
    num = h % 1_000_000
    return f"{num:06d}"


__all__ = [
    "normalize",
    "fnv1a32",
    "six_digit_code_from_fields",
]
