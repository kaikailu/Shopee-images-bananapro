import os
import json
import time
import base64
import mimetypes

import requests
import pandas as pd
from google import genai
from google.genai import types

# ===== 把你的 API Key 放在這裡 =====
API_KEY = "把你的 API Key 放在這裡"

# Nano Banana Pro（Gemini 3 Pro Image 預覽）
IMAGE_MODEL = "gemini-3-pro-image-preview"

# ===== 檔案設定 =====
PRODUCT_FILE = "products.xlsx"                     # 輸入：SKU / 商品名稱 / 商品敘述 / 商品圖URL
JSONL_FILE = "image_batch_with_base.jsonl"         # 給 Batch API 用的請求檔
TMP_IMG_DIR = "tmp_base_images"                    # 暫存原始商品圖
OUTPUT_DIR = "output_images_batch"                 # 產出的主圖
SKIPPED_FILE = "batch_skipped_products.xlsx"       # 失敗清單

# 建立 Gemini Client
client = genai.Client(api_key=API_KEY)


def safe_str(v) -> str:
    """把 None / NaN 變成空字串，順便 strip。"""
    if v is None:
        return ""
    s = str(v)
    if s.lower() == "nan":
        return ""
    return s.strip()


def guess_mime_and_ext(url: str, resp: requests.Response):
    """從 Content-Type 或 URL 猜圖片格式。"""
    ct = resp.headers.get("Content-Type", "").lower()
    if "png" in ct:
        return "image/png", ".png"
    if "webp" in ct:
        return "image/webp", ".webp"
    if "jpeg" in ct or "jpg" in ct:
        return "image/jpeg", ".jpg"

    mt, _ = mimetypes.guess_type(url)
    if mt and mt.startswith("image/"):
        ext = mimetypes.guess_extension(mt) or ".jpg"
        return mt, ext

    # 最保守：當作 jpeg
    return "image/jpeg", ".jpg"


def download_image(url: str, sku: str):
    """從 URL 下載圖片，回傳 (image_path, mime_type)，失敗回傳 None。"""
    if not url:
        print(f"⚠️ SKU={sku} 沒有圖片 URL，略過下載。")
        return None

    os.makedirs(TMP_IMG_DIR, exist_ok=True)

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"⚠️ SKU={sku} 下載圖片失敗：{e}")
        return None

    mime_type, ext = guess_mime_and_ext(url, resp)
    filename_safe = sku.replace("/", "_").replace("\\", "_")
    img_path = os.path.join(TMP_IMG_DIR, f"{filename_safe}{ext}")
    with open(img_path, "wb") as f:
        f.write(resp.content)

    return img_path, mime_type


