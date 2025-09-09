import json
from typing import Dict, Any, List, Optional
from openai import OpenAI
import os
import re

from services.database_service import DatabaseService


class LocationAgent:
    """
    地域・場所特定専門エージェント
    日本全国の重複する駅名や地名を適切に特定する
    """
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.database_service = DatabaseService()
        
        # 都道府県リスト
        self.prefectures = [
            "北海道", "青森県", "岩手県", "宮城県", "秋田県", "山形県", "福島県",
            "茨城県", "栃木県", "群馬県", "埼玉県", "千葉県", "東京都", "神奈川県",
            "新潟県", "富山県", "石川県", "福井県", "山梨県", "長野県", "岐阜県",
            "静岡県", "愛知県", "三重県", "滋賀県", "京都府", "大阪府", "兵庫県",
            "奈良県", "和歌山県", "鳥取県", "島根県", "岡山県", "広島県", "山口県",
            "徳島県", "香川県", "愛媛県", "高知県", "福岡県", "佐賀県", "長崎県",
            "熊本県", "大分県", "宮崎県", "鹿児島県", "沖縄県"
        ]
    
    async def process_location_inquiry(self, message: str, current_requirements: Dict[str, Any]) -> Dict[str, Any]:
        """
        地域に関する問い合わせを処理し、曖昧さを解決する
        """
        try:
            # メッセージから地域情報を抽出
            extracted_locations = await self._extract_location_info(message)
            
            # データベースで該当する地域を検索
            location_matches = await self._find_location_matches(extracted_locations)
            
            # 曖昧さがある場合は確認を求める
            if self._has_ambiguity(location_matches):
                response = await self._generate_clarification_response(location_matches, extracted_locations)
                return {
                    "response": response,
                    "location_info": {},
                    "is_specific": False,
                    "candidates": location_matches
                }
            else:
                # 地域が特定できた場合
                confirmed_location = location_matches[0] if location_matches else {}
                response = await self._generate_confirmation_response(confirmed_location)
                
                return {
                    "response": response,
                    "location_info": confirmed_location,
                    "is_specific": True,
                    "candidates": []
                }
                
        except Exception as e:
            return {
                "response": "申し訳ございませんが、地域の特定中にエラーが発生しました。もう一度、希望の地域を教えていただけますでしょうか？",
                "location_info": {},
                "is_specific": False,
                "candidates": []
            }
    
    async def _extract_location_info(self, message: str) -> Dict[str, List[str]]:
        """
        メッセージから地域情報を抽出
        """
        try:
            prompt = f"""
            以下のメッセージから地域情報を抽出してください：

            メッセージ: "{message}"

            以下のJSON形式で抽出した情報を返してください：
            {{
                "prefectures": ["都道府県名"],
                "cities": ["市区町村名"],
                "stations": ["駅名"],
                "areas": ["地域名・エリア名"]
            }}

            例：
            - "新宿駅周辺" → {{"stations": ["新宿"], "areas": ["新宿周辺"]}}
            - "東京都渋谷区" → {{"prefectures": ["東京都"], "cities": ["渋谷区"]}}
            - "横浜の川崎駅近く" → {{"cities": ["横浜"], "stations": ["川崎"]}}
            """

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )

            result = json.loads(response.choices[0].message.content)
            return result

        except Exception as e:
            # フォールバック：正規表現による抽出
            return self._regex_extract_locations(message)
    
    def _regex_extract_locations(self, message: str) -> Dict[str, List[str]]:
        """
        正規表現を使用した地域情報抽出（フォールバック）
        """
        result = {
            "prefectures": [],
            "cities": [],
            "stations": [],
            "areas": []
        }
        
        # 都道府県の抽出
        for prefecture in self.prefectures:
            if prefecture in message:
                result["prefectures"].append(prefecture)
        
        # 駅名の抽出（〜駅パターン）
        station_pattern = r'([^「」\s]+)駅'
        stations = re.findall(station_pattern, message)
        result["stations"].extend(stations)
        
        # 市区町村の抽出
        city_pattern = r'([^「」\s]+[市区町村])'
        cities = re.findall(city_pattern, message)
        result["cities"].extend(cities)
        
        return result
    
    async def _find_location_matches(self, extracted_locations: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        """
        データベースで地域マッチングを実行
        """
        matches = []
        
        try:
            # 駅名での検索
            for station in extracted_locations.get("stations", []):
                station_matches = await self.database_service.find_stations_by_name(station)
                matches.extend(station_matches)
            
            # 市区町村での検索
            for city in extracted_locations.get("cities", []):
                city_matches = await self.database_service.find_locations_by_city(city)
                matches.extend(city_matches)
            
            # 都道府県での検索
            for prefecture in extracted_locations.get("prefectures", []):
                prefecture_matches = await self.database_service.find_locations_by_prefecture(prefecture)
                matches.extend(prefecture_matches)
            
            # 重複を除去
            unique_matches = []
            seen = set()
            for match in matches:
                key = f"{match.get('prefecture', '')}_{match.get('city', '')}_{match.get('station', '')}"
                if key not in seen:
                    seen.add(key)
                    unique_matches.append(match)
            
            return unique_matches
            
        except Exception as e:
            return []
    
    def _has_ambiguity(self, location_matches: List[Dict[str, Any]]) -> bool:
        """
        地域に曖昧さがあるかチェック
        """
        if len(location_matches) <= 1:
            return False
        
        # 同じ駅名で複数の都道府県にある場合は曖昧
        if len(location_matches) > 1:
            stations = set()
            prefectures = set()
            for match in location_matches:
                stations.add(match.get("station", ""))
                prefectures.add(match.get("prefecture", ""))
            
            # 同じ駅名が複数の都道府県にある場合
            if len(stations) == 1 and len(prefectures) > 1:
                return True
        
        return len(location_matches) > 3  # 候補が多すぎる場合も曖昧とする
    
    async def _generate_clarification_response(self, candidates: List[Dict[str, Any]], extracted_info: Dict[str, List[str]]) -> str:
        """
        曖昧な地域の明確化を求める応答を生成
        """
        if not candidates:
            return "申し訳ございませんが、該当する地域が見つかりませんでした。都道府県名から教えていただけますでしょうか？"
        
        # 駅名の重複がある場合
        stations = extracted_info.get("stations", [])
        if stations and len(candidates) > 1:
            station_name = stations[0]
            response = f"「{station_name}駅」は複数の地域にございます。以下のうち、どちらの地域をご希望でしょうか？\n\n"
            
            for i, candidate in enumerate(candidates[:5], 1):  # 最大5件まで表示
                prefecture = candidate.get("prefecture", "")
                city = candidate.get("city", "")
                station = candidate.get("station", "")
                
                location_str = f"{prefecture}"
                if city:
                    location_str += f" {city}"
                if station:
                    location_str += f" {station}駅"
                
                response += f"{i}. {location_str}\n"
            
            response += "\n番号または地域名で教えてください。"
            return response
        
        # その他の場合
        response = "以下の地域の候補がございます。どちらをご希望でしょうか？\n\n"
        for i, candidate in enumerate(candidates[:5], 1):
            prefecture = candidate.get("prefecture", "")
            city = candidate.get("city", "")
            response += f"{i}. {prefecture} {city}\n"
        
        response += "\n番号または詳細な地域名で教えてください。"
        return response
    
    async def _generate_confirmation_response(self, confirmed_location: Dict[str, Any]) -> str:
        """
        地域確定の確認応答を生成
        """
        if not confirmed_location:
            return "地域の特定ができませんでした。もう少し詳しく地域を教えていただけますでしょうか？"
        
        prefecture = confirmed_location.get("prefecture", "")
        city = confirmed_location.get("city", "")
        station = confirmed_location.get("station", "")
        
        location_str = prefecture
        if city:
            location_str += f" {city}"
        if station:
            location_str += f" {station}駅周辺"
        
        response = f"承知いたしました。{location_str}で物件をお探しですね。\n\n"
        response += "次に、ご希望の条件を教えてください。例えば：\n"
        response += "- 予算（家賃や購入価格）\n"
        response += "- 間取り（1K、1DK、2LDKなど）\n"
        response += "- 築年数\n"
        response += "- その他のご希望"
        
        return response