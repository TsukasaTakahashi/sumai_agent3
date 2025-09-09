import json
import re
from typing import Dict, Any, List, Optional
from openai import OpenAI
import os


class PropertyAnalysisAgent:
    """
    物件条件分析専門エージェント
    ユーザーの要望から具体的な物件検索条件を抽出・分析する
    """
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    async def extract_requirements(self, message: str, current_requirements: Dict[str, Any]) -> Dict[str, Any]:
        """
        ユーザーメッセージから物件条件を抽出
        """
        try:
            # LLMを使用して条件を抽出
            extracted_requirements = await self._llm_extract_requirements(message, current_requirements)
            
            # 抽出された条件を正規化
            normalized_requirements = self._normalize_requirements(extracted_requirements)
            
            # 現在の条件とマージ
            merged_requirements = {**current_requirements, **normalized_requirements}
            
            # 応答メッセージを生成
            response_message = await self._generate_requirements_response(
                normalized_requirements, merged_requirements
            )
            
            return {
                "requirements": normalized_requirements,
                "response": response_message,
                "all_requirements": merged_requirements
            }
            
        except Exception as e:
            # フォールバック：正規表現ベースの抽出
            fallback_requirements = self._regex_extract_requirements(message)
            
            return {
                "requirements": fallback_requirements,
                "response": "条件を承りました。他にもご希望がございましたら教えてください。",
                "all_requirements": {**current_requirements, **fallback_requirements}
            }
    
    async def _llm_extract_requirements(self, message: str, current_requirements: Dict[str, Any]) -> Dict[str, Any]:
        """
        LLMを使用して物件条件を抽出
        """
        prompt = f"""
        以下のユーザーメッセージから不動産物件の検索条件を抽出してください。

        ユーザーのメッセージ: "{message}"
        
        現在の条件: {json.dumps(current_requirements, ensure_ascii=False)}

        以下のJSON形式で抽出した条件を返してください：
        {{
            "price_min": null,  // 最低価格（万円単位の数値）
            "price_max": null,  // 最高価格（万円単位の数値）
            "layout": null,     // 間取り（"1K", "1DK", "2LDK"など）
            "area_min": null,   // 最低面積（平方メートル）
            "area_max": null,   // 最高面積（平方メートル）
            "age_max": null,    // 最大築年数（年）
            "walk_time_max": null, // 駅徒歩最大時間（分）
            "commute_location": null, // 通勤先
            "commute_time_max": null, // 通勤時間上限（分）
            "property_type": null,    // 物件タイプ（"マンション", "アパート", "一戸建て"など）
            "features": []      // その他の特徴（["バス・トイレ別", "駐車場付き"など]）
        }}

        価格の抽出例：
        - "10万円以下" → price_max: 10
        - "15万円から20万円" → price_min: 15, price_max: 20
        - "予算は3000万円まで" → price_max: 3000

        間取りの抽出例：
        - "1Kか1DK" → layout: "1K,1DK"
        - "2LDK以上" → layout: "2LDK+"

        nullの場合は条件が指定されていないことを意味します。
        """

        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )

        result = json.loads(response.choices[0].message.content)
        return result
    
    def _regex_extract_requirements(self, message: str) -> Dict[str, Any]:
        """
        正規表現を使用した条件抽出（フォールバック）
        """
        requirements = {}
        
        # 価格抽出
        price_patterns = [
            r'(\d+)万円以下',
            r'(\d+)万円まで',
            r'予算.*?(\d+)万',
            r'(\d+)万.*?以下'
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, message)
            if match:
                requirements["price_max"] = int(match.group(1))
                break
        
        # 価格範囲抽出
        range_pattern = r'(\d+)万.*?(\d+)万'
        range_match = re.search(range_pattern, message)
        if range_match:
            requirements["price_min"] = int(range_match.group(1))
            requirements["price_max"] = int(range_match.group(2))
        
        # 間取り抽出
        layout_patterns = [
            r'([1-9][SLDK]+)',
            r'([1-9]室)',
            r'([1-9]部屋)'
        ]
        
        for pattern in layout_patterns:
            match = re.search(pattern, message)
            if match:
                requirements["layout"] = match.group(1)
                break
        
        # 築年数抽出
        age_patterns = [
            r'築(\d+)年以内',
            r'築(\d+)年まで',
            r'築浅'
        ]
        
        for pattern in age_patterns:
            match = re.search(pattern, message)
            if match:
                if pattern == r'築浅':
                    requirements["age_max"] = 10
                else:
                    requirements["age_max"] = int(match.group(1))
                break
        
        # 徒歩時間抽出
        walk_patterns = [
            r'徒歩(\d+)分以内',
            r'駅.*?(\d+)分',
            r'徒歩(\d+)分圏内'
        ]
        
        for pattern in walk_patterns:
            match = re.search(pattern, message)
            if match:
                requirements["walk_time_max"] = int(match.group(1))
                break
        
        return requirements
    
    def _normalize_requirements(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """
        抽出された条件を正規化
        """
        normalized = {}
        
        for key, value in requirements.items():
            if value is None:
                continue
                
            if key in ["price_min", "price_max"]:
                # 価格の正規化
                if isinstance(value, (int, float)):
                    normalized[key] = float(value)
                elif isinstance(value, str):
                    # 文字列から数値を抽出
                    price_match = re.search(r'(\d+)', str(value))
                    if price_match:
                        normalized[key] = float(price_match.group(1))
            
            elif key in ["area_min", "area_max"]:
                # 面積の正規化
                if isinstance(value, (int, float)):
                    normalized[key] = float(value)
                elif isinstance(value, str):
                    area_match = re.search(r'(\d+(?:\.\d+)?)', str(value))
                    if area_match:
                        normalized[key] = float(area_match.group(1))
            
            elif key in ["age_max", "walk_time_max", "commute_time_max"]:
                # 整数値の正規化
                if isinstance(value, (int, float)):
                    normalized[key] = int(value)
                elif isinstance(value, str):
                    num_match = re.search(r'(\d+)', str(value))
                    if num_match:
                        normalized[key] = int(num_match.group(1))
            
            elif key == "layout":
                # 間取りの正規化
                if isinstance(value, str) and value.strip():
                    normalized[key] = value.strip()
            
            elif key == "features":
                # 特徴の正規化
                if isinstance(value, list):
                    normalized[key] = [str(item).strip() for item in value if str(item).strip()]
                elif isinstance(value, str) and value.strip():
                    normalized[key] = [value.strip()]
            
            else:
                # その他の条件
                if isinstance(value, str) and value.strip():
                    normalized[key] = value.strip()
                elif value:
                    normalized[key] = value
        
        return normalized
    
    async def _generate_requirements_response(self, new_requirements: Dict[str, Any], all_requirements: Dict[str, Any]) -> str:
        """
        条件抽出結果に対する応答メッセージを生成
        """
        if not new_requirements:
            return "追加の条件があれば教えてください。現在の条件で物件を検索することも可能です。"
        
        try:
            prompt = f"""
            ユーザーから新しく抽出された物件条件に対して、自然で親しみやすい確認・応答メッセージを生成してください。

            新しく抽出された条件:
            {json.dumps(new_requirements, ensure_ascii=False)}

            全体の条件:
            {json.dumps(all_requirements, ensure_ascii=False)}

            以下の要素を含めてください：
            1. 新しい条件の確認
            2. 現在の条件のまとめ
            3. 次のアクションの提案（追加条件の確認または検索実行）

            親しみやすく、自然な日本語で100文字程度で回答してください。
            """

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )

            return response.choices[0].message.content

        except Exception as e:
            # フォールバック応答
            conditions_summary = []
            if new_requirements.get("price_max"):
                conditions_summary.append(f"予算{new_requirements['price_max']}万円以下")
            if new_requirements.get("layout"):
                conditions_summary.append(f"間取り{new_requirements['layout']}")
            if new_requirements.get("age_max"):
                conditions_summary.append(f"築{new_requirements['age_max']}年以内")
            
            if conditions_summary:
                return f"承知いたしました。{', '.join(conditions_summary)}でお探しですね。他にもご希望がございましたら教えてください。"
            else:
                return "条件を承りました。他にもご希望がございましたら教えてください。"