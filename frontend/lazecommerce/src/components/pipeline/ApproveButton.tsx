import { motion } from "framer-motion";
import type { ReactNode } from "react";

export function ApproveButton({
  onClick,
  children,
  disabled,
}: {
  onClick: () => void;
  children: ReactNode;
  disabled?: boolean;
}) {
  return (
    <motion.button
      whileHover={{ scale: disabled ? 1 : 1.02 }}
      whileTap={{ scale: disabled ? 1 : 0.97 }}
      onClick={onClick}
      disabled={disabled}
      className="relative px-6 py-3 rounded-lg bg-accent-primary text-brand-bg text-sm font-bold uppercase tracking-wider flex items-center justify-center gap-2 shadow-[0_0_28px_color-mix(in_oklab,var(--accent-primary)_35%,transparent)] disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none transition-shadow"
    >
      {children}
      <svg
        className="size-4"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2.5}
          d="M13 7l5 5m0 0l-5 5m5-5H6"
        />
      </svg>
    </motion.button>
  );
}
