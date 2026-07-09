import React, { useEffect, useState, useRef } from 'react'
import {
  Package,
  Upload,
  RefreshCw,
  Search,
  Trash2,
  AlertCircle,
  CheckCircle2,
  FileText,
  Globe,
  Loader2,
  ChevronDown,
  ChevronRight,
  File,
} from 'lucide-react'
import ProductScrapeWizard from './ProductScrapeWizard'

interface Product {
  id: string
  merchant_id: string
  platform: string
  shop_id: string | null
  platform_product_id: string | null
  sku: string | null
  title: string
  category: string | null
  price: number | null
  stock: number | null
  description: string | null
  source_type: string
  created_at: string | null
  updated_at: string | null
}

interface ProductListResponse {
  total: number
  products: Product[]
}

const sourceTypeLabels: Record<string, string> = {
  platform_scrape: '平台抓取',
  csv_import: 'CSV 导入',
  manual: '手动添加',
}

const sourceTypeColors: Record<string, string> = {
  platform_scrape: '#2563eb',
  csv_import: '#16a34a',
  manual: '#ca8a04',
}

export default function ProductManagement() {
  const [products, setProducts] = useState<Product[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [importStatus, setImportStatus] = useState<string | null>(null)
  const [importPlatform, setImportPlatform] = useState('pinduoduo')
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [scraping] = useState(false)
  const [expandedProductId, setExpandedProductId] = useState<string | null>(null)
  const [uploadingDoc, setUploadingDoc] = useState(false)
  const [docUploadStatus, setDocUploadStatus] = useState<string | null>(null)
  const [showScrapeWizard, setShowScrapeWizard] = useState(false)

  const toggleExpand = (productId: string) => {
    setExpandedProductId(expandedProductId === productId ? null : productId)
    setDocUploadStatus(null)
  }

  const handleDocUpload = async (productId: string, file: File) => {
    setUploadingDoc(true)
    setDocUploadStatus('uploading')
    const formData = new FormData()
    formData.append('files', file)
    formData.append('merchant_id', 'default')
    formData.append('product_id', productId)

    try {
      const res = await fetch('/api/knowledge/upload', {
        method: 'POST',
        body: formData,
      })
      if (res.ok) {
        setDocUploadStatus('success: 文档已上传，正在后台摄取')
      } else {
        const data = await res.json()
        setDocUploadStatus(`error: ${data.detail || '上传失败'}`)
      }
    } catch {
      setDocUploadStatus('error: 网络错误')
    }
    setUploadingDoc(false)
  }

  const loadProducts = (platform?: string) => {
    setLoading(true)
    const platformParam = platform ? `&platform=${encodeURIComponent(platform)}` : ''
    fetch(`/api/products?merchant_id=default&limit=200${platformParam}`)
      .then((res) => res.json())
      .then((data: ProductListResponse) => {
        setProducts(data.products || [])
        setTotal(data.total || 0)
        setError(null)
      })
      .catch(() => setError('无法加载商品列表'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadProducts(importPlatform)
  }, [importPlatform])

  // Scrape status polling removed — the ProductScrapeWizard handles it internally

  const handleScrape = async () => {
    setShowScrapeWizard(true)
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setImportStatus('uploading')
    const formData = new FormData()
    formData.append('file', file)
    formData.append('merchant_id', 'default')
    formData.append('platform', importPlatform)

    try {
      const res = await fetch('/api/products/import-csv', {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()
      if (res.ok) {
        setImportStatus(`success: 成功导入 ${data.imported_count} 个商品`)
        loadProducts(importPlatform)
      } else {
        setImportStatus(`error: ${data.detail || '导入失败'}`)
      }
    } catch {
      setImportStatus('error: 网络错误')
    }
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleDelete = async (id: string, title: string) => {
    if (!confirm(`确定删除商品「${title}」？`)) return
    try {
      const res = await fetch(`/api/products/${id}`, { method: 'DELETE' })
      if (res.ok) {
        loadProducts(importPlatform)
      }
    } catch {
      // ignore
    }
  }

  const filteredProducts = searchQuery
    ? products.filter(
        (p) =>
          p.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
          (p.sku && p.sku.toLowerCase().includes(searchQuery.toLowerCase()))
      )
    : products

  return (
    <div style={{ padding: '1.5rem 2rem', maxWidth: '1200px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: '#0f172a', marginBottom: 4 }}>
            商品管理
          </h1>
          <p style={{ fontSize: '0.875rem', color: '#64748b' }}>
            管理从平台导入或通过 CSV 上传的商品信息，共 {total} 个商品
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <select
            value={importPlatform}
            onChange={(e) => setImportPlatform(e.target.value)}
            style={{
              padding: '0.5rem 0.75rem',
              border: '1px solid #e2e8f0',
              borderRadius: 8,
              fontSize: '0.8rem',
              color: '#334155',
              background: '#fff',
            }}
          >
            <option value="pinduoduo">拼多多</option>
            <option value="xianyu">闲鱼</option>
            <option value="taobao">淘宝/千牛</option>
            <option value="jd">京东</option>
            <option value="douyin">抖店</option>
          </select>
          <input
            type="file"
            accept=".csv"
            ref={fileInputRef}
            style={{ display: 'none' }}
            onChange={handleFileUpload}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            style={{
              background: '#fff',
              border: '1px solid #e2e8f0',
              borderRadius: 8,
              padding: '0.5rem 1rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              color: '#334155',
              fontSize: '0.875rem',
            }}
          >
            <Upload size={16} />
            CSV 导入
          </button>
          <button
            onClick={handleScrape}
            disabled={scraping || importPlatform !== 'pinduoduo'}
            title={importPlatform !== 'pinduoduo' ? '当前平台暂未支持商品抓取，请先用 CSV 导入' : '从拼多多后台抓取商品'}
            style={{
              background: scraping || importPlatform !== 'pinduoduo' ? '#e2e8f0' : '#2563eb',
              border: 'none',
              borderRadius: 8,
              padding: '0.5rem 1rem',
              cursor: scraping ? 'not-allowed' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              color: scraping ? '#94a3b8' : '#fff',
              fontSize: '0.875rem',
            }}
          >
            {scraping ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
            {scraping ? '抓取中…' : '从平台抓取'}
          </button>
          <button
            onClick={() => loadProducts(importPlatform)}
            disabled={loading}
            style={{
              background: '#fff',
              border: '1px solid #e2e8f0',
              borderRadius: 8,
              padding: '0.5rem 1rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              color: '#64748b',
              fontSize: '0.875rem',
            }}
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            刷新
          </button>
        </div>
      </div>

      {/* Import Status Banner */}
      {importStatus && (
        <div
          style={{
            padding: '0.75rem 1rem',
            borderRadius: 8,
            marginBottom: 16,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            fontSize: '0.875rem',
            backgroundColor: importStatus.startsWith('success') ? '#dcfce7' : '#fef2f2',
            color: importStatus.startsWith('success') ? '#16a34a' : '#dc2626',
            border: `1px solid ${importStatus.startsWith('success') ? '#bbf7d0' : '#fecaca'}`,
          }}
        >
          {importStatus.startsWith('success') ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
          <span style={{ flex: 1 }}>{importStatus.replace(/^(success|error):\s*/, '')}</span>
          <button
            onClick={() => setImportStatus(null)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'inherit', fontSize: '0.875rem' }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Search */}
      <div style={{ marginBottom: 16, display: 'flex', gap: 8, alignItems: 'center' }}>
        <div
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            background: '#fff',
            borderRadius: 8,
            padding: '0.5rem 0.75rem',
            border: '1px solid #e2e8f0',
          }}
        >
          <Search size={16} color="#94a3b8" />
          <input
            placeholder="搜索商品名称或 SKU..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ border: 'none', outline: 'none', flex: 1, fontSize: '0.875rem', background: 'transparent' }}
          />
        </div>
      </div>

      {/* Error */}
      {error && (
        <div
          style={{
            background: '#fef2f2',
            border: '1px solid #fecaca',
            borderRadius: 8,
            padding: '1rem',
            color: '#991b1b',
            marginBottom: 16,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <AlertCircle size={18} />
          {error}
        </div>
      )}

      {/* Table */}
      {!loading && filteredProducts.length === 0 && (
        <div style={{ textAlign: 'center', padding: '3rem', color: '#94a3b8' }}>
          <Package size={48} style={{ margin: '0 auto 12px', opacity: 0.3 }} />
          <div style={{ fontSize: '1rem', marginBottom: 4 }}>暂无商品数据</div>
          <div style={{ fontSize: '0.8rem' }}>通过 CSV 导入或从平台抓取商品后，将在这里显示</div>
        </div>
      )}

      {filteredProducts.length > 0 && (
        <div style={{ background: '#fff', borderRadius: 10, boxShadow: '0 1px 3px rgba(15,23,42,0.08)', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
            <thead>
              <tr style={{ background: '#f8fafc', textAlign: 'left', color: '#64748b' }}>
                <th style={{ padding: '12px 16px' }}>商品名称</th>
                <th style={{ padding: '12px 16px' }}>SKU</th>
                <th style={{ padding: '12px 16px' }}>价格</th>
                <th style={{ padding: '12px 16px' }}>库存</th>
                <th style={{ padding: '12px 16px' }}>来源</th>
                <th style={{ padding: '12px 16px' }}>更新时间</th>
                <th style={{ padding: '12px 16px', width: 80 }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {filteredProducts.map((p) => (
                <React.Fragment key={p.id}>
                  <tr style={{ borderTop: '1px solid #f1f5f9', cursor: 'pointer' }} onClick={() => toggleExpand(p.id)}>
                    <td style={{ padding: '10px 16px', fontWeight: 500, color: '#0f172a', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        {expandedProductId === p.id ? <ChevronDown size={14} color="#94a3b8" /> : <ChevronRight size={14} color="#94a3b8" />}
                        {p.source_type === 'platform_scrape' ? (
                          <Globe size={14} color="#2563eb" />
                        ) : p.source_type === 'csv_import' ? (
                          <FileText size={14} color="#16a34a" />
                        ) : (
                          <Package size={14} color="#ca8a04" />
                        )}
                        {p.title}
                      </div>
                    </td>
                    <td style={{ padding: '10px 16px', color: '#64748b' }}>{p.sku || '-'}</td>
                    <td style={{ padding: '10px 16px', color: '#334155' }}>
                      {p.price != null ? `¥${p.price.toFixed(2)}` : '-'}
                    </td>
                    <td style={{ padding: '10px 16px' }}>
                      <span
                        style={{
                          padding: '2px 8px',
                          borderRadius: 999,
                          fontSize: '0.7rem',
                          fontWeight: 600,
                          backgroundColor: (p.stock ?? 0) > 0 ? '#dcfce7' : '#fef2f2',
                          color: (p.stock ?? 0) > 0 ? '#16a34a' : '#dc2626',
                        }}
                      >
                        {p.stock != null ? p.stock : '-'}
                      </span>
                    </td>
                    <td style={{ padding: '10px 16px' }}>
                      <span
                        style={{
                          padding: '2px 8px',
                          borderRadius: 999,
                          fontSize: '0.7rem',
                          fontWeight: 500,
                          backgroundColor: (sourceTypeColors[p.source_type] || '#64748b') + '15',
                          color: sourceTypeColors[p.source_type] || '#64748b',
                        }}
                      >
                        {sourceTypeLabels[p.source_type] || p.source_type}
                      </span>
                    </td>
                    <td style={{ padding: '10px 16px', color: '#94a3b8', whiteSpace: 'nowrap' }}>
                      {p.updated_at ? new Date(p.updated_at).toLocaleDateString('zh-CN') : '-'}
                    </td>
                    <td style={{ padding: '10px 16px' }}>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDelete(p.id, p.title) }}
                        style={{
                          background: 'none',
                          border: 'none',
                          cursor: 'pointer',
                          color: '#94a3b8',
                          padding: 4,
                          borderRadius: 4,
                        }}
                        title="删除"
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                  {/* Expanded detail panel */}
                  {expandedProductId === p.id && (
                    <tr>
                      <td colSpan={7} style={{ padding: '0 16px 16px 16px', background: '#f8fafc' }}>
                        <div style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 16, background: '#fff', marginTop: 8 }}>
                          <div style={{ display: 'flex', gap: 24 }}>
                            {/* Left: product info */}
                            <div style={{ flex: 1 }}>
                              <h4 style={{ margin: '0 0 8px', fontSize: '0.9rem', color: '#0f172a' }}>商品详情</h4>
                              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 16px', fontSize: '0.8rem', color: '#475569' }}>
                                {p.category && <><span style={{ color: '#94a3b8' }}>分类：</span><span>{p.category}</span></>}
                                {p.description && <><span style={{ color: '#94a3b8' }}>描述：</span><span style={{ gridColumn: 'span 2' }}>{p.description.slice(0, 200)}</span></>}
                                {p.platform_product_id && <><span style={{ color: '#94a3b8' }}>平台商品 ID：</span><span>{p.platform_product_id}</span></>}
                                {p.platform && <><span style={{ color: '#94a3b8' }}>平台：</span><span>{p.platform}</span></>}
                              </div>
                            </div>
                            {/* Right: knowledge binding */}
                            <div style={{ flex: 1 }}>
                              <h4 style={{ margin: '0 0 8px', fontSize: '0.9rem', color: '#0f172a', display: 'flex', alignItems: 'center', gap: 6 }}>
                                <File size={14} />
                                关联知识文档
                              </h4>
                              <p style={{ fontSize: '0.75rem', color: '#94a3b8', margin: '0 0 8px' }}>
                                上传商品说明文档（PDF/DOCX/TXT），客服回复时将优先检索该商品的关联知识
                              </p>
                              {docUploadStatus && (
                                <div style={{
                                  padding: '6px 10px', borderRadius: 6, marginBottom: 8, fontSize: '0.75rem',
                                  backgroundColor: docUploadStatus.startsWith('success') ? '#dcfce7' : '#fef2f2',
                                  color: docUploadStatus.startsWith('success') ? '#16a34a' : '#dc2626',
                                  border: `1px solid ${docUploadStatus.startsWith('success') ? '#bbf7d0' : '#fecaca'}`,
                                }}>
                                  {docUploadStatus.replace(/^(success|error):\s*/, '')}
                                </div>
                              )}
                              <label
                                style={{
                                  display: 'inline-flex', alignItems: 'center', gap: 6,
                                  padding: '6px 12px', borderRadius: 6, border: '1px dashed #cbd5e1',
                                  cursor: uploadingDoc ? 'not-allowed' : 'pointer',
                                  fontSize: '0.8rem', color: uploadingDoc ? '#94a3b8' : '#475569',
                                  background: uploadingDoc ? '#f8fafc' : '#fff',
                                }}
                              >
                                <Upload size={14} />
                                {uploadingDoc ? '上传中…' : '上传关联文档'}
                                <input
                                  type="file"
                                  accept=".pdf,.docx,.doc,.txt,.md"
                                  style={{ display: 'none' }}
                                  disabled={uploadingDoc}
                                  onChange={async (e) => {
                                    const file = e.target.files?.[0]
                                    if (file) {
                                      await handleDocUpload(p.id, file)
                                    }
                                    e.target.value = ''
                                  }}
                                />
                              </label>
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {loading && (
        <div style={{ textAlign: 'center', padding: '3rem', color: '#94a3b8' }}>加载中...</div>
      )}

      {/* Scrape Wizard Modal */}
      {showScrapeWizard && (
        <ProductScrapeWizard
          platform={importPlatform}
          platformName={
            importPlatform === 'pinduoduo' ? '拼多多' :
            importPlatform === 'xianyu' ? '闲鱼' :
            importPlatform === 'taobao' ? '淘宝' :
            importPlatform === 'jd' ? '京东' : '抖店'
          }
          onClose={() => { setShowScrapeWizard(false); loadProducts(importPlatform) }}
        />
      )}
    </div>
  )
}
