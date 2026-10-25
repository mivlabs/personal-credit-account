import { test, expect, type Browser, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readdirSync, renameSync, rmSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

// Съёмка скриншотов и гифок для README (`npm run media`). Данные клиентов готовятся через API на чистой БД.
// Все ИНН синтетические: 9-я цифра выбирает сценарий моков (docs/test-accounts.md), последняя цифра контрольная.
const here = dirname(fileURLToPath(import.meta.url));
const OUT = resolve(here, '../../docs/media');
const VIDEO_DIR = resolve(here, '../test-results/media-video');
const WEB = process.env.MEDIA_URL || 'http://localhost:5173';
const PASSWORD = 'demo1234';
const SIZE = { width: 1280, height: 800 };

const CLIENTS = {
  shots: { login: 'media_shots', inn: '7705000027' }, // цифра 2: одобрение, 2 млн
  counter: { login: 'media_counter', inn: '7705000041' }, // цифра 4: контроффер, 10 млн / 24 мес. -> 6 млн
  queue5: { login: 'media_manual', inn: '7705000059' }, // цифра 5: ручная проверка, компания 9 мес.
  queue2: { login: 'media_manual_2', inn: '7705000250' }, // цифра 5
  queue3: { login: 'media_manual_3', inn: '7705000355' }, // цифра 5
  approve: { login: 'media_approve', inn: '7705000034' }, // цифра 3: одобрение, 3 млн
  underwriter: { login: 'media_review', inn: '7705000154' }, // цифра 5: заявка для сценария андеррайтера
  own: { login: 'media_own_inn', inn: '7705000147' }, // цифра 4: регистрируется в самом ролике
};

const ids: Record<string, number> = {};

async function call<T>(path: string, init: { method?: string; body?: unknown; token?: string; key?: string } = {}) {
  const response = await fetch(`${WEB}/api/v1${path}`, {
    method: init.method ?? (init.body === undefined ? 'GET' : 'POST'),
    headers: {
      ...(init.token ? { Authorization: `Bearer ${init.token}` } : {}),
      ...(init.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(init.key ? { 'Idempotency-Key': init.key } : {}),
    },
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  });
  const text = await response.text();
  if (!response.ok) throw new Error(`${init.method ?? 'GET'} ${path}: ${response.status} ${text}`);
  return JSON.parse(text) as T;
}

async function token(client: { login: string; inn: string }) {
  const r = await call<{ accessToken: string }>('/auth/register', {
    body: { login: client.login, password: PASSWORD, inn: client.inn },
  }).catch(() => call<{ accessToken: string }>('/auth/login', { body: { login: client.login, password: PASSWORD } }));
  return r.accessToken;
}

async function file(client: { login: string; inn: string }, productCode: string, amount: number, term: number) {
  const t = await token(client);
  const app = await call<{ id: number }>('/applications', { body: { productCode, draftStep: 1 }, token: t });
  await call(`/applications/${app.id}`, {
    method: 'PATCH',
    token: t,
    body: { purpose: 'Закупка материалов для производства', requestedAmount: amount, termMonths: term, draftStep: 4 },
  });
  const done = await call<{ status: string }>(`/applications/${app.id}/submit`, {
    method: 'POST',
    token: t,
    key: crypto.randomUUID(),
    body: undefined,
  });
  return { id: app.id, status: done.status };
}

// прокрутка так, чтобы верх элемента оказался на `offset` px от верха окна (под липкой шапкой)
async function scrollTo(page: Page, locator: ReturnType<Page['locator']>, offset: number) {
  const y = await locator.evaluate((el) => el.getBoundingClientRect().top + window.scrollY);
  await page.evaluate((top) => window.scrollTo(0, top), Math.max(0, y - offset));
  await page.waitForTimeout(300);
}

const beat = (page: Page, ms = 800) => page.waitForTimeout(ms);

async function ready(page: Page) {
  await page.evaluate(() => document.fonts.ready);
  await page.waitForLoadState('networkidle');
  await beat(page, 700);
}

async function shot(page: Page, name: string) {
  await ready(page);
  await page.screenshot({ path: join(OUT, name) });
}

async function login(page: Page, name: string, slow = false) {
  await page.goto('/');
  const l = page.getByLabel('Логин', { exact: true });
  if (slow) {
    await l.click({ clickCount: 3 }); // выделить подставленный логин и заменить, не вызывая ошибку «обязательное поле»
    await l.pressSequentially(name, { delay: 45 });
  } else await l.fill(name);
  await page.getByLabel('Пароль', { exact: true }).fill(PASSWORD);
  if (slow) await beat(page, 400);
  await page.getByRole('button', { name: 'Войти', exact: true }).click();
  await expect(page.getByRole('button', { name: /Выйти$/ })).toBeVisible();
  await page.evaluate(() => window.scrollTo(0, 0));
}

async function logout(page: Page) {
  await page.getByRole('button', { name: /Выйти$/ }).click();
  await expect(page.getByRole('button', { name: 'Войти', exact: true })).toBeVisible();
}

async function wizard(page: Page, amount: number, term: number, purpose: string, pace = 0) {
  await page.getByRole('button', { name: 'Оформить заявку', exact: true }).first().click();
  await expect(page.getByRole('heading', { name: 'Ваша компания', exact: true })).toBeVisible();
  await ready(page);
  if (pace) await beat(page, pace);
  await page.getByRole('button', { name: 'Продолжить', exact: true }).click();
  await page.getByLabel('Цель кредита', { exact: true }).fill(purpose);
  await page.getByLabel('Сумма кредита, ₽', { exact: true }).fill(String(amount));
  await page.getByLabel('Срок, месяцев', { exact: true }).fill(String(term));
  if (pace) await beat(page, pace);
}

async function toReview(page: Page, pace = 0) {
  await page.getByRole('button', { name: 'Продолжить', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Финансовые показатели', exact: true })).toBeVisible();
  if (pace) await beat(page, pace);
  await page.getByRole('button', { name: 'Продолжить', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Проверьте заявку', exact: true })).toBeVisible();
  if (pace) await beat(page, pace);
}

async function accept(page: Page, pace = 0) {
  await page.getByRole('button', { name: 'Принять предложение', exact: true }).click();
  await page.getByLabel('Код подтверждения', { exact: true }).fill('123456');
  if (pace) await beat(page, pace);
  await page.getByRole('button', { name: 'Подписать и получить кредит · симуляция', exact: true }).click();
  await expect(page.getByText('Выдача смоделирована', { exact: true })).toBeVisible();
}

function ffmpegPath() {
  if (process.env.FFMPEG) return process.env.FFMPEG;
  if (existsSync('C:\\ffmpeg')) {
    for (const dir of readdirSync('C:\\ffmpeg', { recursive: true }) as string[]) {
      if (dir.toLowerCase().endsWith('ffmpeg.exe')) return join('C:\\ffmpeg', dir);
    }
  }
  return 'ffmpeg';
}

// webm -> gif в два прохода (палитра): без пустого первого кадра, ускорение 1.25x; при превышении лимита снижаем fps и ширину
function toGif(webm: string, gif: string, limit = 3_900_000) {
  const palette = webm.replace(/\.webm$/, '-palette.png');
  for (const [fps, width] of [[12, 960], [10, 960], [10, 800], [8, 800], [8, 720]]) {
    const filter = `setpts=PTS/1.25,fps=${fps},scale=${width}:-1:flags=lanczos`;
    execFileSync(ffmpegPath(), ['-y', '-v', 'error', '-ss', '0.8', '-i', webm, '-vf', `${filter},palettegen=stats_mode=diff`, palette]);
    execFileSync(ffmpegPath(), [
      '-y', '-v', 'error', '-ss', '0.8', '-i', webm, '-i', palette,
      '-lavfi', `${filter}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle`,
      gif,
    ]);
    if (statSync(gif).size <= limit) return;
  }
  throw new Error(`${gif} не уложился в ${limit} байт`);
}

async function record(browser: Browser, name: string, scenario: (page: Page) => Promise<void>) {
  const dir = join(VIDEO_DIR, name);
  rmSync(dir, { recursive: true, force: true });
  mkdirSync(dir, { recursive: true });
  const context = await browser.newContext({
    baseURL: WEB,
    viewport: SIZE,
    deviceScaleFactor: 1,
    recordVideo: { dir, size: SIZE },
  });
  const page = await context.newPage();
  await scenario(page);
  await beat(page, 1000);
  await context.close();
  const [webm] = readdirSync(dir).filter((f) => f.endsWith('.webm'));
  renameSync(join(dir, webm), join(dir, `${name}.webm`));
  toGif(join(dir, `${name}.webm`), join(OUT, `${name}.gif`));
}

test.describe.configure({ mode: 'serial' });

test.beforeAll(async () => {
  mkdirSync(OUT, { recursive: true });
  const health = await fetch(`${WEB}/api/v1/products`).catch(() => undefined);
  if (!health) throw new Error(`Нет ответа от ${WEB}: запустите API и \`npm run dev\``);
  ids.counter = (await file(CLIENTS.counter, 'WORKING_CAPITAL', 10_000_000, 24)).id;
  ids.queue5 = (await file(CLIENTS.queue5, 'WORKING_CAPITAL', 3_000_000, 12)).id;
  ids.queue2 = (await file(CLIENTS.queue2, 'WORKING_CAPITAL', 2_000_000, 12)).id;
  ids.queue3 = (await file(CLIENTS.queue3, 'WORKING_CAPITAL', 2_500_000, 18)).id;
  ids.underwriter = (await file(CLIENTS.underwriter, 'WORKING_CAPITAL', 1_500_000, 12)).id;
  await token(CLIENTS.shots);
  await token(CLIENTS.approve);
});

test('Скриншоты клиента: вход, каталог, мастер, решение, таймлайн', async ({ page }) => {
  await page.goto('/');
  await page.getByText('Зарегистрироваться по ИНН', { exact: true }).click();
  await page.getByLabel('Логин', { exact: true }).fill('my_company');
  await page.getByLabel('Пароль', { exact: true }).fill('secret123');
  await page.getByLabel('ИНН', { exact: true }).fill('7702000011');
  await shot(page, 'login.png');

  await login(page, CLIENTS.shots.login);
  await expect(page.getByText('Подходит под вашу цель', { exact: true })).toBeVisible();
  await shot(page, 'catalog.png');

  await wizard(page, 2_000_000, 12, 'Закупка материалов для производства');
  await shot(page, 'wizard.png');

  await toReview(page);
  await page.getByRole('button', { name: 'Отправить заявку', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Принять предложение', exact: true })).toBeVisible();
  await ready(page);
  await scrollTo(page, page.locator('.offer-card'), 92);
  await shot(page, 'decision.png');

  await accept(page);
  await page.evaluate(() => window.scrollTo(0, 0));
  await shot(page, 'timeline.png');
});

test('Скриншот контроффера', async ({ page }) => {
  await login(page, CLIENTS.counter.login);
  await page.goto(`/applications/${ids.counter}`);
  await expect(page.getByRole('heading', { name: 'Встречное предложение банка', exact: true })).toBeVisible();
  await scrollTo(page, page.getByText('Доступная сумма', { exact: false }).first(), 400);
  await shot(page, 'counter-offer.png');
});

test('Скриншоты банка: очередь и карточка заявки', async ({ page }) => {
  await login(page, 'underwriter');
  await expect(page.getByText('Очередь ручной проверки')).toBeVisible();
  await shot(page, 'bank-queue.png');

  await page.goto(`/bank/${ids.queue5}`);
  await expect(page.getByRole('button', { name: 'Зафиксировать решение', exact: true })).toBeVisible();
  await scrollTo(page, page.locator('.ant-card', { hasText: 'Решение специалиста' }).last(), 92);
  await shot(page, 'bank-review.png');
  await page.locator('details.snapshot summary').first().click();
  await scrollTo(page, page.locator('details.snapshot summary').first(), 300);
  await shot(page, 'bank-snapshot.png');
});

test('Гифка: клиент от входа до выдачи', async ({ browser }) => {
  await record(browser, 'flow-approve', async (page) => {
    await login(page, CLIENTS.approve.login, true);
    await expect(page.getByText('Подходит под вашу цель', { exact: true })).toBeVisible();
    await beat(page, 700);
    await wizard(page, 2_000_000, 12, 'Закупка материалов для производства', 500);
    await toReview(page, 350);
    await page.getByRole('button', { name: 'Отправить заявку', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Принять предложение', exact: true })).toBeVisible();
    await page.getByText('Как принято решение').scrollIntoViewIfNeeded();
    await beat(page, 1500);
    await page.evaluate(() => window.scrollTo(0, 0));
    await beat(page, 500);
    await accept(page, 500);
    await beat(page, 800);
  });
});

test('Гифка: регистрация по своему ИНН', async ({ browser }) => {
  await record(browser, 'flow-own-inn', async (page) => {
    await page.goto('/');
    await beat(page, 800);
    await page.getByText('Зарегистрироваться по ИНН', { exact: true }).click();
    await page.getByLabel('Логин', { exact: true }).fill(CLIENTS.own.login);
    await page.getByLabel('Пароль', { exact: true }).fill(PASSWORD);
    await page.getByLabel('ИНН', { exact: true }).pressSequentially(CLIENTS.own.inn, { delay: 45 });
    await beat(page, 800);
    await page.getByRole('button', { name: 'Зарегистрироваться', exact: true }).click();
    await expect(page.getByRole('button', { name: /Выйти$/ })).toBeVisible();
    await beat(page, 1000);
    await wizard(page, 10_000_000, 24, 'Расширение складских запасов', 1200);
    await toReview(page, 350);
    await page.getByRole('button', { name: 'Отправить заявку', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Встречное предложение банка', exact: true })).toBeVisible();
    await beat(page, 1500);
    await scrollTo(page, page.getByText('Доступная сумма', { exact: false }).first(), 330);
    await beat(page, 1800);
  });
});

test('Гифка: андеррайтер и ручное решение', async ({ browser }) => {
  await record(browser, 'flow-underwriter', async (page) => {
    await login(page, 'underwriter', true);
    await expect(page.getByText('Очередь ручной проверки')).toBeVisible();
    await beat(page, 1000);
    await page.getByRole('link', { name: `№ ${ids.underwriter}`, exact: true }).click();
    await expect(page.getByRole('button', { name: 'Зафиксировать решение', exact: true })).toBeVisible();
    await scrollTo(page, page.locator('.ant-card', { hasText: 'Решение специалиста' }).last(), 92);
    await beat(page, 1500);
    await page.getByLabel('Внутренний комментарий', { exact: true }).fill('Выручка подтверждена ФНС, риск приемлемый');
    await beat(page, 800);
    const override = page.getByLabel('Решение выше расчётного лимита (подтверждаю)');
    if ((await override.count()) > 0) await override.check().catch(() => undefined);
    await page.getByRole('button', { name: 'Зафиксировать решение', exact: true }).click();
    await expect(page.getByText('Решение уже зафиксировано', { exact: true })).toBeVisible();
    await beat(page, 1200);
    await logout(page);
    await login(page, CLIENTS.underwriter.login);
    await page.goto(`/applications/${ids.underwriter}`);
    await expect(page.getByRole('button', { name: 'Принять предложение', exact: true })).toBeVisible();
    await beat(page, 1200);
  });
});
