'use client'
import { useState, useEffect } from 'react'

/** Product workflow stage rendered by the single-page application. */
type Stage = 'idle' | 'scraping' | 'preview' | 'generating' | 'complete' | 'error'
/** Result tab available after AI generation completes. */
type Tab = 'overview' | 'seo' | 'pricing' | 'descriptions' | 'keywords'

/** Sanitized scrape preview returned by POST /extract. */
interface ScrapeData {
  raw_text: string
  vendor: string
  source_url: string
  text_length: number
}

/** Canonical AI product shape returned by the backend. */
interface AIProduct {
  product_title: string
  seo_title: string
  meta_description: string
  hsn_code: string
  sku: string
  weight_kg: number | string
  dimensions_cm: string | { L?: string; W?: string; H?: string }
  tags: string[]
  seo_keywords: string[]
  selling_price: {
    vendor_base_price?: number
    quartz_base_price?: number
    after_gst: number
    after_margin: number
    final_selling_price: number
    currency?: string
  }
  availability?: { status: string; quantity: number | null }
  short_description_html: string
  long_description_html: string
}

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
/** Labels used by the top progress indicator. */
const STEPS = ['Enter URL', 'Scraping', 'Review Text', 'AI Generating', 'Done']
/** Maps workflow stages to progress indicator positions. */
const STAGE_IDX: Record<Stage, number> = { idle: 0, scraping: 1, preview: 2, generating: 3, complete: 4, error: -1 }

/**
 * Product listing generator page.
 *
 * The page intentionally keeps scraping, editing, AI generation, and publishing
 * as explicit user-visible steps so expensive AI/API calls happen only after
 * review and approval.
 */
