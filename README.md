# Global Culinary Knowledge Base

Dự án cuối kỳ xây dựng kho tri thức ẩm thực và website **Trợ lý nhà bếp**. Hệ thống thu thập công thức từ API hoặc trang web công khai, lưu bản gốc vào data lake, chuẩn hóa dữ liệu, lập chỉ mục bằng SQLite rồi cung cấp tìm kiếm, bộ lọc, trang chi tiết và hỏi đáp có trích dẫn nguồn.

Người dùng có thể hỏi bằng tiếng Việt hoặc tiếng Anh. Backend tìm trong bộ sưu tập trước; nếu không có công thức phù hợp và Gemini đã được cấu hình, hệ thống tìm trang công thức trên web, chỉ lưu trang có Schema.org `Recipe` dạng JSON-LD, sau đó chuẩn hóa và lập chỉ mục trước khi trả lời. Câu trả lời chat theo ngôn ngữ câu hỏi khi nhận diện được; nếu không, dùng ngôn ngữ giao diện. Nội dung công thức có thể được dịch theo ngôn ngữ giao diện; các liên kết, nguồn, giấy phép và thông tin ghi công vẫn giữ nguyên.

Gemini là tùy chọn. Không có Gemini, website vẫn tìm và trả lời theo các trường có trong cơ sở dữ liệu nhưng không thể dịch nội dung tùy ý hay tự tìm món mới. Khóa API chỉ nằm trong `.env` ở backend, không nằm trong frontend. Câu trả lời về dị ứng không xác nhận món ăn an toàn; bộ lọc nguyên liệu không phát hiện được mọi tên gọi, nguyên liệu ẩn hoặc lây nhiễm chéo.

Tìm kiếm và bộ lọc nguyên liệu dùng chung danh sách từ Việt–Anh thường gặp, chẳng hạn `cà chua`/`tomato`, `sữa`/`milk`, `đậu phộng`/`peanut`. Tên và nội dung gốc vẫn được giữ trong dữ liệu; danh sách từ này không thay thế khả năng dịch nội dung tùy ý của Gemini.

## Công nghệ

- **Python 3.11 trở lên:** crawler, chuẩn hóa, API và máy chủ website.
- **SQLite FTS5:** lưu kho tri thức trên máy và tìm kiếm toàn văn.
- **Requests, Beautiful Soup:** gọi API nguồn và đọc JSON-LD từ trang công thức.
- **HTML, CSS, JavaScript:** website song ngữ, không cần bước build frontend.
- **Gemini API (tùy chọn):** hỏi đáp dựa trên bản ghi, tìm kiếm web cho món chưa có và dịch nội dung.
- **GitHub Actions:** quy trình kiểm tra tự động của repository.

## Chạy trên Windows bằng PowerShell

Mở PowerShell trong VS Code tại thư mục gốc dự án. Cần Python 3.11 trở lên và kết nối Internet.

### 1. Cài đặt

Chạy một lần:

