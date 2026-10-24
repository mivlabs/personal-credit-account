import type { components } from './api-types';
export type Schemas = components['schemas'];
export type Application = Schemas['ApplicationOut'];
export type User = Schemas['UserOut'];
export class ApiError extends Error {
 constructor(public status: number, public problem: Schemas['ProblemDetail']) { super(problem.detail || problem.title || 'Не удалось выполнить запрос'); }
}
const pendingKeys = new Map<string,string>();
export async function api<T>(path: string, body?: unknown, method?: string, key?: string): Promise<T> {
 const token = sessionStorage.getItem('creditToken');
 const signature = token + path + JSON.stringify(body);
 const replayable = /\/(offer\/accept|sign|missing-info)$/.test(path) && method !== 'GET';
 if (replayable && !key) { key = pendingKeys.get(signature) || crypto.randomUUID(); pendingKeys.set(signature,key); }
 const response = await fetch('/api/v1' + path, {method: method || (body === undefined ? 'GET' : 'POST'), headers: { ...(token ? { Authorization: 'Bearer ' + token } : {}), ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}), ...(key ? { 'Idempotency-Key': key } : {}) },body: body === undefined ? undefined : JSON.stringify(body)});
 const result = await response.json();
 if (!response.ok) { if (response.status === 401 && path !== '/auth/login') { sessionStorage.removeItem('creditToken'); window.dispatchEvent(new Event('credit:logout')); } throw new ApiError(response.status, result); }
 pendingKeys.delete(signature);
 return result as T;
}
export const rub = (value: number | null | undefined) => value == null ? '—' : new Intl.NumberFormat('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 2 }).format(value);
export const when = (value?: string | null) => value ? new Date(value).toLocaleString('ru-RU') : '—';
