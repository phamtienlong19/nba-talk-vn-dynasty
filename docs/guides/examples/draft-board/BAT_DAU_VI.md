# Bắt đầu nhanh — bảng draft ví dụ (dữ liệu giả)

Đây là một bản **thử** để bạn thấy bảng draft chạy và tập đổi dữ liệu. **Chưa phải** công cụ đủ tin cậy cho giải thật (xem cuối trang).

## Chạy trong 2 phút (không cần cài gì)
1. Giải nén file ZIP.
2. Bấm đúp **`index.html`** (mở bằng Chrome hoặc Edge).
3. Trang sẽ yêu cầu chọn file: bấm **"Chọn file CSV…"**, vào thư mục **`data/`**, chọn **cả 4 file** (`teams.csv`, `players.csv`, `draft_order.csv`, `draft_results.csv`) rồi mở.
4. Bạn sẽ thấy Team Rồng đang đến lượt pick 9. Thử chọn một cầu thủ, rồi bấm **Hoàn tác pick cuối**.

(Vì sao phải chọn file? Mở bằng cách bấm đúp thì trình duyệt không cho trang tự đọc các file khác.)

## Cách tốt hơn: chạy máy chủ local (trang tự đọc `data/`)
Mở terminal trong thư mục này:
- **Mac:** `python3 -m http.server 8000` (máy có thể hỏi cài công cụ phát triển lần đầu)
- **Windows:** `py -m http.server 8000` (cần cài Python từ python.org)

Rồi mở `http://localhost:8000`. Dừng bằng Ctrl+C. Ngại terminal thì cứ dùng nút chọn file.

## Đổi sang dữ liệu của bạn
1. Mở 4 file CSV trong `data/` bằng Excel hoặc Google Sheets, giữ **nguyên tên cột**, thay nội dung bằng dữ liệu của bạn. Lưu lại dưới dạng **CSV UTF-8**.
2. Dùng **ID** (T1, P01…) cho đội và cầu thủ; mọi file tham chiếu nhau bằng ID, không bằng tên.
3. Bấm **"Nhập file CSV…"** và chọn lại các file. Nếu có lỗi, trang liệt kê từng lỗi (file + dòng) và **không đổi** dữ liệu hiện có.
4. Nếu sửa file mà trang không đổi: bấm **"Xoá dữ liệu đã lưu"** (trang ưu tiên bản đã lưu trong trình duyệt).

Muốn xem trang báo lỗi: nhập thử các file trong `data-invalid/` (xem `data-invalid/README.md`).

## Tài liệu trong gói này
- `REQUIREMENTS_EXAMPLE_VI.md` — 13 câu hỏi luật cần ban tổ chức trả lời + ví dụ tài liệu yêu cầu kiểu BA.
- `README.md` (tiếng Anh) — chi tiết kỹ thuật và giới hạn.
- Hướng dẫn đầy đủ: bản `BASKETBALL_DRAFT_FAST_START_VI.md` trong kho GitHub của dự án.

## Bản thử ≠ dùng thật cho giải
**Có:** bảng draft, ghi pick, hoàn tác, chống chọn trùng, nhập CSV có kiểm tra, xuất kết quả.

**Chưa có / chưa đủ tin cậy:**
- Pick chỉ lưu **trong trình duyệt của một máy** — không chia sẻ cho ai, mất nếu xoá dữ liệu trình duyệt, và mỗi cách mở (`file://`, `localhost`, link công khai) là một "nơi lưu" khác nhau.
- **Không có đăng nhập/phân quyền.** Nút ẩn đi không phải bảo mật.
- Chưa có đồng hồ đếm giờ, trao đổi pick, nhiều người cùng ghi, cập nhật thời gian thực.
- Chưa được diễn tập với luật và con người của giải bạn.

**Trước khi dùng cho giải thật:** diễn tập cả draft với đúng thiết bị và người; ghi sai một pick rồi hoàn tác; đóng tab giữa chừng rồi mở lại; xuất CSV sau mỗi vài pick; chuẩn bị bản giấy dự phòng; chạy bản trên laptop (không cần internet); chỉ nhập dữ liệu người thật khi họ đã đồng ý (đặc biệt người dưới 18 tuổi).
