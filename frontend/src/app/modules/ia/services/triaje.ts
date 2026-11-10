import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { AuthService } from '../../auth/services/auth'; 

export interface RespuestaTriajeIA {
  respuesta_al_cliente: string;
  escalar_a_humano: boolean;
  resumen_oculto_para_mecanico: string;
  nivel_riesgo_detectado: string;
}

export interface RespuestaApiTriaje {
  success: boolean;
  data: RespuestaTriajeIA;
}

export interface InicioTriaje {
  id_conversacion: number;
  mensaje_ia: string;
}

@Injectable({
  providedIn: 'root'
})
export class TriajeService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private apiUrl = environment.apiUrl;

  private getHeaders(): HttpHeaders {
    const token = this.authService.obtenerToken();
    return token ? new HttpHeaders({ 'Authorization': `Bearer ${token}` }) : new HttpHeaders();
  }

  iniciarChat(): Observable<InicioTriaje> {
    return this.http.post<InicioTriaje>(`${this.apiUrl}/api/triaje/iniciar`, {}, { headers: this.getHeaders() });
  }

  enviarMensaje(idConversacion: number, mensaje: string): Observable<RespuestaApiTriaje> {
    return this.http.post<RespuestaApiTriaje>(
      `${this.apiUrl}/api/triaje/${idConversacion}/mensaje`, 
      { mensaje }, 
      { headers: this.getHeaders() }
    );
  }
}