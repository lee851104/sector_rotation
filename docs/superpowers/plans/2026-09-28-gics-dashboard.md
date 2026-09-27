# GICS Dashboard Implementation Plan

> 2026-09-28 執行狀態：Tasks 1–6 已實作並通過遠端 CI；Task 7 的真實四檔連線已成功，全量下載及公開部署仍待驗收。實際變更、測試及與原計畫的差異以 `docs/implementation-log.md` 為準；以下保留原始細項供逐項核對，不把未驗證的外部結果標成完成。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以真實日線建立可公開部署的「GICS儀表板」，提供產業輪動、排名、每日及管理者手動更新。

**Architecture:** GitHub Actions 執行 Python 取得/驗證/計算資料，產出版本化 JSON，經驗證後連同靜態網站發布 Cloudflare Pages。受 Access 保護的 Pages Functions 只處理管理者驗證、觸發及查詢工作；前端不持有供應商或部署金鑰。

**Tech Stack:** Python 3.12、pandas、httpx、pytest；Node.js 22、Vite、Apache ECharts、jose、Node test runner；Cloudflare Pages/Functions、GitHub Actions。建立依賴鎖檔，實作時查核官方相容版本，不使用浮動 latest 部署。

**Spec:** `docs/superpowers/specs/2026-09-28-gics-dashboard-design.md`

**Execution:** 建議由目前代理在本對話依序實作（Native）。本檔待使用者審閱並確認執行方式。

## Global Constraints

- 標題為「GICS儀表板」，介面繁體中文，股票代碼保留英文。
- 美東週一至週五 18:17 更新，不另外維護休市日曆。
- 使用真實行情，不用模擬數據補缺值。
- 顯示「價格報酬，不含股息」、「相對 SPY（S&P 500 代理）」、「以目前成分股及分類回看」。
- 首版等權重；無可靠權重時市值加權停用並說明。
- 600 筆日線；21/63/126/252 日比較；10週 RS 均線、4週動能均線；軌跡4/13/26/52週。
- 分鐘8、每日800 credits 為已查到的 Basic 上限；實作請求須留安全餘裕，不能繞過限流。
- 行情覆蓋至少98%才能發布，無新行情保留行情日期，錯誤不得覆盖上一份成功網站。
- 手動入口僅管理者可用，驗證 JWT、Origin；未設定時拒絕，不把秘密傳給瀏覽器。
- 所有測試用人工數列僅在 tests 下，絕不打包為公開行情。
- 不對未執行的 live 資料測試、未驗證的憑證或未發布的網站宣稱成功。

## Review Focus

1. 長時間下載跨配額重置時間、手動與排程同時來：任一請求前記帳，同一批次不得重複抓取；Task 2、6。
2. 個別股票只回傳舊日期而 HTTP 200：必須降低最新日覆蓋率而非當作成功；Task 3。
3. 休市、未收盤日、單一公司換代碼與新上市：不假設每星期五都有資料，不前填造出0%報酬；Task 1、3。
4. 伺服器收到偽造 Access header、錯誤 audience、跨站 POST：即使前端有管理入口也不能觸發；Task 5。
5. 首次更新失敗或發布失敗：首跑顯示未初始化；已有資料繼續讀上一版，資料與工作成功狀態不可錯配；Task 4、6。

## File Structure and Shared Contracts

- `src/gics/models.py`：Constituent、PriceBar、FetchState、Dataset 型別與版本。
- `src/gics/universe.py`、`data/gics_structure.json`：公開名單解析及具來源日期的四層分類映射。
- `src/gics/provider.py`、`state.py`：Twelve Data 介面、節流、不可洩密錯誤、增量保存工作紀錄。
- `src/gics/quality.py`、`analytics.py`、`pipeline.py`：日期/覆蓋驗證、公式、組織工作與 CLI。
- `web/index.html`、`web/src/{main,charts,table,format}.js`、`web/styles.css`：公開工作畫面。
- `web/admin/index.html`、`web/src/admin.js`：管理登入入口、更新與進度。
- `functions/api/admin/{status,refresh}.js`、`functions/_lib/{auth,github}.js`：驗證及工作控制。
- `.github/workflows/{ci,update-deploy}.yml`、`scripts/build.mjs`、`wrangler.toml`：驗證、更新、原子部署。
- `tests/python/`、`tests/js/`、`tests/browser/`：對應計算、API及介面測試。
- `README.md`、`docs/deployment.md`、`.env.example`、`.gitignore`：實際設定與金鑰排除。

