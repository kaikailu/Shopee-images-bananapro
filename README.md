# 🖼️ Shopee Images BananaPro
## 使用 Google Gemini 自動產生蝦皮高轉換主圖

本專案是一個 **電商 AI 自動化工具**，透過 Google Gemini（文字模型＋圖像模型），
從 Excel 批次讀取商品資料，自動產生 **符合蝦皮風格的 1:1 商品主圖**。

你只需要準備商品 Excel，剩下的流程（下載圖片、抽賣點、生成主圖、錯誤跳過）全部自動完成。

---

## 🚀 功能特色

- 📊 **Excel 批次處理商品**
- 🧠 **AI 自動從商品敘述抽取賣點**
- 🎨 **AI 生成電商主圖（不改商品本體）**
- 🖼️ **自動補成 1:1 主圖比例**
- ⚠️ **錯誤不中斷流程，自動產生跳過清單 Excel**
- 📁 輸出結果自動整理

---

## 🧩 適合使用情境

- 蝦皮 / 電商賣家大量上架商品
- AI 產圖流程自動化
- 電商美編人力不足時的輔助工具
- Side Project / 履歷作品展示

---

## 🗂️ 專案結構

```
Shopee-images-bananapro/
│
├── Shopee-images-bananapro.py   # 主程式
├── products.xlsx               # 商品資料（自行準備）
├── generated_main/             # AI 產生的主圖
├── skipped_products.xlsx       # 失敗或跳過的商品清單（自動產生）
└── README.md
```

---

## ⚙️ 環境需求

### Python
- Python **3.10+**（建議）

### 必要套件

```bash
pip install requests pandas pillow google-genai
```

---

## 🔑 API Key 設定

請先到 **Google AI Studio** 申請 Gemini API Key，
並填入程式最上方：

```python
API_KEY = "你的_GEMINI_API_KEY"
```

⚠️ 請勿將真實 API Key 上傳到公開 Repo。

---

## 📘 Excel 欄位需求

請確保你的 Excel 至少包含以下欄位（欄位名稱可依程式調整）：

| 欄位名稱 | 說明 |
|--------|------|
| SKU | 商品編號（可空白，會自動補） |
| 商品名稱 | 商品名稱 |
| 商品敘述 | 用於 AI 抽賣點 |
| 商品圖URL | 商品圖片網址 |

---

## ▶️ 使用方式

```bash
python Shopee-images-bananapro.py
```

執行後流程如下：

1. 讀取 Excel
2. 下載商品圖片
3. 自動補成 1:1
4. AI 抽賣點
5. AI 生成主圖
6. 成功輸出至 `generated_main/`
7. 失敗項目輸出 `skipped_products.xlsx`

---

## 🧠 程式設計重點

- **文字模型**：Gemini 2.5 Flash（抽賣點）
- **圖像模型**：Gemini 3 Pro Image Preview（Banana Pro）
- **錯誤處理**：ServerError / API 異常不中斷
- **設計原則**：
  - 不修改商品本體
  - 文案必須來自原始商品敘述
  - 適合縮圖閱讀

---

## ⚠️ 注意事項

- 本工具不保證每張圖片都成功（API / 安全審查限制）
- 失敗商品會完整記錄，不影響其他商品
- 建議先小量測試再大量執行

---

## 🔮 未來可擴充方向

- 多主圖風格模板（科技風 / 清爽風 / 深色）
- GUI 介面（給非工程人員使用）
- 串接 n8n / Airflow
- 支援本地圖片而非 URL
- 自動產生 Canva 模板

---

## 📄 License

MIT License

---

## 👤 作者

此專案為個人 Side Project，
用於展示 **AI × 電商 × 自動化流程設計能力**。
