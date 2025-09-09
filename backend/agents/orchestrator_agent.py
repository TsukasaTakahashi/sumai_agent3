import json
import uuid
from typing import Dict, Any, List, Optional
from openai import OpenAI
import os
from datetime import datetime

from .location_agent import LocationAgent
from .property_analysis_agent import PropertyAnalysisAgent
from .recommendation_agent import RecommendationAgent
from services.database_service import DatabaseService


class OrchestratorAgent:
    """
    統括エージェント：各専門エージェントを調整し、ユーザーとの対話を管理する
    """
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.sessions: Dict[str, Dict] = {}
        
        # 専門エージェントを初期化
        self.location_agent = LocationAgent()
        self.property_analysis_agent = PropertyAnalysisAgent()
        self.recommendation_agent = RecommendationAgent()
        self.database_service = DatabaseService()
    
    async def process_message(self, message: str, session_id: Optional[str] = None, recommendation_count: int = 3) -> Dict[str, Any]:
        """
        ユーザーメッセージを処理し、適切なエージェントに振り分ける
        """
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # セッション情報を初期化または取得
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "chat_history": [],
                "user_requirements": {},
                "location_confirmed": False,
                "ready_for_search": False
            }
        
        session_data = self.sessions[session_id]
        session_data["chat_history"].append({"role": "user", "content": message, "timestamp": datetime.now().isoformat()})
        
        # メッセージの意図を分析
        intent = await self._analyze_intent(message, session_data)
        
        # 意図に基づいて適切なエージェントに振り分け
        if intent["type"] == "location_inquiry":
            response = await self._handle_location_inquiry(message, session_data)
        elif intent["type"] == "property_requirements":
            response = await self._handle_property_requirements(message, session_data)
        elif intent["type"] == "search_request":
            response = await self._handle_search_request(session_data, recommendation_count)
        else:
            response = await self._handle_general_inquiry(message, session_data)
        
        session_data["chat_history"].append({"role": "assistant", "content": response["response"], "timestamp": datetime.now().isoformat()})
        
        return {
            "response": response["response"],
            "session_id": session_id,
            "recommendations": response.get("recommendations"),
            "is_final": response.get("is_final", False)
        }
    
    async def process_pdf_info(self, extracted_info: Dict[str, Any], session_id: Optional[str] = None, recommendation_count: int = 3) -> Dict[str, Any]:
        """
        PDFから抽出された物件情報を基に類似物件を検索
        """
        if not session_id:
            session_id = str(uuid.uuid4())
        
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "chat_history": [],
                "user_requirements": {},
                "location_confirmed": False,
                "ready_for_search": False
            }
        
        session_data = self.sessions[session_id]
        
        # PDFから抽出された情報をユーザー要件として設定
        session_data["user_requirements"].update(extracted_info)
        session_data["location_confirmed"] = True
        session_data["ready_for_search"] = True
        
        # 類似物件を検索
        recommendations = await self.recommendation_agent.find_similar_properties(
            extracted_info, recommendation_count
        )
        
        response_message = f"アップロードされたPDFから物件情報を分析しました。\n\n"
        response_message += f"抽出された条件に基づいて、{len(recommendations)}件の類似物件をおすすめします。"
        
        session_data["chat_history"].append({
            "role": "assistant", 
            "content": response_message, 
            "timestamp": datetime.now().isoformat(),
            "recommendations": recommendations
        })
        
        return {
            "response": response_message,
            "session_id": session_id,
            "recommendations": recommendations,
            "is_final": True
        }
    
    async def _analyze_intent(self, message: str, session_data: Dict) -> Dict[str, Any]:
        """
        ユーザーメッセージの意図を分析
        """
        try:
            prompt = f"""
            ユーザーの発言の意図を分析して、以下のカテゴリのいずれかに分類してください：

            1. location_inquiry: 地域・駅・住所に関する質問や要望
            2. property_requirements: 物件の条件（価格、広さ、間取り、築年数など）に関する要望
            3. search_request: 物件検索の実行を求める発言
            4. general_inquiry: その他の一般的な質問や挨拶

            現在のセッション情報:
            - チャット履歴: {json.dumps(session_data.get("chat_history", []), ensure_ascii=False)}
            - ユーザー要件: {json.dumps(session_data.get("user_requirements", {}), ensure_ascii=False)}
            - 地域確定: {session_data.get("location_confirmed", False)}

            ユーザーの発言: "{message}"

            以下のJSON形式で回答してください：
            {{
                "type": "カテゴリ名",
                "confidence": 0.8,
                "extracted_info": {{
                    "key": "value"
                }}
            }}
            """

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )

            result = json.loads(response.choices[0].message.content)
            return result

        except Exception as e:
            # フォールバック：キーワードベースの分類
            message_lower = message.lower()
            if any(keyword in message_lower for keyword in ["駅", "区", "市", "県", "地域", "場所", "住所"]):
                return {"type": "location_inquiry", "confidence": 0.6}
            elif any(keyword in message_lower for keyword in ["円", "万", "価格", "家賃", "間取り", "広さ", "築年数"]):
                return {"type": "property_requirements", "confidence": 0.6}
            elif any(keyword in message_lower for keyword in ["検索", "探して", "見つけて", "おすすめ", "物件"]):
                return {"type": "search_request", "confidence": 0.6}
            else:
                return {"type": "general_inquiry", "confidence": 0.5}
    
    async def _handle_location_inquiry(self, message: str, session_data: Dict) -> Dict[str, Any]:
        """
        地域・場所に関する問い合わせを処理
        """
        location_result = await self.location_agent.process_location_inquiry(message, session_data.get("user_requirements", {}))
        
        # ユーザー要件を更新
        if location_result.get("location_info"):
            session_data["user_requirements"].update(location_result["location_info"])
        
        # 地域が十分に特定されたかチェック
        if location_result.get("is_specific"):
            session_data["location_confirmed"] = True
        
        return {
            "response": location_result["response"],
            "is_final": False
        }
    
    async def _handle_property_requirements(self, message: str, session_data: Dict) -> Dict[str, Any]:
        """
        物件条件に関する要望を処理
        """
        requirements_result = await self.property_analysis_agent.extract_requirements(message, session_data.get("user_requirements", {}))
        
        # ユーザー要件を更新
        session_data["user_requirements"].update(requirements_result.get("requirements", {}))
        
        # 検索準備完了をチェック
        if self._is_ready_for_search(session_data):
            session_data["ready_for_search"] = True
            response_text = requirements_result["response"] + "\n\n条件が揃いましたので、物件を検索いたします。"
        else:
            response_text = requirements_result["response"]
        
        return {
            "response": response_text,
            "is_final": False
        }
    
    async def _handle_search_request(self, session_data: Dict, recommendation_count: int) -> Dict[str, Any]:
        """
        物件検索リクエストを処理
        """
        if not self._is_ready_for_search(session_data):
            missing_info = []
            if not session_data.get("location_confirmed"):
                missing_info.append("地域・場所の詳細")
            
            return {
                "response": f"検索に必要な情報が不足しています。以下の情報を教えてください：\n- {', '.join(missing_info)}",
                "is_final": False
            }
        
        # 物件検索を実行
        recommendations = await self.recommendation_agent.find_matching_properties(
            session_data["user_requirements"], recommendation_count
        )
        
        response_message = f"ご希望の条件で物件を検索しました。{len(recommendations)}件のおすすめ物件をご紹介します。"
        
        return {
            "response": response_message,
            "recommendations": recommendations,
            "is_final": True
        }
    
    async def _handle_general_inquiry(self, message: str, session_data: Dict) -> Dict[str, Any]:
        """
        一般的な問い合わせを処理
        """
        try:
            prompt = f"""
            あなたは不動産物件検索アシスタントです。ユーザーとの自然な会話を心がけ、
            物件検索に必要な情報（地域、価格、間取り、条件など）を段階的に聞き出してください。

            現在のユーザー情報:
            {json.dumps(session_data.get("user_requirements", {}), ensure_ascii=False)}

            ユーザーの発言: "{message}"

            親しみやすく、的確に回答してください。
            """

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )

            return {
                "response": response.choices[0].message.content,
                "is_final": False
            }

        except Exception as e:
            return {
                "response": "申し訳ございませんが、お手伝いできるよう準備を整えております。どちらの地域で物件をお探しでしょうか？",
                "is_final": False
            }
    
    def _is_ready_for_search(self, session_data: Dict) -> bool:
        """
        検索実行準備が完了しているかチェック
        """
        requirements = session_data.get("user_requirements", {})
        return (
            session_data.get("location_confirmed", False) and
            len(requirements) >= 2  # 場所以外に最低1つの条件が必要
        )
    
    async def get_session_history(self, session_id: str) -> List[Dict]:
        """
        セッション履歴を取得
        """
        if session_id in self.sessions:
            return self.sessions[session_id].get("chat_history", [])
        return []
    
    async def clear_session(self, session_id: str) -> None:
        """
        セッションをクリア
        """
        if session_id in self.sessions:
            del self.sessions[session_id]