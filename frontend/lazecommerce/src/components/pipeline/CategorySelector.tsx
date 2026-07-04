import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { CategoryNode, CategorySuggestResponse } from "@/lib/mock-api";

export type SelectedCategory = {
  category_id: string;
  name: string;
  breadcrumb: string; // e.g. "Electronics > Microcontrollers > ESP32"
};

interface CategorySelectorProps {
  tree: CategoryNode[];
  flat: CategoryNode[];
  suggestion: CategorySuggestResponse | null;
  loading: boolean;
  selected: SelectedCategory | null;
  onSelect: (cat: SelectedCategory) => void;
}

export function CategorySelector({
  tree,
  flat,
  suggestion,
  loading,
  selected,
  onSelect,
}: CategorySelectorProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Build breadcrumb path for a category_id
  function buildBreadcrumb(categoryId: string): string {
    const nodeMap = new Map(flat.map((n) => [n.category_id, n]));
    const parts: string[] = [];
    let current = nodeMap.get(categoryId);
    while (current) {
      parts.unshift(current.name);
      const parent = nodeMap.get(current.parent_category_id);
      current = parent?.category_id === current.category_id ? undefined : parent;
    }
    return parts.join(" › ");
  }

  function selectNode(node: CategoryNode) {
    onSelect({
      category_id: node.category_id,
      name: node.name,
      breadcrumb: buildBreadcrumb(node.category_id),
    });
    setOpen(false);
    setSearch("");
  }

  // Filter flat list for search
  const searchResults =
    search.trim().length > 0
      ? flat.filter((n) => n.name.toLowerCase().includes(search.toLowerCase()))
      : [];

  const suggestedNode =
    suggestion?.category_id ? flat.find((n) => n.category_id === suggestion.category_id) : null;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-[10px] uppercase font-bold tracking-widest text-zinc-500 block">
          Zoho Category
        </label>
        {loading && (
          <span className="text-[10px] font-mono text-accent-secondary animate-pulse">
            AI classifying…
          </span>
        )}
      </div>

      {/* AI suggestion banner */}
      <AnimatePresence>
        {suggestion?.category_id && !loading && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex items-start gap-2 p-2.5 rounded-lg bg-accent-primary/10 border border-accent-primary/30"
          >
            <span className="flex h-1.5 w-1.5 rounded-full bg-accent-primary mt-1.5 shrink-0 shadow-[0_0_6px_var(--accent-primary)]" />
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-widest text-accent-primary mb-0.5">
                AI Suggested · {Math.round((suggestion.confidence || 0) * 100)}% confidence
              </p>
              <p className="text-xs text-white font-medium truncate">{suggestion.category_name}</p>
              {suggestion.reasoning && (
                <p className="text-[10px] text-zinc-500 mt-0.5 font-mono italic truncate">
                  {suggestion.reasoning}
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Selected display / trigger */}
      <div ref={ref} className="relative">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          disabled={loading && flat.length === 0}
          className="w-full flex items-center justify-between gap-2 bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-3 text-left text-sm focus:outline-none focus:border-accent-primary focus:ring-1 focus:ring-accent-primary transition-all disabled:opacity-50"
        >
          <span className={selected ? "text-white truncate" : "text-zinc-500 truncate"}>
            {selected ? selected.breadcrumb || selected.name : "Select a category…"}
          </span>
          <svg
            viewBox="0 0 10 6"
            className={`size-3 shrink-0 text-zinc-500 transition-transform ${open ? "rotate-180" : ""}`}
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <path d="M1 1l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>

        <AnimatePresence>
          {open && (
            <motion.div
              initial={{ opacity: 0, y: 4, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 4, scale: 0.98 }}
              transition={{ duration: 0.15 }}
              className="absolute z-50 mt-1 w-full bg-zinc-950 border border-zinc-700 rounded-xl shadow-2xl overflow-hidden"
              style={{ maxHeight: "380px" }}
            >
              {/* Search */}
              <div className="p-2 border-b border-zinc-800">
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search categories…"
                  autoFocus
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-white placeholder:text-zinc-600 focus:outline-none focus:border-accent-primary"
                />
              </div>

              <div className="overflow-y-auto" style={{ maxHeight: "316px" }}>
                {search.trim() ? (
                  /* Search results — flat filtered list */
                  <div className="py-1">
                    {searchResults.length === 0 ? (
                      <p className="px-4 py-3 text-xs text-zinc-500 font-mono">No matches found</p>
                    ) : (
                      searchResults.map((node) => (
                        <FlatRow
                          key={node.category_id}
                          node={node}
                          isSuggested={node.category_id === suggestion?.category_id}
                          isSelected={node.category_id === selected?.category_id}
                          breadcrumb={buildBreadcrumb(node.category_id)}
                          onSelect={selectNode}
                        />
                      ))
                    )}
                  </div>
                ) : (
                  /* Tree view */
                  <div className="py-1">
                    {tree.map((node) => (
                      <TreeNode
                        key={node.category_id}
                        node={node}
                        depth={0}
                        selectedId={selected?.category_id ?? null}
                        suggestedId={suggestion?.category_id ?? null}
                        onSelect={selectNode}
                        buildBreadcrumb={buildBreadcrumb}
                      />
                    ))}
                  </div>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function TreeNode({
  node,
  depth,
  selectedId,
  suggestedId,
  onSelect,
  buildBreadcrumb,
}: {
  node: CategoryNode;
  depth: number;
  selectedId: string | null;
  suggestedId: string | null;
  onSelect: (n: CategoryNode) => void;
  buildBreadcrumb: (id: string) => string;
}) {
  const hasChildren = node.children.length > 0;
  const [expanded, setExpanded] = useState(false);
  const isSuggested = node.category_id === suggestedId;
  const isSelected = node.category_id === selectedId;

  // Auto-expand if a descendant is selected or suggested
  useEffect(() => {
    const targetId = selectedId || suggestedId;
    if (targetId && hasChildren) {
      const hasTarget = (nodes: CategoryNode[]): boolean =>
        nodes.some((n) => n.category_id === targetId || hasTarget(n.children));
      if (hasTarget(node.children)) setExpanded(true);
    }
  }, [selectedId, suggestedId, hasChildren, node.children]);

  return (
    <div>
      <div
        className={`flex items-center gap-2 px-3 py-2 cursor-pointer transition-colors text-xs
          ${isSelected ? "bg-accent-primary/20 text-accent-primary" : "hover:bg-zinc-800/60 text-zinc-300"}
          ${isSuggested && !isSelected ? "border-l-2 border-accent-primary" : ""}`}
        style={{ paddingLeft: `${12 + depth * 16}px` }}
        onClick={() => {
          if (hasChildren) setExpanded((v) => !v);
          onSelect(node);
        }}
      >
        {hasChildren ? (
          <svg
            viewBox="0 0 10 6"
            className={`size-2.5 shrink-0 transition-transform text-zinc-500 ${expanded ? "rotate-180" : ""}`}
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M1 1l4 4 4-4" />
          </svg>
        ) : (
          <span className="size-2.5 shrink-0" />
        )}
        <span className="truncate flex-1">{node.name}</span>
        {isSuggested && (
          <span className="shrink-0 text-[9px] font-bold uppercase tracking-wider text-accent-primary bg-accent-primary/10 px-1.5 py-0.5 rounded">
            AI
          </span>
        )}
        {isSelected && (
          <svg viewBox="0 0 12 10" className="size-3 shrink-0 text-accent-primary" fill="currentColor">
            <path d="M1 5l3.5 3.5L11 1" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" />
          </svg>
        )}
      </div>

      <AnimatePresence initial={false}>
        {expanded && hasChildren && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18 }}
            style={{ overflow: "hidden" }}
          >
            {node.children.map((child) => (
              <TreeNode
                key={child.category_id}
                node={child}
                depth={depth + 1}
                selectedId={selectedId}
                suggestedId={suggestedId}
                onSelect={onSelect}
                buildBreadcrumb={buildBreadcrumb}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function FlatRow({
  node,
  isSuggested,
  isSelected,
  breadcrumb,
  onSelect,
}: {
  node: CategoryNode;
  isSuggested: boolean;
  isSelected: boolean;
  breadcrumb: string;
  onSelect: (n: CategoryNode) => void;
}) {
  return (
    <div
      onClick={() => onSelect(node)}
      className={`flex items-center gap-2 px-4 py-2 cursor-pointer transition-colors text-xs
        ${isSelected ? "bg-accent-primary/20 text-accent-primary" : "hover:bg-zinc-800/60 text-zinc-300"}`}
    >
      <div className="flex-1 min-w-0">
        <p className="font-medium truncate">{node.name}</p>
        {breadcrumb !== node.name && (
          <p className="text-[10px] text-zinc-500 truncate">{breadcrumb}</p>
        )}
      </div>
      {isSuggested && (
        <span className="shrink-0 text-[9px] font-bold uppercase tracking-wider text-accent-primary bg-accent-primary/10 px-1.5 py-0.5 rounded">
          AI
        </span>
      )}
    </div>
  );
}
