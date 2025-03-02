"""
ツール関連の処理を担当するクラス
"""

from typing import Dict, Optional, Tuple, List, Any
import json
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import os
import uuid
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib_fontja
import numpy as np
from ..utils.exceptions import ToolError
from ..models.bedrock import BedrockModel
from ..config.settings import MODEL_CONFIG, PRIMARY_MODEL, PROMPT_CONFIG, IMAGE_CONFIG, GRAPH_CONFIG
import io
import fitz as pymupdf
from fitz import open as fitz_open
import tempfile


class ToolHandler:
    """
    外部ツールの操作を管理するクラス

    このクラスは、Web検索やコンテンツ取得などの外部ツールの操作を処理し、
    AIモデルからのツール使用リクエストを解釈します。
    """

    def __init__(self,logger,base_filename):
        """
        ツールハンドラの初期化

        Brave Search APIキーを読み込み、APIエンドポイントとヘッダーを設定します。
        """
        self.api_key = self._load_api_key()
        self.search_url = "https://api.search.brave.com/res/v1/web/search"
        self.image_search_url = "https://api.search.brave.com/res/v1/images/search"
        self.headers = {
            "Accept": "application/json",
            "X-Subscription-Token": self.api_key,
        }
        # タイムアウト設定（接続は5秒、読み込みは10秒）
        self.timeout = (5, 10)
        self.logger=logger
        # 現在のレポートの画像ディレクトリ
        self.current_image_dir = (f"{base_filename}_images")

    def _load_api_key(self) -> str:
        """
        Brave API キーの読み込み

        .braveファイルからAPIキーを読み込みます。

        Returns:
            str: API キー

        Raises:
            ToolError: API キーファイルが見つからない場合
        """
        try:
            return Path('.brave').read_text().strip()
        except FileNotFoundError:
            raise ToolError("Brave API key file (.brave) not found")
        except Exception as e:
            raise ToolError(f"Error loading API key: {str(e)}")

    def set_image_directory(self, image_dir: str) -> None:
        """
        画像ディレクトリを設定

        Args:
            image_dir: 画像を保存するディレクトリのパス
        """
        self.current_image_dir = image_dir
        os.makedirs(image_dir, exist_ok=True)
        self.logger.log(f"画像ディレクトリを設定: {image_dir}")

    def _download_pdf(self, url: str) -> Tuple[Optional[bytes], int]:
        """
        指定URLからPDFファイルをダウンロード

        Args:
            url: ダウンロードするPDFファイルのURL

        Returns:
            Tuple[Optional[bytes], int]: PDFファイルのバイナリコンテンツとファイルサイズ（バイト）のタプル
                                        エラー時は(None, 0)
        """
        try:
            self.logger.log(f"PDFファイルをダウンロード: {url}")

            # タイムアウト設定でリクエスト実行
            response = requests.get(url, timeout=self.timeout, stream=True)
            
            # HTTPステータスコードのチェック
            if response.status_code >= 300:  # 300番台以上は全てエラーとして扱う
                return None, 0
                
            # Content-Lengthヘッダーからファイルサイズを取得
            content_length = int(response.headers.get('Content-Length', 0))
            self.logger.log(f"ファイルサイズ: {content_length} bytes")
            
            # ファイルサイズが500MB以上の場合はダウンロードしない
            if content_length >= 500 * 1024 * 1024:  # 500MB in bytes
                return None, content_length
                
            # PDFファイルをダウンロード
            pdf_content = response.content
            self.logger.log(f"PDFファイルダウンロード完了: {len(pdf_content)} bytes")
            
            return pdf_content, len(pdf_content)
            
        except requests.Timeout:
            self.logger.log(f"PDFファイルダウンロードエラー: タイムアウト")
            # タイムアウトエラー
            return None, 0
        except requests.ConnectionError:
            self.logger.log(f"PDFファイルダウンロードエラー: 接続エラー")
            # 接続エラー（DNSエラー、接続拒否など）
            return None, 0
        except Exception as e:
            self.logger.log(f"PDFファイルダウンロードエラー: {str(e)}")
            # その他のエラー
            return None, 0

    def _extract_images_from_pdf(self, pdf_content: bytes) -> List[str]:
        """
        PDFファイルから画像を抽出して保存

        Args:
            pdf_content: PDFファイルのバイナリコンテンツ

        Returns:
            List[str]: 保存した画像ファイルのパスのリスト
        """
        if self.current_image_dir is None:
            self.logger.log("画像ディレクトリが設定されていません")
            return []

        saved_images = []
        
        try:
            # 一時ファイルにPDFを保存
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                temp_file.write(pdf_content)
                temp_path = temp_file.name
            
            # PyMuPDFでPDFを開く
            pdf_document = pymupdf.open(temp_path)
            self.logger.log(f"PDFを開きました: {pdf_document.page_count}ページ")
            
            # 各ページの画像を抽出
            for page_num, page in enumerate(pdf_document):
                image_list = page.get_images(full=True)
                
                for img_index, img in enumerate(image_list):
                    try:
                        xref = img[0]  # 画像の参照番号
                        base_image = pdf_document.extract_image(xref)
                        image_bytes = base_image["image"]
                        image_ext = base_image["ext"]
                        
                        # 許可された拡張子かチェック
                        if image_ext.lower() not in [f.lstrip('.').lower() for f in IMAGE_CONFIG['allowed_formats']]:
                            continue
                            
                        # 画像サイズのチェック
                        if len(image_bytes) > IMAGE_CONFIG['max_size']:
                            continue
                            
                        # 画像を保存
                        filename = f"{uuid.uuid4().hex}.{image_ext}"
                        filepath = os.path.join(self.current_image_dir, filename)
                        
                        with open(filepath, 'wb') as img_file:
                            img_file.write(image_bytes)
                            
                        self.logger.log(f"PDFから画像を抽出して保存しました: {filepath}")
                        saved_images.append(filepath)
                    except Exception as e:
                        self.logger.log(f"画像抽出エラー (ページ {page_num+1}, 画像 {img_index+1}): {str(e)}")
            
            # 一時ファイルを削除
            pdf_document.close()
            os.unlink(temp_path)
            
            self.logger.log(f"PDFから合計 {len(saved_images)} 個の画像を抽出しました")
            return saved_images
            
        except Exception as e:
            self.logger.log(f"PDF画像抽出エラー: {str(e)}")
            # 一時ファイルが残っていれば削除を試みる
            try:
                if 'temp_path' in locals():
                    os.unlink(temp_path)
            except:
                pass
            return []

    def get_content(self, url: str) -> Tuple[str, str]:
        """
        指定URLのコンテンツを取得

        指定されたURLからコンテンツを取得し、HTMLを処理して整形されたテキストを返します。
        また、ページのタイトルも取得します。
        PDFファイルの場合は、ダウンロードしてBedrockにアップロードし、テキストを抽出します。
        また、PDFから画像も抽出して保存します。

        Args:
            url: コンテンツを取得するURL

        Returns:
            Tuple[str, str]: 取得したコンテンツとページタイトル。エラー時は空文字列のタプル
        """
        try:
            # タイムアウト設定でリクエスト実行
            response = requests.get(url, timeout=self.timeout, stream=True)

            # HTTPステータスコードのチェック
            if response.status_code >= 300:  # 300番台以上は全てエラーとして扱う
                return "", ""

            # コンテンツタイプのチェック
            content_type = response.headers.get('Content-Type', '').lower()

            # PDFファイルの場合
            if 'pdf' in content_type or url.lower().endswith('.pdf'):
                # PDFファイルをダウンロード
                pdf_content, file_size = self._download_pdf(url)
                
                # ファイルサイズが500MB以上の場合はダウンロードしない
                if pdf_content is None and file_size >= 500 * 1024 * 1024:
                    self.logger.log(f"PDFファイルサイズ制限超過: {url}")
                    return (
                        f"[このPDFファイルは{file_size / (1024 * 1024):.1f}MBであり、サイズ制限（500MB）を超えています。"
                        f"ファイルを手動でダウンロードして確認してください。]",
                        "大きなPDFファイル",
                    )
                
                # ダウンロードエラーの場合
                if pdf_content is None:
                    self.logger.log(f"PDFダウンロードエラー: {url}")
                    return (
                        f"[このPDFファイルのダウンロード中にエラーが発生しました。"
                        f"ファイルを手動でダウンロードして確認してください。]",
                        "PDFダウンロードエラー",
                    )
                
                # PDFから画像を抽出して保存
                extracted_images = self._extract_images_from_pdf(pdf_content)
                image_info = ""
                if extracted_images:
                    image_info = f"\n\n[PDFから {len(extracted_images)} 個の画像を抽出しました。これらの画像はレポートで参照できます。]"
                    
                # PDFファイルをBedrockにアップロードしてテキストを抽出
                bedrock_model = BedrockModel(self.logger)
                extracted_text = bedrock_model.process_pdf(pdf_content, MODEL_CONFIG[PRIMARY_MODEL])
                self.logger.log(f"PDF / Bedrock extracted_text: {extracted_text}")
                
                # ファイル名をタイトルとして使用
                title = url.split('/')[-1]
                if not title:
                    title = "PDFドキュメント"
                    
                return extracted_text + image_info, title

            # その他のバイナリコンテンツの場合は処理をスキップ
            if (
                'application/' in content_type
                or 'image/' in content_type
            ) and 'application/json' not in content_type:
                return (
                    f"[このコンテンツは{content_type}ファイルであり、直接処理できません。"
                    f"ファイルを手動でダウンロードして確認してください。]",
                    "バイナリコンテンツ",
                )

            # エンコーディングを設定
            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, 'html.parser')

            # タイトルの取得と整形
            title = soup.title.string if soup.title else ""
            title = " ".join(title.split())

            # 不要なHTML要素を削除
            for tag in soup(['script', 'style', 'header', 'footer', 'nav']):
                tag.decompose()

            # テキストを行ごとに抽出して結合
            lines = [
                line.strip() for line in soup.get_text().splitlines() if line.strip()
            ]
            return '\n'.join(lines), title

        except requests.Timeout:
            self.logger.log(f"コンテンツ取得エラー: タイムアウト")
            # タイムアウトエラー
            return "", ""
        except requests.ConnectionError:
            self.logger.log(f"コンテンツ取得エラー: 接続エラー")
            # 接続エラー（DNSエラー、接続拒否など）
            return "", ""
        except Exception as e:
            self.logger.log(f"コンテンツ取得エラー: {str(e)}")
            # その他のエラー
            return "", ""

    def search(self, query: str) -> str:
        """
        Web検索を実行

        Brave Search APIを使用してWeb検索を実行し、結果をJSON形式で返します。

        Args:
            query: 検索クエリ

        Returns:
            str: 検索結果のJSON文字列。エラー時は空文字列
        """
        # 全角スペースを半角に変換
        query = query.replace('　', ' ')
        results = []

        try:
            params = {"q": query, "offset": 0, "count": 10}
            # タイムアウト設定でリクエスト実行
            response = requests.get(
                self.search_url,
                headers=self.headers,
                params=params,
                timeout=self.timeout,
            )

            # HTTPステータスコードのチェック
            if response.status_code >= 300:  # 300番台以上は全てエラーとして扱う
                return ""

            data = response.json()

            # 検索結果の処理
            if 'web' in data and 'results' in data['web']:
                for result in data['web']['results']:
                    result_dict = {
                        "title": result.get('title', ''),
                        "url": result.get('url', ''),
                        "description": result.get('description', ''),
                    }
                    if result_dict["title"] and result_dict["url"]:
                        results.append(result_dict)

            return json.dumps(results, ensure_ascii=False)

        except requests.Timeout:
            # タイムアウトエラー
            return ""
        except requests.ConnectionError:
            # 接続エラー（DNSエラー、接続拒否など）
            return ""
        except Exception as e:
            # その他のエラー
            return ""

    def image_search(self, query: str, max_results: int = None) -> str:
        """
        画像検索を実行し、画像を保存

        Brave Search APIを使用して画像検索を実行し、画像をダウンロードして保存します。
        保存した画像のパスとメタデータを返します。

        Args:
            query: 検索クエリ
            max_results: 取得する最大画像数（指定がない場合はIMAGE_CONFIG['max_images']を使用）

        Returns:
            str: 保存した画像のパスとメタデータのJSON文字列。エラー時は空文字列
        """
        if self.current_image_dir is None:
            return json.dumps({"error": "画像ディレクトリが設定されていません"}, ensure_ascii=False)

        # 全角スペースを半角に変換
        query = query.replace('　', ' ')
        
        # 最大画像数の設定
        if max_results is None:
            max_results = IMAGE_CONFIG['max_images']
        else:
            max_results = min(max_results, 10)  # 最大10枚に制限
            
        saved_images = []

        try:
            params = {"q": query, "offset": 0, "count": max_results * 2}  # 余裕を持って多めに取得
            
            # タイムアウト設定でリクエスト実行
            response = requests.get(
                self.image_search_url,
                headers=self.headers,
                params=params,
                timeout=self.timeout,
            )

            # HTTPステータスコードのチェック
            if response.status_code >= 300:  # 300番台以上は全てエラーとして扱う
                return json.dumps({"error": f"API error: {response.status_code}"}, ensure_ascii=False)

            data = response.json()

            # 検索結果の処理
            if 'results' in data:
                count = 0
                for image in data['results']:
                    if count >= max_results:
                        break
                    
                    # 画像URLの取得
                    property_dict = image.get('properties', {})
                    image_url = property_dict.get('url', '') if property_dict else None
                    if not image_url:
                        continue
                        
                    # 画像の拡張子を取得
                    ext = self._get_image_extension(image_url, image.get('format', ''))
                    if not ext:
                        continue
                        
                    # 画像をダウンロードして保存
                    image_path = self._download_and_save_image(image_url, ext)
                    print("url:"+image_url)
                    if image_path:
                        # 相対パスに変換
                        rel_path = os.path.relpath(image_path, start=os.path.dirname(self.current_image_dir))
                        
                        saved_images.append({
                            "path": rel_path,
                            "title": image.get('title', ''),
                            "source_url": image.get('sourceUrl', ''),
                            "width": image.get('width', 0),
                            "height": image.get('height', 0),
                            "format": image.get('format', ''),
                        })
                        count += 1
                        
            return json.dumps({"images": saved_images}, ensure_ascii=False)

        except requests.Timeout:
            # タイムアウトエラー
            return json.dumps({"error": "タイムアウトエラー"}, ensure_ascii=False)
        except requests.ConnectionError:
            # 接続エラー
            return json.dumps({"error": "接続エラー"}, ensure_ascii=False)
        except Exception as e:
            # その他のエラー
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    def _get_image_extension(self, url: str, format_str: str) -> str:
        """
        画像URLから拡張子を取得

        Args:
            url: 画像URL
            format_str: 画像フォーマット文字列

        Returns:
            str: 拡張子（ドットを含む）。不明な場合は空文字列
        """
        # URLから拡張子を取得
        path = url.split('?')[0]  # クエリパラメータを除去
        ext = os.path.splitext(path)[1].lower()
        
        # 拡張子が取得できない場合はフォーマット文字列から推測
        if not ext and format_str:
            format_lower = format_str.lower()
            if 'jpeg' in format_lower or 'jpg' in format_lower:
                ext = '.jpg'
            elif 'png' in format_lower:
                ext = '.png'
            elif 'gif' in format_lower:
                ext = '.gif'
            elif 'webp' in format_lower:
                ext = '.webp'
                
        # 拡張子から先頭のドットを除去して小文字に変換
        if ext.startswith('.'):
            ext = ext[1:]
        ext = ext.lower()
        
        # 許可された拡張子かチェック
        allowed_formats = [f.lstrip('.').lower() for f in IMAGE_CONFIG['allowed_formats']]
        if ext in allowed_formats:
            return f".{ext}"
            
        return ""

    def _download_and_save_image(self, url: str, ext: str) -> Optional[str]:
        """
        画像をダウンロードして保存

        Args:
            url: 画像URL
            ext: 拡張子（ドットを含む）

        Returns:
            Optional[str]: 保存したファイルのパス。エラー時はNone
        """
        try:
            # タイムアウト設定でリクエスト実行
            response = requests.get(url, timeout=self.timeout, stream=True)
            
            # HTTPステータスコードのチェック
            if response.status_code >= 300:
                self.logger.log(f"画像ダウンロードエラー: HTTP {response.status_code}")
                return None
                
            # Content-Typeのチェック
            content_type = response.headers.get('Content-Type', '').lower()
            if not ('image/' in content_type):
                self.logger.log(f"画像ではないコンテンツ: {content_type}")
                return None
                
            # ファイルサイズのチェック
            content_length = int(response.headers.get('Content-Length', 0))
            if content_length > IMAGE_CONFIG['max_size']:
                self.logger.log(f"画像サイズ制限超過: {content_length} bytes")
                return None
                
            # ユニークなファイル名を生成
            filename = f"{uuid.uuid4().hex}{ext}"
            filepath = os.path.join(self.current_image_dir, filename)
            
            # 画像を保存
            with open(filepath, 'wb') as f:
                f.write(response.content)
                
            self.logger.log(f"画像を保存しました: {filepath}")
            return filepath
            
        except Exception as e:
            self.logger.log(f"画像ダウンロードエラー: {str(e)}")
            return None

    def generate_graph(
        self,
        graph_type: str,
        title: str,
        x_label: str = None,
        y_label: str = None,
        labels: List[str] = None,
        data: List[float] = None,
        series_labels: List[str] = None,
        multi_data: List[List[float]] = None,
        colors: List[str] = None,
    ) -> str:
        """
        データからグラフを生成して保存

        Args:
            graph_type: グラフの種類（line, bar, pie, scatter, horizontal_bar）
            title: グラフのタイトル
            x_label: X軸のラベル（オプション）
            y_label: Y軸のラベル（オプション）
            labels: データのラベル（オプション）
            data: グラフ化するデータ値（オプション）
            series_labels: 複数系列がある場合の系列ラベル（オプション）
            multi_data: 複数系列のデータ（オプション）
            colors: グラフの色（オプション）

        Returns:
            str: 生成したグラフのパスとメタデータのJSON文字列
        """
        if self.current_image_dir is None:
            return json.dumps({"error": "画像ディレクトリが設定されていません"}, ensure_ascii=False)
            
        try:
            # データの検証
            if graph_type not in ['line', 'bar', 'pie', 'scatter', 'horizontal_bar']:
                return json.dumps({"error": f"不正なグラフタイプ: {graph_type}"}, ensure_ascii=False)
                
            # 単一系列の場合
            if data is not None and labels is not None:
                if len(data) != len(labels):
                    return json.dumps({"error": "データとラベルの長さが一致しません"}, ensure_ascii=False)
                    
            # 複数系列の場合
            if multi_data is not None:
                if series_labels is not None and len(multi_data) != len(series_labels):
                    return json.dumps({"error": "系列データと系列ラベルの長さが一致しません"}, ensure_ascii=False)
                    
                if labels is not None:
                    for series in multi_data:
                        if len(series) != len(labels):
                            return json.dumps({"error": "系列データとラベルの長さが一致しません"}, ensure_ascii=False)
            
            # 色の設定
            if colors is None:
                colors = GRAPH_CONFIG['default_colors']
                
            # フィギュアの作成
            plt.figure(figsize=GRAPH_CONFIG['default_figsize'], dpi=GRAPH_CONFIG['dpi'])
            
            # グラフの種類に応じて描画
            if graph_type == 'line':
                self._create_line_chart(labels, data, multi_data, series_labels, colors)
            elif graph_type == 'bar':
                self._create_bar_chart(labels, data, multi_data, series_labels, colors)
            elif graph_type == 'horizontal_bar':
                self._create_horizontal_bar_chart(labels, data, multi_data, series_labels, colors)
            elif graph_type == 'pie':
                self._create_pie_chart(labels, data, colors)
            elif graph_type == 'scatter':
                self._create_scatter_plot(labels, data, multi_data, series_labels, colors)
                
            # タイトルと軸ラベルの設定
            plt.title(title, fontsize=16)
            if x_label and graph_type != 'pie':
                plt.xlabel(x_label, fontsize=12)
            if y_label and graph_type != 'pie':
                plt.ylabel(y_label, fontsize=12)
                
            # 凡例の設定（必要な場合）
            if (multi_data is not None and series_labels is not None) or graph_type == 'pie':
                plt.legend(loc='best')
                
            # グリッドの設定（円グラフ以外）
            if graph_type != 'pie':
                plt.grid(True, linestyle='--', alpha=0.7)
                
            # レイアウトの調整
            plt.tight_layout()
            
            # ファイルの保存
            filename = f"graph_{uuid.uuid4().hex}.png"
            filepath = os.path.join(self.current_image_dir, filename)
            plt.savefig(filepath)
            plt.close()
            
            # 相対パスに変換
            rel_path = os.path.relpath(filepath, start=os.path.dirname(self.current_image_dir))
            
            self.logger.log(f"グラフを生成しました: {filepath}")
            
            return json.dumps({
                "graph_path": rel_path,
                "title": title,
                "type": graph_type,
            }, ensure_ascii=False)
            
        except Exception as e:
            self.logger.log(f"グラフ生成エラー: {str(e)}")
            return json.dumps({"error": f"グラフ生成エラー: {str(e)}"}, ensure_ascii=False)

    def _create_line_chart(
        self,
        labels: List[str],
        data: List[float],
        multi_data: List[List[float]],
        series_labels: List[str],
        colors: List[str],
    ) -> None:
        """折れ線グラフの作成"""
        if multi_data is not None and series_labels is not None:
            for i, series in enumerate(multi_data):
                plt.plot(
                    labels if labels else range(len(series)),
                    series,
                    marker='o',
                    color=colors[i % len(colors)],
                    label=series_labels[i],
                    linewidth=2,
                )
        elif data is not None:
            plt.plot(
                labels if labels else range(len(data)),
                data,
                marker='o',
                color=colors[0],
                linewidth=2,
            )
            
        # X軸のラベルが長い場合は回転
        if labels and any(len(label) > 10 for label in labels):
            plt.xticks(rotation=45, ha='right')

    def _create_bar_chart(
        self,
        labels: List[str],
        data: List[float],
        multi_data: List[List[float]],
        series_labels: List[str],
        colors: List[str],
    ) -> None:
        """棒グラフの作成"""
        if multi_data is not None and series_labels is not None:
            x = np.arange(len(labels) if labels else len(multi_data[0]))
            width = 0.8 / len(multi_data)  # バーの幅
            
            for i, series in enumerate(multi_data):
                plt.bar(
                    x + i * width - (len(multi_data) - 1) * width / 2,
                    series,
                    width=width,
                    color=colors[i % len(colors)],
                    label=series_labels[i],
                )
                
            plt.xticks(x, labels if labels else range(len(multi_data[0])))
        elif data is not None:
            plt.bar(
                labels if labels else range(len(data)),
                data,
                color=colors[0],
            )
            
        # X軸のラベルが長い場合は回転
        if labels and any(len(label) > 10 for label in labels):
            plt.xticks(rotation=45, ha='right')

    def _create_horizontal_bar_chart(
        self,
        labels: List[str],
        data: List[float],
        multi_data: List[List[float]],
        series_labels: List[str],
        colors: List[str],
    ) -> None:
        """水平棒グラフの作成"""
        if multi_data is not None and series_labels is not None:
            y = np.arange(len(labels) if labels else len(multi_data[0]))
            height = 0.8 / len(multi_data)  # バーの高さ
            
            for i, series in enumerate(multi_data):
                plt.barh(
                    y + i * height - (len(multi_data) - 1) * height / 2,
                    series,
                    height=height,
                    color=colors[i % len(colors)],
                    label=series_labels[i],
                )
                
            plt.yticks(y, labels if labels else range(len(multi_data[0])))
        elif data is not None:
            plt.barh(
                labels if labels else range(len(data)),
                data,
                color=colors[0],
            )

    def _create_pie_chart(
        self,
        labels: List[str],
        data: List[float],
        colors: List[str],
    ) -> None:
        """円グラフの作成"""
        if data is not None and labels is not None:
            plt.pie(
                data,
                labels=labels,
                autopct='%1.1f%%',
                startangle=90,
                colors=colors[:len(data)],
                wedgeprops={'edgecolor': 'w', 'linewidth': 1},
                textprops={'fontsize': 10},
            )
            plt.axis('equal')  # 円を真円に

    def _create_scatter_plot(
        self,
        labels: List[str],
        data: List[float],
        multi_data: List[List[float]],
        series_labels: List[str],
        colors: List[str],
    ) -> None:
        """散布図の作成"""
        if multi_data is not None and len(multi_data) >= 2:
            # 複数系列の場合、最初の2つの系列をX軸とY軸として使用
            x_data = multi_data[0]
            y_data = multi_data[1]
            
            if series_labels and len(series_labels) >= 2:
                plt.scatter(x_data, y_data, color=colors[0], alpha=0.7)
                
                # データポイントにラベルを付ける（あれば）
                if labels:
                    for i, label in enumerate(labels):
                        if i < len(x_data) and i < len(y_data):
                            plt.annotate(label, (x_data[i], y_data[i]), fontsize=8)
            else:
                plt.scatter(x_data, y_data, color=colors[0], alpha=0.7)
        elif data is not None and labels is not None:
            # 単一系列の場合、インデックスをX軸として使用
            plt.scatter(range(len(data)), data, color=colors[0], alpha=0.7)
            
            # X軸のラベルを設定
            plt.xticks(range(len(data)), labels)

    def process_tool_response(self, model_response: Dict) -> Optional[Dict]:
        """
        モデルのツール使用レスポンスを処理

        AIモデルのレスポンスからツール使用情報を抽出します。

        Args:
            model_response: モデルからのレスポンス

        Returns:
            Optional[Dict]: ツール使用情報、ツール使用がない場合はNone
        """
        try:
            content_list = (
                model_response.get('output', {}).get('message', {}).get('content', [])
            )
            for content_item in content_list:
                if isinstance(content_item, dict) and 'toolUse' in content_item:
                    return content_item['toolUse']
        except (AttributeError, TypeError) as e:
            # エラーが発生した場合はNoneを返す
            pass
        return None
