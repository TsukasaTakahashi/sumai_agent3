import { useState } from 'react'
import './PropertyRecommendations.css'

const PropertyRecommendations = ({ recommendations, onClose }) => {
  const [expandedCard, setExpandedCard] = useState(null)

  const formatPrice = (price) => {
    if (!price) return '価格未定'
    return typeof price === 'string' ? price : `${price}万円`
  }

  const formatArea = (area) => {
    if (!area) return '面積未定'
    return typeof area === 'string' ? area : `${area}㎡`
  }

  const formatWalkTime = (walkTime) => {
    if (!walkTime) return '徒歩時間未定'
    return typeof walkTime === 'string' ? walkTime : `徒歩${walkTime}分`
  }

  const formatAge = (age) => {
    if (!age) return '築年数未定'
    return typeof age === 'string' ? age : `築${age}年`
  }

  const getScoreColor = (score) => {
    if (score >= 0.8) return '#4CAF50'
    if (score >= 0.6) return '#FF9800'
    if (score >= 0.4) return '#FF5722'
    return '#757575'
  }

  const getScoreLabel = (score) => {
    if (score >= 0.8) return '高い推奨度'
    if (score >= 0.6) return '中程度の推奨度'
    if (score >= 0.4) return '一定の推奨度'
    return '参考レベル'
  }

  const handleCardExpand = (index) => {
    setExpandedCard(expandedCard === index ? null : index)
  }

  const handleUrlClick = (url) => {
    if (url) {
      window.open(url, '_blank', 'noopener,noreferrer')
    }
  }

  if (!recommendations || recommendations.length === 0) {
    return null
  }

  return (
    <div className="property-recommendations">
      <div className="recommendations-header">
        <h3>🏠 おすすめ物件 ({recommendations.length}件)</h3>
        <button onClick={onClose} className="close-button">
          ✕
        </button>
      </div>

      <div className="recommendations-grid">
        {recommendations.map((property, index) => (
          <div 
            key={property.id || index} 
            className={`property-card ${expandedCard === index ? 'expanded' : ''}`}
          >
            {/* 推奨スコア */}
            <div className="score-badge">
              <div 
                className="score-circle"
                style={{ 
                  background: `conic-gradient(${getScoreColor(property.similarity_score)} ${property.similarity_score * 360}deg, rgba(255,255,255,0.1) 0deg)`
                }}
              >
                <div className="score-inner">
                  {Math.round(property.similarity_score * 100)}%
                </div>
              </div>
              <span className="score-label">
                {getScoreLabel(property.similarity_score)}
              </span>
            </div>

            {/* 基本情報 */}
            <div className="property-info">
              <h4 className="property-address">{property.address || '住所未定'}</h4>
              
              <div className="property-details">
                <div className="detail-row">
                  <span className="detail-icon">💰</span>
                  <span className="detail-label">価格:</span>
                  <span className="detail-value price">{formatPrice(property.price)}</span>
                </div>
                
                <div className="detail-row">
                  <span className="detail-icon">📐</span>
                  <span className="detail-label">広さ:</span>
                  <span className="detail-value">{formatArea(property.area)}</span>
                </div>
                
                <div className="detail-row">
                  <span className="detail-icon">🏠</span>
                  <span className="detail-label">間取り:</span>
                  <span className="detail-value">{property.layout || '間取り未定'}</span>
                </div>
                
                <div className="detail-row">
                  <span className="detail-icon">🚉</span>
                  <span className="detail-label">駅徒歩:</span>
                  <span className="detail-value">{formatWalkTime(property.walk_time)}</span>
                </div>
                
                <div className="detail-row">
                  <span className="detail-icon">📅</span>
                  <span className="detail-label">築年数:</span>
                  <span className="detail-value">{formatAge(property.age)}</span>
                </div>
              </div>

              {/* 類似タグ */}
              {property.similarity_tags && property.similarity_tags.length > 0 && (
                <div className="similarity-tags">
                  {property.similarity_tags.map((tag, tagIndex) => (
                    <span key={tagIndex} className="similarity-tag">
                      {tag}
                    </span>
                  ))}
                </div>
              )}

              {/* 推薦理由 */}
              {property.recommendation_reason && (
                <div className="recommendation-reason">
                  <span className="reason-icon">✨</span>
                  <span className="reason-text">{property.recommendation_reason}</span>
                </div>
              )}
            </div>

            {/* 詳細スコア（展開時） */}
            {expandedCard === index && property.detailed_scores && (
              <div className="detailed-scores">
                <h5>詳細評価</h5>
                <div className="scores-grid">
                  {Object.entries(property.detailed_scores).map(([key, score]) => {
                    const scoreLabels = {
                      location: '📍 地域適合',
                      price: '💰 価格適合', 
                      layout: '🏠 間取り適合',
                      area: '📐 面積適合',
                      age: '📅 築年数適合',
                      walk_time: '🚉 駅徒歩適合',
                      commute_time: '🚗 通勤適合'
                    }
                    
                    return (
                      <div key={key} className="score-item">
                        <span className="score-name">{scoreLabels[key] || key}</span>
                        <div className="score-bar">
                          <div 
                            className="score-fill"
                            style={{ 
                              width: `${score * 100}%`,
                              background: getScoreColor(score)
                            }}
                          ></div>
                        </div>
                        <span className="score-value">{Math.round(score * 100)}%</span>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* アクションボタン */}
            <div className="property-actions">
              <button 
                onClick={() => handleCardExpand(index)}
                className="expand-button"
              >
                {expandedCard === index ? '詳細を閉じる' : '詳細を見る'}
              </button>
              
              {property.url && (
                <button 
                  onClick={() => handleUrlClick(property.url)}
                  className="url-button"
                >
                  🔗 物件詳細ページ
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default PropertyRecommendations