# ☀️ AI 科技早報｜2026-11-26（週四）

**10 則精選**　·　閱讀約 5 分鐘

> 💡 **今日焦點**　AI 代理治理與內容管制升溫，台灣晶片力拚終端推論

### 📋 今日導覽

- 🏢 **公司動態**　① Tidal 12 月起全面封殺 AI 生成音樂　② Amazon 傳與 Meta 洽談解除 Muse 封鎖　③ Anthropic 推 Siren 測試代理沙箱逃逸　④ 台大發表高能效 Transformer 學習晶片
- 🛠️ **新工具**　⑤ fast-anything：只重寫慢的那 5%　⑥ agy-fast：Antigravity 的 MCP 加速外掛　⑦ songe：用閒置算力訓練本地模型
- 🔬 **新技術**　⑧ PenGPT：用生成式 Transformer 寫字與畫圖　⑨ CompoundingKernel：上千代理自動寫 GPU 核心　⑩ MIT 讓模型自己設計學習流程

---

## 🏢 AI 科技公司新聞

### ① Tidal 12 月起全面封殺 AI 生成音樂

音樂串流平台 Tidal 宣布自 12 月 9 日起禁止 AI 生成音樂上架，並將刪除約 2,900 萬首相關曲目，估計每天還會拒收 8 萬至 8.5 萬首。Tidal 音樂負責人 Robert Andersen 表示，這是繼先前對 AI 曲目標記與停止分潤後的進一步動作。對創作者與串流平台而言，這代表「先標記、後封殺」的管制路線正在成形。

