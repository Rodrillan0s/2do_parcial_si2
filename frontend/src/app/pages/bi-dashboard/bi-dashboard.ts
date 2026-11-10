import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { BiDashboardService, MetricasBI } from '../../services/bi-dashboard';
import { AuthService } from '../../services/auth';

@Component({
  selector: 'app-bi-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './bi-dashboard.html'
})
export class BiDashboardComponent implements OnInit {
  private biService = inject(BiDashboardService);
  private authService = inject(AuthService);

  cargando: boolean = true;
  procesandoETL: boolean = false;
  metricas: MetricasBI | null = null;
  // LA VARIABLE ESTÁ AQUÍ CON 'l' MINÚSCULA
  mensajeEtl: string | null = null;

  ngOnInit() {
    this.cargarDashboard();
  }

  cargarDashboard() {
    this.cargando = true;
    this.biService.obtenerMetricas().subscribe({
      next: (res) => {
        this.metricas = res.data;
        this.cargando = false;
      },
      error: (err) => {
        console.error('Error cargando KPIs:', err);
        this.cargando = false;
      }
    });
  }

  ejecutarETL() {
    this.procesandoETL = true;
    this.mensajeEtl = null;
    
    this.biService.ejecutarProcesoETL().subscribe({
      next: (res) => {
        this.mensajeEtl = res.message;
        this.procesandoETL = false;
        this.cargarDashboard();
      },
      error: (err) => {
        this.mensajeEtl = 'Error al ejecutar el proceso ETL.';
        this.procesandoETL = false;
      }
    });
  }

  esAdministrador(): boolean {
    const usuario = this.authService.obtenerUsuario();
    return usuario?.nombre_rol === 'ADMINISTRADOR';
  }
}