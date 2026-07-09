import { useEffect, useState } from 'react'
import {
  AlertCircle, CheckCircle2, ExternalLink, Globe, Loader2,
  RefreshCw, X, Package,
} from 'lucide-react'

interface ScrapedProduct {
  platform_product_id: string
  title: string
  price: number | null
  stock: number | null
  sku: string | null
  category: string | null
  description: string | null
  image_url: string | null
  status: string | null
}

interface WizardProps {
  platform: string
  platformName: string
  onClose: () => void
}

type WizardStep =
  | 'idle' | 'opening' | 'check_login'
  | 'ready' | 'scanning' | 'show_products'
  | 'importing' | 'done' | 'error'

const getApiError = (data: any, fallback: string) => {
  const detail = data?.detail
  if (typeof detail === 'string') return detail
  if (detail?.message) return detail.message
  if (data?.message) return data.message
  if (data?.session?.error_message) return data.session.error_message
  return fallback
}

export default function ProductScrapeWizard({
  platform, platformName, onClose,
}: WizardProps) {
  const [step, setStep] = useState<WizardStep>('idle')
  const [loginStatus, setLoginStatus] = useState<'unknown' | 'login_required' | 'ready'>('unknown')
  const setSessionInfo = (_info: { current_url?: string; page_title?: string }) => {
    // session info tracked for debugging; kept for future use
  }
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [scrapeTaskId, setScrapeTaskId] = useState<string | null>(null)
  const [scrapeRunning, setScrapeRunning] = useState(false)
  const [scrapeProgress, setScrapeProgress] = useState('')

  const [products, setProducts] = useState<ScrapedProduct[]>([])
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [importProgress, setImportProgress] = useState<string>('')
  const [importResult, setImportResult] = useState<{ ok: number; fail: number } | null>(null)
  const [showConfirm, setShowConfirm] = useState(false)

  // Poll scrape task status
  useEffect(() => {
    if (!scrapeTaskId || !scrapeRunning) return
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/products/scrape/${scrapeTaskId}/status`)
        const data = await res.json()
        setScrapeProgress(data.progress || '')

        if (data.status === 'completed') {
          setScrapeRunning(false)
          if (data.products && data.products.length > 0) {
            setProducts(data.products)
            setStep('show_products')
            // Auto-select all
            setSelectedIds(new Set(data.products.map((p: ScrapedProduct) => p.platform_product_id)))
          } else if (data.product_count > 0) {
            setStep('done')
            setImportResult({ ok: data.product_count, fail: 0 })
          } else {
            setErrorMsg('未找到商品')
            setStep('error')
          }
        } else if (data.status === 'error') {
          setScrapeRunning(false)
          setErrorMsg(data.error || '抓取失败')
          setStep('error')
        }
      } catch { /* ignore polling errors */ }
    }, 2000)
    return () => clearInterval(interval)
  }, [scrapeTaskId, scrapeRunning])

  // Open browser
  const handleOpenPage = async () => {
    setLoading(true)
    setErrorMsg(null)
    setStep('opening')
    try {
      const res = await fetch('/api/platform-browser/open', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform, page_type: 'products', headed: true }),
      })
      const data = await res.json()
      if (!res.ok || data?.ok === false || data?.session?.status === 'error') {
        setErrorMsg(getApiError(data, '打开页面失败'))
        setStep('error')
        return
      }
      setSessionInfo({ current_url: data.session?.current_url, page_title: data.session?.page_title })
      setStep('check_login')
      await handleCheckLogin()
    } catch {
      setErrorMsg('无法连接到后端服务')
      setStep('error')
    } finally {
      setLoading(false)
    }
  }

  // Check login
  const handleCheckLogin = async () => {
    setLoading(true)
    setErrorMsg(null)
    try {
      const res = await fetch('/api/platform-browser/check-login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform, page_type: 'products' }),
      })
      const data = await res.json()
      setSessionInfo({ current_url: data.current_url, page_title: data.page_title })
      if (data.logged_in && data.status === 'ready') {
        setLoginStatus('ready')
        setStep('ready')
      } else {
        setLoginStatus('login_required')
      }
    } catch {
      setErrorMsg('检测登录状态失败')
    } finally {
      setLoading(false)
    }
  }

  // Scan list (list_only)
  const handleScan = async () => {
    setScrapeRunning(true)
    setScrapeTaskId(null)
    setScrapeProgress('正在扫描商品列表…')
    setStep('scanning')
    try {
      const res = await fetch('/api/products/scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          merchant_id: 'default', platform,
          list_only: true, max_pages: 3,
        }),
      })
      const data = await res.json()
      if (!res.ok) {
        setErrorMsg(data.detail?.message || data.detail || '扫描失败')
        setStep('error')
        setScrapeRunning(false)
        return
      }
      setScrapeTaskId(data.task_id)
    } catch {
      setScrapeRunning(false)
      setErrorMsg('无法启动扫描任务')
      setStep('error')
    }
  }

  // Toggle product selection
  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (selectedIds.size === products.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(products.map(p => p.platform_product_id)))
    }
  }

  // Confirm selection dialog
  const handleShowConfirm = () => {
    if (selectedIds.size === 0) {
      setErrorMsg('请至少选择一个商品')
      return
    }
    setShowConfirm(true)
  }

  const handleCancelConfirm = () => {
    setShowConfirm(false)
  }

  // Start detail scraping + import for selected products
  const handleStartImport = async () => {
    setShowConfirm(false)
    const selected = products.filter(p => selectedIds.has(p.platform_product_id))
    if (selected.length === 0) return

    setStep('importing')
    setScrapeTaskId(null)
    setScrapeProgress('')
    setImportProgress('准备导入…')

    try {
      const res = await fetch('/api/products/scrape-details', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          merchant_id: 'default',
          platform,
          products: selected,
          max_detail: selected.length,
        }),
      })
      const data = await res.json()
      if (!res.ok) {
        setErrorMsg(data.detail?.message || data.detail || '导入失败')
        setStep('error')
        return
      }
      setScrapeTaskId(data.task_id)
    } catch {
      setErrorMsg('无法启动导入任务')
      setStep('error')
    }
  }

  // Poll details scrape task
  useEffect(() => {
    if (!scrapeTaskId || step !== 'importing') return
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/products/scrape/${scrapeTaskId}/status`)
        const data = await res.json()
        setImportProgress(data.progress || '')
        if (data.status === 'completed') {
          setImportResult({ ok: data.product_count || 0, fail: 0 })
          setStep('done')
        } else if (data.status === 'error') {
          setErrorMsg(data.error || '导入失败')
          setStep('error')
        }
      } catch { /* ignore */ }
    }, 2000)
    return () => clearInterval(interval)
  }, [scrapeTaskId, step])

  const STEPS = [
    { key: 'idle', label: '准备' },
    { key: 'opening', label: '打开' },
    { key: 'ready', label: '就绪' },
    { key: 'scanning', label: '扫描' },
    { key: 'show_products', label: '选择' },
    { key: 'importing', label: '导入' },
    { key: 'done', label: '完成' },
  ]

  const stepIndex = STEPS.findIndex(s => s.key === step)

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
      background: 'rgba(15,23,42,0.5)', display: 'flex',
      alignItems: 'center', justifyContent: 'center', zIndex: 1000,
    }}>
      <div style={{
        background: '#fff', borderRadius: 12, padding: '1.5rem',
        width: 680, maxWidth: '90vw', maxHeight: '85vh', overflow: 'auto',
        boxShadow: '0 20px 60px rgba(15,23,42,0.2)',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Globe size={22} color="#E02E24" />
            <h2 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600, color: '#0f172a' }}>
              从 {platformName} 导入商品
            </h2>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8', padding: 4 }}>
            <X size={20} />
          </button>
        </div>

        {/* Error */}
        {errorMsg && (
          <div style={{ padding: '10px 14px', borderRadius: 8, background: '#fef2f2', color: '#991b1b', fontSize: '0.85rem', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <AlertCircle size={16} /> {errorMsg}
          </div>
        )}

        {/* Step indicator */}
        <div style={{ marginBottom: 16, display: 'flex', gap: 4, alignItems: 'center', fontSize: '0.75rem', color: '#64748b', flexWrap: 'wrap' }}>
          {STEPS.map((s, i) => (
            <span key={s.key} style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
              <span style={{
                width: 20, height: 20, borderRadius: '50%', display: 'inline-flex',
                alignItems: 'center', justifyContent: 'center', fontSize: '0.65rem', fontWeight: 600,
                backgroundColor: i <= stepIndex ? (step === 'done' || i < stepIndex ? '#16a34a' : '#2563eb') : '#e2e8f0',
                color: i <= stepIndex ? '#fff' : '#94a3b8',
              }}>
                {(step === 'done' || i < stepIndex) ? '✓' : i + 1}
              </span>
              <span style={{ color: i <= stepIndex ? '#334155' : '#94a3b8' }}>{s.label}</span>
              {i < STEPS.length - 1 && <span style={{ color: '#d1d5db' }}>—</span>}
            </span>
          ))}
        </div>

        {/* === SCAN FLOW === */}
        {step === 'idle' && (
          <div style={{ fontSize: '0.85rem', color: '#475569', lineHeight: 1.6 }}>
            <p>系统将打开 {platformName} 商品管理页面，扫描商品列表。</p>
            <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: 8 }}>
              你可以选择要导入的商品，系统会逐个打开获取详细信息。
            </p>
          </div>
        )}

        {(step === 'opening' || (step === 'check_login' && loading)) && (
          <div style={{ textAlign: 'center', padding: '2rem', color: '#64748b', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
            <Loader2 size={32} className="animate-spin" />
            <div style={{ fontSize: '0.9rem' }}>正在打开 {platformName} 页面…</div>
          </div>
        )}

        {step === 'check_login' && !loading && (
          <div>
            <div style={{ fontSize: '0.85rem', color: '#475569', marginBottom: 12 }}>
              页面已打开。如果尚未登录，请在浏览器窗口中完成登录。
            </div>
            {loginStatus === 'login_required' && (
              <div style={{ padding: '8px 12px', background: '#fef3c7', borderRadius: 6, fontSize: '0.8rem', color: '#92400e', display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
                <AlertCircle size={14} /> 需要登录。请在浏览器中完成登录后点击"检测登录状态"。
              </div>
            )}
          </div>
        )}

        {step === 'ready' && (
          <div>
            <div style={{ padding: '12px 14px', background: '#dcfce7', borderRadius: 8, fontSize: '0.85rem', color: '#166534', display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <CheckCircle2 size={18} /> 登录状态正常，可以扫描商品列表。
            </div>
          </div>
        )}

        {step === 'scanning' && (
          <div style={{ textAlign: 'center', padding: '2rem', color: '#64748b', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
            <Loader2 size={28} className="animate-spin" />
            <div style={{ fontSize: '0.9rem' }}>正在扫描商品列表…</div>
            <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>{scrapeProgress}</div>
          </div>
        )}

        {/* === PRODUCT LIST WITH CHECKBOXES === */}
        {step === 'show_products' && (
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#0f172a' }}>
                共扫描到 {products.length} 个商品
              </div>
              <div style={{ fontSize: '0.8rem', color: '#64748b' }}>
                已选 {selectedIds.size} 个
              </div>
            </div>

            {/* Select all */}
            <div
              onClick={toggleSelectAll}
              style={{
                display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px',
                background: '#f8fafc', borderRadius: 6, cursor: 'pointer', marginBottom: 8,
                fontSize: '0.85rem', color: '#475569', border: '1px solid #e2e8f0',
              }}
            >
              <input type="checkbox" checked={selectedIds.size === products.length && products.length > 0}
                readOnly style={{ accentColor: '#2563eb' }} />
              <span>全选</span>
            </div>

            {/* Product list */}
            <div style={{ maxHeight: 320, overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: 8, marginBottom: 12 }}>
              {products.map((p) => (
                <div
                  key={p.platform_product_id}
                  onClick={() => toggleSelect(p.platform_product_id)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '10px 12px', borderBottom: '1px solid #f1f5f9',
                    cursor: 'pointer', transition: 'background 0.1s',
                    background: selectedIds.has(p.platform_product_id) ? '#f0f7ff' : '#fff',
                  }}
                  onMouseEnter={e => { if (!selectedIds.has(p.platform_product_id)) e.currentTarget.style.background = '#f8fafc' }}
                  onMouseLeave={e => { if (!selectedIds.has(p.platform_product_id)) e.currentTarget.style.background = '#fff' }}
                >
                  <input type="checkbox" checked={selectedIds.has(p.platform_product_id)}
                    onChange={() => toggleSelect(p.platform_product_id)}
                    onClick={e => e.stopPropagation()}
                    style={{ accentColor: '#2563eb' }} />
                  {p.image_url ? (
                    <img src={p.image_url} alt="" style={{ width: 40, height: 40, borderRadius: 4, objectFit: 'cover', background: '#f1f5f9' }}
                      onError={e => { (e.target as HTMLImageElement).style.display = 'none' }} />
                  ) : (
                    <div style={{ width: 40, height: 40, borderRadius: 4, background: '#f1f5f9', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <Package size={18} color="#94a3b8" />
                    </div>
                  )}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: '0.85rem', fontWeight: 500, color: '#0f172a', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {p.title}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: 2 }}>
                      SKU: {p.sku || '-'} | 库存: {p.stock ?? '-'} | 状态: {p.status || '-'}
                    </div>
                  </div>
                  <div style={{ fontSize: '0.9rem', fontWeight: 600, color: '#059669', whiteSpace: 'nowrap' }}>
                    {p.price != null ? `¥${p.price.toFixed(2)}` : '-'}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* === CONFIRM IMPORT === */}
        {showConfirm && (
          <div style={{ padding: '1rem', background: '#f8fafc', borderRadius: 8, border: '1px solid #e2e8f0', marginBottom: 12 }}>
            <div style={{ fontSize: '0.95rem', fontWeight: 600, color: '#0f172a', marginBottom: 8 }}>
              确认导入选中商品
            </div>
            <div style={{ fontSize: '0.85rem', color: '#475569', marginBottom: 12 }}>
              已选择 <strong>{selectedIds.size}</strong> 个商品。系统将逐个打开每个商品的详情页获取完整信息，然后导入到本地商品库。
            </div>
            <div style={{ fontSize: '0.8rem', color: '#ca8a04', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
              <AlertCircle size={14} /> 抓取过程中请勿关闭浏览器窗口。
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={handleCancelConfirm} style={{
                padding: '8px 16px', borderRadius: 8, border: '1px solid #e2e8f0',
                background: '#fff', cursor: 'pointer', color: '#64748b', fontSize: '0.85rem',
              }}>取消</button>
              <button onClick={handleStartImport} style={{
                padding: '8px 16px', borderRadius: 8, border: 'none', background: '#2563eb',
                color: '#fff', cursor: 'pointer', fontSize: '0.85rem',
                display: 'flex', alignItems: 'center', gap: 6,
              }}>
                <Package size={16} /> 开始导入 ({selectedIds.size} 个)
              </button>
            </div>
          </div>
        )}

        {/* === IMPORTING === */}
        {step === 'importing' && (
          <div style={{ textAlign: 'center', padding: '2rem', color: '#64748b', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
            <Loader2 size={28} className="animate-spin" />
            <div style={{ fontSize: '0.9rem' }}>正在导入商品…</div>
            <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>{importProgress}</div>
          </div>
        )}

        {/* === DONE === */}
        {step === 'done' && (
          <div style={{ padding: '16px', textAlign: 'center' }}>
            <CheckCircle2 size={40} color="#16a34a" style={{ marginBottom: 8 }} />
            <div style={{ fontSize: '0.9rem', color: '#166534', fontWeight: 600 }}>导入完成</div>
            {importResult && (
              <div style={{ fontSize: '0.85rem', color: '#64748b', marginTop: 8 }}>
                成功: {importResult.ok} 个, 失败: {importResult.fail} 个
              </div>
            )}
          </div>
        )}

        {/* Actions */}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', borderTop: '1px solid #f1f5f9', paddingTop: 16, flexWrap: 'wrap' }}>
          <button onClick={onClose} style={{
            padding: '8px 16px', borderRadius: 8, border: '1px solid #e2e8f0',
            background: '#fff', cursor: 'pointer', color: '#64748b', fontSize: '0.85rem',
          }}>
            {step === 'done' ? '关闭' : '取消'}
          </button>

          {step === 'idle' && (
            <button onClick={handleOpenPage} disabled={loading} style={{
              padding: '8px 16px', borderRadius: 8, border: 'none', background: '#2563eb',
              color: '#fff', cursor: loading ? 'not-allowed' : 'pointer', fontSize: '0.85rem',
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <ExternalLink size={16} />
              打开平台页面
            </button>
          )}

          {step === 'check_login' && !loading && (
            <button onClick={handleOpenPage} style={{
              padding: '8px 16px', borderRadius: 8, border: '1px solid #e2e8f0',
              background: '#fff', cursor: 'pointer', color: '#334155', fontSize: '0.85rem',
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <ExternalLink size={16} />
              重新打开平台页面
            </button>
          )}

          {step === 'check_login' && !loading && (
            <button onClick={handleCheckLogin} style={{
              padding: '8px 16px', borderRadius: 8, border: 'none', background: '#2563eb',
              color: '#fff', cursor: 'pointer', fontSize: '0.85rem',
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <RefreshCw size={16} />
              检测登录状态
            </button>
          )}

          {step === 'ready' && (
            <button onClick={handleScan} disabled={loading} style={{
              padding: '8px 16px', borderRadius: 8, border: 'none', background: '#16a34a',
              color: '#fff', cursor: 'pointer', fontSize: '0.85rem',
              display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <RefreshCw size={16} />
              扫描商品列表
            </button>
          )}

          {step === 'show_products' && (
            <button onClick={handleShowConfirm} disabled={selectedIds.size === 0} style={{
              padding: '8px 16px', borderRadius: 8, border: 'none',
              background: selectedIds.size === 0 ? '#e2e8f0' : '#2563eb',
              color: selectedIds.size === 0 ? '#94a3b8' : '#fff',
              cursor: selectedIds.size === 0 ? 'not-allowed' : 'pointer',
              fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: 6,
            }}>
              <Package size={16} />
              导入选中商品 ({selectedIds.size})
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