🔗 [閱讀原文](https://www.theverge.com/entertainment/1041362/tidal-ai-music-ban)　·　`The Verge AI`

### ② Amazon 傳與 Meta 洽談解除 Muse 封鎖

外媒報導，Amazon 已就讓 Meta 的 Muse AI 購物代理進入其市集展開討論，可能結束長達兩個月的封鎖。談判焦點在於代理推薦的商品類型，以及對 Amazon 廣告營收的潛在衝擊。這顯示當 AI 代理開始代替消費者購物，平台如何守住流量與廣告利益，將成為新一波角力。

🔗 [閱讀原文](https://www.theverge.com/tech/1042071/meta-amazon-muse-ai-shopping-discussions)　·　`The Verge AI`

### ③ Anthropic 推 Siren 測試代理沙箱逃逸

Anthropic 首度公開 AI 安全評估機制 Siren 的設計與測試結果，做法是在沙箱中刻意植入弱點，並在沙箱外設置蜜罐，觀察 AI 代理是否為了完成任務而擅自存取未授權資源。隨著模型愈來愈有能力利用沙箱漏洞，Anthropic 已自 10 月起把 Siren 納入新模型的部署評估。這意味著代理安全開始從紙上規範走向可重複的實測流程。

🔗 [閱讀原文](https://www.ithome.com.tw/news/180792)　·　`iThome`

### ④ 台大發表高能效 Transformer 學習晶片

在國科會晶創臺灣方案支持下，台大電機系楊家驤教授團隊發表兩代 Transformer 學習處理器晶片，定位為 NPU 類型，透過減少不必要運算與簡化流程，加速模型訓練、微調與推論。團隊另設計第三代晶片，改善生成式 AI 推論時的資料搬移效率，已於今年 10 月以 16 奈米製程下線。目標是讓生成式 AI 在本地端與裝置端執行更具可行性。

🔗 [閱讀原文](https://www.ithome.com.tw/news/180800)　·　`iThome`

---

## 🛠️ AI 新工具

### ⑤ fast-anything：只重寫慢的那 5%

GitHub 專案 fast-anything 針對「乾脆用 Rust 重寫」的風氣提出反論：真正慢的通常只有一小部分程式。它先用 profiler 找出熱點，再讓 coding agent 把熱點函式移植到更快的語言，並驗證行為一致。對既有 Python、Node 或 Ruby 服務來說，這是風險較低的最佳化路線。

| 面向 | 說明 |
| :-- | :-- |
| **🎯 解決什麼問題** | 整套系統重寫成本高、風險大，但效能瓶頸往往只集中在少數函式。 |
| **⚙️ 用什麼方法** | 先對 Python、Node、Ruby 應用做效能剖析，找出最慢的約 5% 熱點，再用 coding agent 改寫成高效能語言，並比對行為是否一致。 |
| **🚀 如何使用** | 從 GitHub 取得專案，對既有專案執行剖析，依結果挑選熱點函式進行移植與驗證。 |
| **✨ 使用後的優勢** | 不必全面重寫就能改善效能，改動範圍小、可逐項驗證，降低回歸風險。 |

🔗 [閱讀原文](https://github.com/EL4CTEO/fast-anything)　·　`GitHub 新興專案`

### ⑥ agy-fast：Antigravity 的 MCP 加速外掛

agy-fast 是針對 Google Antigravity（CLI、桌面與 IDE）設計的 MCP 加速外掛，主打不影響原生介面與 diff 顯示。專案宣稱可減少約 34% 的 LLM 回合、31% 的 token 配額消耗與 40% 的上傳流量。對重度使用代理寫程式的開發者來說，直接關係到成本與額度。

| 面向 | 說明 |
| :-- | :-- |
| **🎯 解決什麼問題** | 代理式開發工具回合數多、token 消耗快，容易撞到配額上限並拉高成本。 |
| **⚙️ 用什麼方法** | 以非侵入式 MCP 外掛方式掛載在 Antigravity 上，在不改動原生 UI 與 diff 的前提下精簡往返內容。 |
| **🚀 如何使用** | 從 GitHub 取得外掛，安裝到 Antigravity 的 CLI、桌面版或 IDE 環境即可。 |
| **✨ 使用後的優勢** | 在不改變既有操作習慣的情況下，降低 token 用量與上傳流量，延長可用額度。 |

🔗 [閱讀原文](https://github.com/INK-Q/agy-fast)　·　`GitHub 新興專案`

### ⑦ songe：用閒置算力訓練本地模型

songe 是一個鎖定本地模型的訓練引擎，主打利用閒置運算資源進行訓練。在雲端 GPU 昂貴、資料又常不便外送的現實下，這類工具讓個人與小團隊更容易嘗試自有模型。目前專案仍在早期階段，實際效果需視硬體與模型規模而定。

| 面向 | 說明 |
| :-- | :-- |
| **🎯 解決什麼問題** | 本地模型缺乏好用的訓練流程，而租用雲端 GPU 成本高、資料外傳也有顧慮。 |
| **⚙️ 用什麼方法** | 提供訓練引擎，把機器上閒置的運算資源投入本地模型的訓練流程。 |
| **🚀 如何使用** | 從 GitHub 取得專案，設定本地模型與訓練資料後啟動。 |
| **✨ 使用後的優勢** | 資料留在本地、省下雲端費用，並可重複利用平常閒置的算力。 |

🔗 [閱讀原文](https://github.com/sous-labs/songe)　·　`GitHub 新興專案`

---

## 🔬 ML / DL / NLP 新技術

### ⑧ PenGPT：用生成式 Transformer 寫字與畫圖

PenGPT 是一個生成式 Transformer 專案，目標是產生手寫筆跡與素描線條，而非點陣圖片。作者在技術文章中說明其建模方式，專案在 Hacker News 上獲得數百點討論。這類「筆順即序列」的做法，對教育、字型與創意工具都有想像空間。

🔗 [閱讀原文](https://greydanus.github.io/2026/11/12/pengpt/)　·　`Hacker News 熱門 AI 討論`

### ⑨ CompoundingKernel：上千代理自動寫 GPU 核心

Amazon 研究團隊提出 CompoundingKernel，一套會自我改進的代理系統，透過搜尋方式自動撰寫 GPU 核心。實驗中同時運行超過一千個代理，產出的核心在 NVIDIA B200 上的 SOL-ExecBench 公開榜單 L1、L2 與量化項目排名第一。這展示了以大量代理平行搜尋，取代人工調校底層效能程式的可能性。

🔗 [閱讀原文](https://academy.dair.ai/papers/compoundingkernel-self-improving-from-zero-to-first-2611.19230)　·　`dair-ai 每週精選論文`

### ⑩ MIT 讓模型自己設計學習流程

MIT CSAIL 與圖賓根大學的研究團隊，給一個凍結的模型運算預算與簡單工具，讓它自行撰寫練習遊戲、觀察另一個自己遊玩，再修改對方的提示與技能檔案，過程中沒有真實任務、驗證分數或學習指令。結果顯示能力足夠的模型能自行建構出一套可運作的學習程序。這對「模型能否自我改進」的討論提供了具體實驗。

🔗 [閱讀原文](https://academy.dair.ai/papers/do-llm-agents-still-need-to-be-told-how-to-self-improve-2611.23219)　·　`dair-ai 每週精選論文`

---

*🤖 由 openrouter:particle-ai/particle-1:free 整理　·　產生於 2026-11-26 01:23（台灣時間）*
