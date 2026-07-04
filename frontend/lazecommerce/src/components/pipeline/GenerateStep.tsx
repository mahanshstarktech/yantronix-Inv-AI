import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  generate,
  getStatus,
  getCategories,
  suggestCategory,
  getBrands,
  type ProductData,
  type CategoryNode,
  type CategorySuggestResponse,
  type ZohoBrand,
} from "@/lib/mock-api";
import { ApproveButton } from "./ApproveButton";
import { CategorySelector, type SelectedCategory } from "./CategorySelector";

const PROCESSING_LINES = [
  "Parsing scraped HTML structure…",
  "Identifying product attributes…",
  "Generating SEO title & meta description…",
  "Calculating final selling price + margin…",
  "Normalizing HSN classification…",
  "Drafting long-form description…",
];

type Phase = "submitting" | "processing" | "review";

export function GenerateStep({
  source,
  initialData,
  initialProductId,
  onProductId,
  onApprove,
}: {
  source: { vendor: string; source_url: string; raw_text: string };
  initialData: ProductData | null;
  initialProductId: string | null;
  onProductId: (id: string) => void;
  onApprove: (data: ProductData, productId: string, categoryId: string | null) => void;
}) {
  const [phase, setPhase] = useState<Phase>(initialData ? "review" : "submitting");
  const [productId, setProductId] = useState<string | null>(initialProductId);
  const [data, setData] = useState<ProductData | null>(initialData);
  const [activeTab, setActiveTab] = useState<"long" | "short">("long");
  const startedRef = useRef(false);

  // Category state
  const [categoryTree, setCategoryTree] = useState<CategoryNode[]>([]);
  const [categoryFlat, setCategoryFlat] = useState<CategoryNode[]>([]);
  const [categorySuggestion, setCategorySuggestion] = useState<CategorySuggestResponse | null>(null);
  const [categoryLoading, setCategoryLoading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<SelectedCategory | null>(null);

  // Brand state
  const [brands, setBrands] = useState<ZohoBrand[]>([]);
  const [matchedBrand, setMatchedBrand] = useState<ZohoBrand | null>(null);

  // kick off generate
  useEffect(() => {
    if (startedRef.current || initialData) return;
    startedRef.current = true;
    (async () => {
      try {
        const res = await generate(source);
        setProductId(res.product_id);
        onProductId(res.product_id);
        setPhase("processing");
      } catch (err: any) {
        import("sonner").then(({ toast }) => toast.error(err.message || "Failed to queue generation"));
      }
    })();
  }, [source, initialData, onProductId]);

  // poll status
  useEffect(() => {
    if (phase !== "processing" || !productId) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const s = await getStatus(productId);
        if (cancelled) return;
        if (s.status === "COMPLETE") {
          setData(s.data);
          setPhase("review");
          // Fetch categories + suggest in parallel after generation is done
          loadCategories(s.data);
        } else if (s.status === "ERROR") {
          import("sonner").then(({ toast }) => toast.error(s.error || "AI generation failed"));
          setPhase("submitting");
        }
      } catch (err: any) {
        if (!cancelled) {
          import("sonner").then(({ toast }) => toast.error(err.message || "Status check failed"));
        }
      }
    };
    tick();
    const id = setInterval(tick, 2000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [phase, productId]);

  // If we already have initialData, load categories immediately
  useEffect(() => {
    if (initialData && phase === "review" && categoryFlat.length === 0) {
      loadCategories(initialData);
    }
  }, []);

  async function loadCategories(product: ProductData) {
    setCategoryLoading(true);
    try {
      // Fetch categories AND brands in parallel
      const [catData, brandData] = await Promise.all([
        getCategories(),
        getBrands().catch(() => ({ brands: [], total: 0 })),
      ]);
      setCategoryTree(catData.tree);
      setCategoryFlat(catData.flat);
      setBrands(brandData.brands);

      // Auto-match brand from fetched Zoho brands
      if (product.brand && brandData.brands.length > 0) {
        const brandLower = product.brand.toLowerCase();
        const exact = brandData.brands.find((b) => b.name.toLowerCase() === brandLower);
        const partial = exact || brandData.brands.find((b) =>
          b.name.toLowerCase().includes(brandLower) || brandLower.includes(b.name.toLowerCase())
        );
        setMatchedBrand(partial ?? { brand_id: "", name: "Generic" });
      } else {
        setMatchedBrand({ brand_id: "", name: "Generic" });
      }

      // Suggest in parallel
      if (catData.flat.length > 0) {
        const flatForSuggest = catData.flat.map((n) => ({
          category_id: n.category_id,
          name: n.name,
        }));
        const suggestion = await suggestCategory(product, flatForSuggest);
        setCategorySuggestion(suggestion);

        // Auto-select the AI suggestion if user hasn't picked one yet
        if (suggestion.category_id && suggestion.category_name) {
          const node = catData.flat.find((n) => n.category_id === suggestion.category_id);
          if (node) {
            setSelectedCategory({
              category_id: node.category_id,
              name: node.name,
              breadcrumb: buildBreadcrumbFromFlat(node.category_id, catData.flat),
            });
          }
        }
      }
    } catch (err: any) {
      import("sonner").then(({ toast }) =>
        toast.error(`Category loading failed: ${err.message || "unknown error"}`)
      );
    } finally {
      setCategoryLoading(false);
    }
  }

  if (phase !== "review" || !data) {
    return <ProcessingPanel />;
  }

  return (
    <ReviewDashboard
      data={data}
      onChange={setData}
      activeTab={activeTab}
      setActiveTab={setActiveTab}
      source={source}
      productId={productId!}
      categoryTree={categoryTree}
      categoryFlat={categoryFlat}
      categorySuggestion={categorySuggestion}
      categoryLoading={categoryLoading}
      selectedCategory={selectedCategory}
      onCategorySelect={setSelectedCategory}
      matchedBrand={matchedBrand}
      onApprove={() => onApprove(data, productId!, selectedCategory?.category_id ?? null)}
    />
  );
}

// ── Utilities ─────────────────────────────────────────────────────────────────

function buildBreadcrumbFromFlat(categoryId: string, flat: CategoryNode[]): string {
  const nodeMap = new Map(flat.map((n) => [n.category_id, n]));
  const parts: string[] = [];
  let current = nodeMap.get(categoryId);
  const visited = new Set<string>();
  while (current && !visited.has(current.category_id)) {
    visited.add(current.category_id);
    parts.unshift(current.name);
    const parent = nodeMap.get(current.parent_category_id);
    current = parent?.category_id !== current.category_id ? parent : undefined;
  }
  return parts.join(" › ");
}

// ── Processing panel ──────────────────────────────────────────────────────────

function ProcessingPanel() {
  const [lineIdx, setLineIdx] = useState(0);
  useEffect(() => {
    const id = setInterval(
      () => setLineIdx((i) => (i + 1) % PROCESSING_LINES.length),
      1400
    );
    return () => clearInterval(id);
  }, []);

  return (
    <div className="min-h-[70vh] grid place-items-center">
      <div className="text-center max-w-md w-full px-4">
        <div className="relative mx-auto size-40 md:size-56 mb-8">
          {[0, 1, 2, 3].map((i) => (
            <span
              key={i}
              className="absolute inset-0 rounded-full border border-accent-primary/40"
              style={{
                animation: `radar 2.4s ease-out ${i * 0.6}s infinite`,
              }}
            />
          ))}
          <div className="absolute inset-1/4 rounded-full bg-accent-primary/20 backdrop-blur grid place-items-center border border-accent-primary/40 shadow-[0_0_40px_color-mix(in_oklab,var(--accent-primary)_40%,transparent)]">
            <svg viewBox="0 0 24 24" fill="none" className="size-10 text-accent-primary">
              <path
                d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
              <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.5" />
            </svg>
          </div>
        </div>
        <span className="inline-block px-2 py-0.5 rounded bg-accent-primary/10 border border-accent-primary/20 text-[10px] text-accent-primary font-mono uppercase mb-3">
          AI Engine v4 · Working
        </span>
        <h2 className="text-2xl md:text-3xl font-bold text-white tracking-tight mb-3">
          Generating product intelligence
        </h2>
        <div className="h-6">
          <AnimatePresence mode="wait">
            <motion.p
              key={lineIdx}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.3 }}
              className="font-mono text-xs text-zinc-400"
            >
              {PROCESSING_LINES[lineIdx]}
            </motion.p>
          </AnimatePresence>
        </div>
        <div className="mt-6 h-1 w-full bg-zinc-900 rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-gradient-to-r from-accent-secondary to-accent-primary"
            initial={{ x: "-100%" }}
            animate={{ x: "100%" }}
            transition={{ repeat: Infinity, duration: 2, ease: "linear" }}
            style={{ width: "60%" }}
          />
        </div>
      </div>
    </div>
  );
}

