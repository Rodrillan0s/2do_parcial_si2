import { describe, it, expect, vi, beforeEach } from 'vitest';
import { TestBed, ComponentFixture } from '@angular/core/testing';
import { of } from 'rxjs';
import { HttpResponse, HttpHeaders } from '@angular/common/http';
import { BackupComponent } from './backup';
import { BackupService } from '../../modules/admin/services/backup';

describe('BackupComponent - Oracle Cloud Gestor & Time Lapse Tests', () => {
  let component: BackupComponent;
  let fixture: ComponentFixture<BackupComponent>;
  let mockBackupService: any;

  beforeEach(async () => {
    mockBackupService = {
      obtenerInfoGestor: vi.fn().mockReturnValue(of({
        success: true,
        data: {
          gestor: 'Oracle Cloud',
          proveedor: 'Oracle Cloud Infrastructure (OCI)',
          region: 'sa-saopaulo-1',
          servicio: 'OCI Autonomous Database & OCI Object Storage',
          bucket_principal: 'oci://aurorastore-db-backups-sa-saopaulo-1/dumps',
          tipo_volcado: 'Oracle Cloud Binary/SQL Dump (.dump)',
          sla_disponibilidad: '99.99%',
          estado_servicio: 'OPERATIVO',
          seguridad: 'OCI Vault AES-256 + Checksum SHA-256'
        }
      })),
      obtenerEmpresas: vi.fn().mockReturnValue(of({
        success: true,
        total: 2,
        data: [
          { id_empresa: 1, nombre_empresa: 'SHOPPING BOLIVIA', razon_social: 'SHOPPING BOLIVIA S.R.L.', nit: '4045127', estado: 'ACTIVO', ciudad: 'Santa Cruz' },
          { id_empresa: 2, nombre_empresa: 'FASHIONWORLD BOLIVIA', razon_social: 'FASHIONWORLD RETAIL S.R.L.', nit: '8594021014', estado: 'ACTIVO', ciudad: 'La Paz' }
        ]
      })),
      obtenerHistorial: vi.fn().mockReturnValue(of({
        success: true,
        total: 1,
        data: [
          {
            id_backup: 'OCI-BK-2026-1108-01',
            id_empresa: null,
            nombre_empresa: 'Base de Datos Global (Multi-Tenant)',
            tipo: 'AUTOMATICO',
            frecuencia: 'Diario',
            fecha: '2026-11-08T02:00:00Z',
            tamano_mb: 142.8,
            gestor: 'Oracle Cloud',
            archivo_dump: 'aurorastore_oci_global.dump',
            checksum_sha256: 'abc123',
            estado: 'COMPLETADO'
          }
        ]
      })),
      obtenerConfiguracionAutomatica: vi.fn().mockReturnValue(of({
        success: true,
        data: {
          habilitado: true,
          frecuencia: 'dia',
          intervalo_horas: 6,
          hora_ejecucion: '02:00',
          dia_semana: 'DOMINGO',
          dia_mes: 1,
          id_empresa: null,
          retencion_dias: 30,
          gestor: 'Oracle Cloud'
        }
      })),
      generarBackupManual: vi.fn().mockReturnValue(of(new HttpResponse({
        body: new Blob(['-- ORACLE CLOUD DUMP']),
        headers: new HttpHeaders({ 'Content-Disposition': 'attachment; filename="aurorastore_oraclecloud_test.dump"' })
      }))),
      guardarConfiguracionAutomatica: vi.fn().mockReturnValue(of({
        success: true,
        message: 'Programación guardada',
        data: {}
      })),
      eliminarBackupHistorial: vi.fn().mockReturnValue(of({ success: true, message: 'Eliminado' }))
    };

    await TestBed.configureTestingModule({
      imports: [BackupComponent],
      providers: [
        { provide: BackupService, useValue: mockBackupService }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(BackupComponent);
    component = fixture.componentInstance;
  });

  it('1. Carga inicial: fija el Gestor Cloud en Oracle Cloud y consulta empresas registradas', () => {
    component.ngOnInit();
    expect(component.gestorInfo.gestor).toBe('Oracle Cloud');
    expect(component.empresas.length).toBe(2);
    expect(component.empresas[0].nombre_empresa).toBe('SHOPPING BOLIVIA');
    expect(component.historial.length).toBe(1);
    expect(component.historial[0].gestor).toBe('Oracle Cloud');
  });

  it('2. Respaldo Manual: llama al servicio y descarga el archivo .dump de Oracle Cloud', () => {
    component.ngOnInit();
    component.idEmpresaManual = 1;
    component.descargarBackupManual();

    expect(mockBackupService.generarBackupManual).toHaveBeenCalledWith(1, 'SHOPPING BOLIVIA');
    expect(component.cargandoManual).toBe(false);
  });

  it('3. Respaldo Automático: permite alternar frecuencias (hora, dia, semana, mes) y guarda en Oracle Cloud', () => {
    component.ngOnInit();
    component.configAutomatica.habilitado = true;
    component.configAutomatica.frecuencia = 'hora';
    component.configAutomatica.intervalo_horas = 3;

    component.guardarConfiguracionAutomatica();

    expect(mockBackupService.guardarConfiguracionAutomatica).toHaveBeenCalled();
    expect(component.configAutomatica.gestor).toBe('Oracle Cloud');
  });

  it('4. Preparar restauración desde historial: precarga el dump de Oracle Cloud y activa pestaña de restauración', () => {
    const item = {
      id_backup: 'OCI-BK-001',
      id_empresa: 1,
      nombre_empresa: 'SHOPPING BOLIVIA',
      tipo: 'MANUAL' as const,
      frecuencia: 'Manual',
      fecha: '2026-11-08T00:00:00Z',
      tamano_mb: 50.0,
      gestor: 'Oracle Cloud',
      archivo_dump: 'aurorastore_oraclecloud_empresa_1.dump',
      checksum_sha256: 'xyz',
      estado: 'COMPLETADO'
    };

    component.prepararRestauracionDesdeHistorial(item);

    expect(component.pestanaActiva).toBe('restauracion');
    expect(component.archivoRestaurarNombre).toBe('aurorastore_oraclecloud_empresa_1.dump');
    expect(component.idEmpresaRestaurar).toBe(1);
    expect(component.restauracionCompletada).toBe(false);
  });

  it('5. Restauración con Time Lapse: valida confirmación y no ejecuta cambios destructivos en base de datos', () => {
    component.archivoRestaurarNombre = 'test.dump';
    component.confirmacionRestaurar = false;

    // Sin confirmación no inicia
    component.iniciarRestauracionSimulada();
    expect(component.restaurando).toBe(false);

    // Con confirmación inicia el time lapse
    component.confirmacionRestaurar = true;
    component.iniciarRestauracionSimulada();
    expect(component.restaurando).toBe(true);
    expect(component.etapaRestauracionActual).toContain('Oracle Cloud');

    // Cancelar detiene el timer de simulación
    component.cancelarRestauracion();
    expect(component.restaurando).toBe(false);
  });
});