PriceBar 為 `{date: YYYY-MM-DD, close: positive finite float}`。Constituent 為 `{symbol, provider_symbol, name, gics: {L1,L2,L3,L4}}`，各層為 `{code,name}` 或 null。

Dataset JSON `schema_version: 1`，包含 `as_of`、`updated_at`、`source`、`methodology`、`coverage`、`missing_symbols`、`groups`。每組包含 id、level、code、name、member_count、valid_count、`periods`（鍵1M/3M/6M/12M，各有 return/rs/breadth/breadth_count）、每日 index 序列、週 rotation 序列、各期間個股報酬。報酬保存小數（0.1為10%），缺值 null，不輸出 NaN/Infinity。

## Task 1: 名單與分類的可驗證資料模型

**Files:** Create `pyproject.toml`, `src/gics/{__init__,models,universe}.py`, `data/gics_structure.json`, `tests/python/test_universe.py`；工具配置納入此任務。

**Interfaces:** `parse_constituents(html: str, structure: dict) -> list[Constituent]`；`load_structure(path: Path) -> dict`。保留原代碼與供應商代碼，明確處理多股別，不硬編碼500家股票。

- [ ] 先寫案例：重複代碼被拒絕、BRK.B 映射不更改顯示代碼、未知子產業四層不猜測、缺必要欄位拋可理解錯誤；assert `unmapped.gics['L4'] is None`。
- [ ] 執行 `python -m pytest tests/python/test_universe.py -q`，確認因未實作失敗。
- [ ] 取得官方版本化結構，記錄 URL 與取得日期，實作上述介面，來源失敗時僅使用已保存且明示日期的名單。
- [ ] 重跑測試通過；核對11個 L1 code 與父子階層，不把相似名稱當精確配對。
- [ ] Commit 此任務。若 Git 沒有使用者 identity，保留未提交檔案並告知，不虛構作者設定；此規則適用後續所有任務。

## Task 2: 行情下載、配額與恢復

**Files:** Create `src/gics/{provider,state}.py`, `tests/python/test_provider.py`。

**Interfaces:** `TwelveDataClient.fetch_daily(symbol: str, outputsize: int = 600) -> list[PriceBar]`；`Budget.reserve(now: datetime) -> None`；`Checkpoint.load/save(path: Path)`。可注入 HTTP transport/clock/sleep 以測試真實控制邏輯。

- [ ] 先測 429/HTTP 200 error JSON、逾時、非正及非有限 close、缺失金鑰、不得在錯誤字串保留 apikey URL；assert 第801次 reserve 拋 `BudgetExceeded`。
- [ ] 執行 `python -m pytest tests/python/test_provider.py -q` 確認失敗。
- [ ] 實作每次發送前記帳、至少8.6秒間隔（不超過7/min）、最多3次暫時錯誤重試；401/403/方案不足不重試。不以快取拼接不同調整尺度的歷史。逐檔保存可恢復結果及 UTC 日期配額帳本，來源回報剩餘額度時採較小值；保留20 credits餘裕。
- [ ] 加入跨 UTC 日、斷線恢復、同次成功 symbol 不重抓測試；已成功當日批次返回 already_updated，人工重跑不重置帳本。
- [ ] 全部測試通過後 commit。

## Task 3: 品質閘門與產業指標

**Files:** Create `src/gics/{quality,analytics,pipeline}.py`, `tests/python/{test_quality,test_analytics,test_pipeline}.py`。

**Interfaces:** `validate_snapshot(universe, prices, now, previous_as_of) -> QualityResult`；`build_dataset(universe, prices, quality) -> dict`；CLI `python -m gics.pipeline --state-dir PATH --output PATH [--smoke]`。smoke 僅取 SPY/AAPL/MSFT/BRK.B 並輸出不含金鑰的結果，不部署。

