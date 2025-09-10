import asyncio
import json
import re
from typing import Dict, List, Tuple, Optional
import aiohttp
import math
from urllib.parse import quote

class LocationDisambiguationAgent:
    def __init__(self, google_maps_api_key: Optional[str] = None):
        """
        位置特定・曖昧さ解消エージェント
        
        Args:
            google_maps_api_key: Google Maps API キー（オプション）
        """
        self.google_maps_api_key = google_maps_api_key
        
    async def analyze_location_ambiguity(self, search_term: str, found_addresses: List[str]) -> Dict:
        """
        検索された住所の曖昧さを分析し、必要に応じて詳細な地域指定を求める
        
        Args:
            search_term: ユーザーが入力した検索語（例：「川崎」）
            found_addresses: 検索でヒットした住所のリスト
            
        Returns:
            Dict: 分析結果と推奨アクション
        """
        if not found_addresses:
            return {
                "needs_clarification": False,
                "message": None,
                "suggested_locations": []
            }
        
        # 住所から都道府県・市区町村を抽出
        location_groups = self._group_addresses_by_region(found_addresses)
        
        # 複数の都道府県にまたがる場合の処理
        if len(location_groups) > 1:
            return await self._handle_multiple_prefectures(search_term, location_groups)
        
        # 同一都道府県内での距離チェック
        if len(found_addresses) >= 5:  # 5件以上の場合に距離チェック
            distances = await self._calculate_distances(found_addresses[:10])  # 最大10件で計算
            
            if distances and self._has_distant_locations(distances):
                return await self._suggest_area_refinement(search_term, location_groups)
        
        return {
            "needs_clarification": False,
            "message": None,
            "suggested_locations": []
        }
    
    def _group_addresses_by_region(self, addresses: List[str]) -> Dict[str, List[str]]:
        """住所を都道府県・市区町村でグループ化"""
        groups = {}
        
        for address in addresses:
            # 都道府県と市区町村を抽出
            prefecture = self._extract_prefecture(address)
            city = self._extract_city(address)
            
            key = f"{prefecture}"
            if city:
                key += f" {city}"
            
            if key not in groups:
                groups[key] = []
            groups[key].append(address)
        
        return groups
    
    def _extract_prefecture(self, address: str) -> str:
        """住所から都道府県を抽出"""
        prefectures = [
            '北海道', '青森県', '岩手県', '宮城県', '秋田県', '山形県', '福島県',
            '茨城県', '栃木県', '群馬県', '埼玉県', '千葉県', '東京都', '神奈川県',
            '新潟県', '富山県', '石川県', '福井県', '山梨県', '長野県', '岐阜県',
            '静岡県', '愛知県', '三重県', '滋賀県', '京都府', '大阪府', '兵庫県',
            '奈良県', '和歌山県', '鳥取県', '島根県', '岡山県', '広島県', '山口県',
            '徳島県', '香川県', '愛媛県', '高知県', '福岡県', '佐賀県', '長崎県',
            '熊本県', '大分県', '宮崎県', '鹿児島県', '沖縄県'
        ]
        
        for pref in prefectures:
            if pref in address:
                return pref
        return "不明"
    
    def _extract_city(self, address: str) -> str:
        """住所から市区町村を抽出"""
        # 市区町村のパターンを検索
        city_patterns = [
            r'([^都道府県]*?[市区町村])',
            r'([^都道府県]*?郡[^市区町村]*?[町村])',
        ]
        
        for pattern in city_patterns:
            match = re.search(pattern, address)
            if match:
                return match.group(1)
        
        return ""
    
    async def _handle_multiple_prefectures(self, search_term: str, location_groups: Dict[str, List[str]]) -> Dict:
        """複数都道府県にまたがる場合の処理"""
        prefecture_list = []
        for region in location_groups.keys():
            pref = region.split()[0]  # 都道府県部分を取得
            if pref not in prefecture_list:
                prefecture_list.append(pref)
        
        if len(prefecture_list) > 1:
            suggestions = []
            for region, addresses in location_groups.items():
                count = len(addresses)
                suggestions.append(f"• {region}（{count}件）")
            
            message = f"「{search_term}」で複数の地域が見つかりました。より具体的な地域を教えてください。\n\n候補地域：\n" + "\n".join(suggestions)
            
            return {
                "needs_clarification": True,
                "message": message,
                "suggested_locations": list(location_groups.keys())
            }
        
        return {
            "needs_clarification": False,
            "message": None,
            "suggested_locations": []
        }
    
    async def _calculate_distances(self, addresses: List[str]) -> List[Tuple[str, str, float]]:
        """住所間の距離を計算（Google Maps API使用、なければ簡易計算）"""
        if not self.google_maps_api_key:
            return await self._calculate_distances_simple(addresses)
        
        try:
            # Google Maps APIを使用した正確な距離計算
            return await self._calculate_distances_with_api(addresses)
        except Exception as e:
            print(f"Google Maps API error: {e}")
            # フォールバック：簡易計算
            return await self._calculate_distances_simple(addresses)
    
    async def _calculate_distances_simple(self, addresses: List[str]) -> List[Tuple[str, str, float]]:
        """簡易距離計算（文字列ベース）"""
        distances = []
        
        # 簡易的に都道府県・市区町村レベルでの距離を推定
        for i, addr1 in enumerate(addresses):
            for j, addr2 in enumerate(addresses[i+1:], i+1):
                pref1 = self._extract_prefecture(addr1)
                pref2 = self._extract_prefecture(addr2)
                city1 = self._extract_city(addr1)
                city2 = self._extract_city(addr2)
                
                # 簡易距離推定
                if pref1 != pref2:
                    distance = 50.0  # 異なる都道府県なら50km以上と仮定
                elif city1 != city2:
                    distance = 20.0  # 異なる市区町村なら20km程度と仮定
                else:
                    distance = 5.0   # 同一市区町村なら5km程度と仮定
                
                distances.append((addr1, addr2, distance))
        
        return distances
    
    async def _calculate_distances_with_api(self, addresses: List[str]) -> List[Tuple[str, str, float]]:
        """Google Maps APIを使用した正確な距離計算"""
        distances = []
        
        async with aiohttp.ClientSession() as session:
            for i, addr1 in enumerate(addresses):
                for j, addr2 in enumerate(addresses[i+1:], i+1):
                    try:
                        distance = await self._get_distance_between_addresses(session, addr1, addr2)
                        distances.append((addr1, addr2, distance))
                    except Exception as e:
                        print(f"Distance calculation error for {addr1} - {addr2}: {e}")
                        # エラー時は簡易推定
                        distances.append((addr1, addr2, 10.0))
        
        return distances
    
    async def _get_distance_between_addresses(self, session: aiohttp.ClientSession, addr1: str, addr2: str) -> float:
        """2つの住所間の距離をGoogle Maps APIで取得"""
        if not self.google_maps_api_key:
            return 10.0  # デフォルト値
        
        url = "https://maps.googleapis.com/maps/api/distancematrix/json"
        params = {
            'origins': addr1,
            'destinations': addr2,
            'units': 'metric',
            'language': 'ja',
            'key': self.google_maps_api_key
        }
        
        async with session.get(url, params=params) as response:
            data = await response.json()
            
            if data['status'] == 'OK' and data['rows'][0]['elements'][0]['status'] == 'OK':
                distance_m = data['rows'][0]['elements'][0]['distance']['value']
                return distance_m / 1000.0  # kmに変換
            else:
                return 10.0  # エラー時のデフォルト値
    
    def _has_distant_locations(self, distances: List[Tuple[str, str, float]]) -> bool:
        """10km以上離れた物件が複数あるかチェック"""
        distant_pairs = [d for d in distances if d[2] > 10.0]
        return len(distant_pairs) >= 2  # 2組以上の遠距離ペアがある場合
    
    async def _suggest_area_refinement(self, search_term: str, location_groups: Dict[str, List[str]]) -> Dict:
        """エリア絞り込みの提案"""
        suggestions = []
        for region, addresses in location_groups.items():
            count = len(addresses)
            if count > 0:
                suggestions.append(f"• {region}（{count}件）")
        
        message = f"「{search_term}」で広範囲の物件が見つかりました（10km以上離れた物件が含まれています）。\n\nより具体的な地域名を教えてください：\n" + "\n".join(suggestions[:5])
        
        return {
            "needs_clarification": True,
            "message": message,
            "suggested_locations": list(location_groups.keys())[:5]
        }
    
    def extract_location_from_query(self, query: str) -> List[str]:
        """クエリから地名を抽出"""
        # 地名パターンの抽出
        location_patterns = [
            r'([^、。！？\s]*?[都道府県])',  # 都道府県
            r'([^、。！？\s]*?[市区町村])',  # 市区町村
            r'([^、。！？\s]*?郡[^、。！？\s]*?[町村])',  # 郡町村
            r'([ぁ-んァ-ヶー一-龠]{2,})',  # 一般的な地名（ひらがな・カタカナ・漢字）
        ]
        
        locations = []
        for pattern in location_patterns:
            matches = re.findall(pattern, query)
            for match in matches:
                if len(match) >= 2 and match not in locations:
                    locations.append(match)
        
        return locations