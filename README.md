# SumaiAgent - AI不動産検索アプリケーション

AI を活用した対話型不動産検索システムです。ユーザーの要望を自然言語で受け取り、最適な物件をレコメンドします。

## 🚀 特徴

### 核心機能
- **対話型検索**: 自然言語での物件検索（「新宿駅周辺で1K、予算10万円以下」など）
- **PDFアップロード**: 物件チラシのPDF/画像をアップロードして類似物件を検索
- **マルチエージェント**: 専門エージェントによる高度な検索・推薦システム
- **地域の曖昧さ解決**: 同名駅（川崎駅など）の曖昧さを自動解決

### 推薦システム
以下の軸で物件を評価・推薦：
- 📍 **エリア**: 都道府県・市区町村・駅からの適合度
- 💰 **価格**: 予算との適合度（±10%の範囲で柔軟評価）
- 🏠 **間取り**: 希望間取りとの適合度
- 📐 **広さ**: 希望面積との適合度
- 📅 **築年数**: 築年数の希望との適合度
- 🚉 **駅徒歩**: 駅からの徒歩時間適合度
- 🚗 **通勤時間**: 通勤・通学先からの時間適合度

## 🏗️ アーキテクチャ

### バックエンド (FastAPI)
```
backend/
├── app.py                 # メインAPIサーバー
├── agents/                # マルチエージェントシステム
│   ├── orchestrator_agent.py      # 統括エージェント
│   ├── location_agent.py          # 地域特定エージェント
│   ├── property_analysis_agent.py # 物件条件分析エージェント
│   └── recommendation_agent.py    # 推薦エージェント
├── services/              # サービス層
│   ├── database_service.py        # データベース操作
│   └── pdf_service.py             # PDF/OCR処理
└── data/db/               # データベース配置場所
    └── properties.db      # SQLite物件データベース
```

### フロントエンド (React + Vite)
```
frontend/
├── src/
│   ├── App.jsx            # メインアプリケーション
│   ├── components/        # Reactコンポーネント
│   │   ├── ChatMessage.jsx        # チャットメッセージ
│   │   ├── MessageInput.jsx       # メッセージ入力
│   │   └── PropertyRecommendations.jsx # 物件推薦表示
│   └── services/
│       └── api.js         # API通信
└── package.json
```

## 🛠️ セットアップ

### 必要な環境
- Python 3.8+
- Node.js 16+
- SQLite3

### 1. バックエンドセットアップ

```bash
cd backend

# 仮想環境を作成・アクティベート
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存関係をインストール
pip install -r requirements.txt

# 環境変数を設定
cp .env.example .env
# .env ファイルを編集してAPI KEYを設定
```

### 2. フロントエンドセットアップ

```bash
cd frontend

# 依存関係をインストール
npm install
```

### 3. 環境変数設定

#### backend/.env
```env
# OpenAI API Key for LLM functionality
OPENAI_API_KEY=your_openai_api_key_here

# Database path  
DATABASE_PATH=./data/db/properties.db

# Server configuration
HOST=0.0.0.0
PORT=8000

# File upload settings
MAX_FILE_SIZE=10485760
UPLOAD_FOLDER=./uploads
```

### 4. データベース配置

SQLiteデータベースファイル（properties.db）を以下の場所に配置してください：
```
backend/data/db/properties.db
```

**データベーススキーマ**:
```sql
CREATE TABLE properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address TEXT,           -- 住所
    prefecture TEXT,        -- 都道府県
    city TEXT,             -- 市区町村
    station_name TEXT,     -- 最寄り駅名
    walk_time INTEGER,     -- 徒歩時間（分）
    price REAL,            -- 価格（万円）
    layout TEXT,           -- 間取り
    area REAL,             -- 面積（㎡）
    age INTEGER,           -- 築年数
    property_type TEXT,    -- 物件種別
    url TEXT,              -- 物件詳細URL
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🚀 起動方法

### 開発サーバーの起動

**1. バックエンド起動**:
```bash
cd backend
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

**2. フロントエンド起動**:
```bash
cd frontend  
npm run dev
```

### アクセス
- **フロントエンド**: http://localhost:3000
- **バックエンドAPI**: http://localhost:8000
- **API仕様**: http://localhost:8000/docs (Swagger UI)

## 💬 使用方法

### 1. 対話検索
チャットインターフェースで自然言語入力：
- 「新宿駅周辺で1K、予算10万円以下」
- 「横浜市内で築浅の2LDK」
- 「川崎駅近くのマンション」（地域の曖昧さを自動解決）

### 2. PDFアップロード
物件チラシのPDFファイルをアップロード：
- テキストベースPDF: 直接テキスト抽出
- 画像ベースPDF: OCR処理後にテキスト抽出
- 抽出された条件に基づいて類似物件を自動推薦

### 3. 推薦結果
- 類似度スコア（0-100%）表示
- 詳細評価軸別スコア表示
- 推薦理由の説明
- 物件詳細URLへのリンク

## 🔧 カスタマイズ

### 推薦重み調整
`backend/agents/recommendation_agent.py`で重み設定を変更可能：

```python
self.feature_weights = {
    "location": 0.25,      # エリア・駅からの距離
    "price": 0.20,         # 価格
    "layout": 0.15,        # 間取り
    "area": 0.15,          # 面積
    "age": 0.10,           # 築年数
    "walk_time": 0.10,     # 駅徒歩時間
    "commute_time": 0.05   # 通勤時間
}
```

### UI色合いの変更
シルバー・ブラック基調のデザインは`frontend/src/*.css`で調整可能。

## 📝 API仕様

### チャットエンドポイント
```http
POST /chat
Content-Type: application/json

{
  "message": "新宿駅周辺で1K、予算10万円以下",
  "session_id": "optional_session_id",
  "recommendation_count": 3
}
```

### PDFアップロードエンドポイント
```http
POST /upload-pdf
Content-Type: multipart/form-data

- file: PDF file
- session_id: optional
- recommendation_count: 3
```

## 🛡️ セキュリティ

- API KEYは環境変数で管理
- ファイルアップロードはPDFのみ許可
- SQLインジェクション対策済み
- CORS設定によるオリジン制限

## 🧪 テスト

```bash
# バックエンドテスト
cd backend
python -m pytest

# フロントエンドテスト  
cd frontend
npm run test
```

## 📚 依存関係

### バックエンド主要ライブラリ
- FastAPI: Webフレームワーク
- OpenAI: LLM API
- PyPDF2: PDF処理
- pytesseract: OCR処理
- scikit-learn: 機械学習・類似度計算
- SQLite3: データベース

### フロントエンド主要ライブラリ
- React: UIフレームワーク  
- Vite: ビルドツール
- Axios: HTTP通信

## 🚧 今後の拡張予定

- [ ] 地図API連携による通勤時間計算
- [ ] 画像認識による物件写真解析
- [ ] ユーザー学習による推薦精度向上
- [ ] 不動産API連携によるリアルタイムデータ取得
- [ ] チャット履歴の永続化
- [ ] マルチユーザー対応

## 📄 ライセンス

MIT License

## 🤝 コントリビューション

1. このリポジトリをフォーク
2. フィーチャーブランチを作成 (`git checkout -b feature/AmazingFeature`)
3. コミット (`git commit -m 'Add some AmazingFeature'`)  
4. ブランチにプッシュ (`git push origin feature/AmazingFeature`)
5. プルリクエストを作成

---

🏠 **SumaiAgent** - AI-Powered Real Estate Search System