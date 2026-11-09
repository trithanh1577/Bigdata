# Global Culinary Knowledge Base

Dự án thử nghiệm cục bộ xây dựng kho tri thức ẩm thực: thu thập công thức từ các nguồn công khai, giữ lại dữ liệu gốc, chuẩn hóa thành bản ghi thống nhất, lập chỉ mục trong SQLite và cung cấp website có trích dẫn nguồn.

Giao diện website hỗ trợ tiếng Việt và tiếng Anh; lựa chọn được lưu trong trình duyệt. Gemini có thể xử lý câu hỏi bằng một trong hai ngôn ngữ, trả lời theo ngôn ngữ giao diện và dịch nội dung công thức khi hiển thị. Tên nhà cung cấp, liên kết, giấy phép và thông tin ghi công được giữ theo nguồn. Khi chưa cấu hình Gemini, website vẫn tìm kiếm và trả lời cơ bản từ dữ liệu hiện có; nội dung công thức giữ ngôn ngữ nguồn.

**Trợ lý nhà bếp** tra cơ sở tri thức SQLite trước. Nếu không tìm thấy công thức phù hợp, Gemini có thể chuyển cụm tìm kiếm sang tiếng Anh rồi tìm trên web; crawler chỉ nhận trang công thức có Schema.org `Recipe`, lưu bản gốc, chuẩn hóa và thêm vào SQLite. Trợ lý trả lời dựa trên bản ghi đó kèm trích dẫn, và giữ ngữ cảnh cho câu hỏi tiếp theo trong cùng phiên. Với dị ứng, hệ thống chỉ nêu cách thay thế nếu nguồn ghi rõ hoặc gợi ý công thức khác dựa trên thành phần đã thu thập; hệ thống không xác nhận món ăn an toàn và không tự bịa nguyên liệu thay thế.

Dự án không bắt buộc dùng Wikibooks. Có thể chọn API hoặc website công thức phù hợp. Bộ thu thập hỗ trợ TheMealDB, Wikibooks Cookbook và trang có dữ liệu JSON-LD `Recipe` theo Schema.org. Có thể thêm URL trang món ăn mới trong `config/recipe_sources.json`; trang không có cấu trúc này cần bộ phân tích riêng. Khi người dùng hỏi món chưa có trong kho, Gemini có thể tìm trên web, tải tối đa ba trang công thức có cấu trúc phù hợp, lưu bản gốc vào data lake, chuẩn hóa rồi cập nhật chỉ mục trước khi trả lời. Website cho phép tìm công thức, lọc nguyên liệu cần tránh, xem nguồn gốc và hỏi đáp dựa trên bản ghi có trích dẫn.

**Phạm vi hiện tại:** quy trình thu thập và chuẩn hóa dữ liệu (thành viên 1–2), cơ sở tri thức SQLite và HTTP API (thành viên 3), website tích hợp API (thành viên 4). Hỏi đáp cơ bản mặc định truy xuất dữ liệu theo quy tắc, không cần API mô hình AI. Có thể cấu hình Gemini để hiểu câu hỏi linh hoạt hơn, tìm món còn thiếu và dịch nội dung công thức; khóa API chỉ được lưu trong `.env` phía máy chủ, không đưa vào mã frontend hay gửi tới trình duyệt. Câu hỏi có thể nhập bằng tiếng Anh hoặc tiếng Việt; câu trả lời và nội dung bộ sưu tập theo ngôn ngữ đang chọn trên giao diện.

## Công nghệ sử dụng

- Python 3.11 trở lên: thu thập, chuẩn hóa, lập chỉ mục và chạy máy chủ HTTP.
- SQLite và FTS5: lưu cơ sở tri thức cục bộ và tìm kiếm toàn văn; được hỗ trợ qua thư viện chuẩn của Python.
- `requests` và Beautiful Soup: gọi API nguồn và phân tích nội dung.
- HTML, CSS và JavaScript trên trình duyệt: xây dựng website.
- GitHub Actions: chạy các bước kiểm tra Python và giao diện website.

## Cách chạy dự án trên Windows bằng PowerShell

Mở cửa sổ PowerShell trong VS Code tại thư mục gốc chứa mã nguồn. Máy cần cài Python 3.11 trở lên và có kết nối Internet.

### 1. Tạo môi trường và cài thư viện

Chạy các lệnh sau một lần:

