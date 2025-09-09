import { useState, useRef } from 'react'
import './MessageInput.css'

const MessageInput = ({ onSendMessage, onFileUpload, isLoading }) => {
  const [message, setMessage] = useState('')
  const [isDragOver, setIsDragOver] = useState(false)
  const [isComposing, setIsComposing] = useState(false)
  const fileInputRef = useRef(null)
  const textareaRef = useRef(null)

  const handleSubmit = (e) => {
    e.preventDefault()
    if (message.trim() && !isLoading) {
      onSendMessage(message.trim())
      setMessage('')
      // テキストエリアのサイズをリセット
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto'
      }
    }
  }

  const handleKeyDown = (e) => {
    // Shift+Enterで改行、Enterで送信（ただし日本語変換中は除く）
    if (e.key === 'Enter' && !e.shiftKey && !isComposing) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const handleCompositionStart = () => {
    setIsComposing(true)
  }

  const handleCompositionEnd = () => {
    setIsComposing(false)
  }

  const handleTextareaChange = (e) => {
    setMessage(e.target.value)
    
    // 自動サイズ調整
    const textarea = e.target
    textarea.style.height = 'auto'
    textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px'
  }

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0]
    if (file && file.type === 'application/pdf') {
      onFileUpload(file)
      // input をリセット
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    } else if (file) {
      alert('PDFファイルのみをアップロードしてください。')
    }
  }

  const handleFileButtonClick = () => {
    fileInputRef.current?.click()
  }

  // ドラッグ＆ドロップ処理
  const handleDragOver = (e) => {
    e.preventDefault()
    setIsDragOver(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    setIsDragOver(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragOver(false)
    
    const files = e.dataTransfer.files
    if (files.length > 0) {
      const file = files[0]
      if (file.type === 'application/pdf') {
        onFileUpload(file)
      } else {
        alert('PDFファイルのみをアップロードしてください。')
      }
    }
  }

  return (
    <div 
      className={`message-input-container ${isDragOver ? 'drag-over' : ''}`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {isDragOver && (
        <div className="drag-overlay">
          <div className="drag-message">
            📄 PDFファイルをドロップしてください
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="message-form">
        <div className="input-section">
          {/* ファイルアップロードボタン */}
          <button
            type="button"
            onClick={handleFileButtonClick}
            disabled={isLoading}
            className="file-upload-button"
            title="PDFファイルをアップロード"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2L12 15M12 2L8 6M12 2L16 6M5 15V18C5 19.1 5.9 20 7 20H17C18.1 20 19 19.1 19 18V15" 
                    stroke="currentColor" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>

          {/* テキスト入力 */}
          <textarea
            ref={textareaRef}
            value={message}
            onChange={handleTextareaChange}
            onKeyDown={handleKeyDown}
            onCompositionStart={handleCompositionStart}
            onCompositionEnd={handleCompositionEnd}
            placeholder="物件のご希望を教えてください... (Shift+Enterで改行)"
            disabled={isLoading}
            className="message-textarea"
            rows={1}
          />

          {/* 送信ボタン */}
          <button
            type="submit"
            disabled={!message.trim() || isLoading}
            className="send-button"
            title="メッセージを送信"
          >
            {isLoading ? (
              <div className="loading-spinner"></div>
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <path d="M2 21L23 12L2 3V10L17 12L2 14V21Z" />
              </svg>
            )}
          </button>
        </div>

        {/* ファイル入力（非表示） */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />
      </form>

      {/* ヒントテキスト */}
      <div className="input-hints">
        <span>💡 例: 「新宿駅周辺で1K、予算10万円以下」</span>
        <span>📄 PDFファイルから物件情報を解析可能</span>
      </div>
    </div>
  )
}

export default MessageInput