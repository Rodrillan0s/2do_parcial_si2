import io
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, Body
from fastapi.responses import StreamingResponse
from app.modules.admin.services import backup_services
from app.core.security import verificar_token

router = APIRouter(tags=["Backups"])


@router.get('/gestor')
def obtener_info_gestor(token_data: dict = Depends(verificar_token)):
    """Retorna información del gestor de base de datos en nube: Oracle Cloud."""
    return {
        "success": True,
        "data": backup_services.obtener_info_gestor_cloud()
    }


@router.get('/empresas')
def listar_empresas_para_backup(token_data: dict = Depends(verificar_token)):
    """Consulta dinámica y escalable de empresas registradas en la base de datos."""
    empresas = backup_services.obtener_empresas_registradas()
    return {
        "success": True,
        "total": len(empresas),
        "data": empresas
    }


@router.get('/historial')
def obtener_historial_backups(token_data: dict = Depends(verificar_token)):
    """Retorna el historial de copias de seguridad de Oracle Cloud."""
    historial = backup_services.obtener_historial_backups()
    return {
        "success": True,
        "total": len(historial),
        "data": historial
    }


@router.post('/manual')
def generar_backup_manual_post(
    payload: Optional[Dict[str, Any]] = Body(default={}),
    token_data: dict = Depends(verificar_token)
):
    """
    Genera y descarga un archivo .dump de Oracle Cloud para una empresa específica o global.
    Actualiza automáticamente el historial.
    """
    id_empresa = payload.get("id_empresa") if payload else None
    nombre_empresa = payload.get("nombre_empresa") if payload else None

    if id_empresa == 0 or id_empresa == "0":
        id_empresa = None

    try:
        res = backup_services.generar_contenido_dump_oracle_cloud(
            id_empresa=id_empresa,
            nombre_empresa=nombre_empresa
        )
        buffer_memoria = io.BytesIO(res['file_bytes'])

        return StreamingResponse(
            buffer_memoria,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{res["file_name"]}"',
                "X-Backup-Id": res["backup_info"]["id_backup"],
                "X-Gestor-Cloud": "Oracle Cloud"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando volcado de Oracle Cloud: {str(e)}")


@router.get('/manual')
def generar_backup_manual_get(
    id_empresa: Optional[int] = Query(None),
    token_data: dict = Depends(verificar_token)
):
    """Compatibilidad GET para generar y descargar volcado .dump directo."""
    try:
        res = backup_services.generar_contenido_dump_oracle_cloud(id_empresa=id_empresa)
        buffer_memoria = io.BytesIO(res['file_bytes'])

        return StreamingResponse(
            buffer_memoria,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{res["file_name"]}"',
                "X-Backup-Id": res["backup_info"]["id_backup"],
                "X-Gestor-Cloud": "Oracle Cloud"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando respaldo: {str(e)}")


@router.get('/download/{id_backup}')
def descargar_backup_existente(
    id_backup: str,
    token_data: dict = Depends(verificar_token)
):
    """Descarga el archivo .dump de un respaldo ya registrado en el historial."""
    historial = backup_services.obtener_historial_backups()
    item = next((b for b in historial if b["id_backup"] == id_backup), None)
    if not item:
        raise HTTPException(status_code=404, detail="Respaldo no encontrado en el historial de Oracle Cloud.")

    res = backup_services.generar_contenido_dump_oracle_cloud(
        id_empresa=item.get("id_empresa"),
        nombre_empresa=item.get("nombre_empresa")
    )
    buffer_memoria = io.BytesIO(res['file_bytes'])

    return StreamingResponse(
        buffer_memoria,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{item["archivo_dump"]}"',
            "X-Backup-Id": item["id_backup"],
            "X-Gestor-Cloud": "Oracle Cloud"
        }
    )


@router.delete('/historial/{id_backup}')
def eliminar_backup_de_historial(
    id_backup: str,
    token_data: dict = Depends(verificar_token)
):
    """Elimina un respaldo del historial."""
    eliminado = backup_services.eliminar_backup_historial(id_backup)
    if not eliminado:
        raise HTTPException(status_code=404, detail="El respaldo no existe o ya fue eliminado.")
    return {
        "success": True,
        "message": f"Respaldo {id_backup} eliminado del historial de Oracle Cloud."
    }


@router.get('/automatico')
def obtener_configuracion_cron(token_data: dict = Depends(verificar_token)):
    """Retorna la configuración actual del programador de respaldos en Oracle Cloud."""
    config = backup_services.obtener_configuracion_automatica()
    return {
        "success": True,
        "data": config
    }


@router.post('/automatico')
def guardar_configuracion_cron(
    payload: Dict[str, Any] = Body(...),
    token_data: dict = Depends(verificar_token)
):
    """Guarda la configuración de respaldos automáticos en Oracle Cloud."""
    config_actualizada = backup_services.guardar_configuracion_automatica(payload)
    frecuencia = config_actualizada.get("frecuencia", "dia").capitalize()
    return {
        "success": True,
        "message": f"Programación de respaldo automático en Oracle Cloud guardada exitosamente (Frecuencia: {frecuencia}).",
        "data": config_actualizada
    }


@router.post('/restaurar/simular')
def simular_restauracion_endpoint(
    payload: Dict[str, Any] = Body(...),
    token_data: dict = Depends(verificar_token)
):
    """
    Endpoint para iniciar la simulación visual de restauración de Oracle Cloud.
    No ejecuta ninguna acción destructiva en la base de datos real.
    """
    archivo_dump = payload.get("archivo_dump", "backup_oraclecloud.dump")
    id_empresa = payload.get("id_empresa")
    res = backup_services.simular_restauracion_oracle_cloud(archivo_dump, id_empresa)
    return {
        "success": True,
        "data": res
    }
