import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { extract, type ExtractResponse } from "@/lib/mock-api";
import { ApproveButton } from "./ApproveButton";
import { toast } from "sonner";

const VENDORS = ["Quartzcomponents", "Robu.in", "Electronicscomp", "Amazon", "Custom"];

export function ExtractStep({
  initial,
  onApprove,
}: {
  initial: { url: string; vendor: string; rawText: string };
  onApprove: (v: ExtractResponse) => void;
}) {
  const [url, setUrl] = useState(initial.url || "https://quartzcomponents.com/products/esp32-wroom-32-module");
  const [vendor, setVendor] = useState(initial.vendor || "Quartzcomponents");
  const [rawText, setRawText] = useState(initial.rawText);
  const [loading, setLoading] = useState(false);
  const [hasData, setHasData] = useState(Boolean(initial.rawText));

  async function handleExtract() {
    if (!url) return;
    setLoading(true);
    setHasData(false);
    try {
      const res = await extract(url);
      setVendor(res.vendor || vendor);
      setRawText(res.raw_text || "");
      setHasData(true);
    } catch (err: any) {
      toast.error(err.message || "Failed to extract");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 md:gap-8">
      <section className="xl:col-span-7 space-y-6">
        <header>
          <span className="inline-block px-2 py-0.5 rounded bg-accent-secondary/10 border border-accent-secondary/20 text-[10px] text-accent-secondary font-mono uppercase mb-2">
            Step 01 / Source Extraction
          </span>
          <h2 className="text-2xl md:text-3xl font-bold text-white tracking-tight">
            Point me at a product page
          </h2>
          <p className="text-sm text-zinc-500 mt-2 max-w-xl">
            I&apos;ll scrape the URL, return the raw text payload, and hand it over for you
            to verify before passing it to the AI.
          </p>
        </header>

        <div className="bg-brand-panel border border-zinc-800 rounded-xl p-6 space-y-5">
          <div className="space-y-2">
            <label className="text-[10px] uppercase font-bold tracking-widest text-zinc-500">
              Product URL
            </label>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/products/widget"
              className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-accent-primary focus:ring-1 focus:ring-accent-primary transition-all"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto] gap-4 items-end">
            <div className="space-y-2 min-w-0">
              <label className="text-[10px] uppercase font-bold tracking-widest text-zinc-500">
                Vendor
              </label>
              <select
                value={vendor}
                onChange={(e) => setVendor(e.target.value)}
                className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-accent-primary focus:ring-1 focus:ring-accent-primary transition-all"
              >
                {VENDORS.map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            </div>
            <motion.button
              whileHover={{ scale: loading ? 1 : 1.02 }}
              whileTap={{ scale: 0.97 }}
              onClick={handleExtract}
              disabled={loading || !url}
              className="px-6 py-3 rounded-lg bg-accent-primary text-brand-bg text-sm font-bold uppercase tracking-wider shadow-[0_0_28px_color-mix(in_oklab,var(--accent-primary)_35%,transparent)] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? "Scraping…" : "Extract Data"}
            </motion.button>
          </div>
        </div>

        <div className="bg-brand-panel border border-zinc-800 rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b border-zinc-800 flex items-center justify-between">
            <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-zinc-400">
              raw_text payload
            </span>
            <span className="text-[10px] font-mono text-zinc-600">
              {rawText?.length?.toLocaleString() || "0"} chars
            </span>
          </div>
          <div className="relative">
            <textarea
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
              placeholder="Awaiting scrape…"
              readOnly={loading}
              className="w-full h-64 md:h-80 bg-zinc-950 p-5 text-zinc-400 font-mono text-xs leading-relaxed resize-none outline-none"
            />
            <AnimatePresence>
              {loading && <ScrapingOverlay />}
            </AnimatePresence>
          </div>
        </div>

        {hasData && !loading && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex justify-end"
          >
            <ApproveButton
              onClick={() =>
                onApprove({ url, vendor, raw_text: rawText })
              }
            >
              Approve & Generate AI Listing
            </ApproveButton>
          </motion.div>
        )}
      </section>

      <aside className="xl:col-span-5 space-y-5">
        <div className="bg-brand-panel border border-zinc-800 rounded-xl p-5">
          <h3 className="text-xs font-mono font-bold text-accent-primary uppercase tracking-wider mb-3">
            What happens here
          </h3>
          <ol className="space-y-3 text-sm text-zinc-400">
            <li className="flex gap-3">
              <span className="font-mono text-accent-secondary text-xs mt-0.5">01</span>
              The scraper fetches the URL through a rotating proxy pool.
            </li>
            <li className="flex gap-3">
              <span className="font-mono text-accent-secondary text-xs mt-0.5">02</span>
              HTML is cleaned, normalized, and converted to a raw text payload.
            </li>
            <li className="flex gap-3">
              <span className="font-mono text-accent-secondary text-xs mt-0.5">03</span>
              You review it. If it looks right, we hand it to the AI in step 2.
            </li>
          </ol>
        </div>

        <div className="bg-brand-panel border border-zinc-800 rounded-xl p-5">
          <h3 className="text-xs font-mono font-bold text-accent-secondary uppercase tracking-wider mb-3">
            Connection
          </h3>
          <div className="space-y-2 font-mono text-[11px]">
            <Row k="POST" v="/extract" />
            <Row k="status" v="ready" accent />
            <Row k="proxy" v="rotating-pool-3" />
            <Row k="vendor" v={vendor} />
          </div>
        </div>
      </aside>
    </div>
  );
}

function Row({ k, v, accent }: { k: string; v: string; accent?: boolean }) {
  return (
    <div className="flex justify-between">
      <span className="text-zinc-500">{k}</span>
      <span className={accent ? "text-accent-primary uppercase" : "text-zinc-300"}>{v}</span>
    </div>
  );
}

function ScrapingOverlay() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="absolute inset-0 bg-zinc-950/70 backdrop-blur-[2px] grid place-items-center overflow-hidden"
    >
      <div className="absolute inset-x-0 top-0 h-full pointer-events-none">
        <div
          className="absolute inset-x-0 h-px bg-gradient-to-r from-transparent via-accent-primary to-transparent"
          style={{ animation: "scanline 1.6s linear infinite" }}
        />
      </div>
      <div className="flex items-center gap-3 font-mono text-xs text-accent-primary">
        <div className="relative size-3">
          <span className="absolute inset-0 rounded-full bg-accent-primary/60" style={{ animation: "radar 1.8s ease-out infinite" }} />
          <span className="absolute inset-0 rounded-full bg-accent-primary" />
        </div>
        SCRAPING WEBSITE…
      </div>
    </motion.div>
  );
}
