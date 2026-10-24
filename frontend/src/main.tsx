import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App as AntApp, ConfigProvider } from 'antd';
import ruRU from 'antd/locale/ru_RU';
import App from './App';
import './style.css';
createRoot(document.getElementById('root')!).render(<React.StrictMode><ConfigProvider locale={ruRU} theme={{token:{colorPrimary:'#EF3124',borderRadius:12,fontFamily:'Inter, Arial, sans-serif'}}}><AntApp><BrowserRouter><App/></BrowserRouter></AntApp></ConfigProvider></React.StrictMode>);
