import os
import json
import tempfile
from typing import Dict, Any, List, Optional
import PyPDF2
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import re
from openai import OpenAI
from fastapi import UploadFile


class PDFService:
    """
    PDF処理サービス
    PDFファイルのテキスト抽出、OCR、物件情報解析を担当
    """
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.upload_folder = os.getenv("UPLOAD_FOLDER", "./uploads")
        
        # アップロードフォルダの作成
        os.makedirs(self.upload_folder, exist_ok=True)
    
    async def process_pdf(self, uploaded_file: UploadFile) -> Dict[str, Any]:
        """
        PDFファイルを処理して物件情報を抽出
        """
        try:
            # 一時ファイルとして保存
            temp_file_path = await self._save_temp_file(uploaded_file)
            
            try:
                # テキスト抽出を試行
                extracted_text = self._extract_text_from_pdf(temp_file_path)
                
                if not extracted_text or len(extracted_text.strip()) < 50:
                    # テキスト抽出に失敗した場合はOCRを実行
                    extracted_text = await self._extract_text_with_ocr(temp_file_path)
                
                if not extracted_text:
                    raise Exception("PDFからテキストを抽出できませんでした")
                
                # 物件情報を解析
                property_info = await self._analyze_property_text(extracted_text)
                
                return {
                    "success": True,
                    "extracted_text": extracted_text[:500],  # 最初の500文字のみ
                    "property_info": property_info
                }
                
            finally:
                # 一時ファイルを削除
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                    
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "property_info": {}
            }
    
    async def _save_temp_file(self, uploaded_file: UploadFile) -> str:
        """
        アップロードされたファイルを一時保存
        """
        # 一時ファイル名を生成
        temp_file = tempfile.NamedTemporaryFile(
            delete=False, 
            suffix=".pdf",
            dir=self.upload_folder
        )
        
        try:
            # ファイル内容を読み込んで保存
            content = await uploaded_file.read()
            temp_file.write(content)
            temp_file.flush()
            
            return temp_file.name
            
        finally:
            temp_file.close()
    
    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        PDFから直接テキストを抽出
        """
        try:
            extracted_text = ""
            
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                # 全ページからテキストを抽出
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    page_text = page.extract_text()
                    
                    if page_text:
                        extracted_text += page_text + "\n"
            
            return extracted_text.strip()
            
        except Exception as e:
            print(f"Text extraction error: {str(e)}")
            return ""
    
    async def _extract_text_with_ocr(self, pdf_path: str) -> str:
        """
        OCRを使用してPDFからテキストを抽出
        """
        try:
            extracted_text = ""
            
            # PDFを画像に変換
            images = convert_from_path(pdf_path)
            
            # 各ページに対してOCRを実行
            for i, image in enumerate(images):
                try:
                    # 日本語OCRの設定
                    custom_config = r'--oem 3 --psm 6 -l jpn'
                    page_text = pytesseract.image_to_string(image, config=custom_config)
                    
                    if page_text.strip():
                        extracted_text += f"[Page {i+1}]\n{page_text}\n\n"
                        
                except Exception as page_error:
                    print(f"OCR error on page {i+1}: {str(page_error)}")
                    continue
            
            return extracted_text.strip()
            
        except Exception as e:
            print(f"OCR extraction error: {str(e)}")
            return ""
    
    async def _analyze_property_text(self, text: str) -> Dict[str, Any]:
        """
        抽出されたテキストから物件情報を解析
        """
        try:
            # LLMを使用して構造化されたデータを抽出
            structured_info = await self._llm_extract_property_info(text)
            
            # 正規化処理
            normalized_info = self._normalize_extracted_info(structured_info)
            
            return normalized_info
            
        except Exception as e:
            print(f"Property analysis error: {str(e)}")
            # フォールバック：正規表現による抽出
            return self._regex_extract_property_info(text)
    
    async def _llm_extract_property_info(self, text: str) -> Dict[str, Any]:
        """
        LLMを使用して物件情報を抽出
        """
        prompt = f"""
        以下のテキストは不動産物件の詳細情報です。このテキストから物件情報を抽出して、構造化されたJSONとして返してください。

        テキスト:
        {text[:2000]}  # 最初の2000文字に制限

        以下のJSON形式で情報を抽出してください：
        {{
            "address": "物件の住所",
            "prefecture": "都道府県",
            "city": "市区町村",
            "station": "最寄り駅名（「駅」を除く）",
            "walk_time": 徒歩時間（数値のみ、分単位）,
            "price": 価格（万円単位の数値、家賃の場合も万円に変換）,
            "layout": "間取り（1K、2LDKなど）",
            "area": 面積（平方メートル、数値のみ）,
            "age": 築年数（数値のみ、年）,
            "property_type": "物件種別（マンション、アパート、戸建てなど）",
            "features": ["特徴1", "特徴2"]
        }}

        抽出例：
        - 住所: "東京都新宿区西新宿1-2-3" → address: "東京都新宿区西新宿1-2-3", prefecture: "東京都", city: "新宿区"
        - 最寄り駅: "JR新宿駅徒歩5分" → station: "新宿", walk_time: 5
        - 家賃: "月額12.5万円" → price: 12.5
        - 間取り: "1K（25.5㎡）" → layout: "1K", area: 25.5
        - 築年数: "築15年" → age: 15

        情報が見つからない項目はnullを設定してください。
        数値は必ず数字のみ抽出してください。
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )

            result = json.loads(response.choices[0].message.content)
            return result

        except Exception as e:
            print(f"LLM extraction error: {str(e)}")
            raise e
    
    def _regex_extract_property_info(self, text: str) -> Dict[str, Any]:
        """
        正規表現を使用した物件情報抽出（フォールバック）
        """
        info = {}
        
        try:
            # 住所抽出
            address_patterns = [
                r'([^「」\n]*[都道府県][^「」\n]*[市区町村][^「」\n]*)',
                r'住所[：:\s]*([^「」\n]+)',
                r'所在地[：:\s]*([^「」\n]+)'
            ]
            
            for pattern in address_patterns:
                match = re.search(pattern, text)
                if match:
                    info["address"] = match.group(1).strip()
                    break
            
            # 都道府県抽出
            prefecture_pattern = r'(北海道|青森県|岩手県|宮城県|秋田県|山形県|福島県|茨城県|栃木県|群馬県|埼玉県|千葉県|東京都|神奈川県|新潟県|富山県|石川県|福井県|山梨県|長野県|岐阜県|静岡県|愛知県|三重県|滋賀県|京都府|大阪府|兵庫県|奈良県|和歌山県|鳥取県|島根県|岡山県|広島県|山口県|徳島県|香川県|愛媛県|高知県|福岡県|佐賀県|長崎県|熊本県|大分県|宮崎県|鹿児島県|沖縄県)'
            prefecture_match = re.search(prefecture_pattern, text)
            if prefecture_match:
                info["prefecture"] = prefecture_match.group(1)
            
            # 市区町村抽出
            city_pattern = r'([^「」\s]+[市区町村])'
            city_match = re.search(city_pattern, text)
            if city_match:
                info["city"] = city_match.group(1)
            
            # 駅名・徒歩時間抽出
            station_patterns = [
                r'([^「」\s]+)駅.*?徒歩.*?(\d+)分',
                r'徒歩.*?(\d+)分.*?([^「」\s]+)駅',
                r'最寄[り駅]*[：:\s]*([^「」\s]+)駅.*?(\d+)分'
            ]
            
            for pattern in station_patterns:
                match = re.search(pattern, text)
                if match:
                    if pattern == station_patterns[1]:  # 順番が逆のパターン
                        info["walk_time"] = int(match.group(1))
                        info["station"] = match.group(2)
                    else:
                        info["station"] = match.group(1)
                        info["walk_time"] = int(match.group(2))
                    break
            
            # 価格抽出
            price_patterns = [
                r'家賃[：:\s]*(\d+(?:\.\d+)?)万円',
                r'月額[：:\s]*(\d+(?:\.\d+)?)万円',
                r'賃料[：:\s]*(\d+(?:\.\d+)?)万円',
                r'(\d+(?:\.\d+)?)万円[/／]月'
            ]
            
            for pattern in price_patterns:
                match = re.search(pattern, text)
                if match:
                    info["price"] = float(match.group(1))
                    break
            
            # 間取り抽出
            layout_pattern = r'([1-9][SLDK]+)'
            layout_match = re.search(layout_pattern, text)
            if layout_match:
                info["layout"] = layout_match.group(1)
            
            # 面積抽出
            area_patterns = [
                r'専有面積[：:\s]*(\d+(?:\.\d+)?)㎡',
                r'(\d+(?:\.\d+)?)㎡',
                r'(\d+(?:\.\d+)?)平米'
            ]
            
            for pattern in area_patterns:
                match = re.search(pattern, text)
                if match:
                    info["area"] = float(match.group(1))
                    break
            
            # 築年数抽出
            age_patterns = [
                r'築(\d+)年',
                r'建築年.*?(\d+)年'
            ]
            
            for pattern in age_patterns:
                match = re.search(pattern, text)
                if match:
                    info["age"] = int(match.group(1))
                    break
            
            # 物件種別抽出
            type_patterns = [
                r'(マンション|アパート|一戸建て|戸建て|ハイツ|コーポ)',
                r'構造[：:\s]*([^「」\n]*(?:マンション|アパート|一戸建て|戸建て)[^「」\n]*)'
            ]
            
            for pattern in type_patterns:
                match = re.search(pattern, text)
                if match:
                    info["property_type"] = match.group(1)
                    break
            
            return info
            
        except Exception as e:
            print(f"Regex extraction error: {str(e)}")
            return {}
    
    def _normalize_extracted_info(self, extracted_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        抽出された情報を正規化
        """
        normalized = {}
        
        # 文字列項目の正規化
        string_fields = ["address", "prefecture", "city", "station", "layout", "property_type"]
        for field in string_fields:
            value = extracted_info.get(field)
            if value and isinstance(value, str):
                normalized[field] = value.strip()
        
        # 数値項目の正規化
        numeric_fields = {
            "walk_time": int,
            "price": float, 
            "area": float,
            "age": int
        }
        
        for field, type_func in numeric_fields.items():
            value = extracted_info.get(field)
            if value is not None:
                try:
                    if isinstance(value, str):
                        # 文字列から数値を抽出
                        numeric_match = re.search(r'(\d+(?:\.\d+)?)', value)
                        if numeric_match:
                            normalized[field] = type_func(float(numeric_match.group(1)))
                    else:
                        normalized[field] = type_func(value)
                except (ValueError, TypeError):
                    pass
        
        # リスト項目の正規化
        if "features" in extracted_info:
            features = extracted_info["features"]
            if isinstance(features, list):
                normalized["features"] = [str(f).strip() for f in features if str(f).strip()]
            elif isinstance(features, str) and features.strip():
                normalized["features"] = [features.strip()]
        
        return normalized