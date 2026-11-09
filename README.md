# Global Culinary Knowledge Base

Dự án cuối kỳ xây dựng kho tri thức ẩm thực và website **Trợ lý nhà bếp**. Hệ thống thu thập công thức từ API hoặc trang web công khai, lưu bản gốc vào data lake, chuẩn hóa dữ liệu, lập chỉ mục bằng SQLite rồi cung cấp tìm kiếm, bộ lọc, trang chi tiết và hỏi đáp có trích dẫn nguồn.

Người dùng có thể hỏi bằng tiếng Việt hoặc tiếng Anh. Backend tìm trong bộ sưu tập trước; nếu không có công thức phù hợp và Gemini đã được cấu hình, hệ thống tìm trang công thức trên web, chỉ lưu trang có Schema.org `Recipe` dạng JSON-LD, sau đó chuẩn hóa và lập chỉ mục trước khi trả lời. Nội dung công thức có thể được dịch theo ngôn ngữ giao diện; các liên kết, nguồn, giấy phép và thông tin ghi công vẫn giữ nguyên.

Gemini là tùy chọn. Không có Gemini, website vẫn tìm và trả lời theo các trường có trong cơ sở dữ liệu nhưng không thể dịch nội dung tùy ý hay tự tìm món mới. Khóa API chỉ nằm trong `.env` ở backend, không nằm trong frontend. Câu trả lời về dị ứng không xác nhận món ăn an toàn; bộ lọc nguyên liệu không phát hiện được mọi tên gọi, nguyên liệu ẩn hoặc lây nhiễm chéo.

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

## Các lệnh chính

| Lệnh | Chức năng |
| --- | --- |
| `python -m recipehub.cli crawl --max-items 10` | Thu thập dữ liệu thô từ nguồn đang bật. Có thể thêm `--source themealdb` để chọn nguồn. |
| `python -m recipehub.cli normalize` | Chuẩn hóa dữ liệu và ghi báo cáo chất lượng. |
| `python -m recipehub.cli build` | Tạo/cập nhật chỉ mục SQLite. `index` cũng là tên lệnh tương đương. |
| `python -m recipehub.cli stats` | Xem số bản ghi thô, đã xử lý, đã lập chỉ mục và vùng miền. |
| `python -m recipehub.cli serve` | Chạy website và API cùng máy chủ tại `127.0.0.1:8000`. |
| `python -m recipehub.cli schedule --minutes 5 --max-items 10` | Chạy pipeline ngay rồi lặp lại mỗi 5 phút cho tới khi dừng tiến trình. |
| `python -m recipehub.cli schedule --days 1 --max-items 10` | Chạy pipeline ngay rồi lặp lại mỗi ngày. |

Trong PowerShell, dùng `\.venv\Scripts\python.exe` thay cho `python` nếu chưa kích hoạt môi trường ảo.

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

Các bản chụp thô, bản ghi đã chuẩn hóa, tiến độ crawler, manifest, cơ sở dữ liệu và bộ nhớ đệm bản dịch đều được lưu trên đĩa trong `data/`. Chúng không bị xóa khi dừng máy chủ hoặc đóng VS Code. SQLite hiện ở `data/knowledge_base.sqlite3`; hội thoại lưu mã các công thức liên quan và điều kiện loại trừ trong SQLite, tự hết hạn sau một giờ. Bản dịch thành công được lưu ở `data/state/translation_cache.json` để dùng lại sau khi chạy lại.

## Cấu trúc thư mục

| Đường dẫn | Chức năng |
| --- | --- |
| `config/recipe_sources.json` | Nguồn dữ liệu, cấu hình và thông tin ghi nguồn. |
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
| `recipehub/cli.py` | Các lệnh `crawl`, `normalize`, `build`, `stats`, `serve`, `schedule`. |
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
