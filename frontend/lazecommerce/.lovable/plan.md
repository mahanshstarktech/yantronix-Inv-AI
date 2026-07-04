Change the name to this: "LazECommerce", The name should not be written as a plain text, Make it look like a logo. also I want the E to be a contrasting color.  
  
Build Plan: AI Scraper → Zoho Publisher Pipeline UI

A single-page, 4-step guided pipeline with cyber-industrial dark aesthetic (emerald #10b981 + cyan #06b6d4 accents, JetBrains Mono + Inter), Framer Motion transitions, and a fully client-side mock backend.

### Tech & dependencies

- Stack: existing TanStack Start + Tailwind v4 + shadcn.
- Add: `framer-motion`, `canvas-confetti`, `@fontsource/inter`, `@fontsource/jetbrains-mono`.
- Design tokens added to `src/styles.css`: `--brand-bg`, `--brand-panel`, `--accent-primary` (emerald), `--accent-secondary` (cyan), scanline keyframes, `.scan-effect` utility.

### Routing

- Single route `src/routes/index.tsx` hosts the entire pipeline as a state machine (`boot → extract → generate → publish → done`). No additional routes — this is one continuous workspace.
- `__root.tsx` updated with title/description for the tool.

### Component structure (`src/components/pipeline/`)

- `PipelineShell.tsx` — sticky top nav with logo, pipeline ID, animated stepper (4 stages).
- `BootScreen.tsx` — Step 0. Sequential check cascade (Redis → MongoDB → Backend API) with checkmark spring animations, then auto-advances.
- `ExtractStep.tsx` — Step 1. URL input + vendor dropdown (Quartzcomponents, +others), glowing "Extract Data" button. While loading: radar/scanline overlay + scrolling code-line skeleton. On result: editable `raw_text` textarea + "Approve & Generate AI Listing".
- `GenerateStep.tsx` — Step 2. Two sub-states:
  - Processing: animated AI brain (pulsing concentric rings + drifting sparkles), rotating status labels ("Analyzing specs…", "Generating SEO…", "Calculating prices…").
  - Review dashboard: ports the selected prototype's two-column layout (source/status sidebar + editable metadata/SEO/descriptions grid, tag chips with remove, tabbed long/short descriptions). All fields editable, bound to state. "Approve & Publish to Zoho" CTA.
- `PublishStep.tsx` — Step 3. Publishing animation (uplink beams), then success state: large checkmark spring, confetti burst, product ID + "Start new pipeline" reset button.
- `Stepper.tsx` — horizontal stepper showing current/complete/pending states with glow on active.

### Mock API (`src/lib/mock-api.ts`)

Pure client functions returning Promises with realistic delays. State kept in a `Map<product_id, MockProduct>`.

- `extract({ url })` → 1.5s delay → `{ url, vendor, raw_text }` (raw_text is a chunk of mock HTML/spec text derived from URL).
- `generate({ vendor, source_url, raw_text })` → 400ms → `{ success: true, product_id, vendor, text_length }`. Schedules the product to flip to COMPLETE after ~6s.
- `getStatus(product_id)` → returns `{ status: "PROCESSING", data: null, error: null }` until timer elapses, then `{ status: "COMPLETE", data: {...full schema...} }` with realistic ESP32/component data.
- `publish(product_id)` → 1.8s delay → `{ success: true, zoho_id: "ZP-XXXX" }`.

Exact response shapes match the spec so swapping mocks for `fetch()` later is a one-file change.

### State management

- Single `usePipeline` hook (or `useReducer`) in the index route holding: `step`, `url`, `vendor`, `rawText`, `productId`, `generatedData` (full schema), `publishResult`.
- Polling: `useEffect` with `setInterval(2000)` while in generate-processing sub-state; cleared on COMPLETE/unmount.
- Approve buttons are the only way to advance steps.

### Animations (Framer Motion)

- `AnimatePresence mode="wait"` on the main canvas to slide+fade between steps.
- Stepper dot fills with spring on completion.
- Boot checkmarks: staggered `scale` + `opacity` spring.
- Approve: button morphs into checkmark briefly, then advances.
- Publish success: confetti via `canvas-confetti`.

### Responsiveness

- Stepper: horizontal scroll on mobile, full inline on md+.
- Review dashboard: stacks single-column on mobile, 2-col on lg, 3-col with sidebar on xl. Sticky mobile bottom action bar (Discard / Approve) per the prototype.
- Inputs fluid `w-full`; max-w-[1800px] on outer container only.

### Out of scope (mock-mode)

- No Lovable Cloud, no auth, no persistence across reloads, no real Zoho integration.  
  
