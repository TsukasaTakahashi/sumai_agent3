from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import time
from dotenv import load_dotenv
import uvicorn

from agents.orchestrator_agent import OrchestratorAgent
from services.database_service import DatabaseService
from services.pdf_service import PDFService

def remove_duplicate_properties(properties):
    """
    物件リストから重複を除去する
    住所、価格、間取り、面積、築年数、駅名、徒歩時間、URLを組み合わせて重複を判定
    """
    seen_properties = set()
    seen_urls = set()
    unique_properties = []
    
    for prop in properties:
        # 重複判定キーを作成（主要な属性を組み合わせ）
        duplicate_key = (
            prop.get('address', '').strip().lower(),
            prop.get('price', 0),
            prop.get('layout', '').strip(),
            prop.get('area', 0),
            prop.get('age', 0),
            prop.get('station_name', '').strip().lower(),
            prop.get('walk_time', 0)
        )
        
        # URLも重複チェック
        url_key = prop.get('url', '').strip()
        
        # 属性キーまたはURLのいずれかが重複していない場合のみ追加
        if duplicate_key not in seen_properties and url_key not in seen_urls:
            seen_properties.add(duplicate_key)
            if url_key:  # URLが空でない場合のみ追加
                seen_urls.add(url_key)
            unique_properties.append(prop)
    
    print(f"重複除去: {len(properties)} 件 → {len(unique_properties)} 件")
    return unique_properties

# Load environment variables
load_dotenv()