```powershell
# Tạo môi trường Python riêng cho dự án trong thư mục .venv.
python -m venv .venv
# Cài các thư viện mà dự án cần vào môi trường vừa tạo.
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Tạo file .env từ mẫu nếu máy chưa có; không ghi đè cấu hình/khóa đã lưu.
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Mở `.env`, đặt `CRAWLER_USER_AGENT` thành tên dự án kèm email liên hệ thật hoặc URL dự án công khai. Wikibooks yêu cầu User-Agent có thông tin liên hệ. Không đưa tệp `.env` hoặc thông tin bí mật lên GitHub. Khóa phát triển của TheMealDB đã được cấu hình cho mục đích học tập; cần tuân thủ yêu cầu ghi nguồn và điều khoản của dịch vụ.

Phần hỏi đáp cơ bản truy xuất dữ liệu hoạt động mà không cần khóa API mô hình AI. Để bật Gemini cho hỏi đáp linh hoạt, dịch nội dung và tự tìm món chưa có, điền `RECIPEHUB_LLM_API_KEY` trong `.env` phía máy chủ; endpoint và model Gemini đã có sẵn trong mẫu. Khởi động lại máy chủ sau khi sửa `.env`. Không dán khóa vào README, mã nguồn hoặc frontend. Mô hình trả lời dựa trên công thức đã truy xuất; kết quả tìm web chỉ được nhập vào kho khi trang có dữ liệu Recipe JSON-LD. Tìm kiếm grounding có thể dùng hạn mức hoặc phát sinh chi phí theo tài khoản Gemini; kiểm tra mức sử dụng trước khi chạy thường xuyên. Nếu chat hiện lỗi `429` như đã hết hạn mức/giới hạn yêu cầu, Gemini không thể trả lời hoặc tìm web cho đến khi tài khoản được cấp lại hạn mức; kiểm tra mức sử dụng/tùy chọn thanh toán hoặc dùng khóa có hạn mức còn lại trong `.env` rồi khởi động lại máy chủ.

Để thêm một website thủ công, thêm một đối tượng vào mảng trong `config/recipe_sources.json`:

```json
{
  "id": "ten_nguon",
  "name": "Tên website công thức",
  "type": "schema_org_recipe",
  "urls": ["https://site.example/recipe-page"],
  "language": "en",
  "license": "Ghi chú điều khoản của website",
  "terms_url": "https://site.example/terms",
  "attribution": "Ghi công theo yêu cầu của website",
  "enabled": true
}
```

Thay URL ví dụ bằng trang công thức công khai thật, kiểm tra điều khoản và thông tin ghi công của trang đó. Crawler chỉ lấy công thức có dữ liệu Schema.org `Recipe`; không có một bộ phân tích chung đọc đúng mọi bố cục HTML.

### 2. Thu thập dữ liệu và tạo cơ sở tri thức

Chạy lần lượt các lệnh sau từ thư mục gốc. `--max-items 10` giới hạn số mục lấy trong một lượt để chạy thử:

```powershell
# Thu thập tối đa 10 mục từ mỗi nguồn và lưu dữ liệu gốc.
.\.venv\Scripts\python.exe -m recipehub.cli crawl --max-items 10
# Chuẩn hóa và kiểm tra các dữ liệu vừa thu thập.
.\.venv\Scripts\python.exe -m recipehub.cli normalize
# Tạo/cập nhật chỉ mục SQLite để website có thể tìm kiếm dữ liệu.
.\.venv\Scripts\python.exe -m recipehub.cli build
# Hiển thị số lượng và tình trạng dữ liệu hiện có.
.\.venv\Scripts\python.exe -m recipehub.cli stats
```

`crawl` lấy dữ liệu từ các nguồn và lưu bản chụp gốc; `normalize` chuẩn hóa và kiểm tra dữ liệu; `build` cập nhật cơ sở tri thức SQLite; `stats` hiển thị số liệu hiện có.

### 3. Mở website và dùng phần hỏi đáp

Trong cửa sổ PowerShell thứ nhất, chạy:

```powershell
# Khởi chạy website cùng HTTP API trên máy cục bộ.
.\.venv\Scripts\python.exe -m recipehub.cli serve
```

Nếu đã thu thập dữ liệu và chỉ muốn mở website lần sau, chỉ cần chạy lệnh `serve`; không cần crawl lại mỗi lần. Lệnh `serve` đọc chỉ mục SQLite đã lưu trên máy.

Mở **http://127.0.0.1:8000** trên trình duyệt. Website và các điểm cuối API `/api/v1` cùng chạy trên địa chỉ này. Bấm **Tiếng Việt / English** ở thanh điều hướng để đổi ngôn ngữ; lựa chọn được lưu trong trình duyệt đó. Dùng khung hỏi đáp trên website để hỏi về các món đã thu thập, ví dụ nguyên liệu, cách chế biến, thời gian hoặc vùng miền. Để dừng máy chủ, quay lại cửa sổ PowerShell và nhấn `Ctrl+C`.

Website mặc định dùng cơ sở tri thức thật đang lưu trên máy. Nếu chưa thu thập hoặc lập chỉ mục dữ liệu, danh sách món sẽ trống; website không tự thay bằng dữ liệu mẫu.

Để kiểm tra dịch vụ, mở **http://127.0.0.1:8000/api/v1/health**. Trường `status` cần là `ok`; `recipes` cho biết số công thức đã lập chỉ mục. `language_model_available` và `web_discovery_available` cho biết cấu hình Gemini đã được nạp. Sau đó thử hỏi một món trong website để kiểm tra luồng chat; health chỉ xác nhận cấu hình, không tự gửi yêu cầu kiểm tra khóa tới Gemini.

### 4. Tự động thu thập mỗi 5 hoặc 30 phút (không bắt buộc)

Để website tiếp tục hoạt động, giữ máy chủ ở cửa sổ PowerShell thứ nhất. Mở cửa sổ PowerShell thứ hai trong VS Code và chọn một lịch chạy:

Chạy mỗi 5 phút:

```powershell
# Thu thập tối đa 10 mục mỗi nguồn, rồi chuẩn hóa và cập nhật kho dữ liệu mỗi 5 phút.
.\.venv\Scripts\python.exe -m recipehub.cli schedule --minutes 5 --max-items 10
```

Hoặc chạy mỗi 30 phút:

```powershell
# Thu thập tối đa 10 mục mỗi nguồn, rồi chuẩn hóa và cập nhật kho dữ liệu mỗi 30 phút.
.\.venv\Scripts\python.exe -m recipehub.cli schedule --minutes 30 --max-items 10
```

Chỉ chạy một trong hai lệnh trên, không khởi động đồng thời hai bộ lập lịch.

Bộ lập lịch sẽ thu thập, chuẩn hóa và cập nhật cơ sở tri thức ngay khi khởi động, sau đó lặp lại theo lịch. Máy cần luôn bật và có Internet. Có thể dùng `--days 1` để chạy hằng ngày hoặc `--days 7` để chạy hằng tuần. Khoảng thời gian được tính giữa thời điểm bắt đầu mỗi lượt; nếu một lượt chạy lâu hơn khoảng đã đặt, lượt tiếp theo bắt đầu ngay khi lượt hiện tại kết thúc. Đây là bộ lập lịch chạy trên máy cục bộ, không phải dịch vụ nền trên Internet. Nhấn `Ctrl+C` trong cửa sổ PowerShell thứ hai để dừng.

### Lệnh thường dùng

Chạy các lệnh này từ thư mục gốc của dự án. `crawl`, `normalize` và `build` thường chạy theo thứ tự; `serve` chạy website/API; `schedule` tự lặp lại ba bước xử lý dữ liệu.

| Lệnh | Chức năng |
| --- | --- |
| `python -m recipehub.cli crawl --max-items 10` | Thu thập tối đa 10 công thức từ mỗi nguồn trong một lượt và lưu bản gốc vào `data/raw/`. |
| `python -m recipehub.cli normalize` | Đọc dữ liệu gốc, chuẩn hóa về cấu trúc chung và ghi bản ghi cùng báo cáo chất lượng vào `data/processed/`. |
| `python -m recipehub.cli build` | Tạo hoặc cập nhật chỉ mục tìm kiếm SQLite từ dữ liệu đã chuẩn hóa. |
| `python -m recipehub.cli stats` | Hiển thị số bản ghi thô, đã chuẩn hóa, đã lập chỉ mục và phân bố vùng miền. |
| `python -m recipehub.cli serve` | Chạy website và HTTP API tại `http://127.0.0.1:8000`; dừng bằng `Ctrl+C`. |
| `python -m recipehub.cli schedule --minutes 5 --max-items 10` | Chạy thu thập, chuẩn hóa và cập nhật SQLite ngay, rồi lặp lại mỗi 5 phút cho đến khi nhấn `Ctrl+C`. |

