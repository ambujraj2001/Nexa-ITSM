import clsx from "clsx";
import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { Icon } from "./ui";

type Tone = "success" | "error" | "info";
interface ToastItem {
  id: number;
  message: string;
  tone: Tone;
}

const ToastContext = createContext<(message: string, tone?: Tone) => void>(() => undefined);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const counter = useRef(0);
  const toast = useCallback((message: string, tone: Tone = "success") => {
    const id = ++counter.current;
    setItems((current) => [...current.slice(-2), { id, message, tone }]);
    window.setTimeout(() => setItems((current) => current.filter((t) => t.id !== id)), 3500);
  }, []);
  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div className="pointer-events-none fixed bottom-6 right-6 z-[60] flex flex-col items-end gap-space-sm" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} role="status" className="pointer-events-auto flex items-center gap-space-sm rounded bg-inverse-surface px-4 py-3 font-body-sm text-body-sm text-inverse-on-surface shadow-xl animate-fade-in">
            <Icon
              name={t.tone === "error" ? "error" : t.tone === "info" ? "info" : "task_alt"}
              className={clsx("text-[18px]", t.tone === "error" ? "text-error-container" : "text-tertiary-fixed")}
            />
            <span>{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