def build_image_prompt(name: str, desc: str) -> str:
    """
    給 Nano Banana Pro 的指令：
    - 一定要用「提供的商品原始照片」當主體，不重畫產品
    - 自己從商品敘述中挑 2~3 個賣點，做標題 / 副標題 / icon 賣點
    """
    name = safe_str(name)
    desc = safe_str(desc)
    short_desc = desc[:400]  # 避免 prompt 太長

    prompt = f"""
你是一位專門為台灣蝦皮賣家設計 1:1 主圖的電商視覺設計師。

系統會提供你一張商品原始照片，請以那張照片為主體，
幫我設計一張 1:1 比例、視覺吸引力強、文字極簡的電商主圖。

【整體版型】
- 上方：一行主標，必要時再加一行很短的副標。
- 左側中間(不擋到字及商品即可)：垂直排列 2～3 個「icon + 很短文字或直接省略文字」的賣點膠囊。
- 中央偏下：大面積顯示商品本體，搭配簡潔場景背景。
- 右側：如果商品有需要強調的細節，一個小的放大圈或氣泡，強調商品某個關鍵特徵，可以搭配一個超短文字，或直接省略。
- 右下角：可以有一個小標籤，但文字也要非常短，或直接省略。

【商品照片使用規則】
- 一定要使用我提供的商品圖片作為主角。
- 不要改變商品本體的外觀、形狀與顏色，不要把商品換成別的東西。
- 可以調整背景、光線、構圖與加上文字、圖標，但不要讓畫面變得太花。
- 請把商品放在畫面中央或略微偏下的位置，保持清楚、立體、有質感。

【背景與場景】
- 背景請設計為簡潔但有層次的場景或漸層色，顏色與商品本身協調。
- 可以加入與商品用途相關的模糊場景元素，但要保持簡單，不要太多細節。
- 目標是讓商品和主標最醒目，而不是背景或特效。

【文案產生規則（重點：字要少！）】
請你根據商品名稱與商品敘述，自行挑選並撰寫以下文字，務必控制字數：

1. 主標（醒目標題）
   - 使用繁體中文。
   - 字數限制：4～8 個中文字。
   - 語氣簡潔有力，能快速說明這個商品「最重要的核心價值」或「主要用途」。
   - 不要寫成句子，不要有標點，只要短語，例如：「穩定水質防異味」、「車速即時顯示」。

2. 副標（可選）
   - 使用繁體中文。
   - 字數限制：最多 10 個中文字。
   - 只有在真的有必要補充時才加上一行副標，否則可以完全不放副標。
   - 如果無法在 10 個字內清楚表達，就乾脆不要放副標。

3. 關鍵特性賣點（搭配 icon）
   - 請整理出 2～3 個最重要的功能或優點。
   - 每個賣點文字限制：3～5 個中文字。
   - 這些文字會出現在左側 icon 膠囊或右側放大圈附近。
   - 不要寫成句子，只用短語，例如：「淡海水用」、「快速定位」、「節省空間」。

4. 文案來源限制
   - 所有文字內容必須有根據，只能來自下方商品敘述或其合理概括與縮寫。
   - 不可以憑空新增商品沒有的功能或誇大療效。
   - 如果需要縮短，請優先刪掉不重要的字，而不是加新資訊。

5. 文字總量限制（非常重要）
   - 整張圖上所有中文字總數，建議控制在「主標 + （可選）一行副標 + 最多 3 個短賣點」的範圍內。
   - 請不要再額外加入其他段落文字、說明句、規格長句或品牌故事。
   - 目標是「畫面乾淨、文字極簡」，讓人一眼就懂，不需要閱讀很多字。

【商品基本資訊】
- 商品名稱（僅供你理解，不一定要完整寫在主標裡）：{name}

【商品敘述（請以這段內容為依據，自己挑選、縮短合適的文案）】
{short_desc}

請直接在生成的圖片中呈現你設計好的主標、副標與賣點文字，
且務必遵守「每段文字都很短、整體文字總量很少」的要求。
請直接輸出完成設計後的圖片，不要額外輸出任何說明文字。
"""
    return prompt


