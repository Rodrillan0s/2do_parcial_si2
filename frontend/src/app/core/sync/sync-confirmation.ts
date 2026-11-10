/** The receipt is evidence returned by the authenticated API, not a local note. */
export interface OperationIdentity {
  operation_id: string;
  user_id: number;
  tenant_id: number;
  kind: string;
  scope_key: string;
  branch_id?: number | null;
  entity_id?: string | number | null;
  payload: Record<string, any>;
  created_at: string;
}

export interface VerifiedSyncResult {
  operation_id: string;
  kind: string;
  status: string;
  http_status: number;
  confirmation_verified?: boolean;
  confirmation?: {
    operation_id: string;
    id_usuario: number;
    id_empresa: number;
    request_hash: string;
  };
  data?: any;
}

export function hasVerifiedConfirmation(op: OperationIdentity, result: VerifiedSyncResult): boolean {
  const receipt = result?.confirmation;
  if (result?.status !== 'synced' || result.confirmation_verified !== true ||
      !Number.isInteger(result.http_status) || result.http_status < 200 || result.http_status >= 300 ||
      result.operation_id !== op.operation_id || result.kind !== op.kind ||
      receipt?.operation_id !== op.operation_id || receipt.id_usuario !== op.user_id ||
      receipt.id_empresa !== op.tenant_id || !/^[0-9a-f]{64}$/.test(receipt.request_hash) ||
      !result.data || typeof result.data !== 'object' || Array.isArray(result.data)) return false;

  const positiveId = (value: unknown) => Number.isSafeInteger(value) && Number(value) > 0;
  if (op.kind === 'VENTA_CONTADO') {
    return positiveId(result.data.id_venta) && positiveId(result.data.id_pago) &&
      result.data.estado_venta === 'PAGADO';
  }
  if (op.kind === 'RESERVA_SOLICITUD') {
    return positiveId(result.data.id_reserva) && typeof result.data.codigo_reserva === 'string' &&
      result.data.codigo_reserva.length > 0;
  }
  return ['CART_ADD_ITEM', 'CART_UPDATE_QTY', 'CART_REMOVE_ITEM', 'CART_CLEAR'].includes(op.kind);
}

/** Compare immutable request content without depending on property order. */
export function sameOperationRequest(a: OperationIdentity, b: OperationIdentity): boolean {
  const canonical = (value: any): string => {
    if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
    if (value && typeof value === 'object') {
      return '{' + Object.keys(value).filter(k => value[k] !== undefined).sort()
        .map(k => JSON.stringify(k) + ':' + canonical(value[k])).join(',') + '}';
    }
    return JSON.stringify(value) ?? 'null';
  };
  const envelope = (op: OperationIdentity) => [op.operation_id, op.user_id, op.tenant_id, op.kind,
    op.scope_key, op.branch_id ?? null, op.entity_id ?? null, op.payload, op.created_at];
  return canonical(envelope(a)) === canonical(envelope(b));
}
