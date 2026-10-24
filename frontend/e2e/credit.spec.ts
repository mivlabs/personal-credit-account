import { test, expect, type Page } from '@playwright/test';
async function login(page:Page,name:string){
 await page.goto('/'); await page.getByLabel('Логин',{exact:true}).fill(name); await page.getByLabel('Пароль',{exact:true}).fill('demo1234'); await page.getByRole('button',{name:'Войти',exact:true}).click();
 await expect(page.getByRole('button',{name:/Выйти$/})).toBeVisible();
}
async function submit(page:Page,amount=1500000){
 await page.getByRole('button',{name:'Оформить заявку',exact:true}).first().click();
 await expect(page.getByRole('heading',{name:'Ваша компания',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Продолжить',exact:true}).click();
 await page.getByLabel('Цель кредита',{exact:true}).fill('Закупка материалов');
 await page.getByLabel('Сумма кредита, ₽',{exact:true}).fill(String(amount));
 await page.getByLabel('Срок, месяцев',{exact:true}).fill('12');
 await page.getByRole('button',{name:'Продолжить',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Финансовые показатели',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Продолжить',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Проверьте заявку',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Отправить заявку',exact:true}).click();
}
async function issue(page:Page){
 await page.getByRole('button',{name:'Принять предложение',exact:true}).click();
 await page.getByLabel('Код подтверждения',{exact:true}).fill('123456');
 await page.getByRole('button',{name:'Подписать и получить кредит · симуляция',exact:true}).click();
 await expect(page.getByText('Выдача смоделирована',{exact:true})).toBeVisible();
}
test('Одобрение, сохранение черновика и выдача',async({page})=>{
 await login(page,'client_fast');
 await page.getByRole('button',{name:'Оформить заявку',exact:true}).first().click();
 await page.getByRole('button',{name:'Продолжить',exact:true}).click();
 await page.getByLabel('Цель кредита',{exact:true}).fill('Оборотные средства');
 await page.getByLabel('Сумма кредита, ₽',{exact:true}).fill('1500000');
 await page.getByLabel('Срок, месяцев',{exact:true}).fill('12');
 await page.getByRole('button',{name:'Сохранить черновик',exact:true}).click();
 await expect(page.getByText('Черновик сохранён',{exact:true})).toBeVisible();
 await page.reload();
 await expect(page.getByLabel('Сумма кредита, ₽',{exact:true})).toHaveValue('1500000.00');
 await page.getByRole('button',{name:'Продолжить',exact:true}).click();
 await page.getByRole('button',{name:'Продолжить',exact:true}).click();
 await page.getByRole('button',{name:'Отправить заявку',exact:true}).click();
 await issue(page);
 await page.screenshot({path:'test-results/client-issued.png',fullPage:true});
});
test('Ручное решение со сменой аккаунта',async({page})=>{
 await login(page,'client_manual');await submit(page);const applicationPath=new URL(page.url()).pathname;const id=applicationPath.split('/').at(-1);
 await expect(page.getByText('Заявку рассматривает специалист',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:/Выйти$/}).click();await login(page,'underwriter');
 await page.goto('/bank/'+id);
 await page.getByLabel('Внутренний комментарий',{exact:true}).fill('Выручка подтверждена для учебного сценария');
 await page.getByRole('button',{name:'Зафиксировать решение',exact:true}).click();
 await expect(page.getByText('Решение уже зафиксировано',{exact:true})).toBeVisible();
 await page.screenshot({path:'test-results/bank-decision.png',fullPage:true});
 await page.getByRole('button',{name:/Выйти$/}).click();await login(page,'client_manual');await page.goto(applicationPath);await issue(page);
});
test('Дозапрос и повторная проверка',async({page})=>{
 await login(page,'client_info');await submit(page);
 await expect(page.getByText('Нужны дополнительные данные',{exact:true})).toBeVisible();
 await page.getByLabel('Годовая выручка, ₽',{exact:true}).fill('12000000');
 await page.getByRole('button',{name:'Отправить данные',exact:true}).click();
 await issue(page);
});
test('Контрпредложение и отказ',async({page})=>{
 await login(page,'client_counter');await submit(page,10000000);
 await expect(page.getByRole('heading',{name:'Встречное предложение банка',exact:true})).toBeVisible();
 await issue(page);
 await page.getByRole('button',{name:/Выйти$/}).click();await login(page,'client_reject');await submit(page);
 await expect(page.getByText('В кредитной истории есть просрочка более 90 дней',{exact:true})).toBeVisible();
 await expect(page.getByRole('button',{name:'Принять предложение',exact:true})).toHaveCount(0);
});
