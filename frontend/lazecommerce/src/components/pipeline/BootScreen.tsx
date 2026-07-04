import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Logo } from "./Logo";

const CHECKS = [
  { id: "redis", label: "Redis cache cluster", detail: "redis://primary:6379" },
  { id: "mongo", label: "MongoDB session store", detail: "mongodb://atlas/prod" },
  { id: "api", label: "Backend API gateway", detail: "https://api.lazecommerce.io" },
  { id: "ai", label: "AI inference engine", detail: "model: gen-turbo-v4" },
];

export function BootScreen({ onComplete }: { onComplete: () => void }) {
  const [idx, setIdx] = useState(-1);

  useEffect(() => {
    if (idx >= CHECKS.length) {
      const t = setTimeout(onComplete, 700);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setIdx((i) => i + 1), idx < 0 ? 350 : 650);
    return () => clearTimeout(t);
  }, [idx, onComplete]);

  return (
    <div className="min-h-[80vh] grid place-items-center px-4">
      <div className="w-full max-w-xl">
        <div className="flex flex-col items-center text-center mb-10">
          <Logo className="text-3xl md:text-4xl mb-3" />
          <p className="text-xs font-mono text-zinc-500 uppercase tracking-[0.3em]">
            System Boot · Verifying Services
          </p>
        </div>

        <div className="bg-brand-panel border border-zinc-800 rounded-xl p-5 md:p-6 space-y-2 scan-effect before:absolute before:inset-0 before:pointer-events-none">
          {CHECKS.map((c, i) => {
            const done = i <= idx;
            const active = i === idx + 1 && idx < CHECKS.length;
            return (
              <div
                key={c.id}
                className="flex items-center gap-3 py-2.5 px-3 rounded-md font-mono text-xs"
              >
                <motion.span
                  initial={{ scale: 0.5, opacity: 0 }}
                  animate={
                    done
                      ? { scale: 1, opacity: 1 }
                      : active
                        ? { scale: 1, opacity: 1 }
                        : { scale: 0.7, opacity: 0.4 }
                  }
                  transition={{ type: "spring", stiffness: 260, damping: 18 }}
                  className={
                    "size-5 rounded-full border flex items-center justify-center text-[10px] shrink-0 " +
                    (done
                      ? "bg-accent-primary text-brand-bg border-accent-primary shadow-[0_0_12px_var(--accent-primary)]"
                      : active
                        ? "border-accent-secondary text-accent-secondary"
                        : "border-zinc-700 text-zinc-600")
                  }
                >
                  {done ? "✓" : active ? <span className="animate-pulse">•</span> : ""}
                </motion.span>
                <div className="flex-1 min-w-0 flex items-center justify-between gap-3">
                  <span
                    className={
                      done ? "text-zinc-200" : active ? "text-zinc-300" : "text-zinc-600"
                    }
                  >
                    {c.label}
                  </span>
                  <span className="text-[10px] text-zinc-600 truncate hidden sm:block">
                    {c.detail}
                  </span>
                </div>
                <span
                  className={
                    "text-[10px] uppercase font-bold " +
                    (done
                      ? "text-accent-primary"
                      : active
                        ? "text-accent-secondary animate-pulse"
                        : "text-zinc-700")
                  }
                >
                  {done ? "Online" : active ? "Checking" : "Pending"}
                </span>
              </div>
            );
          })}
        </div>

        <p className="mt-6 text-center text-[10px] font-mono text-zinc-600 uppercase tracking-widest">
          {idx >= CHECKS.length ? "All systems nominal — booting workspace" : "Please wait"}
        </p>
      </div>
    </div>
  );
}
