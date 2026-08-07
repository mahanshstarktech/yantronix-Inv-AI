import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import confetti from "canvas-confetti";
import { publish } from "@/lib/mock-api";

export function PublishStep({
  productId,
  productTitle,
  categoryId,
  sendToAmazon,     // NEW: Received from index.tsx
  sendToFlipkart,   // NEW: Received from index.tsx
  onReset,
}: {
  productId: string;
  productTitle: string;
  categoryId: string | null;
  sendToAmazon: boolean;   // NEW: Type definition fix
  sendToFlipkart: boolean; // NEW: Type definition fix
  onReset: () => void;
}) {
  const [done, setDone] = useState(false);
  const [zohoId, setZohoId] = useState<string | null>(null);
  const started = useRef(false);
  const [error, setError] = useState<string | null>(null);

  // Automatically start publishing when this page loads
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    
    (async () => {
      try {
        // Sending all data including amazon/flipkart choices to the backend
        const r = await publish(productId, categoryId, sendToAmazon, sendToFlipkart);
        setZohoId(r.zoho_id ?? null);
        setDone(true);
        
        const burst = (originX: number) =>
          confetti({
            particleCount: 80,
            spread: 70,
            origin: { x: originX, y: 0.4 },
            colors: ["#10b981", "#06b6d4", "#ffffff"],
          });
        setTimeout(() => burst(0.3), 50);
        setTimeout(() => burst(0.7), 250);
        setTimeout(() => burst(0.5), 500);
      } catch (err: any) {
        console.error("Publish failed:", err);
        setError(err.message || "Failed to publish to selected marketplaces");
      }
    })();
  }, [productId, categoryId, sendToAmazon, sendToFlipkart]);

  return (
    <div className="min-h-[70vh] grid place-items-center px-4">
      <div className="w-full max-w-lg text-center">
        {!done ? (
          <>
            {error ? (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="p-6 rounded-xl bg-red-500/10 border border-red-500/20 text-center"
              >
                <div className="mx-auto size-14 rounded-full bg-red-500/20 grid place-items-center mb-4">
                  <svg viewBox="0 0 24 24" fill="none" className="size-8 text-red-500">
                    <path
                      d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                      stroke="currentColor" strokeWidth="2" strokeLinecap="round"
                    />
                  </svg>
                </div>
                <h3 className="text-lg font-bold text-red-400 mb-2">Publish Failed</h3>
                <p className="text-sm text-zinc-400 mb-6">{error}</p>
                <button
                  onClick={onReset}
                  className="px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-white text-sm"
                >
                  Start over
                </button>
              </motion.div>
            ) : (
              <>
                <div className="relative mx-auto size-40 mb-8">
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      className="absolute inset-0 rounded-full border border-accent-secondary/40"
                      style={{ animation: `radar 2s ease-out ${i * 0.5}s infinite` }}
                    />
                  ))}
                  <div className="absolute inset-1/4 rounded-full bg-accent-secondary/20 backdrop-blur grid place-items-center border border-accent-secondary/40 shadow-[0_0_40px_color-mix(in_oklab,var(--accent-secondary)_40%,transparent)]">
                    <svg viewBox="0 0 24 24" fill="none" className="size-10 text-accent-secondary">
                      <path
                        d="M12 3v12m0 0l-4-4m4 4l4-4M4 17v2a2 2 0 002 2h12a2 2 0 002-2v-2"
                        stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
                      />
                    </svg>
                  </div>
                </div>
                <span className="inline-block px-2 py-0.5 rounded bg-accent-secondary/10 border border-accent-secondary/20 text-[10px] text-accent-secondary font-mono uppercase mb-3">
                  Uplink Active
                </span>
                <h2 className="text-2xl md:text-3xl font-bold text-white tracking-tight mb-2">
                  Publishing Data...
                </h2>
                <p className="font-mono text-xs text-zinc-500">
                  Transmitting payload to selected marketplaces → Confirming receipt…
                </p>
                
                {/* Visual feedback of what is being published */}
                <div className="flex justify-center gap-3 mt-6">
                  <span className="px-3 py-1 rounded bg-zinc-800 text-xs text-zinc-300">Zoho</span>
                  {sendToAmazon && <span className="px-3 py-1 rounded bg-zinc-800 text-xs text-zinc-300">Amazon</span>}
                  {sendToFlipkart && <span className="px-3 py-1 rounded bg-zinc-800 text-xs text-zinc-300">Flipkart</span>}
                </div>
              </>
            )}
          </>
        ) : (
          <>
            <motion.div
              initial={{ scale: 0, rotate: -90 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ type: "spring", stiffness: 200, damping: 16 }}
              className="mx-auto size-28 rounded-full bg-accent-primary grid place-items-center mb-6 shadow-[0_0_60px_color-mix(in_oklab,var(--accent-primary)_45%,transparent)]"
            >
              <svg viewBox="0 0 24 24" fill="none" className="size-14 text-brand-bg">
                <motion.path
                  initial={{ pathLength: 0 }}
                  animate={{ pathLength: 1 }}
                  transition={{ duration: 0.5, delay: 0.2 }}
                  d="M5 13l4 4L19 7"
                  stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"
                />
              </svg>
            </motion.div>
            <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
              <span className="inline-block px-2 py-0.5 rounded bg-accent-primary/10 border border-accent-primary/20 text-[10px] text-accent-primary font-mono uppercase mb-3">
                Pipeline Complete
              </span>
              <h2 className="text-2xl md:text-3xl font-bold text-white tracking-tight mb-2">
                Published successfully
              </h2>
              <p className="text-sm text-zinc-400 mb-1 truncate">{productTitle}</p>
              
              <div className="flex justify-center gap-2 mt-4 mb-8">
                <span className="px-2 py-1 rounded bg-zinc-800 text-xs text-zinc-400">✅ Zoho</span>
                {sendToAmazon && <span className="px-2 py-1 rounded bg-zinc-800 text-xs text-zinc-400">✅ Amazon</span>}
                {sendToFlipkart && <span className="px-2 py-1 rounded bg-zinc-800 text-xs text-zinc-400">✅ Flipkart</span>}
              </div>

              <motion.button
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                onClick={onReset}
                className="px-6 py-3 rounded-lg bg-accent-primary text-brand-bg text-sm font-bold uppercase tracking-wider shadow-[0_0_28px_color-mix(in_oklab,var(--accent-primary)_35%,transparent)]"
              >
                Start a new pipeline →
              </motion.button>
            </motion.div>
          </>
        )}
      </div>
    </div>
  );
}