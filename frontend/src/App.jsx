import { useState, useEffect, useRef } from 'react'
import './App.css'
import ChatMessage from './components/ChatMessage'
import MessageInput from './components/MessageInput'
import PropertyRecommendations from './components/PropertyRecommendations'
import { sendMessage, uploadPDF } from './services/api'

function App() {
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState(null)
  const [recommendations, setRecommendations] = useState([])
  const [recommendationCount, setRecommendationCount] = useState(3)
  const [totalPropertyCount, setTotalPropertyCount] = useState(null)
  const [filteredPropertyCount, setFilteredPropertyCount] = useState(null)
  const messagesEndRef = useRef(null)

  // 初期メッセージとデータベース統計取得
  useEffect(() => {
    setMessages([
      {
        id: 'welcome',
        type: 'assistant',
        content: 'こんにちは！SumaiAgentです。🏠\n\nご希望の物件について教えてください。例えば：\n• 「新宿駅周辺で3000万円以下のマンション」\n• 「横浜市内で築浅の4LDK」\n• PDFファイルをアップロード\n\nどのようにお手伝いしましょうか？',
        timestamp: new Date().toISOString()
      }
    ])

    // データベース統計を取得
    fetchDatabaseStats()
  }, [])

  const fetchDatabaseStats = async () => {
    try {
      const response = await fetch('/api/database/stats')
      const data = await response.json()
      setTotalPropertyCount(data.total_properties)
    } catch (error) {
      console.error('Failed to fetch database stats:', error)
      setTotalPropertyCount(640736) // フォールバック値
    }
  }

  // メッセージ送信時に最下部へスクロール
  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  const handleSendMessage = async (message) => {
    if (!message.trim() || isLoading) return

    const userMessage = {
      id: Date.now() + '_user',
      type: 'user',
      content: message,
      timestamp: new Date().toISOString()
    }

    setMessages(prev => [...prev, userMessage])
    setIsLoading(true)

    try {
      const response = await sendMessage({
        message,
        session_id: sessionId,
        recommendation_count: recommendationCount
      })

      // セッションIDを更新
      if (response.session_id && !sessionId) {
        setSessionId(response.session_id)
      }

      // アシスタントのレスポンス
      const assistantMessage = {
        id: Date.now() + '_assistant',
        type: 'assistant',
        content: response.response,
        timestamp: new Date().toISOString()
      }

      setMessages(prev => [...prev, assistantMessage])

      // 推薦結果があれば表示
      if (response.recommendations && response.recommendations.length > 0) {
        setRecommendations(response.recommendations)
      }

      // 絞り込み件数を更新
      if (response.filtered_count !== undefined) {
        setFilteredPropertyCount(response.filtered_count)
      }

    } catch (error) {
      console.error('Message send error:', error)
      
      const errorMessage = {
        id: Date.now() + '_error',
        type: 'assistant',
        content: 'メッセージの送信中にエラーが発生しました。もう一度お試しください。',
        timestamp: new Date().toISOString()
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleFileUpload = async (file) => {
    if (!file || isLoading) return

    const userMessage = {
      id: Date.now() + '_file',
      type: 'user',
      content: `📄 ${file.name} をアップロードしました`,
      timestamp: new Date().toISOString()
    }

    setMessages(prev => [...prev, userMessage])
    setIsLoading(true)

    try {
      const response = await uploadPDF(file, sessionId, recommendationCount)

      // セッションIDを更新
      if (response.session_id && !sessionId) {
        setSessionId(response.session_id)
      }

      // アシスタントのレスポンス
      const assistantMessage = {
        id: Date.now() + '_assistant',
        type: 'assistant',
        content: response.message,
        timestamp: new Date().toISOString()
      }

      setMessages(prev => [...prev, assistantMessage])

      // 推薦結果があれば表示
      if (response.recommendations && response.recommendations.length > 0) {
        setRecommendations(response.recommendations)
      }

      // 絞り込み件数を更新
      if (response.filtered_count !== undefined) {
        setFilteredPropertyCount(response.filtered_count)
      }

    } catch (error) {
      console.error('File upload error:', error)
      
      const errorMessage = {
        id: Date.now() + '_error',
        type: 'assistant',
        content: 'ファイルのアップロード中にエラーが発生しました。PDFファイルかご確認の上、もう一度お試しください。',
        timestamp: new Date().toISOString()
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleNewChat = () => {
    setMessages([
      {
        id: 'welcome',
        type: 'assistant',
        content: 'こんにちは！SumaiAgentです。🏠\n\nご希望の物件について教えてください。例えば：\n• 「新宿駅周辺で1K、予算10万円以下」\n• 「横浜市内で築浅の2LDK」\n• PDFファイルをアップロード\n\nどのようにお手伝いしましょうか？',
        timestamp: new Date().toISOString()
      }
    ])
    setSessionId(null)
    setRecommendations([])
  }

  return (
    <div className="app">
      {/* Header */}
      <header className="app-header">
        <div className="header-content">
          <h1 className="app-title">
            SumaiAgent
            {(filteredPropertyCount !== null || totalPropertyCount) && (
              <span className="property-count">
                &lt;{(filteredPropertyCount !== null ? filteredPropertyCount : totalPropertyCount).toLocaleString()}&gt;
              </span>
            )}
          </h1>
          <div className="header-controls">
            <select 
              value={recommendationCount}
              onChange={(e) => setRecommendationCount(parseInt(e.target.value))}
              className="recommendation-count-select"
            >
              <option value={3}>推薦 3件</option>
              <option value={5}>推薦 5件</option>
              <option value={10}>推薦 10件</option>
            </select>
            <button onClick={handleNewChat} className="new-chat-button">
              新しいチャット
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="app-main">
        {/* Chat Area */}
        <div className="chat-container">
          <div className="messages-area">
            {messages.map((message) => (
              <ChatMessage
                key={message.id}
                message={message}
                isLoading={isLoading && message.id === messages[messages.length - 1]?.id}
              />
            ))}
            {isLoading && messages[messages.length - 1]?.type === 'user' && (
              <div className="typing-indicator">
                <div className="typing-animation">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <span className="typing-text">SumaiAgentが回答を準備中...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Property Recommendations */}
          {recommendations.length > 0 && (
            <PropertyRecommendations
              recommendations={recommendations}
              onClose={() => setRecommendations([])}
            />
          )}
        </div>
      </main>

      {/* Footer with Message Input */}
      <footer className="app-footer">
        <div className="footer-content">
          <MessageInput
            onSendMessage={handleSendMessage}
            onFileUpload={handleFileUpload}
            isLoading={isLoading}
          />
        </div>
      </footer>
    </div>
  )
}

export default App