Trong các lệnh trên, thay `python` bằng `\.venv\Scripts\python.exe` nếu chưa kích hoạt môi trường ảo. Các lệnh kiểm thử được ghi ở mục **Kiểm tra dự án** phía dưới; chúng không cần chạy để khởi động website.

## Luồng dữ liệu

```text
API hoặc website công thức đã chọn
              ↓
Bộ thu thập và bộ lập lịch
              ↓
       data/raw (bản chụp gốc)
              ↓
      Chuẩn hóa và kiểm tra
              ↓
   data/processed (bản ghi JSON)
              ↓
    Cơ sở tri thức SQLite + FTS
              ↓
      HTTP API và website công thức
```

Khi thiếu món, Gemini Search có thể tìm URL công thức, sau đó bộ thu thập chỉ lưu các trang có JSON-LD `Recipe`. Bản ghi được thêm vào data lake, chuẩn hóa và lập chỉ mục; bản gốc luôn giữ thông tin URL và ghi công. Nếu trang không có dữ liệu có cấu trúc hoặc không tải được, trang đó không được thêm.

Bản chụp gốc và tệp kê khai thu thập lưu lại mã nguồn, liên kết, thông tin ghi công, ghi chú điều khoản và thời điểm thu thập. Các bản ghi đã chuẩn hóa dùng chung cấu trúc `RecipeRecord` nhưng vẫn giữ riêng phiên bản của từng nhà cung cấp. Công thức tương tự được đánh dấu để xem xét thay vì tự động gộp. Lệnh `build` cập nhật chỉ mục SQLite từ các tệp JSON đã xử lý.

