# OpenMausBot News Push

每天早上自動整理 AI 科技新聞，分成三類：

1. **AI 科技公司新聞**：人事異動、產品決策、商業動態
2. **AI 新工具**：解決什麼問題、用什麼方法、如何使用、有什麼優勢
3. **ML / DL / NLP 新技術**：新論文與新方法

完整內容呈現在 OpenMausBot，精簡重點寄到 Email。全程使用免費服務。

## 運作流程

| 步驟 | 內容 | 狀態 |
| --- | --- | --- |
| 1 | GitHub Actions 每天台灣時間 06:30 抓取新聞、過濾、去重、分類 | 完成 |
| 2 | OpenRouter 免費模型挑 5 到 10 則並寫繁中摘要，寄出 Email | 待做 |
| 3 | OpenMausBot 讀取當日檔案並呈現 | 待做 |

## 檔案

- `news_push/sources.py`：新聞來源與 AI 關鍵字，要增減來源改這裡
- `news_push/fetch.py`：抓取程式，輸出 `data/YYYY-MM-DD/candidates.json`
- `.github/workflows/daily-digest.yml`：每日排程

## 在自己電腦上試跑

```bash
pip install -r requirements.txt
python -m news_push.fetch --out /tmp/candidates.json
```
