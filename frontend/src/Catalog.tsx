import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button, Card, Empty, Select, Spin, Table } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { api, rub, when, type Application, type Schemas } from './api';
import { Failure, KV, PageHeading, StatusTag, useLoad } from './shared';
const goals: {label:string,value:Schemas['PurposeCategory']}[] = [{label:'Пополнить оборотные средства',value:'WORKING_CAPITAL_TOPUP'},{label:'Закупить товар или сырьё',value:'GOODS_PURCHASE'},{label:'Купить оборудование или транспорт',value:'EQUIPMENT_PURCHASE'},{label:'Закрыть кассовый разрыв',value:'CASH_GAP'},{label:'Сезонные расходы',value:'SEASONAL'},{label:'Ремонт или расширение',value:'EXPANSION'},{label:'Другое',value:'OTHER'}];
export function Products(){
 const [goal,setGoal]=useState<Schemas['PurposeCategory']>('WORKING_CAPITAL_TOPUP');const {data,error,loading}=useLoad(()=>api<Schemas['RecommendationsOut']>('/products/recommendations',{purposeCategory:goal}),[goal]);const [busy,setBusy]=useState<string>();const [actionError,setActionError]=useState<unknown>();const navigate=useNavigate();
 const create=async(code:Schemas['ProductCode'])=>{setBusy(code);try{const app=await api<Application>('/applications',{productCode:code,draftStep:1});navigate('/applications/'+app.id);}catch(e){setActionError(e);}finally{setBusy(undefined);}};
 return <>
  <PageHeading eyebrow="Финансирование бизнеса" title="На что направим кредит?" lead="Подберите продукт под задачу. Данные компании заполним за вас."/>
  <Card className="goal-card"><span className="eyebrow">Моя задача</span><div className="chips" role="group" aria-label="Цель кредита">{goals.map(g=><button type="button" key={g.value} className="chip" aria-pressed={goal===g.value} onClick={()=>setGoal(g.value)}>{g.label}</button>)}</div></Card>
  <Failure error={error||actionError}/>
  <Spin spinning={loading}><div className="product-grid">{data?.items.map(({product:p,recommended,matchScore,reasons})=><article className={'product-card'+(recommended?' recommended':'')} key={p.code}>
   <span className={'tag-pill'+(recommended?' lime':'')}>{recommended?'Подходит под вашу цель':'Соответствие '+matchScore+'%'}</span>
   <h3>{p.name}</h3>
   <div className="rate">от {p.rateFrom}%<small>годовых</small></div>
   <p className="muted">Ключевая ставка {p.rateBreakdown.keyRate}% + спред {p.rateBreakdown.productSpread}</p>
   <KV items={[{key:'amount',label:'Сумма',value:`${rub(p.minAmount)} — ${rub(p.maxAmount)}`},{key:'term',label:'Срок',value:`${p.minTermMonths}–${p.maxTermMonths} месяцев`}]}/>
   <p className="desc">{p.code==='OVERDRAFT'?'Лимит для покрытия краткосрочного разрыва. Проценты зависят от фактического использования.':p.requirements}</p>
   <ul className="reasons">{reasons.map(r=><li key={r}>{r}</li>)}</ul>
   <Button type={recommended?'primary':'default'} size="large" block disabled={!!busy} loading={busy===p.code} onClick={()=>void create(p.code)}>Оформить заявку</Button>
  </article>)}</div></Spin>
 </>;
}
export function Applications(){
 const {data,error,loading,reload}=useLoad(()=>api<Schemas['ApplicationSummary'][]>('/applications'),[]);const [filter,setFilter]=useState('all');
 return <>
  <PageHeading eyebrow="Кабинет компании" title="Мои заявки" extra={<Link to="/products"><Button type="primary" size="large" icon={<PlusOutlined/>}>Новая заявка</Button></Link>}/>
  <Failure error={error}/>
  <Card>
   <div className="toolbar"><Select aria-label="Фильтр статуса" value={filter} onChange={setFilter} style={{width:240}} options={[{value:'all',label:'Все статусы'},...Array.from(new Map(data?.map(a=>[a.status,a.statusName])).entries()).map(([value,label])=>({value,label}))]}/><Button onClick={()=>void reload()}>Обновить</Button></div>
   <Table rowKey="id" loading={loading} dataSource={data?.filter(a=>filter==='all'||a.status===filter)} locale={{emptyText:<Empty description="Пока нет заявок. Выберите продукт, чтобы начать."/>}} columns={[{title:'Заявка',dataIndex:'id',render:(id:number)=><Link to={'/applications/'+id}><b>№ {id}</b></Link>},{title:'Продукт',dataIndex:'productName'},{title:'Сумма',dataIndex:'requestedAmount',render:rub},{title:'Статус',render:(_,a)=><StatusTag status={a.status} name={a.statusName}/>},{title:'Обновлена',dataIndex:'updatedAt',render:when},{title:'',align:'right',render:(_,a)=><Link to={'/applications/'+a.id}>{a.status==='DRAFT'?'Продолжить':'Открыть'}</Link>}]} pagination={{pageSize:10}} scroll={{x:700}}/>
  </Card>
 </>;
}