- [ ] 先寫精確斷言：`relative_return(.10,.05) == approx(1.10/1.05-1)`；`quadrant(100,100)=='leading'`；100→110→99 指數累積報酬為-1%；歷史不足的12M為None；廣度分母只含有效個股。
- [ ] 執行 `python -m pytest tests/python/test_analytics.py -q` 確認失敗。
- [ ] 實作規格的逐日再平衡、SPY基準交易日對齊、不前填、週內最後有效觀測、10週與4週均線、期間RS及個股排序。若群組某日無可算日報酬，標斷點，不跨缺口編造連續指數。
- [ ] 加入品質閘門測試：100檔僅97檔具最新日拒絕；98檔通過且列出缺失；基準倒退拒絕；16:00美東前刪當日日線；休市同日期為no_new_data。沒有日曆時對提前收盤日採保守16:00截止。
- [ ] Pipeline 組合Task 1/2，保存 staging，只有 validation 通過才原子替換輸出；測試失敗保留原檔位元內容、不把人工數列放進 web。
- [ ] 執行 `python -m pytest tests/python -q` 通過後 commit。

## Task 4: 公開互動儀表板

**Files:** Create `package.json`, lockfile, `vite.config.js`, `web/index.html`, `web/styles.css`, `web/src/{main,charts,table,format}.js`, `web/favicon.svg`, `tests/js/view-model.test.js`。

**Interfaces:** `loadDataset(url) -> Promise<Dataset>`、`selectGroups(dataset, {level, period, minNames})`、`renderRotation(element, groups, period, pathMode)`、`renderRelative(element, groups, selectedIds, period)`。共用Task 1/3 JSON contract。

- [ ] 先測排序時null在最後、NaN不變0、正負百分比、各層切換重設不存在的 selectedIds；`formatPercent(null)==='—'`。
- [ ] 執行 `node --test tests/js/view-model.test.js` 確認失敗後實作純函式。
- [ ] 建立深色橘色重點的完整工作畫面，所有圖表來自JSON，不內嵌假行情；ECharts 隨套件打包、不依賴執行時外部CDN。
- [ ] 實作四層/期間/最少家數、箭頭/尾跡、可排序排名、曲線選取、最強最弱卡片；資料新舊與來源可見。SPY基準線100，窄螢幕圖表堆疊、表格可橫捲。
- [ ] 本機有真實Dataset時開啟第一個可用預覽；無資料則顯示未初始化，不對使用者宣稱已接實際行情。用測試環境 response fixture 測互動，不把fixture建置到dist。
- [ ] 執行 `npm test`、`npm run build`，檢查 `dist` 不含 Secrets、原始檢查點及測試資料後 commit。

## Task 5: 管理者驗證、手動更新與狀態

**Files:** Create `functions/_lib/{auth,github}.js`, `functions/api/admin/{status,refresh}.js`, `web/admin/index.html`, `web/src/admin.js`, `tests/js/admin.test.js`。

**Interfaces:** `authorize(request, env) -> Promise<{email}>`；`getActiveRun(env) -> Promise<Run|null>`；`dispatchUpdate(env) -> Promise<void>`。POST /api/admin/refresh 與 GET /api/admin/status；狀態只回傳 run id、時間、狀態、進度摘要、管理者可開啟的 GitHub run URL。

- [ ] 使用測試 RSA key 產生JWT，測缺header、偽造簽章、過期、issuer/audience/email不符、未知kid後JWKS刷新仍不符；預期401/403且GitHub請求數為0。
- [ ] 執行 `node --test tests/js/admin.test.js` 確认失敗。
- [ ] 以jose remote JWKS驗證Access token，所有設定固定來自env，不接受客戶端提供 issuer 或repo。POST驗證 Origin 精確匹配 request origin 並限定JSON。
- [ ] 實作Active run查詢、202回覆、失敗狀態、安全錯誤訊息；重複點擊停用。Workflow全域concurrency與持久批次判斷負責抵抗競態，不能只靠查一次active run。
- [ ] 測試未設Secrets為503、跨站403、active run不dispatch、GitHub拒絕不得回成功。管理頁每30秒輪詢，在背景分頁暫停，不輪詢公開訪客。
- [ ] 測試通過後commit。

