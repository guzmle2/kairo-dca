"""Límites absolutos de la tesis (R4): en código, no modificables desde configuración.

La configuración puede ser más estricta que estos valores, nunca más laxa. Subir el techo exige
cambiar este fichero con decisión del dueño del producto. La lista cerrada de ISIN vive en el perfil
de país (``config/perfil_<pais>.json``); añadir un ISIN exige también decisión del dueño.
"""

from decimal import Decimal

COMISION_MAX_POR_APORTACION_PCT = Decimal("0.50")
