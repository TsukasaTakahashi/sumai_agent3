import axios from 'axios'

// API Base URL
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// Axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 30秒のタイムアウト
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
api.interceptors.request.use(
  (config) => {
    console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`)
    return config
  },
  (error) => {
    console.error('API Request Error:', error)
    return Promise.reject(error)
  }
)

// Response interceptor  
api.interceptors.response.use(
  (response) => {
    console.log(`API Response: ${response.status} ${response.config.url}`)
    return response
  },
  (error) => {
    console.error('API Response Error:', error.response?.status, error.response?.data)
    
    // エラーメッセージの標準化
    const errorMessage = error.response?.data?.detail || 
                        error.response?.data?.message || 
                        error.message || 
                        'APIエラーが発生しました'
    
    return Promise.reject(new Error(errorMessage))
  }
)

/**
 * Chat message API
 * @param {Object} messageData - メッセージデータ
 * @param {string} messageData.message - ユーザーメッセージ
 * @param {string} [messageData.session_id] - セッションID
 * @param {number} [messageData.recommendation_count=3] - 推薦件数
 * @returns {Promise<Object>} チャット応答
 */
export const sendMessage = async (messageData) => {
  try {
    const response = await api.post('/chat', {
      message: messageData.message,
      session_id: messageData.session_id || null,
      recommendation_count: messageData.recommendation_count || 3
    })
    
    return response.data
  } catch (error) {
    console.error('Send message error:', error)
    throw error
  }
}

/**
 * PDF upload API
 * @param {File} file - PDFファイル
 * @param {string} [sessionId] - セッションID  
 * @param {number} [recommendationCount=3] - 推薦件数
 * @returns {Promise<Object>} アップロード応答
 */
export const uploadPDF = async (file, sessionId = null, recommendationCount = 3) => {
  try {
    // FormData for file upload
    const formData = new FormData()
    formData.append('file', file)
    
    if (sessionId) {
      formData.append('session_id', sessionId)
    }
    formData.append('recommendation_count', recommendationCount.toString())

    const response = await api.post('/upload-pdf', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 60000, // PDFアップロードは60秒のタイムアウト
    })
    
    return response.data
  } catch (error) {
    console.error('PDF upload error:', error)
    throw error
  }
}

/**
 * Get chat history API
 * @param {string} sessionId - セッションID
 * @returns {Promise<Object>} チャット履歴
 */
export const getChatHistory = async (sessionId) => {
  try {
    const response = await api.get(`/session/${sessionId}/history`)
    return response.data
  } catch (error) {
    console.error('Get chat history error:', error)
    throw error
  }
}

/**
 * Clear session API
 * @param {string} sessionId - セッションID
 * @returns {Promise<Object>} クリア結果
 */
export const clearSession = async (sessionId) => {
  try {
    const response = await api.delete(`/session/${sessionId}`)
    return response.data
  } catch (error) {
    console.error('Clear session error:', error)
    throw error
  }
}

/**
 * Get database stats API
 * @returns {Promise<Object>} データベース統計
 */
export const getDatabaseStats = async () => {
  try {
    const response = await api.get('/database/stats')
    return response.data
  } catch (error) {
    console.error('Get database stats error:', error)
    throw error
  }
}

/**
 * Health check API
 * @returns {Promise<Object>} ヘルスチェック結果
 */
export const healthCheck = async () => {
  try {
    const response = await api.get('/health')
    return response.data
  } catch (error) {
    console.error('Health check error:', error)
    throw error
  }
}

// API functions export
export default {
  sendMessage,
  uploadPDF,
  getChatHistory,
  clearSession,
  getDatabaseStats,
  healthCheck,
}

// Utility functions
export const formatApiError = (error) => {
  if (error.response) {
    // サーバーからのレスポンスエラー
    return `サーバーエラー (${error.response.status}): ${error.response.data?.detail || error.response.data?.message || 'Unknown error'}`
  } else if (error.request) {
    // ネットワークエラー
    return 'ネットワークエラー: サーバーに接続できません'
  } else {
    // その他のエラー
    return `エラー: ${error.message}`
  }
}

export const isNetworkError = (error) => {
  return !error.response && error.request
}

export const isServerError = (error) => {
  return error.response && error.response.status >= 500
}

export const isClientError = (error) => {
  return error.response && error.response.status >= 400 && error.response.status < 500
}