## Task 6: 排程、持久快照與部署

**Files:** Create `.github/workflows/{ci,update-deploy}.yml`, `scripts/build.mjs`, `wrangler.toml`, `.gitignore`, `.env.example`, `tests/python/test_workflow_contract.py`。

**Interfaces:** Workflow `update-deploy.yml` 支援 `workflow_dispatch.inputs.mode`=smoke/update；schedule固定update。生成 `dist/data/dashboard.json`；資料分支 `data-state` 存配額與檢查點；以靜態JSON契約供Task 4讀取。

- [ ] 先測workflow contract包含cron `17 18 * * 1-5`、timezone `America/New_York`、cancel-in-progress false、180分鐘timeout、最小所需contents write權限；部署必須依賴品質驗證成功。
- [ ] 實作schedule/workflow_dispatch、dependency cache、CLI及Wrangler direct upload。只部署main對應的受信任程式，不在pull_request job注入Secrets。
- [ ] 首次沒有data-state可建立；載入快照只當資料不執行其程式。週期保存及always步驟保存配額帳本（Secrets遮罩、原始URL排除）。硬終止後配額保守估算，不重置為0。
- [ ] 行情成功與部署成功分開記錄；部署失敗重跑直接使用已驗證成品，不再消耗全量行情。no_new_data不得改as_of；GitHub工作摘要清楚區分四種結果。
- [ ] 自動workflow在首次provider smoke未成功時先執行smoke並中止全量與發布，避免付出一小時才發現方案不支援。成功結果持久記錄版本，不把測試資料當正式成品。
- [ ] Pages專案不存在時明確回報設定需要，不覆蓋未知專案。CI跑Python/JS測試及build，不要求真實金鑰。
- [ ] 執行 `python -m pytest tests/python/test_workflow_contract.py -q`、`npm run build`後commit。

## Task 7: 部署引導與實際驗收

**Files:** Create `README.md`, `docs/deployment.md`, `tests/browser/dashboard.spec.js`。

**Interfaces:** 使用前六個任務的CLI、JSON、管理API及workflow，保持相同名稱；不新增替代provider。

- [ ] 說明GitHub三個Secrets、Cloudflare Pages direct upload、Access保護/admin與/api/admin、Cloudflare GitHub Actions細粒度Token、Access issuer/audience/email設定。金鑰不出現在聊天、程式或URL。
- [ ] 文件寫明公開原始資料分支的可見性與資料授權尚未取得，不能把repo設private誤認為網站不公開。只將展示所需JSON打包，不另提供整庫行情下載功能。
- [ ] 瀏覽器測試1440px與390px視窗、4層/4期間/最少家數、排序選曲線、hover、無資料、部分覆蓋、管理入口。測試fixture只攔截網路請求，正式dist不得包含。
- [ ] 全部離線測試與build通過後，檢查本機可用GitHub驗證；若尚無push/Actions權限，保留完成檔案並只要求缺少的登入步驟，不讀回Secrets。
- [ ] 在使用者帳戶Actions執行真實smoke，成功後執行全量。若方案回傳權限不足，報告實際endpoint與錯誤，不用模擬數據或未核可provider代替。
- [ ] 查核SPY及3檔股票日期/期間報酬、覆蓋/缺項/耗時，成功後部署Pages並開啟網址驗證。用登入管理者手動按鈕查到真正run id；若Access未設則如實標註尚未驗證。
- [ ] 更新規格/計畫完成勾選與README證據；最後回報網址、已測事項及剩餘外部限制。不以本機build成功等同上線。

## Plan Self-Review

- 七個任務涵蓋規格全部區域：資料分類、600日歷史、缺值/暖機、互動版面、管理權限、額度、持久化、排程、部署與實際驗證。
- 共享JSON與函式介面在此固定；Task 4/5/6沿用名稱。測試資料只放測試範圍。
- 休市同日期、HTTP 200舊資料、跨配額日、首次失敗、驗證繞過均各有負責任務與測試。
- 上線的外部依賴包括TWELVE_DATA_API_KEY、GitHub操作權限及Access設定；可以先完成離線實作，不能先宣稱live成功。
