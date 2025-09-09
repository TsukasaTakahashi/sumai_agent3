import { useState } from 'react'
import './ChatMessage.css'

const ChatMessage = ({ message, isLoading = false }) => {
  const [isExpanded, setIsExpanded] = useState(false)
  
  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('ja-JP', { 
      hour: '2-digit', 
      minute: '2-digit' 
    })
  }

  const formatMessage = (content) => {
    // 改行を<br>に変換
    const lines = content.split('\n')
    return lines.map((line, index) => (
      <span key={index}>
        {line}
        {index < lines.length - 1 && <br />}
      </span>
    ))
  }

  const shouldTruncate = message.content.length > 200
  const displayContent = shouldTruncate && !isExpanded 
    ? message.content.slice(0, 200) + '...'
    : message.content

  return (
    <div className={`chat-message ${message.type}`}>
      <div className="message-avatar">
        {message.type === 'user' ? (
          <div className="user-avatar">👤</div>
        ) : (
          <div className="assistant-avatar">🏠</div>
        )}
      </div>

      <div className="message-content">
        <div className="message-header">
          <span className="message-sender">
            {message.type === 'user' ? 'あなた' : 'SumaiAgent'}
          </span>
          <span className="message-timestamp">
            {formatTimestamp(message.timestamp)}
          </span>
        </div>

        <div className="message-body">
          <div className="message-text">
            {formatMessage(displayContent)}
            
            {shouldTruncate && (
              <button 
                className="expand-button"
                onClick={() => setIsExpanded(!isExpanded)}
              >
                {isExpanded ? '折りたたむ' : 'もっと見る'}
              </button>
            )}
          </div>

          {isLoading && (
            <div className="message-loading">
              <div className="loading-dots">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default ChatMessage