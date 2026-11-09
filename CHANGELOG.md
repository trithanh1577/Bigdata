# Nhật ký thay đổi

File này ghi lại các thay đổi gần nhất của dự án để nhóm tiện theo dõi. Mục mới nhất ở trên; các thay đổi bên dưới chưa được xác nhận là đã phát hành cho đến khi được đẩy lên GitHub.

## 2026-11-10 — Hoàn thiện luồng ứng dụng

- Mở rộng CLI với các lệnh tạo/cập nhật cơ sở tri thức SQLite, chạy website cùng HTTP API và lập lịch thu thập theo phút hoặc ngày.
- Bổ sung crawler cho trang công thức dùng Schema.org `Recipe`; lưu dữ liệu gốc, URL, thông tin nguồn và lịch sử thu thập trước khi chuẩn hóa.
- Hoàn thiện chuẩn hóa và kiểm tra chất lượng bản ghi; thêm tìm kiếm và lọc công thức trong SQLite.
- Nối API với website song ngữ để tìm kiếm, xem công thức, hỏi đáp có trích dẫn và hiển thị cảnh báo khi chưa dịch được nội dung.
- Cập nhật tài liệu kiến trúc, hợp đồng API, hướng dẫn bàn giao cho thành viên 3–4 và dàn ý thuyết trình cuối kỳ.
- Bổ sung/cập nhật kiểm thử cho crawler, chuẩn hóa dữ liệu và luồng khám phá công thức.

## Ghi chú cấu hình

- Khóa API được cấu hình cục bộ trong `.env`; không đưa khóa vào mã nguồn, changelog hoặc GitHub.
- Bộ lập lịch chạy trên máy cục bộ; máy cần bật và có kết nối Internet trong thời gian thu thập.