export default function Home() {
  const [stage, setStage] = useState<Stage>('idle')
  const [url, setUrl] = useState('')
  const [scrapeData, setScrapeData] = useState<ScrapeData | null>(null)
  const [editedText, setEditedText] = useState('')
  const [productId, setProductId] = useState<string | null>(null)
  const [aiData, setAiData] = useState<AIProduct | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<Tab>('overview')
  const [publishDone, setPublishDone] = useState(false)
  const [polling, setPolling] = useState(false)
  const [htmlView, setHtmlView] = useState<'rendered' | 'source'>('rendered')
  const [copied, setCopied] = useState<string | null>(null)
  const [genSeconds, setGenSeconds] = useState(0)

  /** Poll /status every 3 seconds while the Celery worker generates content. */
  useEffect(() => {
    if (!polling || !productId) return
    const iv = setInterval(async () => {
      try {
        const res = await fetch(`${API}/status/${productId}`)
        const d = await res.json()
        if (d.status === 'complete') {
          setAiData(d.data)
          setStage('complete')
          setPolling(false)
        } else if (d.status === 'failed') {
          setError(d.error || 'AI generation failed. Check the worker logs for details.')
          setStage('error')
          setPolling(false)
        } else if (!res.ok) {
          throw new Error(d.detail || 'Status check failed')
        }
      } catch {
        // Keep polling on transient network errors.
      }
    }, 3000)

    const tm = setTimeout(() => {
      setPolling(false)
      setError('AI generation timed out after 4 minutes. Check the Celery terminal for details.')
      setStage('error')
    }, 240_000)

    return () => { clearInterval(iv); clearTimeout(tm) }
  }, [polling, productId])

  /** Display elapsed generation time while polling is active. */
  useEffect(() => {
    if (stage !== 'generating') { setGenSeconds(0); return }
    const iv = setInterval(() => setGenSeconds(s => s + 1), 1000)
    return () => clearInterval(iv)
  }, [stage])

  /** Submit a supplier URL for extraction and move to editable preview. */
  async function handleScrape() {
    if (!url.trim()) return
    setStage('scraping')
    setError(null)
    try {
      const res = await fetch(`${API}/extract`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      })
      const d = await res.json()
      if (!res.ok) throw new Error(d.detail || 'Scrape failed')
      setScrapeData(d)
      setEditedText(d.raw_text)
      setStage('preview')
    } catch (e: unknown) {
      setError(errorMessage(e))
      setStage('error')
    }
  }

  /** Queue AI generation after the user approves or edits scraped text. */
  async function handleApprove() {
    if (!scrapeData) return
    setStage('generating')
    setError(null)
    try {
      const res = await fetch(`${API}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ raw_text: editedText, vendor: scrapeData.vendor, source_url: scrapeData.source_url }),
      })
      const d = await res.json()
      if (!res.ok) throw new Error(d.detail || 'Failed to queue generation')
      setProductId(d.product_id)
      setPolling(true)
    } catch (e: unknown) {
      setError(errorMessage(e))
      setStage('error')
    }
  }

  /** Publish the completed product or trigger a backend dry run in test mode. */
  async function handlePublish() {
    if (!productId) return
    try {
      const res = await fetch(`${API}/publish/${productId}`, { method: 'POST' })
      const d = await res.json()
      if (!res.ok) throw new Error(d.detail || 'Publish failed')
      setPublishDone(true)
    } catch (e: unknown) {
      setError(errorMessage(e))
    }
  }

  /** Copy a generated field to the clipboard and briefly mark it as copied. */
  function copy(text: string, key: string) {
    navigator.clipboard.writeText(text)
    setCopied(key)
    setTimeout(() => setCopied(null), 1800)
  }

  /** Reset all transient UI state for a new product search. */
  function reset() {
    setStage('idle'); setUrl(''); setScrapeData(null); setEditedText('')
    setProductId(null); setAiData(null); setError(null)
    setActiveTab('overview'); setPublishDone(false); setPolling(false)
  }

  const stageIdx = STAGE_IDX[stage]

  /** Format dimensions returned as either a string or structured L/W/H object. */
  function formatDimensions(dimensions: AIProduct['dimensions_cm']): string {
    if (typeof dimensions === 'string') return dimensions
    return [dimensions.L, dimensions.W, dimensions.H].filter(Boolean).join(' × ')
  }

  /** Convert unknown thrown values into display-safe error text. */
  function errorMessage(error: unknown): string {
    return error instanceof Error ? error.message : 'Unexpected error'
  }

  return (
    <div className="page-shell">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <header className="top-bar">
        <div className="brand">
          <div className="brand-icon">⚡</div>
          <div>
            <div className="brand-name">YANTRONIX</div>
            <div className="brand-sub">AI PRODUCT LISTING GENERATOR</div>
          </div>
        </div>
        {stage !== 'idle' && (
          <button className="btn-ghost" onClick={reset}>← New Search</button>
        )}
      </header>

      <main className="main-content">

        {/* ── Step indicator ──────────────────────────────────────────────── */}
        <div className="steps">
          {STEPS.map((label, i) => (
            <div key={i} className="step-item">
              <div className={`step-node ${i < stageIdx ? 'done' : i === stageIdx ? 'active' : ''}`}>
                {i < stageIdx ? '✓' : String(i + 1).padStart(2, '0')}
              </div>
              <span className={`step-label ${i <= stageIdx ? 'lit' : ''}`}>{label}</span>
              {i < STEPS.length - 1 && <div className={`step-line ${i < stageIdx ? 'lit' : ''}`} />}
            </div>
          ))}
        </div>

        {/* ── Error banner ────────────────────────────────────────────────── */}
        {error && (
          <div className="error-banner">
            <div className="error-inner">
              <span className="error-icon">⚠</span>
              <div>
                <div className="error-title">Error</div>
                <div className="error-body">{error}</div>
              </div>
            </div>
            <button className="error-close" onClick={() => setError(null)}>×</button>
          </div>
        )}

        {/* ── IDLE / ERROR — URL input ─────────────────────────────────────── */}
        {(stage === 'idle' || stage === 'error') && (
          <div className="center-section">
            <h1 className="hero-title">Paste a product URL</h1>
            <p className="hero-sub">Supports quartzcomponents.com · robu.in</p>
            <div className="url-row">
              <input
                type="text"
                className="url-input"
                placeholder="https://quartzcomponents.com/products/..."
                value={url}
                onChange={e => setUrl(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleScrape()}
              />
              <button
                className={`btn-primary ${!url.trim() ? 'disabled' : ''}`}
                onClick={handleScrape}
                disabled={!url.trim()}
              >
                Extract →
              </button>
            </div>
          </div>
        )}

        {/* ── SCRAPING — spinner ───────────────────────────────────────────── */}
        {stage === 'scraping' && (
          <div className="center-section">
            <div className="spinner">⟳</div>
            <div className="status-title">Fetching page...</div>
            <div className="status-sub">Converting HTML to plain text</div>
            <div className="url-chip">{url}</div>
          </div>
        )}

        {/* ── PREVIEW — extracted text review ─────────────────────────────── */}
        {stage === 'preview' && scrapeData && (
          <div>
            <div className="preview-header">
              <div>
                <h2 className="section-title">Review Extracted Text</h2>
                <div className="section-sub">
                  <span className="mono">{scrapeData.text_length.toLocaleString()}</span> characters from{' '}
                  <span className="accent mono">{scrapeData.vendor}</span>
                  {' · '}Edit below before sending to AI
                </div>
              </div>
              <div className="btn-row">
                <button className="btn-ghost" onClick={reset}>Cancel</button>
                <button className="btn-primary" onClick={handleApprove}>
                  Approve &amp; Send to AI →
                </button>
              </div>
            </div>

            <div className="text-box">
              <div className="text-box-bar mono">EXTRACTED TEXT — EDITABLE</div>
              <textarea
                className="text-area mono"
                value={editedText}
                onChange={e => setEditedText(e.target.value)}
              />
            </div>
            <div className="char-count mono">{editedText.length.toLocaleString()} chars</div>
          </div>
        )}

        {/* ── GENERATING — polling ─────────────────────────────────────────── */}
        {stage === 'generating' && (
          <div className="center-section">
            <div className="pulse-dots">
              <div className="dot" style={{ animationDelay: '0s' }} />
              <div className="dot" style={{ animationDelay: '0.2s' }} />
              <div className="dot" style={{ animationDelay: '0.4s' }} />
            </div>
            <div className="status-title">Gemini is generating your listing...</div>
            <div className="status-sub">Usually takes 20–40 seconds</div>
            <div className="timer mono">{String(Math.floor(genSeconds / 60)).padStart(2, '0')}:{String(genSeconds % 60).padStart(2, '0')}</div>
          </div>
        )}

        {/* ── COMPLETE — tabbed results ────────────────────────────────────── */}
        {stage === 'complete' && aiData && (
          <div>
            <div className="result-header">
              <div>
                <div className="result-label mono">GENERATION COMPLETE</div>
                <h2 className="result-title">{aiData.product_title}</h2>
              </div>
              <button
                className={`btn-publish ${publishDone ? 'done' : ''}`}
                onClick={handlePublish}
                disabled={publishDone}
              >
                {publishDone ? '✓ Published to Zoho' : 'Approve & Publish →'}
              </button>
            </div>

            {/* Tabs */}
            <div className="tab-bar">
              {(['overview', 'seo', 'pricing', 'descriptions', 'keywords'] as Tab[]).map(tab => (
                <button
                  key={tab}
                  className={`tab-btn ${activeTab === tab ? 'active' : ''}`}
                  onClick={() => setActiveTab(tab)}
                >
                  {tab.charAt(0).toUpperCase() + tab.slice(1)}
                </button>
              ))}
            </div>

            {/* ── OVERVIEW ── */}
            {activeTab === 'overview' && (
              <div>
                <table className="data-table">
                  <tbody>
                    {([
                      ['Product Title', aiData.product_title],
                      ['SKU', aiData.sku],
                      ['HSN Code', aiData.hsn_code],
                      ['Weight', `${aiData.weight_kg} kg`],
                      ['Dimensions', formatDimensions(aiData.dimensions_cm)],
                      ['Availability', aiData.availability?.status ?? '—'],
                    ] as [string, string | number][]).map(([k, v], i) => (
                      <tr key={k} className={i % 2 === 0 ? 'row-alt' : ''}>
                        <td className="td-key mono">{k}</td>
                        <td className="td-val">{v}</td>
                        <td className="td-copy">
                          <button className="copy-btn" onClick={() => copy(String(v), k)}>
                            {copied === k ? '✓' : '⧉'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="tags-section">
                  <div className="field-label mono">TAGS</div>
                  <div className="chip-row">
                    {(aiData.tags ?? []).map(tag => (
                      <span key={tag} className="chip chip-blue" onClick={() => copy(tag, tag)}>
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* ── SEO ── */}
            {activeTab === 'seo' && (
              <div className="col-gap">
                {[
                  { label: 'SEO TITLE', value: aiData.seo_title, max: 70 },
                  { label: 'META DESCRIPTION', value: aiData.meta_description, max: 160 },
                ].map(({ label, value, max }) => (
                  <div key={label} className="field-card">
                    <div className="field-card-head">
                      <span className="field-label mono">{label}</span>
                      <span className={`char-pill mono ${value.length > max ? 'over' : 'ok'}`}>
                        {value.length}/{max}
                      </span>
                    </div>
                    <div className="field-value">{value}</div>
                    <button className="copy-link" onClick={() => copy(value, label)}>
                      {copied === label ? '✓ Copied' : 'Copy'}
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* ── PRICING ── */}
            {activeTab === 'pricing' && (
              <div className="price-table">
                {[
                  { label: 'Vendor Base Price', val: aiData.selling_price.vendor_base_price ?? aiData.selling_price.quartz_base_price ?? 0 },
                  { label: 'After GST (18%)', val: aiData.selling_price.after_gst },
                  { label: 'After Margin (5%)', val: aiData.selling_price.after_margin },
                  { label: 'Final Selling Price', val: aiData.selling_price.final_selling_price, highlight: true },
                ].map(({ label, val, highlight }) => (
                  <div key={label} className={`price-row ${highlight ? 'price-highlight' : ''}`}>
                    <span className={`price-label ${highlight ? 'highlight-text' : ''}`}>{label}</span>
                    <span className={`price-val mono ${highlight ? 'highlight-text' : ''}`}>
                      ₹{Number(val).toFixed(2)}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* ── DESCRIPTIONS ── */}
            {activeTab === 'descriptions' && (
              <div className="col-gap">
                <div>
                  <div className="field-label mono" style={{ marginBottom: '10px' }}>SHORT DESCRIPTION</div>
                  <div className="html-preview" dangerouslySetInnerHTML={{ __html: aiData.short_description_html }} />
                </div>
                <div>
                  <div className="desc-head">
                    <span className="field-label mono">LONG DESCRIPTION</span>
                    <div className="view-toggle">
                      {(['rendered', 'source'] as const).map(v => (
                        <button
                          key={v}
                          className={`toggle-btn mono ${htmlView === v ? 'active' : ''}`}
                          onClick={() => setHtmlView(v)}
                        >
                          {v}
                        </button>
                      ))}
                    </div>
                  </div>
                  {htmlView === 'rendered'
                    ? <div className="html-preview html-scroll" dangerouslySetInnerHTML={{ __html: aiData.long_description_html }} />
                    : <pre className="html-source mono">{aiData.long_description_html}</pre>
                  }
                </div>
              </div>
            )}

            {/* ── KEYWORDS ── */}
            {activeTab === 'keywords' && (
              <div className="col-gap">
                <div>
                  <div className="field-label mono" style={{ marginBottom: '10px' }}>KEYWORDS</div>
                  <div className="chip-row">
                    {(aiData.seo_keywords ?? []).map(kw => (
                      <span key={kw} className="chip chip-green" onClick={() => copy(kw, kw)}>
                        {kw}
                      </span>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="field-label mono" style={{ marginBottom: '8px' }}>ALL KEYWORDS (comma separated)</div>
                  <div className="kw-block mono">
                    {(aiData.seo_keywords ?? []).join(', ')}
                  </div>
                  <button className="copy-link" onClick={() => copy((aiData.seo_keywords ?? []).join(', '), 'all-kw')}>
                    {copied === 'all-kw' ? '✓ Copied all' : 'Copy all'}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  )
}