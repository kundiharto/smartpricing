// Format tampilan saja. Konversi ke Number hanya untuk Intl.NumberFormat, tidak untuk perhitungan.

const LOCALES = { id: "id-ID", en: "en-US" } as const;
export type Lang = keyof typeof LOCALES;

const MINOR: Record<string, number> = { IDR: 0, JPY: 0, KRW: 0, VND: 0 };

export function money(value: string | null | undefined, currency = "IDR", lang: Lang = "id", exact = false): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return value;
  const digits = exact ? Math.min(Math.max(decimals(value), MINOR[currency] ?? 2), 4) : (MINOR[currency] ?? 2);
  return new Intl.NumberFormat(LOCALES[lang], {
    style: "currency",
    currency,
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(n);
}

export function num(value: string | null | undefined, lang: Lang = "id", maxDigits = 4): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return value;
  return new Intl.NumberFormat(LOCALES[lang], { maximumFractionDigits: maxDigits }).format(n);
}

/** Pecahan (0.3) → "30,00%". */
export function pct(value: string | null | undefined, lang: Lang = "id", digits = 2): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return value;
  return new Intl.NumberFormat(LOCALES[lang], {
    style: "percent",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(n);
}

export function date(value: string | null | undefined, lang: Lang = "id"): string {
  if (!value) return "—";
  const d = value.length === 10 ? new Date(`${value}T00:00:00`) : new Date(value);
  return new Intl.DateTimeFormat(LOCALES[lang], { day: "numeric", month: "short", year: "numeric" }).format(d);
}

export function dateTime(value: string | null | undefined, lang: Lang = "id"): string {
  if (!value) return "—";
  return new Intl.DateTimeFormat(LOCALES[lang], { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function decimals(v: string): number {
  const i = v.indexOf(".");
  return i < 0 ? 0 : v.length - i - 1;
}

/** Persen yang diketik pengguna ("30") → pecahan string ("0.3") tanpa floating point. */
export function percentToFraction(input: string): string {
  const s = input.trim().replace(",", ".");
  if (!/^-?\d+(\.\d+)?$/.test(s)) return s;
  const neg = s.startsWith("-");
  const [int, frac = ""] = s.replace("-", "").split(".");
  const padded = int.padStart(3, "0");
  const whole = padded.slice(0, -2).replace(/^0+(?=\d)/, "");
  const result = `${whole}.${padded.slice(-2)}${frac}`.replace(/\.?0+$/, "") || "0";
  return neg && result !== "0" ? `-${result}` : result;
}

/** Hapus nol di belakang koma: "1000.000000" → "1000", "12.50" → "12.5". Bilangan bulat tidak disentuh. */
export function trimDecimal(s: string): string {
  if (!s.includes(".")) return s;
  return s.replace(/0+$/, "").replace(/\.$/, "");
}

/** Pecahan string ("0.03") → persen string ("3") tanpa floating point. */
export function fractionToPercent(s: string): string {
  const neg = s.startsWith("-");
  const v = neg ? s.slice(1) : s;
  const [i, f = ""] = v.split(".");
  const fp = f.padEnd(2, "0");
  const whole = `${i}${fp.slice(0, 2)}`.replace(/^0+(?=\d)/, "");
  const res = trimDecimal(fp.length > 2 ? `${whole}.${fp.slice(2)}` : whole);
  return neg && res !== "0" ? `-${res}` : res;
}

export function today(): string {
  const d = new Date();
  const pad = (x: number) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
