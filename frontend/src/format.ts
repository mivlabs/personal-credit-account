// Отображение кодов и чисел из API человеческим языком. Контракт API не меняется: форматируем только на показе.
const num = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 });
const numeric = (value: unknown) => (typeof value === 'number' || (typeof value === 'string' && value.trim() !== '')) && Number.isFinite(Number(value));
// Число с пробелами между разрядами и не более 2 знаков после запятой; не число возвращается как есть
export const fmtNum = (value: unknown): string => numeric(value) ? num.format(Number(value)) : String(value ?? '—');
export const fmtPct = (value: unknown): string => numeric(value) ? num.format(Number(value)) + '%' : String(value ?? '—');
// Доля (0.0714…) → проценты
export const fmtShare = (value: unknown): string => numeric(value) ? num.format(Number(value) * 100) + '%' : String(value ?? '—');
export const fmtDate = (value: unknown): string => typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value.split('-').reverse().join('.') : String(value ?? '—');
export const sourceNames: Record<string,string> = { EGRUL:'ЕГРЮЛ', FNS:'ФНС', BKI:'БКИ' };
export const statusNames: Record<string,string> = { DRAFT:'Черновик', SUBMITTED:'Подана', CHECKING:'Проверяем заявку', EXTERNAL_CHECK:'Получаем данные из внешних сервисов', SCORING:'Оцениваем заявку', NEEDS_INFO:'Нужны данные', MANUAL_REVIEW:'На рассмотрении у специалиста', APPROVED:'Одобрено', COUNTER_OFFER:'Встречное предложение', REJECTED:'Отказ', OFFER_ACCEPTED:'Предложение принято', SIGNING:'Подписание', ISSUED:'Кредит выдан', DECLINED_BY_CLIENT:'Клиент отказался', WITHDRAWN:'Заявка отозвана', EXPIRED:'Срок истёк' };
export const industryNames: Record<string,string> = { trade:'Торговля', services:'Услуги', manufacturing:'Производство', construction:'Строительство', other:'Другое' };
const yesNo = (value: unknown) => /^(true|1)$/i.test(String(value)) ? 'Да' : /^(false|0)$/i.test(String(value)) ? 'Нет' : String(value);
// Значения входов решения (inputs) по коду
export function fmtInput(code: string, value: unknown): string {
 switch (code) {
  case 'requestedAmount': case 'annualRevenue': case 'debtAmount': return numeric(value) ? fmtNum(value) + ' ₽' : String(value);
  case 'overdueDays': return fmtNum(value);
  case 'registrationDate': return fmtDate(value);
  case 'active': return yesNo(value);
  case 'industry': return industryNames[String(value)] ?? String(value);
  default: return typeof value === 'boolean' ? (value ? 'Да' : 'Нет') : numeric(value) ? fmtNum(value) : String(value);
 }
}
// Значения факторов скоринга по коду
export function fmtFactor(code: string, value: unknown): string {
 switch (code) {
  case 'DEBT_TO_ANNUAL_REVENUE': return fmtShare(value);
  case 'INDUSTRY': return industryNames[String(value)] ?? String(value);
  default: return fmtNum(value);
 }
}
// Тексты бэкенда с суммами и ставками: «2000000.00 ₽» → «2 000 000 ₽», «16.5%» → «16,5%»
export const fmtText = (text: string): string => text.replace(/(\d+(?:\.\d+)?) ₽/g, (_, n: string) => fmtNum(n) + ' ₽').replace(/(\d)\.(\d)/g, '$1,$2');
const queueRules: Record<string,string> = { BORDERLINE_SCORE:'Пограничный', LOW_SCORE:'Низкий', LIMIT_BELOW_MINIMUM:'Лимит ниже минимума', ABOVE_LIMIT:'Запрошено выше лимита', WITHIN_LIMIT:'В пределах лимита' };
// «BORDERLINE_SCORE; балл 60; доступная сумма 2000000.00 ₽» → «Пограничный балл 60, доступная сумма 2 000 000 ₽».
// Незнакомый формат возвращается без изменений.
export function fmtQueueReason(text: string | null | undefined): string {
 if (!text) return '';
 const parts = text.split(';').map(p => p.trim());
 const head = queueRules[parts[0]];
 if (!head) return text;
 const rest = parts.slice(1).map(fmtText);
 const [first, ...others] = rest;
 if (parts[0] === 'BORDERLINE_SCORE' && first && /^балл \d+$/.test(first)) return [head + ' ' + first, ...others].join(', ');
 return [head, ...rest].join(', ');
}
// Поля сумм (antd InputNumber): пробелы между разрядами при показе, при вводе пробелы и запятая принимаются
export const moneyInput = {
 formatter: (value?: string | number) => { const [int, frac] = String(value ?? '').split('.'); return int.replace(/\B(?=(\d{3})+(?!\d))/g, ' ') + (frac !== undefined ? '.' + frac : ''); },
 parser: (value?: string) => (value ?? '').replace(/[\s ]/g, '').replace(',', '.') as unknown as number,
};
