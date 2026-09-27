# 部署與手動更新設定

## 1. 憑證

GitHub → `lee851104/sector_rotation` → Settings → Secrets and variables → Actions。

| Secret | 內容 |
|---|---|
| CLOUDFLARE_API_TOKEN | 已建立的 Pages Write Token |
| CLOUDFLARE_ACCOUNT_ID | 已建立的帳戶 ID |
| TWELVE_DATA_API_KEY | Twelve Data Secret key |

不要把金鑰放进Issue、程式碼、聊天、JSON資料或網址截圖。GitHub Secret建立後無法讀回明文，程式只在Actions執行時使用。

## 2. Pages 專案

第一次部署會自動建立 **Pages / Direct Upload** 專案 `sector-rotation`，並把專案識別記錄在data-state分支。此專案由GitHub Actions用Wrangler上傳，勿另外啟用同一專案Git自動建置。部署分支main。

若同名專案已存在、但沒有本專案保存的識別記錄，工作會停止，避免覆蓋其他網站；需核對現有專案身分後再處理。免費Pages預設網址不需買網域。

## 3. 程式與真實資料驗收

1. 將本專案推至儲存庫main。CI執行測試；更新workflow的push事件只部署現有資料及介面，沒有資料時顯示未初始化。
2. Actions → **Update and deploy GICS** → Run workflow → main → mode選 **smoke**。真實取得SPY/AAPL/MSFT/BRK.B各600筆，檢查帳戶方案權限；此步驟不部署行情。
3. 成功後再 Run workflow，mode選 **update**。全量約一至兩小時，最後驗證覆蓋並部署。無權限、配額不足或覆蓋不足均不發布部分資料。
4. 成功後檢查Action摘要、Cloudflare部署紀錄及實際網址上的行情日期。不要把workflow啟動或build成功誤認為已上線。
5. 若資料計算成功但部署失敗，修正部署設定後選 **deploy**，會復用已驗證JSON，不重抓全部股票。

日後排程為美東週一至週五18:17，隨夏令時間轉換。GitHub排程可能延遲；休市保持上一行情日期。同一時間僅一個update workflow，GitHub可能合併/替換待執行工作，不承諾每次點擊各執行一份。

`data-state`為持久資料分支；不要刪除它來重置API配額。每5檔存遠端檢查點、失敗時再保存；硬終止恢復時保守計入20次不確定請求。當日成功批次不再抓取。

## 4. 管理者按鈕

在未完成以下設定前，公開儀表板可運作，但管理頁會拒絕更新，不提供免登入後門。這段期間可直接用已登入的GitHub Actions **Run workflow**手動更新。

### GitHub 細粒度 Token

GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens。

- 僅選 `sector_rotation`。
- Repository permissions：**Actions Read and write**、**Contents Read-only**（讀進度JSON）；Metadata為GitHub必要的讀取權限。
- 在Cloudflare Pages專案的Settings → Variables and Secrets新增加密Secret `GITHUB_ACTIONS_TOKEN`。
- 此Token不是既有的Cloudflare部署Token，也不是Twelve Data金鑰。

### Cloudflare Access

依[Pages已知限制](https://developers.cloudflare.com/pages/platform/known-issues/)設定Pages的Access應用，再將應用的網域路徑限縮至正式網址的 **`/admin`、`/admin/*`、`/api/admin/*`**，不要保護整個網站根路徑。若後續加入自訂網域，對該網域同樣設定路徑；不能只保護preview網址。

Access應用使用email一次性登入碼或既有身份供應商，Allow政策只填管理者信箱，**不要設定Everyone或Bypass**。在同一Access應用加入上述路徑，取得相同Audience。

在Pages專案的production Variables/Secrets新增：

| 名稱 | 值 |
|---|---|
| ACCESS_ISSUER | `https://你的team.cloudflareaccess.com` |
| ACCESS_AUDIENCE | Access應用的Application Audience（AUD） |
| ADMIN_EMAIL | 唯一允許登入的信箱 |
| GITHUB_ACTIONS_TOKEN | 上述GitHub細粒度Token（Secret） |

`GITHUB_REPOSITORY=lee851104/sector_rotation`及`GITHUB_BRANCH=main`由wrangler.toml提供。修改環境後重新deploy，確認函式能取得設定。

### 驗收

- 無痕視窗可看根目錄儀表板。
- 開啟/admin會要求Access登入，其他信箱不能登入。
- 未帶JWT呼叫/api/admin/refresh，應被Access或API拒絕；不能成功觸發。
- 登入後按「立即更新」，取得真正GitHub run紀錄；更新中不能重複按。
- 如果同日已更新，工作返回already_updated；休市同日期為no_new_data。結果與最新成功部署日期須分開核對。

## 常見故障

- **Missing TWELVE_DATA_API_KEY**：到GitHub Secrets新增，不是Cloudflare Variables。
- **ProviderError**：檢查smoke工作摘要及Twelve Data方案；程式刻意不印出可能含金鑰的原始URL/錯誤訊息。
- **Latest-day coverage**：查看data-state的status/batch，待來源資料補齊後重試失敗股票，不能以假值填入。
- **Cloudflare project request failed**：確認Account ID、Pages Write權限；已存在但不認識的專案不會被自動覆蓋。
- **GitHub拒絕操作**：確認細粒度Token的儲存庫及Actions/Contents權限，workflow需存在於main。
- **管理者登入尚未設定**：Access變數缺漏；此狀態按鈕停用是預期行為。

本文件不表示資料已取得公開展示授權，亦不表示部署或真實行情已驗收。
