# Nhật ký thay đổi

Các thay đổi được ghi từ mới đến cũ. Dự án hiện chưa phát hành phiên bản đánh số.

## 2026-11-10

### Sửa lỗi

- Dùng chung từ nguyên liệu Việt–Anh cho tìm kiếm bộ sưu tập và lọc nguyên liệu cần tránh trong chat; giữ tên gốc và tránh khớp nhầm từ ngắn bên trong nguyên liệu khác.
- Ưu tiên món được nêu rõ trong câu hỏi mới thay vì tiếp tục trả lời món cũ chỉ vì câu có đại từ; câu xã giao không trả công thức ngẫu nhiên.
- Kiểm tra cấu trúc bản dịch Gemini trước khi sử dụng; phản hồi sai định dạng trả lại nội dung gốc thay vì ngắt yêu cầu của website.
- Khóa cập nhật dữ liệu dùng chung giữa thread và tiến trình để chat, crawler, chuẩn hóa và nhập SQLite không tranh chấp file tạm hoặc manifest. Thêm hậu tố duy nhất cho mỗi lượt thu thập.
- Giữ scheduler hoạt động qua lỗi ghi dữ liệu/SQLite tạm thời và lưu vị trí quốc gia kế tiếp để lượt thu thập ít món không bỏ qua các quốc gia phía sau.

### Thêm

- Thêm `export-seed` để xuất công thức đã lập chỉ mục thành `seed/recipes.json`, có thể đưa lên GitHub. Server tự nhập bộ này khi khởi động; `import-seed` hỗ trợ nhập thủ công. Chỉ xuất bản ghi công thức kèm nguồn, không xuất hội thoại, khóa API hoặc cache.
- Hợp nhất dữ liệu mẫu với dữ liệu đã thu thập theo ID và thời điểm cập nhật, để deploy lại hoặc chạy crawler không làm mất các món đã có trong bộ sưu tập.
- Tích hợp backend gồm cơ sở tri thức SQLite/FTS5, dịch vụ hội thoại, HTTP API và máy chủ phục vụ website.
- Bổ sung Gemini tùy chọn để trả lời dựa trên công thức đã truy xuất, chuyển câu hỏi tiếng Việt sang cụm tìm kiếm tiếng Anh, dịch nội dung công thức và tìm món chưa có bằng Google Search grounding.
- Cho phép crawler nhận tối đa ba trang được tìm thấy khi mỗi trang có dữ liệu Schema.org `Recipe` dạng JSON-LD. Dữ liệu gốc, URL và thông tin nguồn được lưu trước khi chuẩn hóa và lập chỉ mục.
- Lưu bộ nhớ đệm bản dịch và ngữ cảnh hội thoại trên đĩa để có thể dùng lại sau khi khởi động lại máy chủ.
- Bổ sung CLI cho `build`, `serve`, `stats` và lịch thu thập theo phút hoặc ngày; website và API chạy cùng máy chủ cục bộ.

### Cập nhật

- Kết nối website tiếng Việt/tiếng Anh với API để tìm kiếm, lọc, xem chi tiết công thức và nhận câu trả lời có trích dẫn nguồn.
- Cải thiện nhận diện câu hỏi và nguyên liệu cần tránh bằng tiếng Việt; áp dụng lại bộ lọc dị ứng trong hội thoại tiếp nối.
- Trả lời theo ngôn ngữ câu hỏi khi nhận diện được tiếng Việt; phân biệt lỗi Gemini/API, không có kết quả web và trang thiếu Recipe JSON-LD thay vì chỉ báo chung là không tìm thấy.
- Cập nhật README, hợp đồng dữ liệu/API, quyết định kiến trúc, tài liệu bàn giao thành viên và hướng dẫn trình bày cuối kỳ.

### Lưu ý

- Gemini không bắt buộc. Khóa được đọc ở backend từ `.env`; không lưu khóa trong mã nguồn, frontend, tài liệu hoặc GitHub.
- Chỉ trang có cấu trúc Recipe JSON-LD được nhận tự động; điều khoản tái sử dụng của từng website vẫn cần được nhóm kiểm tra.
- Dữ liệu dị ứng từ nguồn có thể thiếu. Bộ lọc nguyên liệu không xác nhận món ăn an toàn và không thay thế tư vấn y tế.
- Bộ lập lịch chạy trên máy cục bộ; máy và tiến trình phải hoạt động để tiếp tục thu thập.
