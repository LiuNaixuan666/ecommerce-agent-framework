export interface ChatResponsePayload {
  merchant_id: string
  user_query: string
  conversation_id?: string | null
  page_context?: Record<string, unknown> | null
}

export interface EvidenceSource {
  type?: string
  source?: string
  title?: string | null
  product_id?: string | null
  platform?: string | null
  shop_id?: string | null
  sku?: string | null
  price?: unknown
  stock?: unknown
  score?: number | null
  chunk_index?: number | null
  preview?: string | null
  metadata?: Record<string, unknown>
}

export interface ChatResponseData {
  merchant_id: string
  user_query: string
  response_text: string
  intent?: string
  confidence?: number
  sources?: string[]
  is_clarification_triggered: boolean
  conversation_id?: string
  timestamp?: string
  recommended_reply?: string
  risk_level?: string
  auto_send_allowed?: boolean
  auto_send_blockers?: string[]
  requires_human_review?: boolean
  handoff_reason?: string | null
  missing_info?: string[]
  retrieval_type?: string
  evidence_sources?: EvidenceSource[]
}

export interface UploadTask {
  upload_id: string
  merchant_id: string
  status: string
  files_received: number
  documents_processed: number
  chunks_created: number
  progress_percentage: number
  created_at: string | null
  updated_at: string | null
}

export async function fetchChatResponse(payload: ChatResponsePayload): Promise<ChatResponseData> {
  const response = await fetch('/api/chat/query', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(errorText || '聊天请求失败')
  }

  return response.json()
}

export interface KnowledgeUploadResponse {
  merchant_id: string
  status: string
  files_received: number
  upload_id: string
  message: string
}

export async function uploadKnowledge(formData: FormData): Promise<KnowledgeUploadResponse> {
  const response = await fetch('/api/knowledge/upload', {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(errorText || '文件上传失败')
  }

  return response.json()
}

export interface ProductSummary {
  id: string
  merchant_id: string
  platform: string
  shop_id?: string | null
  platform_product_id?: string | null
  sku?: string | null
  title: string
  category?: string | null
  price?: number | null
  stock?: number | null
  description?: string | null
  image_url?: string | null
  source_type?: string
  source_url?: string | null
}

export interface ProductListData {
  total: number
  products: ProductSummary[]
}

export async function fetchProducts(params: {
  merchant_id?: string
  platform?: string
  shop_id?: string | null
  limit?: number
  offset?: number
} = {}): Promise<ProductListData> {
  const query = new URLSearchParams()
  query.set('merchant_id', params.merchant_id || 'default')
  if (params.platform) query.set('platform', params.platform)
  if (params.shop_id) query.set('shop_id', params.shop_id)
  query.set('limit', String(params.limit || 100))
  query.set('offset', String(params.offset || 0))

  const response = await fetch(`/api/products?${query.toString()}`)
  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(errorText || '获取商品列表失败')
  }
  return response.json()
}

export interface UploadTasksResponse {
  total: number
  tasks: UploadTask[]
}

export async function listUploadTasks(merchantId = 'default'): Promise<UploadTask[]> {
  const response = await fetch(`/api/knowledge/list-uploads?merchant_id=${encodeURIComponent(merchantId)}`)
  if (!response.ok) {
    throw new Error('获取上传任务失败')
  }
  const data: UploadTasksResponse = await response.json()
  return data.tasks
}

export interface RpaMessagePayload {
  merchant_id?: string
  platform: string
  external_conversation_id: string
  external_message_id?: string
  customer_message: string
  customer_id?: string
  customer_name?: string
  page_context?: Record<string, unknown>
  metadata?: Record<string, unknown>
}

export interface RpaMessageResponse {
  schema_version: string
  request_id: string
  merchant_id: string
  platform: string
  external_conversation_id: string
  conversation_id: string
  reply: {
    recommended_reply: string
    send_text?: string | null
  }
  decision: {
    action: string
    auto_send_allowed: boolean
    risk_level?: string
    confidence?: number
    auto_send_blockers: string[]
    requires_human_review: boolean
    handoff_reason?: string | null
    missing_info: string[]
  }
  rpa_instruction: {
    should_send: boolean
    should_handoff: boolean
    send_text?: string | null
    handoff_note?: string | null
  }
  trace?: {
    intent?: string | null
    retrieval_type?: string | null
    sources?: string[]
    evidence_sources?: EvidenceSource[]
  }
}