def build_jsonl_and_product_map(products_path: str, jsonl_path: str):
    """
    讀 products.xlsx：

      - 有圖片 URL 且下載成功 → 上傳 Files API，寫入帶 fileData 的 Batch 請求
      - 沒有圖片 URL → 略過，不送進 Batch，記錄到 skipped 清單（失敗原因：無圖片URL）
      - 圖片下載失敗 → 略過，不送進 Batch，記錄到 skipped 清單（失敗原因：圖片下載失敗）

    回傳：
      product_row_map: {SKU -> 原始那一列的 dict}
      pre_skipped_rows:  前置階段就被略過的列（已含「失敗原因」）
      base_columns:      products.xlsx 的欄位順序，用來之後組清單
    """
    print(f"讀取 Excel：{products_path}")
    df = pd.read_excel(products_path)

    required_cols = ["SKU", "商品名稱", "商品敘述", "商品圖URL"]
    for col in required_cols:
        if col not in df.columns:
            raise KeyError(f"在 {products_path} 裡找不到欄位：{col}")

    base_columns = list(df.columns)
    product_row_map = {}      # 所有 SKU 對應原始列（之後 Batch 解析用）
    pre_skipped_rows = []     # 還沒進 Batch 前就被略過的（沒圖 / 下載失敗）

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for idx, row in df.iterrows():
            sku = safe_str(row.get("SKU")) or f"row_{idx:04d}"
            name = safe_str(row.get("商品名稱"))
            desc = safe_str(row.get("商品敘述"))
            img_url = safe_str(row.get("商品圖URL"))

            row_dict = row.to_dict()
            product_row_map[sku] = row_dict

            # ❌ 情況 1：完全沒有圖片 URL → 直接略過，記錄
            if not img_url:
                print(f"⚠️ 第 {idx} 列（SKU={sku}）沒有圖片 URL，此商品不送進 Batch（略過）。")
                row_failed = dict(row_dict)
                row_failed["失敗原因"] = "無圖片URL"
                pre_skipped_rows.append(row_failed)
                continue

            # 有圖片 URL → 嘗試下載
            img_info = download_image(img_url, sku)
            if not img_info:
                # ❌ 情況 2：圖片 URL 有，但下載失敗 → 也略過，記錄
                print(f"⚠️ SKU={sku} 圖片下載失敗，此商品不送進 Batch（略過）。")
                row_failed = dict(row_dict)
                row_failed["失敗原因"] = "圖片下載失敗"
                pre_skipped_rows.append(row_failed)
                continue

            # ✅ 只有「有 URL 且下載成功」才會走到這裡
            img_path, mime_type = img_info
            print(f"SKU={sku} 圖片下載完成：{img_path}")

            # 上傳圖片到 Files API
            uploaded_file = client.files.upload(
                file=img_path,
                config=types.UploadFileConfig(
                    display_name=f"sku-{sku}",
                    mime_type=mime_type,
                ),
            )

            # 等待檔案處理完成（通常很快）
            while getattr(uploaded_file, "state", None) and getattr(
                uploaded_file.state, "name", ""
            ) == "PROCESSING":
                time.sleep(1)
                uploaded_file = client.files.get(name=uploaded_file.name)

            file_uri = getattr(uploaded_file, "uri", None) or uploaded_file.name

            prompt = build_image_prompt(name, desc)

            # 一行 Batch JSONL 請求：帶 fileData + prompt
            req = {
                "key": sku,
                "request": {
                    "contents": [{
                        "role": "user",
                        "parts": [
                            {
                                "fileData": {
                                    "fileUri": file_uri,
                                    "mimeType": mime_type,
                                }
                            },
                            {"text": prompt},
                        ],
                    }],
                    "generation_config": {"responseModalities": ["IMAGE"]},
                },
            }

            f.write(json.dumps(req, ensure_ascii=False) + "\n")

    print(f"✔ 已產生 Batch 請求檔：{jsonl_path}")

    return product_row_map, pre_skipped_rows, base_columns


