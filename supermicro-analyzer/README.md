# Supermicro 型號分析

輸入 Supermicro 系統或主機板型號，從官方產品頁整理：

- 產品類別
- 系統所搭配的主機板型號
- 支援的 CPU
- 支援的記憶體
- 是否有 BMC
- 是否有 RoT
- Supermicro 官網目前提供的最新 BIOS 與 BMC 韌體版本

輸入系統型號時，程式會再讀取所搭配的官方主機板頁，以主機板資料補充
BMC 與 RoT 支援狀態。
查詢期間會依照實際完成的步驟顯示進度與百分比。

## 啟動

需要 Python 3.10 以上版本，不需要安裝額外套件。

```bash
cd supermicro-analyzer
python3 server.py
```

啟動後會自動開啟瀏覽器；若沒有自動開啟，請手動開啟 <http://127.0.0.1:8000>。
使用期間請保持終端機視窗開啟。Windows 若找不到 `python3`，請改用 `py server.py`。

若顯示「無法啟動：連接埠 8000 可能已被其他程式使用」，可改用其他連接埠：

```bash
python3 server.py --port 8001
```

如需讓同一個內部網路上的其他電腦使用：

```bash
python3 server.py --host 0.0.0.0
```

## 資料來源

程式只接受簡短的產品型號，並只組合 Supermicro 官方網址，避免輸入值被當成任意網址使用。
Supermicro 部分型號會寫成 `AS -2116GT-DTNF`；程式會自動移除連字號旁的空格。

Supermicro 的 CDN 會拒絕來自部分伺服器的直接請求，因此程式透過
[Jina Reader](https://jina.ai/reader/) 將官方公開頁面轉成可讀文字。結果畫面上的
「看官網」仍會開啟實際使用的 Supermicro 官方產品頁。

目前支援：

- 系統規格表：`/en/products/system/datasheet/<型號>`
- 主機板頁：`/en/products/motherboard/<型號>`

其他產品種類（MEM、AOC、AOM、PWS、CBL）尚未支援。
