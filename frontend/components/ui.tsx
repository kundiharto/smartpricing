"use client";

import clsx from "clsx";
import { AlertTriangle, Info, Loader2, X } from "lucide-react";
import { forwardRef, useEffect, useId, useRef, useState } from "react";
import { useHelp } from "@/lib/help";

export function cn(...args: Parameters<typeof clsx>) {
  return clsx(...args);
}

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
  loading?: boolean;
};

export function Button({ variant = "primary", size = "md", loading, className, children, disabled, ...rest }: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" ? "h-8 px-3 text-sm" : "h-10 px-4 text-sm",
        variant === "primary" && "bg-accent text-white hover:bg-accent-hover",
        variant === "secondary" && "border border-line bg-surface text-ink hover:bg-surface-2",
        variant === "ghost" && "text-muted hover:bg-surface-2 hover:text-ink",
        variant === "danger" && "border border-line bg-surface text-danger hover:bg-danger-soft",
        className,
      )}
    >
      {loading && <Loader2 className="size-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

const fieldClass =
  "h-10 w-full min-w-0 rounded-lg border border-line bg-surface px-3 text-sm text-ink placeholder:text-muted/70 focus:border-accent focus:outline-none disabled:bg-surface-2";

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, ...rest },
  ref,
) {
  return <input ref={ref} {...rest} className={cn(fieldClass, className)} />;
});

export function Select({ className, children, ...rest }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select {...rest} className={cn(fieldClass, "pr-8", className)}>
      {children}
    </select>
  );
}

export function Textarea({ className, ...rest }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...rest} className={cn(fieldClass, "h-auto min-h-20 py-2", className)} />;
}

/** Label + kontrol + bantuan. Kontrol menerima id otomatis. */
export function Field({
  label,
  hint,
  help,
  children,
  className,
}: {
  label: string;
  hint?: string;
  /** Kunci teks bantuan di lib/help.ts — tampil sebagai ⓘ dan kotak bantuan saat kolom diisi. */
  help?: string;
  children: (id: string) => React.ReactNode;
  className?: string;
}) {
  const id = useId();
  const helpId = `${id}-help`;
  const { help: getHelp, exampleLabel } = useHelp();
  const entry = help ? getHelp(help) : undefined;

  // Hubungkan kontrol ke teks bantuan untuk pembaca layar.
  useEffect(() => {
    if (!entry) return;
    document.getElementById(id)?.setAttribute("aria-describedby", helpId);
  }, [entry, id, helpId]);

  return (
    <div className={cn("group/field flex flex-col gap-1.5", className)}>
      {label && (
        <div className="flex items-center gap-1.5">
          <label htmlFor={id} className="text-sm font-medium text-ink">
            {label}
          </label>
          {entry && <InfoTip text={entry.text} example={entry.example} exampleLabel={exampleLabel} label={label} />}
        </div>
      )}
      {children(id)}
      {hint && <p className="text-xs text-muted">{hint}</p>}
      {entry && <HelpPanel id={helpId} text={entry.text} example={entry.example} exampleLabel={exampleLabel} />}
    </div>
  );
}

/** Kotak bantuan yang muncul saat kolom di dalam grupnya sedang aktif (focus). */
export function HelpPanel({ id, text, example, exampleLabel, always }: { id?: string; text: string; example?: string; exampleLabel: string; always?: boolean }) {
  return (
    <div
      id={id}
      role="note"
      className={cn(
        "rounded-lg border border-accent/20 bg-accent-soft px-3 py-2 text-xs leading-relaxed text-ink",
        // Hanya saat kolom isian aktif — bukan saat tombol ditekan, agar tombol tidak bergeser di tengah klik.
        !always &&
          "hidden group-has-[input:focus]/field:block group-has-[select:focus]/field:block group-has-[textarea:focus]/field:block",
      )}
    >
      <p>{text}</p>
      {example && (
        <p className="mt-1 text-muted">
          <span className="font-medium text-accent">{exampleLabel}:</span> {example}
        </p>
      )}
    </div>
  );
}