```powershell
# Tạo môi trường Python riêng trong thư mục .venv.
python -m venv .venv
# Cài thư viện crawler và API vào môi trường dự án.
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Tạo cấu hình cục bộ nếu chưa có; không ghi đè file .env đang tồn tại.
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Mở `.env` để kiểm tra `CRAWLER_USER_AGENT`. Với nguồn yêu cầu, giá trị này cần là URL dự án công khai hoặc email liên hệ thật. Để bật Gemini, điền khóa hợp lệ vào `RECIPEHUB_LLM_API_KEY`; model và endpoint đã có trong `.env.example`. Sau khi sửa `.env`, khởi động lại máy chủ. Không chép khóa vào README, mã nguồn, ảnh chụp màn hình hoặc `frontend/`. Tệp `.env` đã được Git bỏ qua.

### 2. Thu thập và lập chỉ mục dữ liệu

Chạy từ thư mục gốc:

```powershell
# Thu thập tối đa 10 công thức từ mỗi nguồn đang bật và lưu dữ liệu thô.
.\.venv\Scripts\python.exe -m recipehub.cli crawl --max-items 10
# Chuẩn hóa dữ liệu thô thành các bản ghi RecipeRecord và tạo báo cáo chất lượng.
.\.venv\Scripts\python.exe -m recipehub.cli normalize
# Tạo hoặc cập nhật cơ sở tri thức SQLite từ các bản ghi đã chuẩn hóa.
.\.venv\Scripts\python.exe -m recipehub.cli build
# Hiển thị số bản ghi và phân bố theo vùng miền.
.\.venv\Scripts\python.exe -m recipehub.cli stats
```

`crawl` lưu bản gốc; `normalize` tạo dữ liệu dùng chung; `build` cập nhật SQLite. Khi thêm hoặc chuẩn hóa dữ liệu mới, chạy lại `build` để cập nhật chỉ mục. Nguồn đang bật được khai báo trong `config/recipe_sources.json`; Wikibooks hiện tắt mặc định. Người vận hành chịu trách nhiệm kiểm tra điều khoản, quyền sử dụng và yêu cầu ghi nguồn trước khi bật/thêm nguồn.

### 3. Mở website và hỏi đáp

Trong một cửa sổ PowerShell, chạy:

```powershell
# Nạp bản ghi đã chuẩn hóa vào SQLite rồi chạy website và HTTP API tại máy cục bộ.
.\.venv\Scripts\python.exe -m recipehub.cli serve
```

Mở **http://127.0.0.1:8000**. Đổi ngôn ngữ bằng nút **Tiếng Việt / English**; giao diện ghi nhớ lựa chọn trong trình duyệt. Hãy hỏi về công thức, nguyên liệu, cách chế biến hoặc món phù hợp với nguyên liệu cần tránh. Nếu món chưa có trong kho, Gemini có thể tìm tối đa ba trang và chỉ nhận trang có dữ liệu công thức cấu trúc. Câu trả lời dựa trên bản ghi được truy xuất và website hiển thị trích dẫn.

Kiểm tra máy chủ tại **http://127.0.0.1:8000/api/v1/health**. `status` cần là `ok`; `recipes` là số công thức đã lập chỉ mục; `language_model_available` và `web_discovery_available` cho biết cấu hình Gemini đã được nạp. Hai trường cuối chỉ xác nhận cấu hình, không kiểm tra khóa hoặc hạn mức bằng một yêu cầu thật. Nếu Gemini hết hạn mức, tính năng hỏi đáp linh hoạt, tìm web và dịch có thể không hoạt động; hệ thống sẽ dùng câu trả lời dựa trên nguồn nếu có thể. Nhấn `Ctrl+C` để dừng máy chủ.

### 4. Tự động thu thập định kỳ (không bắt buộc)

Giữ website chạy ở cửa sổ thứ nhất. Mở cửa sổ PowerShell thứ hai và chọn **một** lệnh:

```powershell
# Thu thập, chuẩn hóa và cập nhật SQLite ngay, sau đó lặp lại mỗi 5 phút.
.\.venv\Scripts\python.exe -m recipehub.cli schedule --minutes 5 --max-items 10
```

Hoặc dùng 30 phút:

```powershell
# Thu thập, chuẩn hóa và cập nhật SQLite ngay, sau đó lặp lại mỗi 30 phút.
.\.venv\Scripts\python.exe -m recipehub.cli schedule --minutes 30 --max-items 10
```

Bộ lập lịch chạy trên máy đang mở, bắt đầu ngay rồi lặp theo khoảng thời gian. Máy và tiến trình phải tiếp tục hoạt động; tắt máy hoặc đóng terminal sẽ dừng việc thu thập. Dừng bằng `Ctrl+C` trong cửa sổ lịch.

Chat và bộ lập lịch dùng chung khóa cập nhật dữ liệu để tránh ghi đè file khi chạy đồng thời. Các lượt cập nhật sẽ chờ nhau; website vẫn có thể đọc công thức đã lập chỉ mục. Nếu gặp lỗi tạm thời khi ghi dữ liệu hoặc cập nhật SQLite, bộ lập lịch ghi lỗi và thử lại ở chu kỳ tiếp theo. Nguồn TheMealDB lưu cả món cuối từng quốc gia và quốc gia kế tiếp, nên giới hạn nhỏ như `--max-items 1` vẫn lần lượt đi qua các quốc gia đã cấu hình.

## Đưa bộ sưu tập local lên Render qua GitHub

Nhóm có thể thu thập trên máy cá nhân, xuất các công thức đã lập chỉ mục thành `seed/recipes.json`, rồi đưa tệp này cùng mã nguồn lên GitHub. Khi Render triển khai và chạy `serve`, máy chủ tự nạp tệp mặc định này nếu có. Việc khôi phục bộ sưu tập từ tệp không cần kết nối tới nguồn công thức hoặc Gemini.

Mỗi lần muốn thêm món lên website, làm theo thứ tự:

1. Chạy `pipeline` ở local để thu thập, chuẩn hóa và cập nhật kho công thức.
2. Chạy `export-seed` để cập nhật `seed/recipes.json` từ kho local.
3. Commit và push mã nguồn cùng tệp JSON lên nhánh GitHub mà Render đang theo dõi. Chọn tài khoản `trithanh1577` hoặc `Ngan3112` cho lần push đó.
4. Chờ Render triển khai commit mới, rồi kiểm tra bộ sưu tập trên website.

Chạy ở local chưa cập nhật website Render. File SQLite trong `data/` được Git bỏ qua; tệp được dùng để chuyển công thức qua GitHub là `seed/recipes.json`. Cần xuất lại tệp này sau mỗi đợt bổ sung dữ liệu.

### 1. Thu thập và xuất dữ liệu trên máy

Chạy trong thư mục gốc bằng PowerShell:

```powershell
# Thu thập tối đa 10 công thức từ mỗi nguồn, chuẩn hóa và cập nhật SQLite trong một lượt.
.\.venv\Scripts\python.exe -m recipehub.cli pipeline --max-items 10
# Xuất các công thức hiện có trong SQLite thành seed/recipes.json để đưa lên GitHub.
.\.venv\Scripts\python.exe -m recipehub.cli export-seed
```

Tệp xuất giữ các bản ghi công thức và thông tin nguồn. Tệp này không chứa hội thoại, khóa API, bộ nhớ đệm bản dịch hoặc dữ liệu thô. `export-seed` lấy dữ liệu đã lập chỉ mục trong SQLite; khi có dữ liệu thô mới, chạy `pipeline` hoặc `normalize` rồi `build` trước khi xuất.

Nếu cần chọn tệp xuất hoặc chủ động nhập dữ liệu vào SQLite, dùng:

```powershell
# Xuất bộ sưu tập vào đường dẫn tự chọn thay cho seed/recipes.json.
.\.venv\Scripts\python.exe -m recipehub.cli export-seed --output seed/recipes-backup.json
# Nhập thủ công từ seed/recipes.json vào SQLite hiện tại.
.\.venv\Scripts\python.exe -m recipehub.cli import-seed
# Nhập thủ công từ một tệp khác.
.\.venv\Scripts\python.exe -m recipehub.cli import-seed --input seed/recipes-backup.json
```

Nhập dữ liệu theo mã bản ghi nên không tạo thêm bản sao của cùng mã. Các công thức khác đã có trong SQLite và phiên bản mới hơn được giữ lại. Lệnh `serve` tự thực hiện bước nhập từ `seed/recipes.json` khi khởi động nếu tệp tồn tại, nên không cần chạy `import-seed` riêng mỗi lần mở website.

### 2. Đưa tệp lên GitHub và cấu hình Render

Sau khi xuất, chọn tài khoản GitHub cho lần xuất bản đó rồi đưa mã nguồn và `seed/recipes.json` lên repository của nhóm. Bộ sưu tập local chỉ xuất hiện trên website Render sau khi đã xuất lại tệp, đưa bản mới lên GitHub và Render triển khai thành công.

Trong phần cài đặt dịch vụ Render, dùng **Build Command** sau để cài thư viện:

```bash
pip install -r requirements.txt
```

Dùng **Start Command** sau để mở máy chủ, lắng nghe cổng Render cấp và cho phép origin của website:

```bash
python -m recipehub.cli serve --host 0.0.0.0 --port $PORT --allow-origin https://ecipe-atlas.onrender.com
```

Nếu dịch vụ đang có lệnh khởi động chạy `crawl`, `normalize`, `build` hoặc `pipeline` trước `serve`, thay toàn bộ Start Command bằng lệnh trên để khởi động từ bộ dữ liệu đã đóng gói. Các biến cấu hình hiện có, bao gồm cấu hình Gemini phía máy chủ, vẫn được sử dụng; tính năng này không cần thêm biến môi trường.

Trên **Render Free**, `seed/recipes.json` là bộ dữ liệu nền được khôi phục sau khi ổ đĩa tạm bị làm mới hoặc dịch vụ triển khai lại. Công thức mới chỉ thu thập trên Render mà chưa xuất và đưa lên GitHub có thể mất khi ổ đĩa tạm bị làm mới. Để cập nhật bộ dữ liệu nền, tiếp tục thu thập ở local, xuất lại rồi xuất bản và triển khai phiên bản mới. Xem [giới hạn lưu trữ của Render Free](https://render.com/docs/free).

### 3. Kiểm tra dữ liệu sau khi triển khai

Trên máy local, xem số món trong tệp đã xuất:

```powershell
# Đọc số công thức và thời điểm xuất của bộ dữ liệu chuẩn bị đưa lên GitHub.
Get-Content .\seed\recipes.json -Raw -Encoding UTF8 | ConvertFrom-Json | Select-Object recipe_count, exported_at
```

Sau khi Render triển khai thành công, mở [API trạng thái của website](https://ecipe-atlas.onrender.com/api/v1/health). `status` cần là `ok`; `recipes` cần ít nhất bằng `recipe_count` trong tệp đã triển khai. Số món có thể lớn hơn nếu máy chủ còn giữ các món đã thu thập riêng.

Trong Logs của Render, dòng `startup_import` cho biết kết quả nhập và số công thức sau khi khởi động. Vào bộ sưu tập để tìm một món vừa thêm, mở công thức để kiểm tra nguồn rồi hỏi trợ lý về món đó. Nếu vẫn thấy bộ dữ liệu cũ, kiểm tra commit đã được Render triển khai có chứa bản `seed/recipes.json` mới và Start Command đã dùng lệnh `serve` ở trên.

## Các lệnh chính

| Lệnh | Chức năng |
| --- | --- |
| `python -m recipehub.cli crawl --max-items 10` | Thu thập dữ liệu thô từ nguồn đang bật. Có thể thêm `--source themealdb` để chọn nguồn. |
| `python -m recipehub.cli normalize` | Chuẩn hóa dữ liệu và ghi báo cáo chất lượng. |
| `python -m recipehub.cli build` | Tạo/cập nhật chỉ mục SQLite. `index` cũng là tên lệnh tương đương. |
| `python -m recipehub.cli pipeline --max-items 10` | Thu thập, chuẩn hóa và lập chỉ mục trong một lượt. |
| `python -m recipehub.cli stats` | Xem số bản ghi thô, đã xử lý, đã lập chỉ mục và vùng miền. |
| `python -m recipehub.cli export-seed` | Xuất công thức trong SQLite thành `seed/recipes.json`; thêm `--output` để chọn tệp khác. |
| `python -m recipehub.cli import-seed` | Nhập công thức từ `seed/recipes.json`; thêm `--input` để chọn tệp khác. |
| `python -m recipehub.cli serve` | Nạp tệp dữ liệu nền nếu có rồi chạy website và API tại `127.0.0.1:8000`. |
| `python -m recipehub.cli schedule --minutes 5 --max-items 10` | Chạy pipeline ngay rồi lặp lại mỗi 5 phút cho tới khi dừng tiến trình. |
| `python -m recipehub.cli schedule --days 1 --max-items 10` | Chạy pipeline ngay rồi lặp lại mỗi ngày. |

Trong PowerShell, dùng `.\.venv\Scripts\python.exe` thay cho `python` nếu chưa kích hoạt môi trường ảo.

## Luồng dữ liệu

```text
API / website công thức đã chọn / Gemini Search khi thiếu món
                         ↓
             Crawler và bộ lập lịch
                         ↓
       data/raw/ — bản chụp gốc và nguồn
                         ↓
        Chuẩn hóa, kiểm tra, báo cáo
                         ↓
    data/processed/ — RecipeRecord JSON
                         ↓
       SQLite + FTS5 — kho tri thức
                         ↓
     HTTP API + website + trợ lý hỏi đáp