Dữ liệu thu thập được lưu trên đĩa tại `data/raw/`, `data/processed/` và `data/state/recipes.sqlite3`; tắt máy chủ không xóa các tệp này. Bản dịch thành công được lưu trong `data/state/translation_cache.json` để dùng lại sau khi khởi động lại. Lịch sử hội thoại hiện chỉ ở bộ nhớ và sẽ đặt lại khi khởi động lại máy chủ.

Giao diện hỏi đáp truy xuất các bản ghi đó và trả về trích dẫn nguồn. Chế độ không dùng mô hình AI có thể trả lời các câu hỏi phổ biến về nguyên liệu, hướng dẫn, thời gian, vùng miền và nguyên liệu thay thế do nguồn cung cấp. Có thể cấu hình mô hình ngôn ngữ tùy chọn để diễn đạt linh hoạt hơn, dựa trên dữ liệu đã truy xuất. Trường thông tin bị thiếu phải được xem là chưa rõ. Hệ thống không được tự bịa nguyên liệu thay thế, dinh dưỡng, thông tin dị ứng hoặc kết luận an toàn y tế. Bộ lọc nguyên liệu chỉ so khớp văn bản nên không phát hiện được mọi nguyên liệu ẩn hoặc nguy cơ nhiễm chéo.

## Cấu trúc thư mục mã nguồn

| Đường dẫn | Chức năng |
| --- | --- |
| `config/recipe_sources.json` | Cấu hình API nguồn, vùng miền và ghi chú ghi nguồn |
| `data/raw/` | Bản chụp dữ liệu gốc, được nhóm theo nhà cung cấp và lượt thu thập |
| `data/processed/recipes/` | Các bản ghi công thức JSON đã chuẩn hóa |
| `data/processed/quality_report.json` | Báo cáo chất lượng dữ liệu |
| `data/state/crawl_manifest.jsonl` | Tệp kê khai lưu lịch sử thu thập và URL nguồn |
| `data/state/crawl_cursors.json` | Tiến độ thu thập của từng nguồn |
| `data/state/recipes.sqlite3` | Cơ sở tri thức SQLite được tạo trên máy; Git bỏ qua tệp này |
| `data/state/translation_cache.json` | Bản dịch nội dung công thức đã tạo thành công để dùng lại giữa các lần chạy |
| `recipehub/recipe_crawler.py` | Bộ kết nối nguồn, thử lại khi lỗi, lưu dữ liệu gốc và hỗ trợ bộ lập lịch |
| `recipehub/normalize.py` | Cấu trúc dữ liệu công thức chung, phân tích, kiểm tra chất lượng và báo cáo bản ghi trùng tiềm năng |
| `recipehub/knowledge_base.py` | Chỉ mục SQLite, bộ lọc, danh mục và tìm kiếm toàn văn |
| `recipehub/api.py` | Máy chủ website, HTTP API và dịch vụ hỏi đáp có trích dẫn |
| `recipehub/cli.py` | Các lệnh `crawl`, `normalize`, `build`, `stats`, `schedule` và `serve` |
| `frontend/` | Website song ngữ để tìm món, xem chi tiết, lọc và hỏi đáp |
| `docs/` | Quyết định kiến trúc, cấu trúc dữ liệu, API và tài liệu bàn giao |
| `tests/` | Kiểm thử quy trình xử lý dữ liệu Python |
| `frontend/tests/` | Kiểm thử JavaScript của website |
| `.github/workflows/ci.yml` | Các bước kiểm tra tự động trên GitHub Actions |

