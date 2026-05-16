export interface ChatResponsePayload {
  merchant_id: string
  user_query: string
  conversation_id?: string | null
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
}

export interface UploadTask {
  upload_id: string
  merchant_id: string
  status: string
  files_received: number
  documents_processed: number
  chunks_created: number
  progress_percentage: number
  created_at: string
  updated_at: string
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