export async function sendRpaMessage(payload: RpaMessagePayload): Promise<RpaMessageResponse> {
  const response = await fetch('/api/chat/rpa/message', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(errorText || 'RPA 消息处理失败')
  }

  return response.json()
}

export interface RpaSendResultPayload {
  request_id: string
  merchant_id?: string
  platform: string
  external_conversation_id: string
  external_message_id?: string
  customer_message?: string | null
  send_status: 'success' | 'failed' | 'handoff' | 'skipped_duplicate' | 'skipped_stale' | 'skipped_dry_run'
  sent_text?: string | null
  agent_id?: string
  error_code?: string | null
  error_message?: string | null
  metadata?: Record<string, unknown>
}

export async function reportRpaSendResult(payload: RpaSendResultPayload) {
  const response = await fetch('/api/chat/rpa/send-result', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(errorText || '发送结果回写失败')
  }

  return response.json()
}

export interface LocalAgentHeartbeatPayload {
  agent_id: string
  merchant_id?: string
  platform?: string
  shop_id?: string
  status: 'running' | 'paused' | 'stopped' | 'error'
  watched_window_title?: string
  error_code?: string | null
  error_message?: string | null
  metadata?: Record<string, unknown>
}

export async function sendLocalAgentHeartbeat(payload: LocalAgentHeartbeatPayload) {
  const response = await fetch('/api/local-agent/heartbeat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(errorText || 'Local Agent 心跳失败')
  }

  return response.json()
}

// ---------------------------------------------------------------------------
// Platform management API (for the multi-platform console)
// ---------------------------------------------------------------------------

export interface PlatformInfo {
  code: string
  name: string
  icon: string
  color: string
  order: number
  status: 'active' | 'beta' | 'coming_soon'
  description: string
  agent_count: number
  running_count: number
  error_count: number
  has_active_agent: boolean
  latest_heartbeat_at: string | null
}

export interface PlatformListResponse {
  platforms: PlatformInfo[]
  total: number
}

export async function fetchPlatformList(): Promise<PlatformListResponse> {
  const response = await fetch('/api/platform/list')
  if (!response.ok) {
    throw new Error('获取平台列表失败')
  }
  return response.json()
}

export interface AgentInfo {
  agent_id: string
  status: string
  platform: string
  shop_id: string | null
  last_heartbeat_at: string | null
  watched_window_title: string | null
  last_message_seen_at: string | null
  last_send_at: string | null
  error_message: string | null
  // Stage 6: live monitoring fields
  latest_buyer_message: string | null
  selector_profile: string | null
  current_page_url: string | null
  metadata: Record<string, unknown> | null
}

/** Typed structure expected inside AgentInfo.metadata for session monitoring. */
export interface AgentMetadata {
  product_name?: string
  sku?: string
  product_price?: string
  stock?: number
  recommended_reply?: string | null
  risk_level?: string
  auto_send_allowed?: boolean
  auto_send_blockers?: string[]
  intent?: string
  retrieval_type?: string
  sources?: string[]
  evidence_sources?: EvidenceSource[]
  confidence?: number
  status?: string
  send_status?: string
}

export interface SendResultInfo {
  id: string
  send_status: string
  processing_status: string
  customer_message: string | null
  sent_text: string | null
  created_at: string
}

export interface PlatformStatusResponse {
  platform: {
    code: string
    name: string
    color: string
    description: string
  }
  agents: AgentInfo[]
  agent_count: number
  recent_send_results: SendResultInfo[]
  send_result_count: number
}

export async function fetchPlatformStatus(platformCode: string): Promise<PlatformStatusResponse> {
  const response = await fetch(`/api/platform/${encodeURIComponent(platformCode)}/status`)
  if (!response.ok) {
    throw new Error('获取平台状态失败')
  }
  return response.json()
}

