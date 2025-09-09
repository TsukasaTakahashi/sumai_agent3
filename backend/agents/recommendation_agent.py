import json
import math
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime
import re

from services.database_service import DatabaseService


class RecommendationAgent:
    """
    物件推薦専門エージェント
    ユーザーの条件や類似物件に基づいて最適な物件を推薦する
    """
    
    def __init__(self):
        self.database_service = DatabaseService()
        self.feature_weights = {
            "location": 0.25,      # エリア・駅からの距離
            "price": 0.20,         # 価格
            "layout": 0.15,        # 間取り
            "area": 0.15,          # 面積
            "age": 0.10,           # 築年数
            "walk_time": 0.10,     # 駅徒歩時間
            "commute_time": 0.05   # 通勤時間
        }
    
    async def find_matching_properties(self, requirements: Dict[str, Any], limit: int = 3) -> List[Dict[str, Any]]:
        """
        ユーザーの条件に基づいて物件を検索・推薦
        """
        try:
            # データベースから候補物件を取得
            candidate_properties = await self.database_service.search_properties(requirements)
            
            if not candidate_properties:
                return []
            
            # 類似度を計算して物件をスコアリング
            scored_properties = await self._calculate_similarity_scores(
                candidate_properties, requirements
            )
            
            # スコア順にソートして上位を返す
            sorted_properties = sorted(scored_properties, key=lambda x: x["similarity_score"], reverse=True)
            
            return await self._format_recommendations(sorted_properties[:limit], requirements)
            
        except Exception as e:
            print(f"Error in find_matching_properties: {str(e)}")
            return []
    
    async def find_similar_properties(self, reference_property: Dict[str, Any], limit: int = 3) -> List[Dict[str, Any]]:
        """
        参照物件（PDFから抽出）と類似する物件を検索
        """
        try:
            # 参照物件の特徴を正規化
            normalized_reference = self._normalize_property_features(reference_property)
            
            # データベースから全物件を取得（地域フィルタ適用）
            search_criteria = self._create_search_criteria_from_reference(normalized_reference)
            candidate_properties = await self.database_service.search_properties(search_criteria)
            
            if not candidate_properties:
                return []
            
            # 類似度計算
            scored_properties = await self._calculate_reference_similarity(
                candidate_properties, normalized_reference
            )
            
            # スコア順にソートして上位を返す
            sorted_properties = sorted(scored_properties, key=lambda x: x["similarity_score"], reverse=True)
            
            return await self._format_recommendations(sorted_properties[:limit], normalized_reference, is_reference=True)
            
        except Exception as e:
            print(f"Error in find_similar_properties: {str(e)}")
            return []
    
    async def _calculate_similarity_scores(self, properties: List[Dict[str, Any]], requirements: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        ユーザー条件に基づく類似度スコアを計算
        """
        scored_properties = []
        
        for property_data in properties:
            try:
                # 各軸での類似度を計算
                similarity_scores = {
                    "location": self._calculate_location_similarity(property_data, requirements),
                    "price": self._calculate_price_similarity(property_data, requirements),
                    "layout": self._calculate_layout_similarity(property_data, requirements),
                    "area": self._calculate_area_similarity(property_data, requirements),
                    "age": self._calculate_age_similarity(property_data, requirements),
                    "walk_time": self._calculate_walk_time_similarity(property_data, requirements),
                    "commute_time": self._calculate_commute_time_similarity(property_data, requirements)
                }
                
                # 重み付き総合スコアを計算
                total_score = sum(
                    similarity_scores[key] * self.feature_weights[key]
                    for key in similarity_scores.keys()
                )
                
                scored_property = property_data.copy()
                scored_property["similarity_score"] = total_score
                scored_property["detailed_scores"] = similarity_scores
                
                scored_properties.append(scored_property)
                
            except Exception as e:
                print(f"Error calculating similarity for property: {str(e)}")
                continue
        
        return scored_properties
    
    async def _calculate_reference_similarity(self, properties: List[Dict[str, Any]], reference: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        参照物件との類似度スコアを計算
        """
        scored_properties = []
        
        for property_data in properties:
            try:
                # 各軸での類似度を計算
                similarity_scores = {
                    "location": self._calculate_location_similarity_reference(property_data, reference),
                    "price": self._calculate_price_similarity_reference(property_data, reference),
                    "layout": self._calculate_layout_similarity_reference(property_data, reference),
                    "area": self._calculate_area_similarity_reference(property_data, reference),
                    "age": self._calculate_age_similarity_reference(property_data, reference),
                    "walk_time": self._calculate_walk_time_similarity_reference(property_data, reference),
                    "commute_time": 0.5  # 通勤時間は参照物件では計算困難
                }
                
                # 重み付き総合スコアを計算
                total_score = sum(
                    similarity_scores[key] * self.feature_weights[key]
                    for key in similarity_scores.keys()
                )
                
                scored_property = property_data.copy()
                scored_property["similarity_score"] = total_score
                scored_property["detailed_scores"] = similarity_scores
                
                scored_properties.append(scored_property)
                
            except Exception as e:
                print(f"Error calculating reference similarity: {str(e)}")
                continue
        
        return scored_properties
    
    def _calculate_location_similarity(self, property_data: Dict[str, Any], requirements: Dict[str, Any]) -> float:
        """
        地域・場所の類似度を計算
        """
        try:
            prop_prefecture = property_data.get("prefecture", "")
            prop_city = property_data.get("city", "")
            prop_station = property_data.get("station_name", "")
            
            req_prefecture = requirements.get("prefecture", "")
            req_city = requirements.get("city", "")
            req_station = requirements.get("station", "")
            
            score = 0.0
            
            # 都道府県マッチ
            if req_prefecture and prop_prefecture == req_prefecture:
                score += 0.4
            
            # 市区町村マッチ
            if req_city and prop_city == req_city:
                score += 0.4
            
            # 駅マッチ
            if req_station and prop_station == req_station:
                score += 0.8
            elif req_station and req_station in prop_station:
                score += 0.6
            
            return min(score, 1.0)
            
        except Exception:
            return 0.5
    
    def _calculate_price_similarity(self, property_data: Dict[str, Any], requirements: Dict[str, Any]) -> float:
        """
        価格の類似度を計算（±10%の範囲で評価）
        """
        try:
            prop_price = float(property_data.get("price", 0))
            if prop_price <= 0:
                return 0.5
            
            # 価格範囲の取得
            price_min = requirements.get("price_min")
            price_max = requirements.get("price_max")
            
            if price_min is None and price_max is None:
                return 0.5
            
            if price_min and price_max:
                # 範囲指定の場合
                if price_min <= prop_price <= price_max:
                    return 1.0
                else:
                    # 範囲外の場合、距離に基づいてスコア計算
                    if prop_price < price_min:
                        diff_ratio = (price_min - prop_price) / price_min
                    else:
                        diff_ratio = (prop_price - price_max) / price_max
                    
                    return max(0.0, 1.0 - diff_ratio)
            
            elif price_max:
                # 上限のみの場合
                if prop_price <= price_max:
                    return 1.0
                else:
                    diff_ratio = (prop_price - price_max) / price_max
                    return max(0.0, 1.0 - diff_ratio)
            
            elif price_min:
                # 下限のみの場合
                if prop_price >= price_min:
                    return 1.0
                else:
                    diff_ratio = (price_min - prop_price) / price_min
                    return max(0.0, 1.0 - diff_ratio)
            
            return 0.5
            
        except Exception:
            return 0.5
    
    def _calculate_layout_similarity(self, property_data: Dict[str, Any], requirements: Dict[str, Any]) -> float:
        """
        間取りの類似度を計算
        """
        try:
            prop_layout = str(property_data.get("layout", "")).upper()
            req_layout = requirements.get("layout", "")
            
            if not req_layout:
                return 0.5
            
            req_layout = str(req_layout).upper()
            
            # 完全一致
            if prop_layout == req_layout:
                return 1.0
            
            # 複数候補の場合
            if "," in req_layout:
                req_layouts = [l.strip() for l in req_layout.split(",")]
                if prop_layout in req_layouts:
                    return 1.0
            
            # "以上"の場合の処理
            if "+" in req_layout:
                base_layout = req_layout.replace("+", "")
                base_rooms = self._extract_room_count(base_layout)
                prop_rooms = self._extract_room_count(prop_layout)
                
                if prop_rooms >= base_rooms:
                    return 1.0
                else:
                    return max(0.0, 1.0 - (base_rooms - prop_rooms) * 0.3)
            
            # 部屋数での近似マッチ
            req_rooms = self._extract_room_count(req_layout)
            prop_rooms = self._extract_room_count(prop_layout)
            
            if req_rooms == prop_rooms:
                return 0.8
            elif abs(req_rooms - prop_rooms) == 1:
                return 0.6
            else:
                return 0.3
            
        except Exception:
            return 0.5
    
    def _extract_room_count(self, layout: str) -> int:
        """
        間取りから部屋数を抽出
        """
        try:
            match = re.search(r'(\d+)', layout)
            return int(match.group(1)) if match else 0
        except:
            return 0
    
    def _calculate_area_similarity(self, property_data: Dict[str, Any], requirements: Dict[str, Any]) -> float:
        """
        面積の類似度を計算
        """
        try:
            prop_area = float(property_data.get("area", 0))
            if prop_area <= 0:
                return 0.5
            
            area_min = requirements.get("area_min")
            area_max = requirements.get("area_max")
            
            if area_min is None and area_max is None:
                return 0.5
            
            if area_min and area_max:
                if area_min <= prop_area <= area_max:
                    return 1.0
                else:
                    if prop_area < area_min:
                        diff_ratio = (area_min - prop_area) / area_min
                    else:
                        diff_ratio = (prop_area - area_max) / area_max
                    
                    return max(0.0, 1.0 - diff_ratio)
            
            elif area_max:
                if prop_area <= area_max:
                    return 1.0
                else:
                    diff_ratio = (prop_area - area_max) / area_max
                    return max(0.0, 1.0 - diff_ratio * 0.5)
            
            elif area_min:
                if prop_area >= area_min:
                    return 1.0
                else:
                    diff_ratio = (area_min - prop_area) / area_min
                    return max(0.0, 1.0 - diff_ratio)
            
            return 0.5
            
        except Exception:
            return 0.5
    
    def _calculate_age_similarity(self, property_data: Dict[str, Any], requirements: Dict[str, Any]) -> float:
        """
        築年数の類似度を計算
        """
        try:
            prop_age = float(property_data.get("age", 0))
            age_max = requirements.get("age_max")
            
            if age_max is None:
                return 0.5
            
            if prop_age <= age_max:
                return 1.0
            else:
                # 超過した場合のペナルティ
                excess_ratio = (prop_age - age_max) / age_max
                return max(0.0, 1.0 - excess_ratio)
            
        except Exception:
            return 0.5
    
    def _calculate_walk_time_similarity(self, property_data: Dict[str, Any], requirements: Dict[str, Any]) -> float:
        """
        駅徒歩時間の類似度を計算
        """
        try:
            prop_walk_time = float(property_data.get("walk_time", 999))
            walk_time_max = requirements.get("walk_time_max")
            
            if walk_time_max is None:
                return 0.5
            
            if prop_walk_time <= walk_time_max:
                return 1.0
            else:
                excess_ratio = (prop_walk_time - walk_time_max) / walk_time_max
                return max(0.0, 1.0 - excess_ratio)
            
        except Exception:
            return 0.5
    
    def _calculate_commute_time_similarity(self, property_data: Dict[str, Any], requirements: Dict[str, Any]) -> float:
        """
        通勤時間の類似度を計算（簡易実装）
        """
        try:
            commute_location = requirements.get("commute_location")
            commute_time_max = requirements.get("commute_time_max")
            
            if not commute_location or not commute_time_max:
                return 0.5
            
            # 実際の実装では地図APIを使用して通勤時間を計算
            # ここでは簡易的に同一市区町村かどうかで判定
            prop_city = property_data.get("city", "")
            if commute_location in prop_city or prop_city in commute_location:
                return 1.0
            else:
                return 0.3
            
        except Exception:
            return 0.5
    
    # 参照物件用の類似度計算メソッド群
    def _calculate_location_similarity_reference(self, property_data: Dict[str, Any], reference: Dict[str, Any]) -> float:
        """参照物件との地域類似度"""
        try:
            prop_prefecture = property_data.get("prefecture", "")
            prop_city = property_data.get("city", "")
            
            ref_prefecture = reference.get("prefecture", "")
            ref_city = reference.get("city", "")
            
            score = 0.0
            if ref_prefecture and prop_prefecture == ref_prefecture:
                score += 0.5
            if ref_city and prop_city == ref_city:
                score += 0.5
            
            return score
        except:
            return 0.5
    
    def _calculate_price_similarity_reference(self, property_data: Dict[str, Any], reference: Dict[str, Any]) -> float:
        """参照物件との価格類似度（±10%）"""
        try:
            prop_price = float(property_data.get("price", 0))
            ref_price = float(reference.get("price", 0))
            
            if prop_price <= 0 or ref_price <= 0:
                return 0.5
            
            diff_ratio = abs(prop_price - ref_price) / ref_price
            if diff_ratio <= 0.1:  # ±10%
                return 1.0
            else:
                return max(0.0, 1.0 - diff_ratio)
        except:
            return 0.5
    
    def _calculate_layout_similarity_reference(self, property_data: Dict[str, Any], reference: Dict[str, Any]) -> float:
        """参照物件との間取り類似度"""
        try:
            prop_layout = str(property_data.get("layout", "")).upper()
            ref_layout = str(reference.get("layout", "")).upper()
            
            if prop_layout == ref_layout:
                return 1.0
            
            prop_rooms = self._extract_room_count(prop_layout)
            ref_rooms = self._extract_room_count(ref_layout)
            
            if prop_rooms == ref_rooms:
                return 0.8
            elif abs(prop_rooms - ref_rooms) == 1:
                return 0.6
            else:
                return 0.3
        except:
            return 0.5
    
    def _calculate_area_similarity_reference(self, property_data: Dict[str, Any], reference: Dict[str, Any]) -> float:
        """参照物件との面積類似度"""
        try:
            prop_area = float(property_data.get("area", 0))
            ref_area = float(reference.get("area", 0))
            
            if prop_area <= 0 or ref_area <= 0:
                return 0.5
            
            diff_ratio = abs(prop_area - ref_area) / ref_area
            if diff_ratio <= 0.2:  # ±20%
                return 1.0
            else:
                return max(0.0, 1.0 - diff_ratio)
        except:
            return 0.5
    
    def _calculate_age_similarity_reference(self, property_data: Dict[str, Any], reference: Dict[str, Any]) -> float:
        """参照物件との築年数類似度"""
        try:
            prop_age = float(property_data.get("age", 0))
            ref_age = float(reference.get("age", 0))
            
            diff_years = abs(prop_age - ref_age)
            if diff_years <= 5:
                return 1.0
            else:
                return max(0.0, 1.0 - diff_years / 30)
        except:
            return 0.5
    
    def _calculate_walk_time_similarity_reference(self, property_data: Dict[str, Any], reference: Dict[str, Any]) -> float:
        """参照物件との徒歩時間類似度"""
        try:
            prop_walk = float(property_data.get("walk_time", 999))
            ref_walk = float(reference.get("walk_time", 999))
            
            diff_time = abs(prop_walk - ref_walk)
            if diff_time <= 3:
                return 1.0
            else:
                return max(0.0, 1.0 - diff_time / 15)
        except:
            return 0.5
    
    def _normalize_property_features(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        物件特徴を正規化
        """
        normalized = {}
        
        # 基本情報
        normalized["prefecture"] = property_data.get("prefecture", "")
        normalized["city"] = property_data.get("city", "")
        normalized["station"] = property_data.get("station", "")
        
        # 価格（万円単位に変換）
        price = property_data.get("price", 0)
        if isinstance(price, str):
            price_match = re.search(r'(\d+(?:\.\d+)?)', price)
            price = float(price_match.group(1)) if price_match else 0
        normalized["price"] = float(price)
        
        # 面積
        area = property_data.get("area", 0)
        if isinstance(area, str):
            area_match = re.search(r'(\d+(?:\.\d+)?)', area)
            area = float(area_match.group(1)) if area_match else 0
        normalized["area"] = float(area)
        
        # 間取り
        normalized["layout"] = str(property_data.get("layout", ""))
        
        # 築年数
        age = property_data.get("age", 0)
        if isinstance(age, str):
            age_match = re.search(r'(\d+)', age)
            age = int(age_match.group(1)) if age_match else 0
        normalized["age"] = int(age)
        
        # 徒歩時間
        walk_time = property_data.get("walk_time", 999)
        if isinstance(walk_time, str):
            walk_match = re.search(r'(\d+)', walk_time)
            walk_time = int(walk_match.group(1)) if walk_match else 999
        normalized["walk_time"] = int(walk_time)
        
        return normalized
    
    def _create_search_criteria_from_reference(self, reference: Dict[str, Any]) -> Dict[str, Any]:
        """
        参照物件から検索条件を作成
        """
        criteria = {}
        
        # 地域条件
        if reference.get("prefecture"):
            criteria["prefecture"] = reference["prefecture"]
        if reference.get("city"):
            criteria["city"] = reference["city"]
        
        # 価格条件（±20%の範囲）
        if reference.get("price") and reference["price"] > 0:
            price = reference["price"]
            criteria["price_min"] = price * 0.8
            criteria["price_max"] = price * 1.2
        
        return criteria
    
    async def _format_recommendations(self, scored_properties: List[Dict[str, Any]], requirements: Dict[str, Any], is_reference: bool = False) -> List[Dict[str, Any]]:
        """
        推薦結果をフォーマット
        """
        recommendations = []
        
        for prop in scored_properties:
            try:
                # 基本情報
                recommendation = {
                    "id": prop.get("id"),
                    "address": prop.get("address", ""),
                    "prefecture": prop.get("prefecture", ""),
                    "city": prop.get("city", ""),
                    "station_name": prop.get("station_name", ""),
                    "price": prop.get("price", ""),
                    "layout": prop.get("layout", ""),
                    "area": prop.get("area", ""),
                    "age": prop.get("age", ""),
                    "walk_time": prop.get("walk_time", ""),
                    "url": prop.get("url", ""),
                    "similarity_score": round(prop.get("similarity_score", 0), 3),
                    "recommendation_reason": await self._generate_recommendation_reason(prop, requirements, is_reference)
                }
                
                # 詳細スコア（デバッグ用）
                if "detailed_scores" in prop:
                    recommendation["detailed_scores"] = {
                        k: round(v, 3) for k, v in prop["detailed_scores"].items()
                    }
                
                recommendations.append(recommendation)
                
            except Exception as e:
                print(f"Error formatting recommendation: {str(e)}")
                continue
        
        return recommendations
    
    async def _generate_recommendation_reason(self, property_data: Dict[str, Any], requirements: Dict[str, Any], is_reference: bool = False) -> str:
        """
        推薦理由を生成
        """
        try:
            reasons = []
            detailed_scores = property_data.get("detailed_scores", {})
            
            # 高スコアの要素を理由として抽出
            if detailed_scores.get("location", 0) > 0.7:
                reasons.append("希望地域にマッチ")
            
            if detailed_scores.get("price", 0) > 0.8:
                reasons.append("予算内で好条件")
            
            if detailed_scores.get("layout", 0) > 0.8:
                reasons.append("希望の間取り")
            
            if detailed_scores.get("age", 0) > 0.8:
                reasons.append("築年数が希望に合致")
            
            if detailed_scores.get("walk_time", 0) > 0.8:
                reasons.append("駅から近い")
            
            if is_reference:
                reasons.append("アップロードされた物件と類似")
            
            return "、".join(reasons) if reasons else "総合的におすすめ"
            
        except Exception:
            return "おすすめ物件"