// ── Review dashboard ──────────────────────────────────────────────────────────

function ReviewDashboard({
  data,
  onChange,
  activeTab,
  setActiveTab,
  source,
  productId,
  categoryTree,
  categoryFlat,
  categorySuggestion,
  categoryLoading,
  selectedCategory,
  onCategorySelect,
  matchedBrand,
  onApprove,
}: {
  data: ProductData;
  onChange: (d: ProductData) => void;
  activeTab: "long" | "short";
  setActiveTab: (t: "long" | "short") => void;
  source: { vendor: string; source_url: string; raw_text: string };
  productId: string;
  categoryTree: CategoryNode[];
  categoryFlat: CategoryNode[];
  categorySuggestion: CategorySuggestResponse | null;
  categoryLoading: boolean;
  selectedCategory: SelectedCategory | null;
  onCategorySelect: (cat: SelectedCategory) => void;
  matchedBrand: ZohoBrand | null;
  onApprove: () => void;
}) {
  const set = <K extends keyof ProductData>(k: K, v: ProductData[K]) =>
    onChange({ ...data, [k]: v });

  return (
    <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 md:gap-8">
      <aside className="xl:col-span-3 space-y-6 order-2 xl:order-1">
        {/* System status */}
        <div className="bg-brand-panel border border-zinc-800 rounded-xl p-5 scan-effect relative overflow-hidden">
          <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent-primary/40 to-transparent" style={{animation:"scanline 5s linear infinite"}} />
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xs font-mono font-bold text-accent-primary uppercase tracking-wider">
              System Status
            </h3>
            <span className="flex h-2 w-2 rounded-full bg-accent-primary shadow-[0_0_8px_var(--accent-primary)]" />
          </div>
          <div className="space-y-3 font-mono text-[11px]">
            <Row k="Redis Cluster" v="Online" accent />
            <Row k="Z-API Proxy" v="Connected" accent />
            <Row k="AI Engine (v4)" v="Ready" accent />
          </div>
          <div className="mt-6 p-3 bg-zinc-950 rounded border border-zinc-800/50">
            <p className="text-[10px] leading-relaxed text-zinc-400 font-mono">
              &gt; Processed data for{" "}
              <span className="text-accent-secondary">{source.vendor}</span>
              <br />
              &gt; Product ID:{" "}
              <span className="text-accent-secondary">{productId}</span>
              <br />
              &gt; Status:{" "}
              <span className="text-accent-primary animate-pulse">COMPLETE</span>
            </p>
          </div>
        </div>

        {/* Category Selector */}
        <div className="bg-brand-panel border border-zinc-800 rounded-xl p-5">
          <h3 className="text-xs font-mono font-bold text-accent-secondary uppercase tracking-wider mb-4">
            Zoho Category
          </h3>
          {categoryFlat.length === 0 && !categoryLoading ? (
            <p className="text-[11px] text-zinc-500 font-mono">
              Could not load categories. You can still publish — the product will appear uncategorised,
              or check your Zoho OAuth scopes.
            </p>
          ) : (
            <CategorySelector
              tree={categoryTree}
              flat={categoryFlat}
              suggestion={categorySuggestion}
              loading={categoryLoading}
              selected={selectedCategory}
              onSelect={onCategorySelect}
            />
          )}
        </div>

        {/* Zoho Fields Preview */}
        <div className="bg-brand-panel border border-zinc-800 rounded-xl p-5">
          <h3 className="text-xs font-mono font-bold text-accent-primary uppercase tracking-wider mb-4">
            Zoho Fields Preview
          </h3>
          <div className="space-y-2.5 font-mono text-[11px]">
            <Row k="Unit" v="Nos" accent />
            <Row k="Brand → Zoho" v={matchedBrand?.name ?? "Matching…"} accent={matchedBrand?.name !== "Generic"} />
            <Row k="Company Division" v="Yantronix" accent />
            <div className="flex justify-between gap-2">
              <span className="text-zinc-500 shrink-0">Ref Link</span>
              <a
                href={source.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent-secondary text-right truncate hover:underline"
                title={source.source_url}
              >
                {source.source_url.length > 30
                  ? source.source_url.slice(0, 30) + "…"
                  : source.source_url}
              </a>
            </div>
          </div>
        </div>

        <div className="bg-brand-panel border border-zinc-800 rounded-xl overflow-hidden">
          <div className="p-4 border-b border-zinc-800">
            <span className="text-xs font-bold uppercase tracking-widest text-zinc-400">
              Source URL
            </span>
          </div>
          <div className="p-4">
            <p className="text-xs font-mono text-zinc-500 truncate">
              {source.source_url}
            </p>
          </div>
          <details className="border-t border-zinc-800">
            <summary className="px-4 py-3 cursor-pointer text-[10px] uppercase font-bold tracking-widest text-accent-secondary hover:text-accent-primary transition-colors">
              View scraped raw text
            </summary>
            <pre className="px-4 pb-4 text-[10px] font-mono text-zinc-500 max-h-64 overflow-auto whitespace-pre-wrap">
              {source.raw_text}
            </pre>
          </details>
        </div>
      </aside>

      <section className="xl:col-span-9 space-y-6 order-1 xl:order-2">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <span className="inline-block px-2 py-0.5 rounded bg-accent-primary/10 border border-accent-primary/20 text-[10px] text-accent-primary font-mono uppercase mb-2">
              Generation Complete
            </span>
            <h2 className="text-2xl md:text-3xl font-bold text-white tracking-tight">
              Review & Approve Listing
            </h2>
          </div>
          <div className="hidden md:block">
            <ApproveButton onClick={onApprove}>
              Approve & Publish to Zoho
            </ApproveButton>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-brand-panel border border-zinc-800 rounded-xl p-6 space-y-6">
            <Field label="Product Title">
              <input
                type="text"
                value={data.product_title}
                onChange={(e) => set("product_title", e.target.value)}
                className={inputCls}
              />
            </Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="SKU">
                <input
                  type="text"
                  value={data.sku}
                  onChange={(e) => set("sku", e.target.value)}
                  className={inputCls + " font-mono text-sm"}
                />
              </Field>
              <Field label="HSN Code">
                <input
                  type="text"
                  value={data.hsn_code}
                  onChange={(e) => set("hsn_code", e.target.value)}
                  className={inputCls + " font-mono text-sm"}
                />
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Brand (AI extracted)">
                <input
                  type="text"
                  value={data.brand}
                  onChange={(e) => set("brand", e.target.value)}
                  className={inputCls + " text-sm"}
                />
              </Field>
              <Field label="Zoho Brand Match">
                <div className={inputCls + " flex items-center gap-2 text-sm " + (matchedBrand && matchedBrand.name !== "Generic" ? "border-accent-primary/50 text-accent-primary" : "text-zinc-400")}>
                  <span className={"size-2 rounded-full shrink-0 " + (matchedBrand && matchedBrand.name !== "Generic" ? "bg-accent-primary" : "bg-zinc-600")} />
                  {matchedBrand ? matchedBrand.name : "Matching…"}
                </div>
              </Field>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Base Price (INR)">
                <input
                  type="number"
                  value={data.base_price}
                  onChange={(e) =>
                    set("base_price", parseFloat(e.target.value) || 0)
                  }
                  className={inputCls + " font-mono text-sm"}
                />
              </Field>
              <Field label="Final Selling Price">
                <input
                  type="number"
                  value={data.final_selling_price}
                  onChange={(e) =>
                    set("final_selling_price", parseFloat(e.target.value) || 0)
                  }
                  className={
                    "w-full bg-zinc-950 border border-accent-primary/40 rounded-lg px-4 py-3 text-accent-primary font-mono text-sm focus:outline-none focus:ring-1 focus:ring-accent-primary"
                  }
                />
              </Field>
            </div>
            <Field label="Tags">
              <ChipEditor
                values={data.tags}
                onChange={(v) => set("tags", v)}
                placeholder="Add tag"
              />
            </Field>
          </div>

          <div className="bg-brand-panel border border-zinc-800 rounded-xl p-6 space-y-6">
            <Field label="SEO Meta Title">
              <input
                type="text"
                value={data.seo_title}
                onChange={(e) => set("seo_title", e.target.value)}
                className={inputCls}
              />
            </Field>
            <Field label="Meta Description">
              <textarea
                value={data.meta_description}
                onChange={(e) => set("meta_description", e.target.value)}
                className={inputCls + " h-28 resize-none text-sm"}
              />
            </Field>
            <Field label="SEO Keywords">
              <ChipEditor
                values={data.seo_keywords}
                onChange={(v) => set("seo_keywords", v)}
                placeholder="Add keyword"
              />
            </Field>
            <div className="p-4 rounded-lg bg-accent-secondary/5 border border-accent-secondary/20">
              <div className="flex items-center gap-2 mb-2">
                <div className="size-2 bg-accent-secondary rounded-full animate-pulse" />
                <span className="text-[10px] font-bold uppercase tracking-widest text-accent-secondary">
                  AI Content Analysis
                </span>
              </div>
              <p className="text-[11px] text-zinc-400 leading-relaxed font-mono italic">
                "Keywords optimized for high intent. Calculated margin:{" "}
                {(
                  ((data.final_selling_price - data.base_price) /
                    Math.max(data.base_price, 0.01)) *
                  100
                ).toFixed(1)}
                % over base price."
              </p>
            </div>
          </div>

          <div className="lg:col-span-2">
            <div className="bg-brand-panel border border-zinc-800 rounded-xl overflow-hidden">
              <div className="flex border-b border-zinc-800">
                <TabBtn active={activeTab === "long"} onClick={() => setActiveTab("long")}>
                  Long Description (HTML)
                </TabBtn>
                <TabBtn active={activeTab === "short"} onClick={() => setActiveTab("short")}>
                  Short Description
                </TabBtn>
              </div>
              <div className="p-6">
                {activeTab === "long" ? (
                  <textarea
                    value={data.long_description_html}
                    onChange={(e) => set("long_description_html", e.target.value)}
                    className="w-full h-64 bg-zinc-950 border border-zinc-800 rounded-lg p-6 text-zinc-300 font-mono text-xs leading-relaxed focus:outline-none focus:border-accent-primary"
                  />
                ) : (
                  <textarea
                    value={data.short_description_html}
                    onChange={(e) => set("short_description_html", e.target.value)}
                    className="w-full h-32 bg-zinc-950 border border-zinc-800 rounded-lg p-6 text-zinc-300 font-mono text-xs leading-relaxed focus:outline-none focus:border-accent-primary"
                  />
                )}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* mobile bottom action bar */}
      <div className="md:hidden fixed bottom-0 inset-x-0 p-3 bg-brand-bg/90 backdrop-blur-xl border-t border-zinc-800 z-40">
        <button
          onClick={onApprove}
          className="w-full py-3 rounded-lg bg-accent-primary text-brand-bg text-sm font-bold uppercase tracking-wider"
        >
          Approve & Publish to Zoho
        </button>
      </div>
    </div>
  );
}

