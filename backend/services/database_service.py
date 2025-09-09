import sqlite3
import os
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json


class DatabaseService:
    """
    SQLiteデータベース操作サービス
    不動産物件データの検索・取得を担当
    """
    
    def __init__(self):
        self.db_path = os.getenv("DATABASE_PATH", "./data/db/properties.db")
        self.executor = ThreadPoolExecutor(max_workers=5)
        
        # データベーススキーマの確認・作成
        asyncio.create_task(self._ensure_database_schema())
    
    async def _ensure_database_schema(self):
        """
        データベーススキーマが存在するか確認し、必要に応じて作成
        """
        try:
            await self._execute_async(self._create_schema_if_not_exists)
        except Exception as e:
            print(f"Database schema initialization error: {str(e)}")
    
    def _create_schema_if_not_exists(self):
        """
        データベーススキーマを作成（存在しない場合）
        """
        # データベースディレクトリが存在しない場合は作成
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 物件テーブルのスキーマを作成
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS properties (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT,
                    prefecture TEXT,
                    city TEXT,
                    station_name TEXT,
                    walk_time INTEGER,
                    price REAL,
                    layout TEXT,
                    area REAL,
                    age INTEGER,
                    property_type TEXT,
                    url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # インデックスの作成
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_prefecture ON properties(prefecture)",
                "CREATE INDEX IF NOT EXISTS idx_city ON properties(city)", 
                "CREATE INDEX IF NOT EXISTS idx_station ON properties(station_name)",
                "CREATE INDEX IF NOT EXISTS idx_price ON properties(price)",
                "CREATE INDEX IF NOT EXISTS idx_layout ON properties(layout)",
                "CREATE INDEX IF NOT EXISTS idx_age ON properties(age)",
            ]
            
            for index_sql in indexes:
                cursor.execute(index_sql)
            
            conn.commit()
    
    async def _execute_async(self, func, *args, **kwargs):
        """
        同期的なデータベース操作を非同期で実行
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, func, *args, **kwargs)
    
    async def search_properties(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        検索条件に基づいて物件を検索
        """
        return await self._execute_async(self._search_properties_sync, criteria)
    
    def _search_properties_sync(self, criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        物件検索の同期実装
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # SQLクエリとパラメータを構築 (購入物件用に調整)
                query_parts = ["SELECT url, address, pref, station_name, mi_price, floor_plan, exclusive_area, years, types, traffic1 FROM BUY_data_url_uniqued WHERE 1=1"]
                params = []
                
                # 地域フィルタ
                if criteria.get("prefecture"):
                    query_parts.append("AND pref LIKE ?")
                    params.append(f"%{criteria['prefecture']}%")
                
                if criteria.get("city"):
                    query_parts.append("AND address LIKE ?")
                    params.append(f"%{criteria['city']}%")
                
                if criteria.get("station"):
                    query_parts.append("AND station_name LIKE ?")
                    params.append(f"%{criteria['station']}%")
                
                # 価格フィルタ (mi_price列を使用、万円に変換)
                if criteria.get("price_min"):
                    query_parts.append("AND CAST(mi_price AS REAL) >= ?")
                    params.append(criteria["price_min"] * 10000)  # 万円を円に変換
                
                if criteria.get("price_max"):
                    query_parts.append("AND CAST(mi_price AS REAL) <= ?")
                    params.append(criteria["price_max"] * 10000)  # 万円を円に変換
                
                # 間取りフィルタ (floor_plan列を使用)
                if criteria.get("layout"):
                    layout = criteria["layout"]
                    if "," in layout:
                        # 複数の間取り候補
                        layouts = [l.strip() for l in layout.split(",")]
                        layout_conditions = " OR ".join(["floor_plan LIKE ?" for _ in layouts])
                        query_parts.append(f"AND ({layout_conditions})")
                        params.extend([f"%{l}%" for l in layouts])
                    elif "+" in layout:
                        # 以上の条件（簡易実装）
                        base_layout = layout.replace("+", "")
                        query_parts.append("AND floor_plan LIKE ?")
                        params.append(f"%{base_layout}%")
                    else:
                        query_parts.append("AND floor_plan LIKE ?")
                        params.append(f"%{layout}%")
                
                # 面積フィルタ (exclusive_area列を使用)
                if criteria.get("area_min"):
                    query_parts.append("AND CAST(REPLACE(REPLACE(exclusive_area, 'm²', ''), '㎡', '') AS REAL) >= ?")
                    params.append(criteria["area_min"])
                
                if criteria.get("area_max"):
                    query_parts.append("AND CAST(REPLACE(REPLACE(exclusive_area, 'm²', ''), '㎡', '') AS REAL) <= ?")
                    params.append(criteria["area_max"])
                
                # 築年数フィルタ (years列を使用)
                if criteria.get("age_max"):
                    query_parts.append("AND CAST(REPLACE(years, '年', '') AS INTEGER) <= ?")
                    params.append(criteria["age_max"])
                
                # 物件タイプフィルタ
                if criteria.get("property_type"):
                    query_parts.append("AND types LIKE ?")
                    params.append(f"%{criteria['property_type']}%")
                
                # NULL値を除外、価格が0でないものに限定
                query_parts.append("AND mi_price IS NOT NULL AND mi_price != '' AND mi_price != '0' AND address IS NOT NULL AND address != ''")
                
                # 結果の制限
                limit = criteria.get("limit", 100)
                query_parts.append("ORDER BY CAST(mi_price AS REAL) ASC LIMIT ?")  # 価格順にソート
                params.append(limit)
                
                # クエリ実行
                query = " ".join(query_parts)
                cursor.execute(query, params)
                
                # 結果を標準化された形式で返す
                results = []
                for row in cursor.fetchall():
                    try:
                        # データを標準化
                        result = {
                            "url": row[0] or "",
                            "address": row[1] or "",
                            "prefecture": row[2] or "",
                            "city": self._extract_city_from_address(row[1] or ""),
                            "station_name": row[3] or "",
                            "price": self._parse_buy_price(row[4]),  # 購入価格用パーサー
                            "layout": row[5] or "",
                            "area": self._parse_area(row[6]),
                            "age": self._parse_age(row[7]),
                            "property_type": row[8] or "",
                            "traffic": row[9] or "",
                            "walk_time": self._parse_walk_time(row[9])
                        }
                        results.append(result)
                    except Exception as e:
                        print(f"Row parsing error: {str(e)}")
                        continue
                
                return results
                
        except Exception as e:
            print(f"Database search error: {str(e)}")
            return []
    
    async def find_stations_by_name(self, station_name: str) -> List[Dict[str, Any]]:
        """
        駅名で検索して複数の候補を取得
        """
        return await self._execute_async(self._find_stations_by_name_sync, station_name)
    
    def _find_stations_by_name_sync(self, station_name: str) -> List[Dict[str, Any]]:
        """
        駅名検索の同期実装
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT DISTINCT pref as prefecture, address as city, station_name, COUNT(*) as property_count
                    FROM BUY_data_url_uniqued 
                    WHERE station_name LIKE ? AND station_name IS NOT NULL AND station_name != ''
                    GROUP BY pref, address, station_name
                    ORDER BY property_count DESC
                    LIMIT 20
                """
                
                cursor.execute(query, [f"%{station_name}%"])
                columns = [desc[0] for desc in cursor.description]
                results = []
                
                for row in cursor.fetchall():
                    result = dict(zip(columns, row))
                    # 市区町村を住所から抽出
                    if result.get("city"):
                        result["city"] = self._extract_city_from_address(result["city"])
                    results.append(result)
                
                return results
                
        except Exception as e:
            print(f"Station search error: {str(e)}")
            return []
    
    async def find_locations_by_city(self, city_name: str) -> List[Dict[str, Any]]:
        """
        市区町村で検索
        """
        return await self._execute_async(self._find_locations_by_city_sync, city_name)
    
    def _find_locations_by_city_sync(self, city_name: str) -> List[Dict[str, Any]]:
        """
        市区町村検索の同期実装
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT DISTINCT prefecture, city, COUNT(*) as property_count
                    FROM properties 
                    WHERE city LIKE ?
                    GROUP BY prefecture, city
                    ORDER BY property_count DESC
                """
                
                cursor.execute(query, [f"%{city_name}%"])
                columns = [desc[0] for desc in cursor.description]
                results = []
                
                for row in cursor.fetchall():
                    result = dict(zip(columns, row))
                    results.append(result)
                
                return results
                
        except Exception as e:
            print(f"City search error: {str(e)}")
            return []
    
    async def find_locations_by_prefecture(self, prefecture_name: str) -> List[Dict[str, Any]]:
        """
        都道府県で検索
        """
        return await self._execute_async(self._find_locations_by_prefecture_sync, prefecture_name)
    
    def _find_locations_by_prefecture_sync(self, prefecture_name: str) -> List[Dict[str, Any]]:
        """
        都道府県検索の同期実装
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT DISTINCT prefecture, city, COUNT(*) as property_count
                    FROM properties 
                    WHERE prefecture = ?
                    GROUP BY prefecture, city
                    ORDER BY property_count DESC
                    LIMIT 20
                """
                
                cursor.execute(query, [prefecture_name])
                columns = [desc[0] for desc in cursor.description]
                results = []
                
                for row in cursor.fetchall():
                    result = dict(zip(columns, row))
                    results.append(result)
                
                return results
                
        except Exception as e:
            print(f"Prefecture search error: {str(e)}")
            return []
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """
        データベースの統計情報を取得
        """
        return await self._execute_async(self._get_database_stats_sync)
    
    def _get_database_stats_sync(self) -> Dict[str, Any]:
        """
        統計情報取得の同期実装
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                stats = {}
                
                # 総物件数
                cursor.execute("SELECT COUNT(*) FROM BUY_data_url_uniqued")
                stats["total_properties"] = cursor.fetchone()[0]
                
                # 都道府県数
                cursor.execute("SELECT COUNT(DISTINCT pref) FROM BUY_data_url_uniqued WHERE pref IS NOT NULL AND pref != ''")
                stats["total_prefectures"] = cursor.fetchone()[0]
                
                # 駅数
                cursor.execute("SELECT COUNT(DISTINCT station_name) FROM BUY_data_url_uniqued WHERE station_name IS NOT NULL AND station_name != ''")
                stats["total_stations"] = cursor.fetchone()[0]
                
                # 価格帯統計（mi_price列から、万円単位に変換）
                cursor.execute("""
                    SELECT 
                        MIN(CAST(mi_price AS REAL) / 10000),
                        MAX(CAST(mi_price AS REAL) / 10000),
                        AVG(CAST(mi_price AS REAL) / 10000)
                    FROM BUY_data_url_uniqued 
                    WHERE mi_price IS NOT NULL AND mi_price != '' AND mi_price != '0'
                """)
                price_stats = cursor.fetchone()
                stats["price_range"] = {
                    "min": round(price_stats[0], 1) if price_stats[0] else 0,
                    "max": round(price_stats[1], 1) if price_stats[1] else 0, 
                    "avg": round(price_stats[2], 1) if price_stats[2] else 0
                }
                
                # サンプルデータの確認
                cursor.execute("SELECT address, pref, station_name, mi_price, floor_plan FROM BUY_data_url_uniqued WHERE mi_price IS NOT NULL AND mi_price != '' AND mi_price != '0' LIMIT 3")
                sample_data = cursor.fetchall()
                stats["sample_properties"] = [
                    {
                        "address": row[0],
                        "prefecture": row[1], 
                        "station": row[2],
                        "price": f"{int(row[3])/10000:.0f}万円",  # 万円表示
                        "layout": row[4]
                    }
                    for row in sample_data
                ]
                
                return stats
                
        except Exception as e:
            print(f"Stats error: {str(e)}")
            return {"error": str(e)}
    
    async def insert_sample_data(self):
        """
        サンプルデータを挿入（テスト用）
        """
        sample_properties = [
            {
                "address": "東京都新宿区西新宿1-1-1",
                "prefecture": "東京都",
                "city": "新宿区",
                "station_name": "新宿",
                "walk_time": 5,
                "price": 12.5,
                "layout": "1K",
                "area": 25.0,
                "age": 10,
                "property_type": "マンション",
                "url": "https://example.com/property1"
            },
            {
                "address": "神奈川県横浜市神奈川区鶴屋町2-2-2",
                "prefecture": "神奈川県",
                "city": "横浜市神奈川区",
                "station_name": "横浜",
                "walk_time": 8,
                "price": 9.8,
                "layout": "1DK",
                "area": 30.0,
                "age": 15,
                "property_type": "マンション",
                "url": "https://example.com/property2"
            }
        ]
        
        return await self._execute_async(self._insert_sample_data_sync, sample_properties)
    
    def _insert_sample_data_sync(self, properties: List[Dict[str, Any]]):
        """
        サンプルデータ挿入の同期実装
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for prop in properties:
                    cursor.execute("""
                        INSERT INTO properties 
                        (address, prefecture, city, station_name, walk_time, price, layout, area, age, property_type, url)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, [
                        prop["address"], prop["prefecture"], prop["city"], prop["station_name"],
                        prop["walk_time"], prop["price"], prop["layout"], prop["area"],
                        prop["age"], prop["property_type"], prop["url"]
                    ])
                
                conn.commit()
                return {"status": "success", "inserted": len(properties)}
                
        except Exception as e:
            print(f"Sample data insertion error: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def _parse_price(self, price_str: str) -> float:
        """価格文字列から数値を抽出（賃料用）"""
        if not price_str:
            return 0.0
        try:
            # "12.5万円" -> 12.5
            price_clean = price_str.replace('万円', '').replace(',', '').strip()
            return float(price_clean) if price_clean else 0.0
        except:
            return 0.0
    
    def _parse_buy_price(self, price_str: str) -> float:
        """購入価格文字列から万円単位の数値を抽出"""
        if not price_str:
            return 0.0
        try:
            # "29800000" -> 2980.0（万円）
            price_int = int(price_str)
            return round(price_int / 10000, 1)  # 円から万円に変換
        except:
            return 0.0
    
    def _parse_area(self, area_str: str) -> float:
        """面積文字列から数値を抽出"""
        if not area_str:
            return 0.0
        try:
            # "25.5m²" or "25.5㎡" -> 25.5
            area_clean = area_str.replace('m²', '').replace('㎡', '').strip()
            return float(area_clean) if area_clean else 0.0
        except:
            return 0.0
    
    def _parse_age(self, age_str: str) -> int:
        """築年数文字列から数値を抽出"""
        if not age_str:
            return 0
        try:
            # "15年" -> 15
            age_clean = age_str.replace('年', '').strip()
            return int(age_clean) if age_clean else 0
        except:
            return 0
    
    def _parse_walk_time(self, traffic_str: str) -> int:
        """交通情報から徒歩時間を抽出"""
        if not traffic_str:
            return 999
        try:
            import re
            # "徒歩5分" pattern
            match = re.search(r'徒歩(\d+)分', traffic_str)
            if match:
                return int(match.group(1))
            return 999
        except:
            return 999
    
    def _extract_city_from_address(self, address: str) -> str:
        """住所から市区町村を抽出"""
        if not address:
            return ""
        try:
            import re
            # "東京都新宿区西新宿..." -> "新宿区"
            match = re.search(r'[都道府県]([^市区町村]+[市区町村])', address)
            if match:
                return match.group(1)
            return ""
        except:
            return ""