/** Ikon ⓘ: penjelasan muncul saat kursor diarahkan, saat difokus keyboard, atau saat diketuk (HP). */
export function InfoTip({ text, example, exampleLabel, label }: { text: string; example?: string; exampleLabel?: string; label: string }) {
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const ref = useRef<HTMLButtonElement>(null);
  const show = () => {
    const r = ref.current?.getBoundingClientRect();
    if (!r) return;
    const width = 288;
    setPos({ top: r.bottom + 8, left: Math.max(8, Math.min(r.left - 12, window.innerWidth - width - 8)) });
  };
  const hide = () => setPos(null);
  useEffect(() => {
    if (!pos) return;
    window.addEventListener("scroll", hide, true);
    return () => window.removeEventListener("scroll", hide, true);
  }, [pos]);
  return (
    <>
      <button
        ref={ref}
        type="button"
        aria-label={`Info: ${label}`}
        aria-expanded={Boolean(pos)}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
        onClick={() => (pos ? hide() : show())}
        onKeyDown={(e) => e.key === "Escape" && hide()}
        className="rounded-full text-muted transition-colors hover:text-accent"
      >
        <Info className="size-3.5" aria-hidden />
      </button>
      {pos && (
        <span
          role="tooltip"
          style={{ top: pos.top, left: pos.left }}
          className="fixed z-[100] w-72 rounded-lg bg-ink px-3 py-2 text-xs leading-relaxed font-normal text-white shadow-lg"
        >
          {text}
          {example && (
            <span className="mt-1 block text-white/70">
              {exampleLabel}: {example}
            </span>
          )}
        </span>
      )}
    </>
  );
}

/** Judul bagian form dengan ⓘ, untuk grup kolom (baris fee, tenaga kerja, dll.). */
export function LegendWithHelp({ label, help, iconOnly }: { label: string; help: string; iconOnly?: boolean }) {
  const { help: getHelp, exampleLabel } = useHelp();
  const entry = getHelp(help);
  return (
    <span className="flex items-center gap-1.5 text-sm font-medium">
      {!iconOnly && label}
      {entry && <InfoTip text={entry.text} example={entry.example} exampleLabel={exampleLabel} label={label} />}
    </span>
  );
}

/** Input angka desimal sebagai teks (tidak pernah float). Menerima koma sebagai desimal. */
export function DecimalInput({
  value,
  onChange,
  suffix,
  ...rest
}: Omit<React.InputHTMLAttributes<HTMLInputElement>, "onChange" | "value"> & {
  value: string;
  onChange: (v: string) => void;
  suffix?: string;
}) {
  return (
    <div className="relative">
      <Input
        {...rest}
        inputMode="decimal"
        value={value}
        onChange={(e) => onChange(e.target.value.replace(",", ".").replace(/[^\d.\-]/g, ""))}
        className={cn("num text-right", suffix && "pr-10")}
      />
      {suffix && <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-sm text-muted">{suffix}</span>}
    </div>
  );
}

export function Card({ className, children, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div {...rest} className={cn("rounded-xl border border-line bg-surface", className)}>
      {children}
    </div>
  );
}

export function CardHeader({ title, description, action }: { title: string; description?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4">
      <div>
        <h2 className="text-base font-semibold text-ink">{title}</h2>
        {description && <p className="mt-0.5 text-sm text-muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function PageHeader({ title, description, action }: { title: string; description?: string; action?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function Badge({ tone = "neutral", children }: { tone?: "neutral" | "ok" | "warn" | "danger" | "accent"; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        tone === "neutral" && "bg-surface-2 text-muted ring-1 ring-line",
        tone === "ok" && "bg-ok-soft text-ok",
        tone === "warn" && "bg-warn-soft text-warn",
        tone === "danger" && "bg-danger-soft text-danger",
        tone === "accent" && "bg-accent-soft text-accent",
      )}
    >
      {children}
    </span>
  );
}

export function statusTone(status: string): "neutral" | "ok" | "warn" | "danger" | "accent" {
  if (["ACTIVE", "APPROVED", "PUBLISHED"].includes(status)) return "ok";
  if (["DRAFT", "PENDING_APPROVAL"].includes(status)) return "accent";
  if (["REJECTED"].includes(status)) return "danger";
  return "neutral";
}