// ── Shared UI helpers ─────────────────────────────────────────────────────────

const inputCls =
  "w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-accent-primary focus:ring-1 focus:ring-accent-primary transition-all";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <label className="text-[10px] uppercase font-bold tracking-widest text-zinc-500 block">
        {label}
      </label>
      {children}
    </div>
  );
}

function TabBtn({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={
        "px-6 py-3 text-xs font-bold uppercase tracking-widest border-b-2 transition-colors " +
        (active
          ? "border-accent-primary text-white"
          : "border-transparent text-zinc-500 hover:text-zinc-300")
      }
    >
      {children}
    </button>
  );
}

function Row({ k, v, accent }: { k: string; v: string; accent?: boolean }) {
  return (
    <div className="flex justify-between">
      <span className="text-zinc-500">{k}</span>
      <span className={accent ? "text-accent-primary uppercase" : "text-zinc-300"}>
        {v}
      </span>
    </div>
  );
}

function ChipEditor({
  values,
  onChange,
  placeholder,
}: {
  values: string[];
  onChange: (v: string[]) => void;
  placeholder: string;
}) {
  const [draft, setDraft] = useState("");
  return (
    <div className="flex flex-wrap gap-2">
      {values.map((t, i) => (
        <span
          key={t + i}
          className="px-2 py-1 rounded-md bg-zinc-900 border border-zinc-700 text-[11px] text-zinc-300 flex items-center gap-2"
        >
          {t}
          <button
            onClick={() => onChange(values.filter((_, j) => j !== i))}
            className="text-zinc-500 hover:text-white"
            aria-label="remove"
          >
            ×
          </button>
        </span>
      ))}
      <input
        type="text"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if ((e.key === "Enter" || e.key === ",") && draft.trim()) {
            e.preventDefault();
            onChange([...values, draft.trim()]);
            setDraft("");
          }
        }}
        placeholder={placeholder}
        className="px-2 py-1 rounded-md border border-dashed border-zinc-700 text-[11px] bg-transparent text-zinc-300 placeholder:text-zinc-600 focus:outline-none focus:border-accent-primary min-w-[8ch]"
      />
    </div>
  );
}
