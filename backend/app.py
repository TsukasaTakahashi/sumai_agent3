from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict
import sqlite3
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# データベースパス（同じデータベースを使用）
DB_PATH = "../../sumai_agent/backend/data/db/local.db"

class StationService:
    def __init__(self):
        self.db_path = DB_PATH
    
    def get_connection(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)
    
    def get_prefectures(self) -> List[str]:
        """利用可能な都道府県一覧を取得"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT pref FROM BUY_data_url_uniqued WHERE pref IS NOT NULL ORDER BY pref")
            return [row[0] for row in cursor.fetchall()]
    
    def get_stations_by_prefecture(self, prefecture: str) -> List[Dict]:
        """特定の都道府県の駅一覧を取得"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # traffic1からの駅名抽出とstation_nameの両方から取得
            cursor.execute("""
                SELECT DISTINCT 
                    CASE 
                        WHEN station_name IS NOT NULL AND station_name != '' THEN station_name
                        ELSE TRIM(SUBSTR(SUBSTR(traffic1, INSTR(traffic1, '「') + 1), 1, 
                                       INSTR(SUBSTR(traffic1, INSTR(traffic1, '「') + 1), '」') - 1))
                    END as station,
                    COUNT(*) as property_count
                FROM BUY_data_url_uniqued 
                WHERE pref = ? 
                    AND (
                        (station_name IS NOT NULL AND station_name != '') 
                        OR traffic1 LIKE '%「%」%'
                    )
                GROUP BY station
                HAVING station IS NOT NULL AND station != ''
                ORDER BY property_count DESC, station
            """, (prefecture,))
            
            results = []
            for row in cursor.fetchall():
                station_name = row[0]
                property_count = row[1]
                if station_name and len(station_name) > 0:
                    results.append({
                        "name": station_name,
                        "property_count": property_count
                    })
            return results
    
    def search_properties_by_prefecture_station(self, prefecture: str, station: str, limit: int = 20) -> Dict:
        """都道府県と駅名で物件検索"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 物件検索
            query = """
                SELECT id, title, address, mi_price, mx_price, exclusive_area, 
                       years, floor_plan, traffic1, station_name, url
                FROM BUY_data_url_uniqued 
                WHERE pref = ? 
                    AND (
                        station_name = ? 
                        OR traffic1 LIKE ?
                    )
                ORDER BY CAST(mi_price as INTEGER) ASC 
                LIMIT ?
            """
            
            cursor.execute(query, (prefecture, station, f'%「{station}」%', limit))
            properties = []
            
            for row in cursor.fetchall():
                property_data = {
                    "id": row[0],
                    "title": row[1] or "",
                    "address": row[2] or "",
                    "price": self._format_price(row[3], row[4]),
                    "area": self._format_area(row[5]),
                    "age": self._format_age(row[6]),
                    "layout": row[7] or "",
                    "traffic": row[8] or "",
                    "station": row[9] or station,
                    "url": row[10] or "",
                    "prefecture": prefecture
                }
                properties.append(property_data)
            
            # 件数取得
            count_query = """
                SELECT COUNT(*) 
                FROM BUY_data_url_uniqued 
                WHERE pref = ? 
                    AND (
                        station_name = ? 
                        OR traffic1 LIKE ?
                    )
            """
            cursor.execute(count_query, (prefecture, station, f'%「{station}」%'))
            total_count = cursor.fetchone()[0]
            
            return {
                "properties": properties,
                "total_count": total_count,
                "prefecture": prefecture,
                "station": station
            }
    
    def _format_price(self, mi_price, mx_price) -> str:
        """価格を整形"""
        try:
            if mi_price and mx_price:
                mi = int(mi_price) // 10000
                mx = int(mx_price) // 10000
                if mi == mx:
                    return f"{mi}万円"
                else:
                    return f"{mi}～{mx}万円"
            elif mi_price:
                return f"{int(mi_price) // 10000}万円"
            elif mx_price:
                return f"{int(mx_price) // 10000}万円"
        except (ValueError, TypeError):
            pass
        return "価格不明"
    
    def _format_area(self, exclusive_area) -> str:
        """面積を整形"""
        if not exclusive_area:
            return ""
        try:
            area_str = str(exclusive_area).split("m2")[0]
            return f"{area_str}㎡"
        except:
            return str(exclusive_area) if exclusive_area else ""
    
    def _format_age(self, years) -> str:
        """築年数を整形"""
        if not years:
            return ""
        try:
            return f"築{years}年"
        except:
            return str(years) if years else ""

station_service = StationService()

@app.get("/")
async def root():
    return {"message": "App3 - Prefecture-Station Property Search API", "status": "running"}

@app.get("/prefectures")
async def get_prefectures():
    """都道府県一覧を取得"""
    try:
        prefectures = station_service.get_prefectures()
        return JSONResponse({
            "prefectures": prefectures,
            "count": len(prefectures)
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching prefectures: {str(e)}")

@app.get("/stations/{prefecture}")
async def get_stations(prefecture: str):
    """指定した都道府県の駅一覧を取得"""
    try:
        stations = station_service.get_stations_by_prefecture(prefecture)
        return JSONResponse({
            "prefecture": prefecture,
            "stations": stations,
            "count": len(stations)
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching stations: {str(e)}")

@app.post("/search")
async def search_properties(
    prefecture: str = Form(...),
    station: str = Form(...),
    limit: Optional[int] = Form(20)
):
    """都道府県と駅名で物件検索"""
    try:
        result = station_service.search_properties_by_prefecture_station(prefecture, station, limit)
        return JSONResponse({
            "success": True,
            "data": result,
            "message": f"{prefecture}の{station}駅周辺で{result['total_count']}件の物件が見つかりました"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)