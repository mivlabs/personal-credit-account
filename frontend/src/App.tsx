import { useCallback, useEffect, useState } from 'react';
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { Button, Card, Form, Input, Layout, Menu, Space, Spin, Tag, Typography } from 'antd';
import { BankOutlined, FileTextOutlined, LogoutOutlined } from '@ant-design/icons';
import { api, type Schemas, type User } from './api';
import { Failure } from './shared';
import { Products, Applications } from './Catalog';
import ApplicationPage from './ApplicationPage';
import Bank from './Bank';
const { Title, Text, Paragraph } = Typography;
export default function App() {
 const [user,setUser] = useState<User>(); const [boot,setBoot] = useState(true); const [error,setError] = useState<unknown>();
 const navigate=useNavigate(); const location=useLocation();
 const logout=useCallback(()=>{sessionStorage.removeItem('creditToken');setUser(undefined);navigate('/login');},[navigate]);
 useEffect(()=>{window.addEventListener('credit:logout',logout);return()=>window.removeEventListener('credit:logout',logout);},[logout]);
 useEffect(()=>{if(!sessionStorage.getItem('creditToken')){setBoot(false);return;} api<User>('/auth/me').then(setUser).catch(setError).finally(()=>setBoot(false));},[]);
 if(boot)return <div className="center"><Spin size="large"/></div>;
 if(!user)return <Login error={error} onLogin={u=>{setUser(u);setError(undefined);navigate(u.role==='UNDERWRITER'?'/bank':'/products');}}/>;
 const bank=user.role==='UNDERWRITER';
 return <Layout className="app-layout"><Layout.Header className="topbar"><Link className="brand" to={bank?'/bank':'/products'}><span className="brand-mark">А</span><span>Кредитный кабинет<small>для бизнеса</small></span></Link><Space><Tag color="default">Демо · синтетические данные</Tag><Text>{user.name}</Text><Button aria-label="Выйти" icon={<LogoutOutlined/>} onClick={logout}>Выйти</Button></Space></Layout.Header><Layout><Layout.Sider width={220} theme="light" breakpoint="lg" collapsedWidth={0}><Menu mode="inline" selectedKeys={[location.pathname.startsWith('/applications')?'/applications':bank?'/bank':'/products']} items={bank?[{key:'/bank',icon:<BankOutlined/>,label:<Link to="/bank">Рабочая очередь</Link>}]:[{key:'/products',icon:<BankOutlined/>,label:<Link to="/products">Кредитные продукты</Link>},{key:'/applications',icon:<FileTextOutlined/>,label:<Link to="/applications">Мои заявки</Link>}]} /><div className="side-note">Все действия проходят в кабинете. Подписание и выдача денег моделируются.</div></Layout.Sider><Layout.Content className="content"><Routes>{bank?<><Route path="/bank" element={<Bank/>}/><Route path="/bank/:id" element={<Bank/>}/></>:<><Route path="/products" element={<Products/>}/><Route path="/applications" element={<Applications/>}/><Route path="/applications/:id" element={<ApplicationPage/>}/></>}<Route path="*" element={<Navigate to={bank?'/bank':'/products'} replace/>}/></Routes></Layout.Content></Layout><Layout.Footer>Учебный прототип. Условия и решения демонстрационные.</Layout.Footer></Layout>;
}
function Login({onLogin,error:initialError}:{onLogin:(u:User)=>void,error:unknown}) {
 const [busy,setBusy]=useState(false); const [error,setError]=useState(initialError);
 const submit=async(body:Schemas['LoginRequest'])=>{setBusy(true);setError(undefined);try{const r=await api<Schemas['LoginResponse']>('/auth/login',body);sessionStorage.setItem('creditToken',r.accessToken);onLogin(r.user);}catch(e){setError(e);}finally{setBusy(false);}};
 return <div className="login"><div className="login-story"><span className="brand-mark">А</span><Tag>Для предпринимателей</Tag><Title>От планов бизнеса<br/>к новым возможностям</Title><Paragraph>Выберите кредит, отправьте заявку и следите за решением в одном кабинете.</Paragraph><div className="login-points"><p>01 · Данные компании уже под рукой</p><p>02 · Понятный статус на каждом этапе</p><p>03 · Решение и условия без звонков</p></div></div><Card className="login-form"><Title level={2}>Вход в кабинет</Title><Paragraph type="secondary">Демонстрационные аккаунты действующих клиентов банка</Paragraph><Failure error={error}/><Form layout="vertical" initialValues={{login:'client_fast',password:'demo1234'}} onFinish={submit}><Form.Item name="login" label="Логин" rules={[{required:true}]}><Input autoComplete="username"/></Form.Item><Form.Item name="password" label="Пароль" rules={[{required:true}]}><Input.Password autoComplete="current-password"/></Form.Item><Button block type="primary" size="large" htmlType="submit" loading={busy}>Войти</Button></Form><Paragraph className="demo-note">Пароль для демо: demo1234<br/>Клиенты: client_fast, client_counter, client_manual, client_info, client_reject, client_timeout.<br/>Сотрудник банка: underwriter.</Paragraph></Card></div>;
}