def run_batch_and_save_images(
    jsonl_path: str,
    output_dir: str,
    product_row_map: dict,
    pre_skipped_rows: list[dict],
    base_columns: list[str],
):
    """呼叫 Batch API，等它跑完，把圖片存起來，所有失敗/略過的統一寫到 SKIPPED_FILE。"""
    os.makedirs(output_dir, exist_ok=True)

    # 1) 上傳 JSONL 到 Files API
    uploaded_file = client.files.upload(
        file=jsonl_path,
        config=types.UploadFileConfig(
            display_name="shopee-image-batch-with-base",
            mime_type="jsonl",
        ),
    )
    print(f"✔ 已上傳 JSONL 檔：{uploaded_file.name}")

    # 2) 建立 Batch Job
    batch_job = client.batches.create(
        model=IMAGE_MODEL,
        src=uploaded_file.name,
        config={"display_name": "shopee-image-batch-with-base"},
    )
    job_name = batch_job.name
    print(f"✔ 建立 Batch Job：{job_name}")

    # 3) 等待 Batch 完成
    done_states = {
        "JOB_STATE_SUCCEEDED",
        "JOB_STATE_FAILED",
        "JOB_STATE_CANCELLED",
        "JOB_STATE_EXPIRED",
    }

    print("⏳ 開始輪詢 Batch 狀態...")
    job = client.batches.get(name=job_name)
    while job.state.name not in done_states:
        print(f"目前狀態：{job.state.name}")
        time.sleep(30)  # 可自行調整輪詢間隔
        job = client.batches.get(name=job_name)

    print(f"✅ Batch 結束，狀態：{job.state.name}")

    if job.state.name != "JOB_STATE_SUCCEEDED":
        if job.error:
            print("Batch 失敗原因：", job.error)
        # 即使整個 Batch 失敗，也把 pre_skipped_rows 存起來
        all_skipped_rows = list(pre_skipped_rows)
        if all_skipped_rows:
            df_skip = pd.DataFrame(all_skipped_rows)
            # 確保欄位順序：原本欄位 + 失敗原因
            cols = base_columns + ["失敗原因"]
            for col in cols:
                if col not in df_skip.columns:
                    df_skip[col] = None
            df_skip = df_skip[cols]
            df_skip.to_excel(SKIPPED_FILE, index=False)
            print(f"⚠️ 共 {len(all_skipped_rows)} 筆商品失敗/略過，已輸出到：{SKIPPED_FILE}")
        return

    # 4) 下載結果 JSONL
    result_file_name = job.dest.file_name
    file_bytes = client.files.download(file=result_file_name)
    content = file_bytes.decode("utf-8")

    # ⭐ 把前置階段失敗的先丟進來
    all_skipped_rows: list[dict] = list(pre_skipped_rows)

    for line in content.splitlines():
        if not line.strip():
            continue

        obj = json.loads(line)
        key = obj.get("key", "no_key")
        resp = obj.get("response")

        # 小工具：從 product_row_map 拿原始列，塞上失敗原因
        def add_skip(reason: str):
            base_row = product_row_map.get(key)
            if base_row is None:
                row_dict = {col: None for col in base_columns}
                if "SKU" in base_columns:
                    row_dict["SKU"] = key
            else:
                row_dict = dict(base_row)
            row_dict["失敗原因"] = reason
            all_skipped_rows.append(row_dict)

        if not resp:
            print(f"[{key}] 沒有 response，可能該筆失敗：{obj.get('status') or obj}")
            add_skip("Batch無回應")
            continue

        try:
            parts = resp["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError):
            print(f"[{key}] response 結構不如預期：{resp}")
            add_skip("Batch回應結構錯誤")
            continue

        saved = False
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data")
            if not inline:
                continue
            data_b64 = inline.get("data")
            if not data_b64:
                continue

            img_bytes = base64.b64decode(data_b64)
            filename_safe = key.replace("/", "_").replace("\\", "_")
            out_path = os.path.join(output_dir, f"{filename_safe}.png")
            with open(out_path, "wb") as img_f:
                img_f.write(img_bytes)

            print(f"[{key}] 圖片已儲存：{out_path}")
            saved = True
            break

        if not saved:
            print(f"[{key}] 回應中沒有圖片資料。")
            add_skip("Batch回應無圖片")

    # 5) 把「所有失敗/略過」統一寫成一份 Excel
    if all_skipped_rows:
        df_skip = pd.DataFrame(all_skipped_rows)
        cols = base_columns + ["失敗原因"]
        for col in cols:
            if col not in df_skip.columns:
                df_skip[col] = None
        df_skip = df_skip[cols]
        df_skip.to_excel(SKIPPED_FILE, index=False)
        print(f"⚠️ 共 {len(all_skipped_rows)} 筆商品失敗/略過，已輸出到：{SKIPPED_FILE}")
    else:
        print("🎉 所有送進 Batch 的商品都成功產出圖片。")


def main():
    product_row_map, pre_skipped_rows, base_columns = build_jsonl_and_product_map(
        PRODUCT_FILE,
        JSONL_FILE,
    )
    run_batch_and_save_images(
        JSONL_FILE,
        OUTPUT_DIR,
        product_row_map,
        pre_skipped_rows,
        base_columns,
    )

if __name__ == "__main__":
    main()