export function Alert({ tone = "danger", title, children }: { tone?: "danger" | "warn" | "info" | "ok"; title?: string; children?: React.ReactNode }) {
  const Icon = tone === "info" || tone === "ok" ? Info : AlertTriangle;
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={cn(
        "flex gap-3 rounded-lg px-4 py-3 text-sm",
        tone === "danger" && "bg-danger-soft text-danger",
        tone === "warn" && "bg-warn-soft text-warn",
        tone === "info" && "bg-surface-2 text-muted ring-1 ring-line",
        tone === "ok" && "bg-ok-soft text-ok",
      )}
    >
      <Icon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <div className="min-w-0">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className={cn(title && "mt-0.5")}>{children}</div>}
      </div>
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted">
      <Loader2 className="size-4 animate-spin" aria-hidden />
      {label}
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="px-5 py-10 text-center text-sm text-muted">{children}</div>;
}

export function Table({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className="overflow-x-auto">
      <table className={cn("w-full text-sm", className)}>{children}</table>
    </div>
  );
}

export function Th({ children, className, align = "left" }: { children?: React.ReactNode; className?: string; align?: "left" | "right" }) {
  return (
    <th
      scope="col"
      className={cn(
        "border-b border-line bg-surface-2 px-4 py-2.5 text-xs font-medium tracking-wide text-muted uppercase",
        align === "right" ? "text-right" : "text-left",
        className,
      )}
    >
      {children}
    </th>
  );
}

export function Td({ children, className, align = "left" }: { children?: React.ReactNode; className?: string; align?: "left" | "right" }) {
  return <td className={cn("border-b border-line px-4 py-3 align-middle", align === "right" && "num text-right", className)}>{children}</td>;
}

export function Dialog({
  open,
  onClose,
  title,
  children,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onCancel={onClose}
      className={cn(
        "m-auto w-[calc(100%-2rem)] rounded-xl border border-line bg-surface p-0 text-ink shadow-xl backdrop:bg-black/30",
        wide ? "max-w-3xl" : "max-w-lg",
      )}
    >
      {open && (
        <div>
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <h2 className="text-base font-semibold">{title}</h2>
            <button type="button" onClick={onClose} className="rounded-md p-1 text-muted hover:bg-surface-2" aria-label="Close">
              <X className="size-4" />
            </button>
          </div>
          <div className="max-h-[75vh] overflow-y-auto px-5 py-4">{children}</div>
        </div>
      )}
    </dialog>
  );
}

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
}: {
  tabs: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <div role="tablist" className="mb-5 flex gap-1 overflow-x-auto border-b border-line">
      {tabs.map((t) => (
        <button
          key={t.value}
          role="tab"
          type="button"
          aria-selected={value === t.value}
          onClick={() => onChange(t.value)}
          className={cn(
            "-mb-px border-b-2 px-3 py-2 text-sm font-medium whitespace-nowrap transition-colors",
            value === t.value ? "border-accent text-accent" : "border-transparent text-muted hover:text-ink",
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function Stat({ label, value, sub, tone }: { label: string; value: React.ReactNode; sub?: React.ReactNode; tone?: "accent" }) {
  return (
    <div className={cn("rounded-xl border border-line bg-surface p-4", tone === "accent" && "border-accent/30 bg-accent-soft")}>
      <p className="text-sm text-muted">{label}</p>
      <p className={cn("num mt-1 text-2xl font-semibold tracking-tight", tone === "accent" ? "text-accent" : "text-ink")}>{value}</p>
      {sub && <p className="mt-1 text-xs text-muted">{sub}</p>}
    </div>
  );
}

/** Daftar langkah perhitungan dari engine (trace). */
export function Trace({ lines }: { lines: string[] }) {
  if (!lines.length) return null;
  return (
    <ol className="space-y-1 rounded-lg bg-surface-2 p-4 font-mono text-xs leading-relaxed text-ink ring-1 ring-line">
      {lines.map((l, i) => (
        <li key={i} className="break-words">
          <span className="mr-2 text-muted select-none">{String(i + 1).padStart(2, "0")}</span>
          {l}
        </li>
      ))}
    </ol>
  );
}
