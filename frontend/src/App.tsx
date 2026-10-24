import { useCallback, useEffect, useState } from 'react';
import { Link, Navigate, NavLink, Route, Routes, useNavigate } from 'react-router-dom';
import { Button, Card, Form, Input, Layout, Spin, Typography } from 'antd';
import { LogoutOutlined } from '@ant-design/icons';
import { api, type Schemas, type User } from './api';
import { Failure } from './shared';
import { Products, Applications } from './Catalog';
import ApplicationPage from './ApplicationPage';
import Bank from './Bank';
const { Title } = Typography;
export default function App() {
 const [user,setUser] = useState<User>(); const [boot,setBoot] = useState(true); const [error,setError] = useState<unknown>();
 const navigate=useNavigate();
 const logout=useCallback(()=>{sessionStorage.removeItem('creditToken');setUser(undefined);navigate('/login');},[navigate]);
 useEffect(()=>{window.addEventListener('credit:logout',logout);return()=>window.removeEventListener('credit:logout',logout);},[logout]);
 useEffect(()=>{if(!sessionStorage.getItem('creditToken')){setBoot(false);return;} api<User>('/auth/me').then(setUser).catch(setError).finally(()=>setBoot(false));},[]);
 if(boot)return <div className="center"><Spin size="large"/></div>;
 if(!user)return <Login error={error} onLogin={u=>{setUser(u);setError(undefined);navigate(u.role==='UNDERWRITER'?'/bank':'/products');}}/>;
 const bank=user.role==='UNDERWRITER';
 const links=bank?[{to:'/bank',label:'Рабочая очередь'}]:[{to:'/products',label:'Кредитные продукты'},{to:'/applications',label:'Мои заявки'}];
 return <Layout className="app-layout">
  <Layout.Header className="topbar">
   <Link className="brand" to={bank?'/bank':'/products'}><span className="brand-mark">А</span><span>Кредитный кабинет<small>для бизнеса</small></span></Link>
   <nav className="nav" aria-label="Разделы">{links.map(l=><NavLink key={l.to} to={l.to} className={({isActive})=>isActive?'active':undefined}>{l.label}</NavLink>)}</nav>
   <div className="topbar-right"><span className="tag-pill lime">Демо · синтетические данные</span><span className="user-name">{user.name}</span><Button aria-label="Выйти" icon={<LogoutOutlined/>} onClick={logout}>Выйти</Button></div>
  </Layout.Header>
  <Layout.Content className="content"><Routes>{bank?<><Route path="/bank" element={<Bank/>}/><Route path="/bank/:id" element={<Bank/>}/></>:<><Route path="/products" element={<Products/>}/><Route path="/applications" element={<Applications/>}/><Route path="/applications/:id" element={<ApplicationPage/>}/></>}<Route path="*" element={<Navigate to={bank?'/bank':'/products'} replace/>}/></Routes></Layout.Content>
  <Layout.Footer className="footer">Учебный прототип. Подписание и выдача денег моделируются, условия и решения демонстрационные.</Layout.Footer>
 </Layout>;
}
function Login({onLogin,error:initialError}:{onLogin:(u:User)=>void,error:unknown}) {
 const [busy,setBusy]=useState(false); const [error,setError]=useState(initialError);
 const submit=async(body:Schemas['LoginRequest'])=>{setBusy(true);setError(undefined);try{const r=await api<Schemas['LoginResponse']>('/auth/login',body);sessionStorage.setItem('creditToken',r.accessToken);onLogin(r.user);}catch(e){setError(e);}finally{setBusy(false);}};
 return <div className="login">
  <div className="login-story">
   <span className="brand-mark">А</span>
   <span className="eyebrow">Кредитный кабинет для предпринимателей</span>
   <h1>Кредит для бизнеса <span className="hl">без звонков</span> и повторных анкет</h1>
   <p className="lead">Выберите продукт под задачу, отправьте заявку и следите за решением в одном кабинете. Данные компании банк уже знает.</p>
   <div className="login-points"><span><b>01</b>Данные компании уже под рукой</span><span><b>02</b>Понятный статус на каждом этапе</span><span><b>03</b>Решение и условия в кабинете</span></div>
  </div>
  <Card className="login-form">
   <Title level={2}>Вход в кабинет</Title>
   <p className="muted" style={{marginTop:0}}>Демонстрационные аккаунты действующих клиентов банка</p>
   <Failure error={error}/>
   <Form layout="vertical" initialValues={{login:'client_fast',password:'demo1234'}} onFinish={submit}>
    <Form.Item name="login" label="Логин" rules={[{required:true}]}><Input autoComplete="username"/></Form.Item>
    <Form.Item name="password" label="Пароль" rules={[{required:true}]}><Input.Password autoComplete="current-password"/></Form.Item>
    <Button block type="primary" size="large" htmlType="submit" loading={busy}>Войти</Button>
   </Form>
   <p className="demo-note">Пароль для демо: <code>demo1234</code><br/>Клиенты: <code>client_fast</code>, <code>client_counter</code>, <code>client_manual</code>, <code>client_info</code>, <code>client_reject</code>, <code>client_timeout</code>.<br/>Сотрудник банка: <code>underwriter</code>.</p>
  </Card>
 </div>;
}
