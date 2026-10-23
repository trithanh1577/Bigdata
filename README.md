# Global Culinary Knowledge Base

Kho tri thức ẩm thực đa quốc gia: tự động lấy dữ liệu món ăn từ nhiều nguồn Internet, lưu bản gốc vào data lake, chuẩn hoá thành một định dạng chung để các phần knowledge base và website có thể dùng tiếp.

> **Phạm vi code hiện tại:** chỉ triển khai nhiệm vụ Người 1 và Người 2 (crawler, data lake, chuẩn hoá dữ liệu). Knowledge base/backend hỏi đáp và website là phần việc của Người 3 và Người 4, chưa được triển khai trong repo.

## Tổng quan và luồng dữ liệu

```text
TheMealDB API ─┐
               ├─> Crawler/Scheduler ─> data/raw/ ─> Chuẩn hoá/kiểm tra ─> data/processed/
Wikibooks API ─┘                                                        │
                                      schema chung + provenance ────────┘
```

- **Data lake (`data/raw/`)** giữ snapshot JSON nguyên gốc từ API, tên nguồn, URL, giấy phép/điều khoản, thời điểm thu thập và metadata từng lần chạy.
- **Processed data (`data/processed/`)** chứa recipe JSON cùng schema, giữ định lượng gốc, thông tin nguồn và báo cáo chất lượng.
- Mỗi công thức từ một nguồn được giữ thành một record riêng. Các món cùng tên chỉ được đánh dấu là ứng viên trùng để người vận hành xem xét, không tự gộp các phiên bản hợp lệ.
- Chỉ lưu thông tin dị ứng/dinh dưỡng/mẹo/thay thế nếu nguồn có cung cấp; không suy đoán. Ảnh được lưu dưới dạng URL nguồn, không tải/copy file ảnh.
- Mục tiêu demo theo tài liệu đề xuất: khoảng 5 quốc gia, 100–150 món, 2–3 nguồn và 5–8 nhóm món. Đây là mục tiêu mở rộng dữ liệu, không phải số liệu đã có sẵn trong repo.

## Nguồn dữ liệu hiện cấu hình

