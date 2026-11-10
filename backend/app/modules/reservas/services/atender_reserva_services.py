from typing import Optional, Dict, Any, List
from app.modules.reservas.repos.atender_reserva_repos import (
    listar_reservas_para_atender,
    obtener_reserva_para_atender,
    cobrar_y_atender_reserva_pos,
    atender_reserva_pagada,
    atender_reserva
)


def listar_reservas_atender(
    id_empresa: int,
    id_sucursal: int,
    busqueda: Optional[str] = None,
    estado: Optional[str] = None
) -> Dict[str, Any]:
    if not id_sucursal:
        return {
            "success": False,
            "message": "El ID de la sucursal es obligatorio."
        }

    return listar_reservas_para_atender(
        id_empresa=id_empresa,
        id_sucursal=id_sucursal,
        busqueda=busqueda,
        estado=estado
    )


def obtener_reserva_atender(
    id_reserva: int,
    id_empresa: int,
    id_sucursal: int
) -> Dict[str, Any]:
    if not id_reserva:
        return {
            "success": False,
            "message": "El ID de la reserva es obligatorio."
        }

    if not id_sucursal:
        return {
            "success": False,
            "message": "El ID de la sucursal es obligatorio."
        }

    return obtener_reserva_para_atender(
        id_reserva=id_reserva,
        id_empresa=id_empresa,
        id_sucursal=id_sucursal
    )


def ejecutar_cobro_reserva_pos(
    id_reserva: int,
    id_empresa: int,
    id_sucursal: int,
    id_usuario: int,
    datos_cobro: Dict[str, Any]
) -> Dict[str, Any]:
    if not id_reserva:
        return {
            "success": False,
            "message": "El ID de la reserva es obligatorio."
        }
    if not id_sucursal:
        return {
            "success": False,
            "message": "El ID de la sucursal es obligatorio."
        }

    return cobrar_y_atender_reserva_pos(
        id_reserva=id_reserva,
        id_empresa=id_empresa,
        id_sucursal=id_sucursal,
        id_usuario=id_usuario,
        datos_cobro=datos_cobro
    )


def ejecutar_entrega_reserva_pagada(
    id_reserva: int,
    id_empresa: int,
    id_sucursal: int,
    id_usuario: Optional[int] = None,
    items_seleccionados: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    if not id_reserva:
        return {
            "success": False,
            "message": "El ID de la reserva es obligatorio."
        }
    if not id_sucursal:
        return {
            "success": False,
            "message": "El ID de la sucursal es obligatorio."
        }

    return atender_reserva_pagada(
        id_reserva=id_reserva,
        id_empresa=id_empresa,
        id_sucursal=id_sucursal,
        id_usuario=id_usuario,
        items_seleccionados=items_seleccionados
    )


def ejecutar_atencion_reserva(
    id_reserva: int,
    id_empresa: int,
    id_sucursal: int
) -> Dict[str, Any]:
    if not id_reserva:
        return {
            "success": False,
            "message": "El ID de la reserva es obligatorio."
        }

    if not id_sucursal:
        return {
            "success": False,
            "message": "El ID de la sucursal es obligatorio."
        }

    return atender_reserva(
        id_reserva=id_reserva,
        id_empresa=id_empresa,
        id_sucursal=id_sucursal
    )