## Phân công công việc

- **Thành viên 1 — Nguyễn Thành Trí (`2474802010400`):** chọn nguồn, xây bộ thu thập qua API, lưu bản chụp gốc và thông tin nguồn, xử lý thử lại, vị trí tiếp tục thu thập và lịch thu thập.
- **Thành viên 2 — Phạm Thị Khánh Ngân (`2474802016786`):** xây cấu trúc dữ liệu công thức chung, chuẩn hóa, kiểm tra dữ liệu và báo cáo các bản ghi có khả năng trùng.
- **Thành viên 3 — Nguyễn Dũng (`2474802015692`):** xây cơ sở tri thức SQLite, tìm kiếm toàn văn, các điểm truy cập API, truy xuất và câu trả lời dựa trên nguồn.
- **Thành viên 4 — Nguyễn Trần Hoàng Nhân (`2474802010272`):** xây website tìm kiếm, bộ lọc, chi tiết công thức, trích dẫn nguồn và giao diện hỏi đáp.

Quy ước bàn giao dữ liệu chung được mô tả trong [integration-contract.md](docs/integration-contract.md). Các điểm truy cập API của website được ghi trong [frontend-api-contract.md](docs/frontend-api-contract.md); ghi chú triển khai của thành viên 3 nằm trong [person-3-delivery.md](docs/person-3-delivery.md).

## Báo cáo và thuyết trình cuối kỳ

Báo cáo cuối kỳ cần trình bày kiến trúc và lý do chọn kiến trúc, phần đã triển khai, một thử nghiệm nhỏ và các giới hạn hiện tại. Bài trình chiếu và phần bảo vệ trực tiếp nên trình bày:

1. Chủ đề, nguồn dữ liệu, ghi công/điều khoản và thông tin mỗi nguồn cung cấp.
2. Một lượt thu thập dữ liệu và nơi lưu bản chụp gốc, tệp kê khai cùng tiến độ thu thập.
3. Quá trình chuẩn hóa theo cấu trúc dữ liệu chung, kiểm tra dữ liệu và xử lý các bản ghi có khả năng trùng.
4. Cách tạo cơ sở tri thức SQLite và tìm theo nguyên liệu/vùng miền, gồm cả bộ lọc loại trừ.
5. Cách đặt câu hỏi trên website và mở trích dẫn để xem bản ghi gốc.
6. Bộ lập lịch hằng ngày/hằng tuần, cách hệ thống xử lý dữ liệu nguồn bị thiếu và lý do kết quả lọc dị ứng không phải cam kết an toàn.

Mỗi thành viên cần giải thích và trình diễn phần việc được giao. Mục tiêu khoảng năm vùng miền, 100–150 món, nhiều nguồn và một số danh mục là mục tiêu thu thập, không phải số liệu đã có sẵn trong thư mục mã nguồn. Khi thuyết trình, hãy báo cáo số liệu thực tế từ lệnh `stats`.

Tham khảo [dàn ý trình chiếu và thứ tự trình diễn trực tiếp](docs/presentation-outline.md) khi chuẩn bị thuyết trình.

## Kiểm tra dự án

Bộ kiểm thử Python dùng phản hồi mô phỏng nên không cần truy cập các nguồn dữ liệu trực tiếp:

```powershell
# Chạy bộ kiểm thử Python từ thư mục gốc của dự án.
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Các bước kiểm tra giao diện website cần Node.js 24; không cần cài thêm gói npm:

```powershell
# Chuyển vào thư mục chứa mã nguồn website.
cd frontend
# Kiểm tra cú pháp các tệp JavaScript của website.
npm run check
# Chạy các kiểm thử JavaScript của website.
npm test
```

GitHub Actions tự chạy cả hai nhóm kiểm tra. Thu thập dữ liệu trực tiếp vẫn phụ thuộc vào kết nối Internet, hoạt động của API/trang nguồn và User-Agent có thông tin liên hệ thật đối với các nguồn yêu cầu điều đó. Wikibooks đang tắt mặc định; có thể bật lại nếu nhóm muốn dùng và đã cấu hình User-Agent phù hợp.