// ---------------------------------------------------------------------------
// Handoff ticket API (persistent human handoff queue)
// ---------------------------------------------------------------------------

export interface HandoffTicket {
  ticket_id: string
  merchant_id: string
  platform: string
  conversation_id: string
  external_conversation_id: string
  external_message_id: string
  customer_message: string
  recommended_reply: string
  reason: string
  blockers: string[]
  risk_level: string
  confidence: number | null
  status: 'pending' | 'processing' | 'resolved' | 'returned_to_ai' | 'closed'
  assigned_to: string | null
  human_reply: string | null
  created_at: string
  updated_at: string
  resolved_at: string | null
  returned_to_ai_at: string | null
  duplicate_count: number
  source: string
}

export interface HandoffListResponse {
  total: number
  tickets: HandoffTicket[]
}

export interface HandoffSummaryResponse {
  platforms: Record<string, { pending: number; processing: number }>
  total_pending: number
  total_processing: number
  total_active: number
}

export async function fetchHandoffTickets(params: {
  merchant_id?: string
  platform?: string
  status?: string
  limit?: number
}): Promise<HandoffListResponse> {
  const query = new URLSearchParams()
  if (params.merchant_id) query.set('merchant_id', params.merchant_id)
  if (params.platform) query.set('platform', params.platform)
  if (params.status) query.set('status', params.status)
  if (params.limit) query.set('limit', String(params.limit))
  const response = await fetch(`/api/handoff/tickets?${query.toString()}`)
  if (!response.ok) throw new Error('获取待人工列表失败')
  return response.json()
}

export async function fetchHandoffSummary(merchantId?: string): Promise<HandoffSummaryResponse> {
  const query = merchantId ? `?merchant_id=${encodeURIComponent(merchantId)}` : ''
  const response = await fetch(`/api/handoff/summary${query}`)
  if (!response.ok) throw new Error('获取待人工汇总失败')
  return response.json()
}

export async function fetchHandoffTicket(ticketId: string): Promise<HandoffTicket> {
  const response = await fetch(`/api/handoff/tickets/${encodeURIComponent(ticketId)}`)
  if (!response.ok) throw new Error('获取待人工 ticket 失败')
  return response.json()
}

export async function createHandoffTicket(payload: {
  merchant_id?: string
  platform: string
  conversation_id?: string
  external_conversation_id?: string
  external_message_id?: string
  customer_message: string
  recommended_reply?: string
  reason?: string
  blockers?: string[]
  risk_level?: string
  confidence?: number
  source?: string
}): Promise<{ status: string; ticket: HandoffTicket; created: boolean }> {
  const response = await fetch('/api/handoff/tickets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) throw new Error('创建待人工 ticket 失败')
  return response.json()
}

export async function resolveHandoffTicket(
  ticketId: string,
  humanReply?: string,
): Promise<HandoffTicket> {
  const response = await fetch(`/api/handoff/tickets/${encodeURIComponent(ticketId)}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ human_reply: humanReply || null }),
  })
  if (!response.ok) throw new Error('标记已处理失败')
  return response.json()
}

export async function returnHandoffTicketToAi(ticketId: string): Promise<HandoffTicket> {
  const response = await fetch(`/api/handoff/tickets/${encodeURIComponent(ticketId)}/return-to-ai`, {
    method: 'POST',
  })
  if (!response.ok) throw new Error('转回 AI 失败')
  return response.json()
}

export async function startHandoffTicket(ticketId: string, assignedTo?: string): Promise<HandoffTicket> {
  const response = await fetch(`/api/handoff/tickets/${encodeURIComponent(ticketId)}/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ assigned_to: assignedTo || null }),
  })
  if (!response.ok) throw new Error('标记处理中失败')
  return response.json()
}

export async function closeHandoffTicket(ticketId: string): Promise<HandoffTicket> {
  const response = await fetch(`/api/handoff/tickets/${encodeURIComponent(ticketId)}/close`, {
    method: 'POST',
  })
  if (!response.ok) throw new Error('关闭 ticket 失败')
  return response.json()
}
