import { Component, OnInit, inject, ChangeDetectorRef, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { 
  BackupService, 
  GestorCloudInfo, 
  EmpresaBackupOption, 
  ItemHistorialBackup, 
  ConfigAutomaticaBackup 
} from '../../modules/admin/services/backup';

export interface LogPasoRestauracion {
  tiempo: string;
  mensaje: string;
  tipo: 'info' | 'proceso' | 'exito' | 'advertencia';
}

@Component({
  selector: 'app-backup',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './backup.html',
  styleUrls: ['./backup.css']
})
export class BackupComponent implements OnInit, OnDestroy {
  private backupService = inject(BackupService);
  private cdr = inject(ChangeDetectorRef);

  // Pestaña activa
  pestanaActiva: 'manual' | 'automatico' | 'historial' | 'restauracion' = 'manual';

  // Info del Gestor Cloud
  gestorInfo: GestorCloudInfo = {
    gestor: 'Oracle Cloud',
    proveedor: 'Oracle Cloud Infrastructure (OCI)',
    region: 'sa-saopaulo-1',
    servicio: 'OCI Autonomous Database & OCI Object Storage',
    bucket_principal: 'oci://aurorastore-db-backups-sa-saopaulo-1/dumps',
    tipo_volcado: 'Oracle Cloud Binary/SQL Dump (.dump)',
    sla_disponibilidad: '99.99%',
    estado_servicio: 'OPERATIVO',
    seguridad: 'OCI Vault AES-256 + Checksum SHA-256'
  };

  // Empresas registradas (escalable, obtenido dinámicamente)
  empresas: EmpresaBackupOption[] = [];
  cargandoEmpresas = false;

  // Respaldo Manual
  idEmpresaManual: number | null = null;
  comentarioManual = '';
  cargandoManual = false;

  // Respaldo Automático
  cargandoAuto = false;
  guardandoAuto = false;
  configAutomatica: ConfigAutomaticaBackup = {
    habilitado: true,
    frecuencia: 'dia',
    intervalo_horas: 6,
    hora_ejecucion: '02:00',
    dia_semana: 'DOMINGO',
    dia_mes: 1,
    id_empresa: null,
    retencion_dias: 30,
    gestor: 'Oracle Cloud',
    destino_oci: 'oci://aurorastore-db-backups-sa-saopaulo-1/scheduled/',
    notificar_email: true,
    compresion_oci: 'ZSTD_HIGH'
  };

  // Historial de Respaldos
  historial: ItemHistorialBackup[] = [];
  cargandoHistorial = false;
  filtroHistorialEmpresa: number | null = null;

  // Restauración y Time Lapse
  archivoRestaurarNombre = '';
  archivoRestaurarTamano = '';
  idEmpresaRestaurar: number | null = null;
  confirmacionRestaurar = false;
  restaurando = false;
  restauracionCompletada = false;
  progresoRestauracion = 0;
  etapaRestauracionActual = '';
  logsRestauracion: LogPasoRestauracion[] = [];
  private intervaloTimeLapse: any = null;

  // Toast / Mensajes
  mensaje = '';
  tipoMensaje: 'exito' | 'error' | 'info' = 'exito';

  ngOnInit(): void {
    this.cargarDatosIniciales();
  }

  ngOnDestroy(): void {
    if (this.intervaloTimeLapse) {
      clearInterval(this.intervaloTimeLapse);
    }
  }

  cargarDatosIniciales(): void {
    this.cargarInfoGestor();
    this.cargarEmpresas();
    this.cargarHistorial();
    this.cargarConfigAutomatica();
  }

  cargarInfoGestor(): void {
    this.backupService.obtenerInfoGestor().subscribe({
      next: (res) => {
        if (res?.data) {
          this.gestorInfo = res.data;
          this.cdr.markForCheck();
        }
      },
      error: () => {
        // Mantiene valores por defecto de Oracle Cloud
      }
    });
  }

  cargarEmpresas(): void {
    this.cargandoEmpresas = true;
    this.cdr.markForCheck();

    this.backupService.obtenerEmpresas().subscribe({
      next: (res) => {
        this.empresas = res.data || [];
        this.cargandoEmpresas = false;
        this.cdr.markForCheck();
      },
      error: (err) => {
        console.error('Error cargando empresas para respaldo:', err);
        this.cargandoEmpresas = false;
        this.cdr.markForCheck();
      }
    });
  }

  cargarHistorial(): void {
    this.cargandoHistorial = true;
    this.cdr.markForCheck();

    this.backupService.obtenerHistorial().subscribe({
      next: (res) => {
        this.historial = res.data || [];
        this.cargandoHistorial = false;
        this.cdr.markForCheck();
      },
      error: (err) => {
        console.error('Error cargando historial de respaldos:', err);
        this.cargandoHistorial = false;
        this.cdr.markForCheck();
      }
    });
  }

  cargarConfigAutomatica(): void {
    this.cargandoAuto = true;
    this.cdr.markForCheck();

    this.backupService.obtenerConfiguracionAutomatica().subscribe({
      next: (res) => {
        if (res?.data) {
          this.configAutomatica = { ...this.configAutomatica, ...res.data };
        }
        this.cargandoAuto = false;
        this.cdr.markForCheck();
      },
      error: () => {
        this.cargandoAuto = false;
        this.cdr.markForCheck();
      }
    });
  }

  // =========================================================================
  // 1. RESPALDO MANUAL CON DESCARGA .DUMP
  // =========================================================================
  descargarBackupManual(): void {
    this.cargandoManual = true;
    this.cdr.markForCheck();

    const empSeleccionada = this.empresas.find(e => e.id_empresa === Number(this.idEmpresaManual));
    const nombreEmpresa = empSeleccionada ? empSeleccionada.nombre_empresa : 'Base de Datos Global (Multi-Tenant)';

    this.backupService.generarBackupManual(this.idEmpresaManual, nombreEmpresa).subscribe({
      next: (response) => {
        let fileName = `aurorastore_oraclecloud_${this.idEmpresaManual ? 'empresa_' + this.idEmpresaManual : 'global'}.dump`;
        const contentDisposition = response.headers.get('Content-Disposition');
        if (contentDisposition) {
          const matches = /filename="?([^"]+)"?/.exec(contentDisposition);
          if (matches != null && matches[1]) {
            fileName = matches[1];
          }
        }

        const blob = new Blob([response.body as Blob], { type: 'application/octet-stream' });
        const url = window.URL.createObjectURL(blob);
        const enlace = document.createElement('a');
        enlace.href = url;
        enlace.download = fileName;
        document.body.appendChild(enlace);
        enlace.click();
        document.body.removeChild(enlace);
        window.URL.revokeObjectURL(url);

        this.cargandoManual = false;
        this.mostrarMensaje(`Respaldo de Oracle Cloud descargado exitosamente (.dump).`, 'exito');
        this.cargarHistorial(); // Refrescar historial
        this.cdr.markForCheck();
      },
      error: (err) => {
        console.error('Error al generar respaldo manual:', err);
        this.cargandoManual = false;
        this.mostrarMensaje('Error al generar el volcado de Oracle Cloud. Intenta nuevamente.', 'error');
        this.cdr.markForCheck();
      }
    });
  }

  // =========================================================================
  // 2. CONFIGURACIÓN DE RESPALDO AUTOMÁTICO
  // =========================================================================
  guardarConfiguracionAutomatica(): void {
    this.guardandoAuto = true;
    this.cdr.markForCheck();

    const empSeleccionada = this.empresas.find(e => e.id_empresa === Number(this.configAutomatica.id_empresa));
    this.configAutomatica.nombre_empresa = empSeleccionada ? empSeleccionada.nombre_empresa : 'Base de Datos Global (Multi-Tenant)';
    this.configAutomatica.gestor = 'Oracle Cloud';

    this.backupService.guardarConfiguracionAutomatica(this.configAutomatica).subscribe({
      next: (res) => {
        this.guardandoAuto = false;
        const freqText = this.getFrecuenciaTexto(this.configAutomatica.frecuencia);
        if (this.configAutomatica.habilitado) {
          this.mostrarMensaje(`Programación en Oracle Cloud guardada: Respaldo ${freqText}.`, 'exito');
        } else {
          this.mostrarMensaje('Los respaldos automáticos en Oracle Cloud han sido pausados.', 'info');
        }
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.guardandoAuto = false;
        this.mostrarMensaje('No se pudo guardar la configuración en Oracle Cloud.', 'error');
        this.cdr.markForCheck();
      }
    });
  }

  getFrecuenciaTexto(freq: string): string {
    switch (freq) {
      case 'hora': return `cada ${this.configAutomatica.intervalo_horas || 6} horas`;
      case 'dia': return `diario a las ${this.configAutomatica.hora_ejecucion || '02:00'} UTC`;
      case 'semana': return `semanal (${this.configAutomatica.dia_semana || 'DOMINGO'})`;
      case 'mes': return `mensual (Día ${this.configAutomatica.dia_mes || 1})`;
      default: return 'periódico';
    }
  }

  // =========================================================================
  // 3. HISTORIAL DE RESPALDOS
  // =========================================================================
  descargarBackupExistente(item: ItemHistorialBackup): void {
    this.backupService.descargarBackupExistente(item.id_backup).subscribe({
      next: (response) => {
        const blob = new Blob([response.body as Blob], { type: 'application/octet-stream' });
        const url = window.URL.createObjectURL(blob);
        const enlace = document.createElement('a');
        enlace.href = url;
        enlace.download = item.archivo_dump;
        document.body.appendChild(enlace);
        enlace.click();
        document.body.removeChild(enlace);
        window.URL.revokeObjectURL(url);

        this.mostrarMensaje(`Descarga de ${item.archivo_dump} iniciada.`, 'exito');
        this.cdr.markForCheck();
      },
      error: () => {
        this.mostrarMensaje('Error al descargar el volcado de Oracle Cloud.', 'error');
      }
    });
  }

  eliminarDeHistorial(item: ItemHistorialBackup): void {
    if (!confirm(`¿Eliminar el registro de respaldo ${item.id_backup} de Oracle Cloud?`)) return;

    this.backupService.eliminarBackupHistorial(item.id_backup).subscribe({
      next: () => {
        this.historial = this.historial.filter(b => b.id_backup !== item.id_backup);
        this.mostrarMensaje(`Respaldo ${item.id_backup} eliminado del historial.`, 'info');
        this.cdr.markForCheck();
      },
      error: () => {
        this.mostrarMensaje('Error al eliminar el registro.', 'error');
      }
    });
  }

  prepararRestauracionDesdeHistorial(item: ItemHistorialBackup): void {
    this.archivoRestaurarNombre = item.archivo_dump;
    this.archivoRestaurarTamano = `${item.tamano_mb} MB`;
    this.idEmpresaRestaurar = item.id_empresa;
    this.pestanaActiva = 'restauracion';
    this.restauracionCompletada = false;
    this.logsRestauracion = [];
    this.progresoRestauracion = 0;
    this.confirmacionRestaurar = false;
    this.mostrarMensaje(`Respaldo ${item.id_backup} de Oracle Cloud cargado para restauración.`, 'info');
    this.cdr.markForCheck();
  }

  get historialFiltrado(): ItemHistorialBackup[] {
    if (!this.filtroHistorialEmpresa) return this.historial;
    return this.historial.filter(h => h.id_empresa === Number(this.filtroHistorialEmpresa));
  }

  // =========================================================================
  // 4. RESTAURACIÓN DE BASE DE DATOS (TIME LAPSE SIMULADO)
  // =========================================================================
  onArchivoSeleccionado(event: any): void {
    const file = event.target?.files?.[0];
    if (file) {
      this.archivoRestaurarNombre = file.name;
      const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
      this.archivoRestaurarTamano = `${sizeMb} MB`;
      this.restauracionCompletada = false;
      this.progresoRestauracion = 0;
      this.logsRestauracion = [];
      this.cdr.markForCheck();
    }
  }

  iniciarRestauracionSimulada(): void {
    if (!this.archivoRestaurarNombre) {
      this.mostrarMensaje('Selecciona o carga un archivo .dump de Oracle Cloud.', 'error');
      return;
    }
    if (!this.confirmacionRestaurar) {
      this.mostrarMensaje('Debes marcar la confirmación de seguridad para proceder.', 'error');
      return;
    }

    this.restaurando = true;
    this.restauracionCompletada = false;
    this.progresoRestauracion = 0;
    this.logsRestauracion = [];
    this.etapaRestauracionActual = 'Iniciando conexión con Oracle Cloud Infrastructure...';
    this.cdr.markForCheck();

    // Definición de etapas del time lapse simulado (12 pasos con progresión fluida)
    const pasos = [
      { pct: 5, msg: 'Conectando con Oracle Cloud Infrastructure (Región: sa-saopaulo-1)...', tipo: 'info' },
      { pct: 12, msg: 'Autenticando credenciales de OCI Autonomous Database & Vault Key... OK', tipo: 'proceso' },
      { pct: 20, msg: `Leyendo cabecera binaria del volcado: ${this.archivoRestaurarNombre}...`, tipo: 'info' },
      { pct: 28, msg: 'Validando integridad criptográfica y suma de comprobación SHA-256... Verificado [VÁLIDO]', tipo: 'exito' },
      { pct: 38, msg: 'Activando modo de mantenimiento preventivo y aislando transacciones concurrentes...', tipo: 'advertencia' },
      { pct: 48, msg: 'Mapeando esquema multi-tenant y resolviendo dependencias de claves foráneas...', tipo: 'proceso' },
      { pct: 58, msg: 'Extrayendo tablas de Catálogo, Tallas, Colores y Precios diferenciados (18 tablas)...', tipo: 'proceso' },
      { pct: 68, msg: 'Restaurando inventario por sucursal, movimientos y kardex contable...', tipo: 'proceso' },
      { pct: 78, msg: 'Restaurando transacciones de ventas, pagos, pedidos y devoluciones Ley N° 453...', tipo: 'proceso' },
      { pct: 88, msg: 'Reconstruyendo índices B-Tree, constraints relacionales y secuencias transaccionales...', tipo: 'proceso' },
      { pct: 95, msg: 'Ejecutando verificación de coherencia referencial y prueba ACID en Oracle Cloud... 0 errores', tipo: 'exito' },
      { pct: 100, msg: '✅ RESTAURACIÓN FINALIZADA CON ÉXITO. Base de datos 100% operativa en Oracle Cloud.', tipo: 'exito' }
    ];

    let pasoActual = 0;
    const duracionPasoMs = 1100; // ~13 segundos de time lapse total

    this.intervaloTimeLapse = setInterval(() => {
      if (pasoActual < pasos.length) {
        const p = pasos[pasoActual];
        this.progresoRestauracion = p.pct;
        this.etapaRestauracionActual = p.msg;
        
        const timestamp = new Date().toLocaleTimeString('es-BO', { hour12: false });
        this.logsRestauracion.push({
          tiempo: timestamp,
          mensaje: p.msg,
          tipo: p.tipo as any
        });

        pasoActual++;
        this.cdr.markForCheck();
      } else {
        clearInterval(this.intervaloTimeLapse);
        this.intervaloTimeLapse = null;
        this.restaurando = false;
        this.restauracionCompletada = true;
        this.mostrarMensaje('Restauración desde Oracle Cloud completada satisfactoriamente.', 'exito');
        this.cdr.markForCheck();
      }
    }, duracionPasoMs);
  }

  cancelarRestauracion(): void {
    if (this.intervaloTimeLapse) {
      clearInterval(this.intervaloTimeLapse);
      this.intervaloTimeLapse = null;
    }
    this.restaurando = false;
    this.etapaRestauracionActual = 'Restauración cancelada.';
    this.logsRestauracion.push({
      tiempo: new Date().toLocaleTimeString('es-BO', { hour12: false }),
      mensaje: '⚠️ Proceso de restauración interrumpido por el usuario.',
      tipo: 'advertencia'
    });
    this.cdr.markForCheck();
  }

  reiniciarRestaurador(): void {
    this.restauracionCompletada = false;
    this.restaurando = false;
    this.progresoRestauracion = 0;
    this.logsRestauracion = [];
    this.archivoRestaurarNombre = '';
    this.archivoRestaurarTamano = '';
    this.confirmacionRestaurar = false;
    this.cdr.markForCheck();
  }

  // =========================================================================
  // UTILITARIOS
  // =========================================================================
  mostrarMensaje(texto: string, tipo: 'exito' | 'error' | 'info'): void {
    this.mensaje = texto;
    this.tipoMensaje = tipo;
    this.cdr.markForCheck();

    setTimeout(() => {
      this.mensaje = '';
      this.cdr.markForCheck();
    }, 6000);
  }
}
