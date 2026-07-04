import { motion } from "framer-motion";
import type { PipelineStep } from "./types";

const STEPS: { id: PipelineStep; label: string; n: string }[] = [
  { id: "boot", label: "Boot", n: "00" },
  { id: "extract", label: "Extraction", n: "01" },
  { id: "generate", label: "AI Generation", n: "02" },
  { id: "publish", label: "Publishing", n: "03" },
];

const ORDER: PipelineStep[] = ["boot", "extract", "generate", "publish", "done"];

export function Stepper({ current }: { current: PipelineStep }) {
  const currentIdx = ORDER.indexOf(current);
  return (
    <div className="flex items-center gap-2 md:gap-6 overflow-x-auto pb-1 md:pb-0 -mx-2 px-2">
      {STEPS.map((s, i) => {
        const idx = ORDER.indexOf(s.id);
        const isActive = idx === currentIdx;
        const isDone = idx < currentIdx || current === "done";
        return (
          <div key={s.id} className="flex items-center gap-3 shrink-0">
            <motion.span
              layout
              animate={{
                backgroundColor: isDone
                  ? "color-mix(in oklab, var(--accent-primary) 100%, transparent)"
                  : isActive
                    ? "color-mix(in oklab, var(--accent-primary) 20%, transparent)"
                    : "transparent",
                borderColor: isDone || isActive
                  ? "color-mix(in oklab, var(--accent-primary) 50%, transparent)"
                  : "rgb(63 63 70)",
                color: isDone
                  ? "var(--brand-bg)"
                  : isActive
                    ? "var(--accent-primary)"
                    : "rgb(113 113 122)",
                boxShadow: isActive
                  ? "0 0 18px color-mix(in oklab, var(--accent-primary) 40%, transparent)"
                  : "0 0 0px transparent",
              }}
              transition={{ duration: 0.4 }}
              className="size-6 rounded-full border text-[10px] flex items-center justify-center font-bold font-mono"
            >
              {isDone ? "✓" : s.n}
            </motion.span>
            <span
              className={
                "text-xs font-medium whitespace-nowrap " +
                (isActive
                  ? "text-white"
                  : isDone
                    ? "text-zinc-400"
                    : "text-zinc-600")
              }
            >
              {s.label}
            </span>
            {i < STEPS.length - 1 && (
              <div className="w-6 md:w-10 h-px bg-zinc-800" />
            )}
          </div>
        );
      })}
    </div>
  );
}