```

Khi chạy trên máy cá nhân, các bản chụp thô, bản ghi đã chuẩn hóa, tiến độ crawler, manifest, cơ sở dữ liệu và bộ nhớ đệm bản dịch đều được lưu trên đĩa trong `data/`. Chúng không bị xóa khi dừng máy chủ hoặc đóng VS Code. SQLite hiện ở `data/knowledge_base.sqlite3`; hội thoại lưu mã các công thức liên quan và điều kiện loại trừ trong SQLite, tự hết hạn sau một giờ. Bản dịch thành công được lưu ở `data/state/translation_cache.json` để dùng lại sau khi chạy lại. Việc giữ dữ liệu trên Render Free được mô tả ở phần triển khai phía trên.

## Cấu trúc thư mục

| Đường dẫn | Chức năng |
| --- | --- |
| `config/recipe_sources.json` | Nguồn dữ liệu, cấu hình và thông tin ghi nguồn. |
| `seed/recipes.json` | Bản xuất công thức được đưa lên GitHub để tự nạp vào SQLite khi máy chủ khởi động. |
| `data/raw/` | Bản chụp gốc được nhóm theo nguồn và lượt thu thập. |
| `data/processed/recipes/` | Công thức JSON đã chuẩn hóa. |
| `data/processed/quality_report.json` | Báo cáo bản ghi hợp lệ, lỗi và trùng tiềm năng. |
| `data/state/crawl_cursors.json` | Tiến độ tiếp tục thu thập của các nguồn có phân trang. |
| `data/state/crawl_manifest.jsonl` | Lịch sử thu thập, URL và thời điểm của từng bản ghi thô. |
| `data/state/translation_cache.json` | Bản dịch thành công để tránh dịch lại mỗi lần mở món. |
| `data/knowledge_base.sqlite3` | Cơ sở tri thức và phiên ngữ cảnh hội thoại trên máy. |
| `recipehub/recipe_crawler.py` | Adapter nguồn, tải dữ liệu và ghi data lake. |
| `recipehub/normalize.py` | Chuẩn hóa RecipeRecord, kiểm tra dữ liệu và báo cáo chất lượng. |
| `recipehub/models.py`, `recipehub/text.py` | Lược đồ bản ghi và hàm xử lý văn bản/định danh. |
| `recipehub/knowledge_base.py` | SQLite, FTS5, truy vấn, bộ lọc và phiên hội thoại. |
| `recipehub/conversation.py` | Tìm công thức, quản lý ngữ cảnh, gọi Gemini và phát hiện món mới. |
| `recipehub/gemini.py` | Tích hợp Gemini phía máy chủ, dịch và lưu bộ nhớ đệm. |
| `recipehub/server.py` | HTTP API, phục vụ website và xử lý ngôn ngữ giao diện. |
| `recipehub/cli.py` | Các lệnh `crawl`, `normalize`, `build`, `pipeline`, `stats`, `export-seed`, `import-seed`, `serve`, `schedule`. |
| `recipehub/seed.py` | Xuất và nhập tệp dữ liệu nền chứa các bản ghi công thức. |
| `recipehub/ingestion_lock.py` | Khóa cập nhật dữ liệu dùng chung giữa các luồng chat và tiến trình thu thập. |
| `frontend/` | Website song ngữ, trang bộ sưu tập, chi tiết công thức và khung chat. |
| `docs/` | Quyết định kiến trúc, hợp đồng dữ liệu/API, bàn giao và trình bày. |
| `tests/`, `frontend/tests/` | Kiểm thử pipeline/backend và giao diện. |
| `.github/workflows/ci.yml` | Tự động kiểm tra trên GitHub Actions. |

## Phân công thành viên

- **Người 1 — Nguyễn Thành Trí (`2474802010400`):** chọn và kết nối nguồn, thu thập dữ liệu, lưu bản gốc, metadata, tiến độ và lịch chạy.
- **Người 2 — Phạm Thị Khánh Ngân (`2474802016786`):** lược đồ công thức chung, chuẩn hóa, kiểm tra chất lượng và báo cáo bản ghi trùng tiềm năng.
- **Người 3 — Nguyễn Dũng (`2474802015692`):** cơ sở tri thức SQLite/FTS5, API backend, truy xuất, hội thoại và tích hợp Gemini phía máy chủ.
- **Người 4 — Nguyễn Trần Hoàng Nhân (`2474802010272`):** website song ngữ, bộ lọc, chi tiết công thức, trích dẫn và giao diện hỏi đáp.

Hợp đồng dữ liệu nằm trong [docs/integration-contract.md](docs/integration-contract.md); API website trong [docs/frontend-api-contract.md](docs/frontend-api-contract.md); quyết định kiến trúc trong [docs/architecture-decisions.md](docs/architecture-decisions.md).

## Nội dung báo cáo và trình bày cuối kỳ

Trình bày chủ đề và nguồn dữ liệu; cách crawler lưu bản gốc và tiến độ; cách chuẩn hóa và kiểm soát chất lượng; kiến trúc SQLite/FTS5; luồng từ câu hỏi tới bản ghi và trích dẫn; một lần chạy thu thập thực tế; và giới hạn về độ phủ dữ liệu, giấy phép, dịch, dị ứng cùng lịch chạy cục bộ. Dùng `stats` để báo cáo số liệu thực tế, không trình bày mục tiêu thu thập như số liệu đã đạt. Mỗi thành viên cần giải thích phần việc của mình. Xem [docs/presentation-outline.md](docs/presentation-outline.md) để theo thứ tự demo.

## Kiểm tra

Các lệnh sau dành cho lúc nhóm muốn tự kiểm tra; chúng không cần thiết để khởi động website:

```powershell
# Chạy các kiểm thử Python từ thư mục gốc.
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
# Kiểm tra và chạy kiểm thử giao diện JavaScript.
cd frontend
npm run check
npm test
```

Kiểm tra tích hợp HTTP cần máy chủ đang chạy và dữ liệu đã thu thập. Trong thư mục `frontend/`, chạy `npm run test:integration`.
