import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { Alert, Typography } from 'antd';
import { ApiError } from './api';
const { Title } = Typography;
export const fieldNames: Record<string,string> = { requestedAmount:'Сумма кредита, ₽', termMonths:'Срок, месяцев', purpose:'Цель кредита', revenueAmount:'Годовая выручка, ₽', debtAmount:'Текущий остаток долга, ₽' };
export const factorNames: Record<string,string> = { AGE_MONTHS:'Возраст бизнеса, месяцев', ANNUAL_REVENUE_RUB:'Годовая выручка, ₽', DEBT_TO_ANNUAL_REVENUE:'Долг / годовая выручка', OVERDUE_DAYS:'Просрочка, дней', INDUSTRY:'Отрасль' };
// Тон статуса: зелёный только для положительного исхода, красный только для отказа, оранжевый там, где нужно действие клиента.
export const statusTone = (s: string) => ['APPROVED','ISSUED','OFFER_ACCEPTED','SIGNING'].includes(s) ? 'good' : s === 'REJECTED' ? 'bad' : ['NEEDS_INFO','COUNTER_OFFER'].includes(s) ? 'warn' : ['DRAFT','WITHDRAWN','EXPIRED','DECLINED_BY_CLIENT'].includes(s) ? 'neutral' : 'info';
export function StatusTag({status,name}: {status: string, name: string}) { return <span className={'status '+statusTone(status)}>{name}</span>; }
export function KV({items,className}: {items: {key?: string, label: ReactNode, value: ReactNode, note?: ReactNode}[], className?: string}) {
 return <dl className={'kv'+(className?' '+className:'')}>{items.map((i,n)=><div className="kv-row" key={i.key ?? n}><dt className="kv-label">{i.label}</dt><dd className="kv-value">{i.value}{i.note && <span className="kv-note">{i.note}</span>}</dd></div>)}</dl>;
}
export function Figure({label,value,unit}: {label: ReactNode, value: ReactNode, unit?: ReactNode}) { return <div className="figure"><div className="figure-label">{label}</div><div className="figure-value">{value}{unit && <small>{unit}</small>}</div></div>; }
export function PageHeading({eyebrow,title,lead,extra}: {eyebrow?: ReactNode, title: ReactNode, lead?: ReactNode, extra?: ReactNode}) {
 const body = <div>{eyebrow && <span className="eyebrow">{eyebrow}</span>}<Title>{title}</Title>{lead && <p className="lead">{lead}</p>}</div>;
 return extra ? <div className="page-heading heading-row">{body}{extra}</div> : <div className="page-heading">{body}</div>;
}
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
