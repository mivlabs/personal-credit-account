import { useCallback, useEffect, useRef, useState } from 'react';
import { Alert } from 'antd';
import { ApiError } from './api';
export const fieldNames: Record<string,string> = { requestedAmount:'Сумма кредита, ₽', termMonths:'Срок, месяцев', purpose:'Цель кредита', revenueAmount:'Годовая выручка, ₽', debtAmount:'Текущий остаток долга, ₽' };
export const factorNames: Record<string,string> = { AGE_MONTHS:'Возраст бизнеса, месяцев', ANNUAL_REVENUE_RUB:'Годовая выручка, ₽', DEBT_TO_ANNUAL_REVENUE:'Долг / годовая выручка', OVERDUE_DAYS:'Просрочка, дней', INDUSTRY:'Отрасль' };
export const statusColor = (s: string) => ['APPROVED','ISSUED'].includes(s) ? 'green' : s === 'REJECTED' ? 'red' : ['NEEDS_INFO','COUNTER_OFFER'].includes(s) ? 'orange' : 'blue';
export function Failure({error}: {error: unknown}) {
 if (!error) return null;
 return <Alert type="error" showIcon message={error instanceof Error ? error.message : 'Не удалось загрузить данные'} description={error instanceof ApiError ? <>{error.problem.errors?.map((e,i)=><div key={i}>{fieldNames[e.field] || e.field}: {e.message}</div>)}<small>Номер запроса: {error.problem.requestId}</small></> : undefined}/>;
}
export function useLoad<T>(load: () => Promise<T>, deps: unknown[]) {
 const [data,setData] = useState<T>(); const [error,setError] = useState<unknown>(); const [loading,setLoading] = useState(true); const counter = useRef(0);
 const reload = useCallback(async () => {const run=++counter.current; setLoading(true); try { const value=await load(); if(run===counter.current){setData(value);setError(undefined);} } catch(e){if(run===counter.current)setError(e);} finally {if(run===counter.current)setLoading(false);} }, deps);
 useEffect(()=>{void reload(); return ()=>{counter.current++;};},[reload]);
 return {data,error,loading,reload};
}