1. **TheMealDB API** — endpoint chính thức, đang dùng test key `1` cho mục đích phát triển/giáo dục; giữ attribution và tuân thủ [điều khoản TheMealDB](https://www.themealdb.com/terms_of_use.php). Không crawl trực tiếp website thay cho API.
2. **Wikibooks Cookbook API** — lấy trang trong danh mục công thức; giữ URL/attribution. Phần lớn văn bản Wikibooks theo CC BY-SA 4.0 và GFDL, nhưng cần xem thông báo license riêng của từng trang/media; đọc [chính sách bản quyền Wikibooks](https://en.wikibooks.org/wiki/Wikibooks:Copyrights).

Danh sách nguồn, vùng ẩm thực và metadata được đặt trong [`config/recipe_sources.json`](config/recipe_sources.json). Nguồn mới chỉ được thêm sau khi kiểm tra API/robots, điều khoản sử dụng, attribution và quyền lưu trữ. Với TheMealDB, tài liệu nói free API dành cho phát triển và học tập; không xem đó là giấy phép cho phát hành ứng dụng công khai.

## Công nghệ

- Python 3.11+
- `requests` để gọi API; `BeautifulSoup` để trích xuất phần công thức từ HTML do Wikibooks API trả về
- JSON cho raw snapshots và normalized records; JSONL không bắt buộc trong PoC này
- File system làm data lake cục bộ; GitHub Actions kiểm tra cú pháp
- Database quan hệ/full-text, vector search, backend API, LLM và website là các lựa chọn/đầu việc cho Người 3–4, chưa thuộc phần code hiện tại. Vector database là một công cụ truy xuất, không đồng nghĩa với knowledge base.

## Cấu trúc repo

```text
.
├── config/
│   └── recipe_sources.json       # Danh sách API/nguồn và quy tắc nguồn
├── data/
│   ├── raw/                      # Snapshot theo nguồn/lần crawl/record
│   ├── processed/
│   │   ├── recipes/              # Recipe JSON đã chuẩn hoá, chia theo nguồn
│   │   └── quality_report.json   # Bản ghi lỗi và ứng viên trùng
│   └── state/
│       ├── crawl_cursors.json    # Tiến độ phân trang/crawl giữa các lần chạy
│       └── crawl_manifest.jsonl  # Nhật ký URL đã thu thập + liên kết tới raw snapshot
├── docs/
│   ├── architecture-decisions.md # Quyết định và giới hạn kiến trúc
│   └── integration-contract.md   # Contract raw → processed cho phần kế tiếp
├── recipehub/
│   ├── recipe_crawler.py         # Người 1: API adapters, scheduler input, raw lake
│   ├── normalize.py              # Người 2: parse, chuẩn hoá, kiểm tra chất lượng
│   ├── models.py                 # Schema RecipeRecord/Ingredient dùng chung
│   ├── text.py                   # Làm sạch chuỗi, chuẩn hoá tên, ID/hash
│   ├── config.py                 # Paths, source config và crawler settings
│   └── cli.py                    # Các lệnh crawl/normalize/schedule/stats
├── tests/                        # Kiểm tra parser và logic crawl bằng dữ liệu giả lập
├── .github/workflows/ci.yml      # Kiểm tra cú pháp trên GitHub Actions
├── .env.example                  # Mẫu User-Agent/delay/timeout; tự tạo .env cục bộ
├── requirements.txt              # Dependencies runtime
└── README.md                     # Tổng quan, hướng dẫn chạy, phân công
```

### Recipe schema chung

Mỗi record giữ tên gốc và tên chuẩn hoá, vùng/quốc gia, URL ảnh nếu nguồn có, mô tả, nguyên liệu (tên gốc, lượng gốc, đơn vị và tên chuẩn), khẩu phần, thời gian, độ khó, dụng cụ, bước nấu, mẹo, thay thế, allergens/nutrition nếu có nguồn, cùng provenance (nguồn, URL, license/terms, collected/updated time). Trường không có trong nguồn để trống; không tự sinh.

Contract chi tiết nằm trong [`docs/integration-contract.md`](docs/integration-contract.md).

## Phân công 4 thành viên

### Người 1 — Nguyễn Thành Trí (`2474802010400`)

- Chọn/kiểm tra các nguồn được phép; triển khai API adapters và crawl theo cấu hình.
- Lấy record và snapshot JSON nguyên gốc vào `data/raw/<source>/runs/<run_id>/records/`.
- Giữ URL, attribution, điều khoản/license, ID nguồn và thời điểm thu thập; xử lý timeout/429 và giới hạn tốc độ.
- Thiết lập crawl định kỳ hằng ngày hoặc hằng tuần; không cần crawl recipe mỗi 30 phút.

### Người 2 — Phạm Thị Khánh Ngân (`2474802016786`)

- Đồng thiết kế schema Recipe/Ingredient với Người 1 để các nguồn khác nhau cùng đưa vào pipeline.
- Đọc raw snapshot, chuẩn hoá tên/nguyên liệu/đơn vị khi xác định được, trích xuất định lượng và các trường recipe.
- Kiểm tra trường bắt buộc/chất lượng dữ liệu, tạo `data/processed/` và báo cáo lỗi/ứng viên trùng.
- Bảo toàn từng recipe/version theo nguồn; không gộp mù quáng món cùng tên.

**Cách phối hợp Người 1–2:** thống nhất schema và ví dụ raw→processed trước; Người 1 sở hữu `recipe_crawler.py`/`config/`, Người 2 sở hữu `normalize.py`/schema. Cùng review contract nhưng tránh sửa chồng cùng module.

### Người 3 — Nguyễn Dũng (`2474802015692`) — phần cần làm

- Xây database/knowledge base từ `data/processed/`, truy vấn chính xác và full-text search.
- Làm backend/API cho tìm món, lọc, xem chi tiết và hỏi đáp có trích dẫn nguồn.
- Quản lý ngữ cảnh hội thoại; nếu dùng LLM, chỉ tổng hợp kết quả đã truy xuất, không tự bịa nguyên liệu, dị ứng hay dinh dưỡng.
- Hỗ trợ lọc món theo nguyên liệu người dùng khai báo dị ứng/không ăn; chỉ gợi ý nguyên liệu thay thế khi có dữ liệu nguồn, không cam kết món an toàn y tế.
- Có thể cân nhắc vector search sau khi baseline SQL/full-text chạy.

### Người 4 — Nguyễn Trần Hoàng Nhân (`2474802010272`) — phần cần làm

- Xây website tìm kiếm/khám phá và giao diện hội thoại; làm theo API contract của Người 3.
- Hiển thị công thức, nguồn/attribution, lọc theo quốc gia/loại món/thời gian/độ khó khi dữ liệu có trường đó.
- Cho phép nhập yêu cầu dị ứng/kiêng ăn và hiển thị rõ nguồn cùng giới hạn dữ liệu.
- Dùng mock response để phát triển giao diện song song, sau đó tích hợp backend.

## Cách chạy phần Người 1–2 (PowerShell trong VS Code)

Yêu cầu Python 3.11 trở lên.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Trước khi crawl, tạo `.env` cục bộ và sửa `CRAWLER_USER_AGENT` thành tên bot có email liên hệ thật hoặc URL repo/site công khai của dự án theo [chính sách truy cập API Wikimedia](https://www.mediawiki.org/wiki/Wikimedia_APIs/Access_policy). Placeholder trong `.env.example` không được chấp nhận. Ví dụ:

```powershell
Copy-Item .env.example .env
```

Mở `.env` trong VS Code để sửa dòng `CRAWLER_USER_AGENT`. Không đưa `.env` lên GitHub. Nếu chưa muốn dùng Wikibooks, có thể tạm đặt `"enabled": false` cho nguồn đó trong `config/recipe_sources.json`.

Crawl tối đa 10 recipe mỗi nguồn trong một lần chạy (thay đổi được):

```powershell
python -m recipehub.cli crawl --max-items 10
```

Chuẩn hoá snapshot mới nhất của mỗi recipe, sau đó xem số lượng và độ phủ quốc gia:

```powershell
python -m recipehub.cli normalize
python -m recipehub.cli stats
```

Chạy crawl + chuẩn hoá tự động mỗi ngày; dùng `--days 7` để chạy hằng tuần. Terminal phải để mở; `Ctrl+C` để dừng:

```powershell
python -m recipehub.cli schedule --days 1 --max-items 10
```

Scheduler chạy tuần tự hai bước crawl rồi normalize. TheMealDB lưu ID cuối theo từng vùng; Wikibooks lưu token phân trang để các lần chạy tiếp tục ở vị trí kế tiếp. Tiến độ nằm trong `data/state/crawl_cursors.json`. Mỗi raw record được ghi thêm thành một dòng trong `data/state/crawl_manifest.jsonl` gồm URL, nguồn, thời điểm thu thập và đường dẫn snapshot; chạy lại cùng trang sẽ tạo thêm dòng lịch sử. Lệnh `crawl` báo mã lỗi nếu có nguồn thất bại; lệnh `normalize` báo mã lỗi nếu có record không hợp lệ. Cả hai in JSON để xem chi tiết nguồn/nguyên nhân.

Chạy kiểm tra cục bộ (chỉ dùng dữ liệu giả lập, không gọi Internet):

```powershell
python -m compileall -q recipehub
python -m unittest discover -s tests -v
```

Dữ liệu sinh ra nằm trong `data/`, được Git bỏ qua để không đẩy raw snapshots, recipe content hoặc DB cục bộ lên GitHub. Không commit `.env` hoặc API secrets.

## Giới hạn PoC

Phần Người 1–2 hiện cung cấp ingestion và normalized data lake; chưa có UI, API backend, relational/vector knowledge base hay câu trả lời LLM. Chất lượng parse phụ thuộc cấu trúc mỗi nguồn; các trường không lấy được sẽ rỗng và được báo cáo, không được suy đoán. Recipe cùng món có thể là các phiên bản khác nhau. Nguồn hiện cấu hình không cung cấp dữ liệu dị ứng hoặc nguyên liệu thay thế có cấu trúc một cách đầy đủ, nên các trường này thường để trống. Phần lọc theo dị ứng/thay thế là nhiệm vụ tích hợp của Người 3–4 và không được trình bày như cam kết an toàn y tế.