app = FastAPI(title="SumaiAgent API", description="Real Estate Property Recommendation System", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services lazily
orchestrator = None
database_service = None
pdf_service = None

def get_orchestrator():
    global orchestrator
    if orchestrator is None:
        orchestrator = OrchestratorAgent()
    return orchestrator

def get_database_service():
    global database_service
    if database_service is None:
        database_service = DatabaseService()
    return database_service

def get_pdf_service():
    global pdf_service
    if pdf_service is None:
        pdf_service = PDFService()
    return pdf_service

# Request/Response models
class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None
    recommendation_count: int = 3

class ChatResponse(BaseModel):
    response: str
    session_id: str
    recommendations: Optional[List[Dict[str, Any]]] = None
    is_final: bool = False
    filtered_count: Optional[int] = None

class PDFUploadResponse(BaseModel):
    message: str
    session_id: str
    recommendations: Optional[List[Dict[str, Any]]] = None
    extracted_info: Dict[str, Any]

@app.get("/")
async def root():
    return {"message": "SumaiAgent API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "SumaiAgent API is operational"}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(chat_request: ChatMessage):
    """
    Handle chat messages and return conversational responses with property recommendations
    """
    try:
        import re
        import httpx
        import json
        from dotenv import load_dotenv
        
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        
        # セッションIDを生成または使用
        session_id = chat_request.session_id or f"session_{int(time.time())}"
        
        # データベースから物件検索
        db_service = get_database_service()
        
        # メッセージから検索条件を抽出（簡易版）
        search_criteria = {}
        
        # 都道府県抽出
        prefectures = ['東京', '神奈川', '大阪', '京都', '埼玉', '千葉', '兵庫', '愛知', '福岡', '北海道']
        for pref in prefectures:
            if pref in chat_request.message:
                search_criteria['prefecture'] = pref
                break
        
        # 価格抽出
        price_match = re.search(r'(\d+)万円以下', chat_request.message)
        if price_match:
            search_criteria['price_max'] = int(price_match.group(1))
        
        # 間取り抽出
        layout_match = re.search(r'([1-9][SLDK]+)', chat_request.message)
        if layout_match:
            search_criteria['layout'] = layout_match.group(1)
        
        # 駅名抽出と曖昧さ解決
        station_match = re.search(r'([^駅\s]+)駅', chat_request.message)
        if station_match:
            station_name = station_match.group(1)
            
            # 駅の曖昧さをチェック
            station_candidates = await db_service.find_stations_by_name(station_name)
            
            if len(station_candidates) > 1 and 'prefecture' not in search_criteria:
                # 複数の候補がある場合、選択を促すレスポンスを返す
                candidate_list = []
                for i, candidate in enumerate(station_candidates[:5], 1):
                    prefecture = candidate.get('prefecture', '')
                    city = candidate.get('city', '')
                    count = candidate.get('property_count', 0)
                    candidate_list.append(f"{i}. {prefecture} {city} ({count}件)")
                
                disambiguation_response = f"「{station_name}駅」は複数の地域にございます。どちらの地域をご希望でしょうか？\n\n" + "\n".join(candidate_list) + "\n\n数字または「東京都の新宿駅」のように詳しく教えてください。"
                
                return ChatResponse(
                    response=disambiguation_response,
                    session_id=session_id,
                    recommendations=[],
                    is_final=False
                )
            elif len(station_candidates) == 1:
                # 一意に特定できる場合
                candidate = station_candidates[0]
                search_criteria['station'] = station_name
                if not search_criteria.get('prefecture'):
                    search_criteria['prefecture'] = candidate.get('prefecture', '').replace('県', '').replace('都', '').replace('府', '')
            else:
                search_criteria['station'] = station_name
        
        # デフォルト検索条件
        if not search_criteria:
            search_criteria = {'prefecture': '東京', 'price_max': 5000}
        
        # 重複除去を考慮して多めに取得
        original_limit = chat_request.recommendation_count
        search_criteria['limit'] = original_limit * 3  # 3倍多く取得して重複除去後に十分な件数を確保
        
        # 物件検索実行
        properties = await db_service.search_properties(search_criteria)
        
        # 重複除去処理
        properties = remove_duplicate_properties(properties)
        
        # 最終的に必要な件数に制限
        properties = properties[:original_limit]
        
        # OpenAI APIで応答生成
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        conditions_text = ", ".join([f"{k}: {v}" for k, v in search_criteria.items()])
        property_count = len(properties)
        
        data = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": f"あなたは不動産検索アシスタントです。検索条件「{conditions_text}」で{property_count}件の物件が見つかりました。結果を親しみやすく説明してください。"},
                {"role": "user", "content": chat_request.message}
            ],
            "max_tokens": 300
        }
        
        async with httpx.AsyncClient() as client:
            ai_response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=data
            )
        
        if ai_response.status_code == 200:
            ai_result = ai_response.json()
            response_text = ai_result["choices"][0]["message"]["content"]
            
            # 物件データを推薦形式に変換（類似タグ付き）
            recommendations = []
            for prop in properties:
                # 検索条件と物件データの合致度を判定
                matching_tags = []
                similarity_scores = {}
                
                # 都道府県マッチング
                if search_criteria.get('prefecture') and prop.get('prefecture'):
                    prop_pref = prop.get('prefecture', '').replace('県', '').replace('都', '').replace('府', '')
                    if search_criteria['prefecture'] in prop_pref or prop_pref in search_criteria['prefecture']:
                        matching_tags.append('地域')
                        similarity_scores['location'] = 1.0
                
                # 価格マッチング（±10%の許容範囲）
                if search_criteria.get('price_max') and prop.get('price'):
                    max_price = search_criteria['price_max']
                    prop_price = prop.get('price', 0)
                    if prop_price <= max_price * 1.1:  # 10%の許容範囲
                        matching_tags.append('価格')
                        # 価格が近いほど高スコア
                        price_ratio = min(prop_price / max_price, 1.0) if max_price > 0 else 0.5
                        similarity_scores['price'] = 1.0 - abs(1.0 - price_ratio) * 0.5
                
                # 間取りマッチング
                if search_criteria.get('layout') and prop.get('layout'):
                    if search_criteria['layout'] == prop.get('layout'):
                        matching_tags.append('間取り')
                        similarity_scores['layout'] = 1.0
                
                # 駅名マッチング
                if search_criteria.get('station') and prop.get('station_name'):
                    if search_criteria['station'] in prop.get('station_name', ''):
                        matching_tags.append('最寄り駅')
                        similarity_scores['station'] = 1.0
                
                # 徒歩時間マッチング（15分以内なら良好）
                walk_time = prop.get('walk_time', 999)
                if walk_time < 999 and walk_time <= 15:
                    matching_tags.append('駅近')
                    similarity_scores['walk_time'] = max(0.5, 1.0 - walk_time / 30.0)
                
                # 築年数マッチング（20年以内なら良好）
                age = prop.get('age', 999)
                if age < 999 and age <= 20:
                    matching_tags.append('築浅')
                    similarity_scores['age'] = max(0.5, 1.0 - age / 40.0)
                
                # 全体の類似度スコア計算
                overall_score = sum(similarity_scores.values()) / max(len(similarity_scores), 1) if similarity_scores else 0.3
                
                recommendations.append({
                    "id": prop.get("url", ""),
                    "address": prop.get("address", ""),
                    "price": f"{prop.get('price', 0)}万円",
                    "layout": prop.get("layout", ""),
                    "area": f"{prop.get('area', 0)}㎡" if prop.get('area', 0) > 0 else "面積未定",
                    "age": f"築{prop.get('age', 0)}年" if prop.get('age', 0) > 0 else "築年数未定",
                    "station_name": prop.get("station_name", ""),
                    "walk_time": f"徒歩{prop.get('walk_time', 0)}分" if prop.get('walk_time', 0) < 999 else "徒歩時間未定",
                    "url": prop.get("url", ""),
                    "similarity_score": min(overall_score, 1.0),
                    "similarity_tags": matching_tags,
                    "detailed_scores": similarity_scores,
                    "recommendation_reason": f"検索条件に合致 ({', '.join(matching_tags)})" if matching_tags else "検索条件に合致"
                })
            
            return ChatResponse(
                response=response_text,
                session_id=session_id,
                recommendations=recommendations,
                is_final=len(recommendations) > 0,
                filtered_count=len(properties)  # 絞り込み後の件数を追加
            )
        else:
            # OpenAI APIエラー時も推薦リストを返す
            recommendations = []
            for prop in properties:
                recommendations.append({
                    "id": prop.get("url", ""),
                    "address": prop.get("address", ""),
                    "price": f"{prop.get('price', 0)}万円",
                    "layout": prop.get("layout", ""),
                    "area": f"{prop.get('area', 0)}㎡" if prop.get('area', 0) > 0 else "面積未定",
                    "age": f"築{prop.get('age', 0)}年" if prop.get('age', 0) > 0 else "築年数未定",
                    "station_name": prop.get("station_name", ""),
                    "walk_time": f"徒歩{prop.get('walk_time', 0)}分" if prop.get('walk_time', 0) < 999 else "徒歩時間未定",
                    "url": prop.get("url", ""),
                    "similarity_score": 0.8,
                    "similarity_tags": ["検索結果"],
                    "detailed_scores": {},
                    "recommendation_reason": "検索条件に合致"
                })
            
            return ChatResponse(
                response=f"検索条件「{conditions_text}」で{property_count}件の物件が見つかりました。",
                session_id=session_id,
                recommendations=recommendations,
                is_final=True,
                filtered_count=property_count
            )
    
    except Exception as e:
        import traceback
        print(f"Chat error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error processing chat message: {str(e)}")

