import type { ReactNode } from "react";
import { Logo } from "./Logo";
import { Stepper } from "./Stepper";
import type { PipelineStep } from "./types";

export function PipelineShell({
  step,
  pipelineId,
  children,
}: {
  step: PipelineStep;
  pipelineId: string;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-brand-bg text-zinc-300 font-sans selection:bg-accent-primary/30 selection:text-white">
      <nav className="sticky top-0 z-50 border-b border-zinc-800/60 bg-brand-bg/80 backdrop-blur-md px-4 md:px-6 py-3 md:py-4">
        <div className="max-w-[1800px] mx-auto flex flex-col md:flex-row md:items-center justify-between gap-4 md:gap-6">
          <div className="flex items-center gap-3">
            <div className="size-8 rounded bg-accent-primary/15 flex items-center justify-center border border-accent-primary/30">
              <div className="size-2.5 bg-accent-primary rounded-sm animate-pulse shadow-[0_0_10px_var(--accent-primary)]" />
            </div>
            <div className="leading-tight">
              <Logo className="text-base md:text-lg" />
              <p className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest">
                Pipeline ID: {pipelineId}
              </p>
            </div>
          </div>
          <Stepper current={step} />
        </div>
      </nav>
      <main className="max-w-[1800px] mx-auto p-4 md:p-8 pb-24 md:pb-8">
        {children}
      </main>
    </div>
  );
}
