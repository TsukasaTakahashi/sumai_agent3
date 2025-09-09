import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [prefectures, setPrefectures] = useState([])
  const [selectedPrefecture, setSelectedPrefecture] = useState('')
  const [stations, setStations] = useState([])
  const [selectedStation, setSelectedStation] = useState('')
  const [properties, setProperties] = useState([])
  const [searchResult, setSearchResult] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [step, setStep] = useState(1) // 1: 都道府県選択, 2: 駅選択, 3: 結果表示

  // 都道府県一覧を取得
  useEffect(() => {
    fetchPrefectures()
  }, [])

  const fetchPrefectures = async () => {
    try {
      const response = await fetch('http://localhost:8001/prefectures')
      const data = await response.json()
      setPrefectures(data.prefectures)
    } catch (error) {
      console.error('都道府県の取得に失敗:', error)
    }
  }

  // 都道府県選択時の処理
  const handlePrefectureSelect = async (prefecture) => {
    setSelectedPrefecture(prefecture)
    setIsLoading(true)
    
    try {
      const response = await fetch(`http://localhost:8001/stations/${encodeURIComponent(prefecture)}`)
      const data = await response.json()
      setStations(data.stations)
      setStep(2)
    } catch (error) {
      console.error('駅の取得に失敗:', error)
    } finally {
      setIsLoading(false)
    }
  }

  // 駅選択時の処理
  const handleStationSelect = async (stationName) => {
    setSelectedStation(stationName)
    setIsLoading(true)

    try {
      const formData = new FormData()
      formData.append('prefecture', selectedPrefecture)
      formData.append('station', stationName)
      formData.append('limit', '20')

      const response = await fetch('http://localhost:8001/search', {
        method: 'POST',
        body: formData
      })

      const result = await response.json()
      if (result.success) {
        setSearchResult(result.data)
        setProperties(result.data.properties)
        setStep(3)
      }
    } catch (error) {
      console.error('物件検索に失敗:', error)
    } finally {
      setIsLoading(false)
    }
  }

  // リセット処理
  const handleReset = () => {
    setSelectedPrefecture('')
    setSelectedStation('')
    setStations([])
    setProperties([])
    setSearchResult(null)
    setStep(1)
  }

  const handleBack = () => {
    if (step === 3) {
      setStep(2)
      setProperties([])
      setSearchResult(null)
    } else if (step === 2) {
      setStep(1)
      setStations([])
      setSelectedPrefecture('')
    }
  }

  return (
    <div className="app-container">
      <header className="header">
        <h1>🏠 都道府県別物件検索</h1>
        <p>まず都道府県を選択し、次に駅を選択してください</p>
      </header>

      <div className="content">
        {/* 進行状況表示 */}
        <div className="progress-bar">
          <div className={`step ${step >= 1 ? 'active' : ''}`}>
            <span className="step-number">1</span>
            <span className="step-text">都道府県選択</span>
          </div>
          <div className={`step ${step >= 2 ? 'active' : ''}`}>
            <span className="step-number">2</span>
            <span className="step-text">駅選択</span>
          </div>
          <div className={`step ${step >= 3 ? 'active' : ''}`}>
            <span className="step-number">3</span>
            <span className="step-text">物件一覧</span>
          </div>
        </div>

        {/* 選択状態表示 */}
        {selectedPrefecture && (
          <div className="selection-display">
            <span className="selection-item">
              📍 {selectedPrefecture}
              {selectedStation && <span> → 🚉 {selectedStation}駅</span>}
            </span>
          </div>
        )}

        {isLoading && (
          <div className="loading">
            <div className="spinner"></div>
            <p>読み込み中...</p>
          </div>
        )}

        {/* ステップ1: 都道府県選択 */}
        {step === 1 && !isLoading && (
          <div className="prefecture-selection">
            <h2>📍 都道府県を選択してください</h2>
            <div className="prefecture-grid">
              {prefectures.map((prefecture) => (
                <button
                  key={prefecture}
                  className="prefecture-button"
                  onClick={() => handlePrefectureSelect(prefecture)}
                >
                  {prefecture}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ステップ2: 駅選択 */}
        {step === 2 && !isLoading && (
          <div className="station-selection">
            <h2>🚉 {selectedPrefecture}の駅を選択してください</h2>
            <div className="station-list">
              {stations.map((station, index) => (
                <button
                  key={`${station.name}-${index}`}
                  className="station-button"
                  onClick={() => handleStationSelect(station.name)}
                >
                  <span className="station-name">{station.name}駅</span>
                  <span className="property-count">{station.property_count}件</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ステップ3: 物件一覧 */}
        {step === 3 && searchResult && (
          <div className="property-results">
            <h2>🏠 {searchResult.prefecture} {searchResult.station}駅の物件一覧</h2>
            <p className="result-summary">
              {searchResult.total_count}件中 {properties.length}件を表示
            </p>
            
            <div className="property-list">
              {properties.map((property, index) => (
                <div key={index} className="property-card">
                  <div className="property-info">
                    <h3>{property.address}</h3>
                    <div className="property-details">
                      <span className="price">💰 {property.price}</span>
                      <span className="area">📐 {property.area}</span>
                      <span className="layout">🏠 {property.layout}</span>
                      <span className="age">📅 {property.age}</span>
                    </div>
                    <div className="property-access">
                      <span>🚉 {property.traffic}</span>
                    </div>
                  </div>
                  {property.url && (
                    <div className="property-actions">
                      <button
                        className="url-button"
                        onClick={() => window.open(property.url, '_blank')}
                      >
                        🔗 詳細を見る
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 操作ボタン */}
        <div className="action-buttons">
          {step > 1 && (
            <button className="back-button" onClick={handleBack}>
              ← 戻る
            </button>
          )}
          {step > 1 && (
            <button className="reset-button" onClick={handleReset}>
              🔄 最初から
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default App