@app.post("/upload-pdf", response_model=PDFUploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    session_id: Optional[str] = None,
    recommendation_count: int = 3
):
    """
    Handle PDF file uploads and extract property information for recommendations
    """
    try:
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
        # Process PDF through PDF service
        extracted_info = await get_pdf_service().process_pdf(file)
        
        # Get recommendations based on extracted information
        result = await get_orchestrator().process_pdf_info(
            extracted_info=extracted_info,
            session_id=session_id,
            recommendation_count=recommendation_count
        )
        
        return PDFUploadResponse(
            message=result["response"],
            session_id=result["session_id"],
            recommendations=result.get("recommendations"),
            extracted_info=extracted_info
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")

@app.get("/session/{session_id}/history")
async def get_chat_history(session_id: str):
    """
    Get chat history for a specific session
    """
    try:
        history = await get_orchestrator().get_session_history(session_id)
        return {"session_id": session_id, "history": history}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving chat history: {str(e)}")

@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """
    Clear a specific session's data
    """
    try:
        await get_orchestrator().clear_session(session_id)
        return {"message": f"Session {session_id} cleared successfully"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing session: {str(e)}")

@app.get("/database/stats")
async def get_database_stats():
    """
    Get database statistics (total properties, etc.)
    """
    try:
        stats = await get_database_service().get_database_stats()
        return stats
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving database stats: {str(e)}")

@app.post("/test-search")
async def test_search():
    """
    Test basic property search without AI
    """
    try:
        db_service = get_database_service()
        results = await db_service.search_properties({
            'prefecture': '東京',
            'price_max': 3000,
            'limit': 10  # 重複除去前により多く取得
        })
        # 重複除去処理
        results = remove_duplicate_properties(results)
        # 必要に応じて上位3件に制限
        results = results[:3]
        return {"message": "Search test successful", "results": results, "count": len(results)}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in test search: {str(e)}")

@app.post("/simple-chat")
async def simple_chat(chat_request: ChatMessage):
    """
    Simple chat without complex agents - for debugging
    """
    try:
        import httpx
        import json
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        
        # Direct HTTP call to OpenAI API
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "あなたは不動産検索アシスタントです。簡潔に回答してください。"},
                {"role": "user", "content": chat_request.message}
            ],
            "max_tokens": 150
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=data
            )
        
        if response.status_code == 200:
            result = response.json()
            return {
                "response": result["choices"][0]["message"]["content"],
                "session_id": "test_session",
                "recommendations": [],
                "is_final": False
            }
        else:
            return {
                "response": f"OpenAI API エラー: {response.status_code} - {response.text}",
                "session_id": "error_session",
                "recommendations": [],
                "is_final": False
            }
    
    except Exception as e:
        import traceback
        return {
            "response": f"エラーが発生しました: {str(e)}",
            "session_id": "error_session", 
            "recommendations": [],
            "is_final": False,
            "error_details": traceback.format_exc()
        }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=True
    )