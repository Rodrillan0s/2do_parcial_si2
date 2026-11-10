import { Directive, Input, TemplateRef, ViewContainerRef, inject, effect } from '@angular/core';
import { AuthService } from '../services/auth';

@Directive({
  selector: '[hasPermission]',
  standalone: true
})
export class HasPermissionDirective {
  private templateRef = inject(TemplateRef<any>);
  private viewContainer = inject(ViewContainerRef);
  private authService = inject(AuthService);

  private currentPermission: string | string[] = [];
  private hasView = false;

  constructor() {
    // Reaccionar a cambios de los permisos del usuario usando Angular Signals effect
    effect(() => {
      // Registrar dependencia reactiva del signal de permisos
      this.authService.permissions();
      this.updateView();
    });
  }

  @Input() set hasPermission(permission: string | string[]) {
    this.currentPermission = permission;
    this.updateView();
  }

  private updateView(): void {
    let allowed = false;

    if (typeof this.currentPermission === 'string') {
      allowed = this.authService.hasPermission(this.currentPermission);
    } else if (Array.isArray(this.currentPermission)) {
      allowed = this.authService.hasAnyPermission(this.currentPermission);
    }

    if (allowed && !this.hasView) {
      this.viewContainer.createEmbeddedView(this.templateRef);
      this.hasView = true;
    } else if (!allowed && this.hasView) {
      this.viewContainer.clear();
      this.hasView = false;
    }
  }
}
