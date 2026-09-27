# 執行紀錄

Plan: docs/superpowers/plans/2026-09-28-gics-dashboard.md

- 使用者核准規格與依計畫執行，並要求參照 ML repo 結構。
- Ruling: 空白儲存庫沒有初始 commit，不能從不存在的 HEAD 建立 worktree；使用獨立開發分支 feat/gics-dashboard，保留 D:/GICS 已有文件。
- Ruling: 分層改用 src/gics/data、features、serving；設定與 GICS 結構放 configs；data/ 忽略。MODEL_CARD 改 DATA_CARD，沒有訓練程式，不建 models/。
- Ruling: 最初沒有 git 作者設定；後續透過已有 Git Credential Manager 登入查核 GitHub /user，取得 lee851104 / id 247008474，使用此帳戶官方 noreply 格式建立專案 commit，不更改全域設定。
- Pre-flight: data -> features -> pipeline -> web 使用 schema_version=1；functions -> Actions 僅傳 mode，不接受訪客提供的 repo/workflow/ref。
- Task 1: complete. 官方結構解析、4項單元測試；503檔公開名單全部映射L4。排除官方Excel刪除線舊分類並移除名稱修訂註記，保留source_name。
- Task 2: complete. 11項下載/配額/錯誤脫敏測試通過。
- Task 3: complete. 報酬、週頻、品質、恢復、no_new_data測試通過；目前Python合計30項通過。
- Task 4: complete offline. 完整圖表與篩選；4項前端model測試、桌面/手機瀏覽器測試通過。只有測試攔截人工資料，正式build沒有假行情。
- Task 5: complete offline. 12項JWT/Origin/dispatch測試通過；未完成外部Access設定前fail closed。
- Task 6: implemented. Workflow YAML解析、Vite build與Wrangler Pages Functions compile通過；尚待遠端真實執行。
- Task 7: in progress. README、DATA_CARD、部署說明完成；等待code review後真實資料與遠端部署驗收。
- Ruling: 按使用者目錄習慣忽略根data/，不可使用無根錨點的data/模式（會誤忽略src/gics/data）；獨立review發現並修正。
- Ruling: 每5檔（最多15次含重試）保存遠端，hard-kill恢复保守加計20次，避免超出配額；相較計畫增加checkpoint頻率。
- Ruling: 增加deploy-only workflow模式，資料成功但發布失敗時重用成品，首次可部署誠實未初始化介面。
- GitHub僅查核Secret名稱：三項已存在；沒有讀回或輸出金鑰值。
- 獨立最終review已完成，修正過期快取、延遲基準日鎖定、缺口後輪動暖機、按實際嘗試數保存、首筆請求前保存running、600筆基準驗證、完整歷史跳價驗證及前端行情日期過期提示。新增回歸測試。
- Ruling: 初次部署自動建立專用Pages專案並保存身分；若既有同名專案缺少可核對記錄則停止，不覆蓋。
- 遠端CI與四檔真實smoke成功：各600筆、2024-05-06至2026-09-25；workflow run 36336542249。首次deploy在空白data-state的git add失敗，增加本機真實Git整合測試後修正。
- Ruling: 管理頁增加既有GitHub權限控制的手動入口，無需另建金鑰；Access設定仍保留供站內立即更新使用。
- 遠端CI已通過44項Python、17項JS、4項browser測試（commit f1578fa）。完整行情工作36337228471正從21檔檢查點續傳；全量品質/報酬核對仍待完成。
- 外部部署問題：Cloudflare GET專案查詢回404，POST建立回HTTP500、代碼8000000，三次獨立工作皆失敗。Account ID格式通過，尚不能斷言Token或帳戶功能完全正常。建立request補齊官方Wrangler相同的production/preview配置；遠端結果待驗證，不宣稱修復。
