# Ví dụ yêu cầu: draft cho giải bóng rổ (dữ liệu giả)

Tài liệu mẫu cho người có nền BA. **Các con số dưới đây (4 đội, 12 cầu thủ, 8 pick) chỉ là dữ liệu ví dụ.**
Luật thật của giải bạn do ban tổ chức quyết định — đừng chép câu trả lời của ví dụ vào giải thật.

---

## 1. Những câu hỏi ban tổ chức phải trả lời trước

Ghi câu trả lời vào cột "Quyết định". Chưa biết thì để **"CHƯA QUYẾT"** — phần mềm không được tự đoán.

| # | Câu hỏi | Quyết định (điền) | Ảnh hưởng tới phần mềm |
|---|---|---|---|
| 1 | Ai tham gia draft? (đội trưởng, huấn luyện viên, quản lý?) | | Có bao nhiêu "người dùng", ai được ghi pick |
| 2 | Có bao nhiêu đội? | | Số dòng `teams.csv`, độ dài vòng draft |
| 3 | Mỗi đội chọn tối đa bao nhiêu cầu thủ? | | Tổng số pick = đội × số cầu thủ |
| 4 | Thứ tự: cố định, snake, ngẫu nhiên hay tuỳ chỉnh? | | Nội dung `draft_order.csv` (thứ tự là **dữ liệu**, không phải code) |
| 5 | Có trao đổi pick không? | | Nếu có: thứ tự phải sửa được và có lịch sử → khó hơn nhiều |
| 6 | Cầu thủ chia theo vị trí / nhóm / tier? | | Cột `position`, bộ lọc |
| 7 | Có đồng hồ đếm giờ mỗi pick? | | Cần timer, và luật khi hết giờ (auto-pick?) |
| 8 | Ai được phép ghi pick? | | Một người (ban tổ chức) hay nhiều người → quyết định có cần đăng nhập không |
| 9 | Pick có thể sửa/huỷ không? Ai quyết định? | | Cần "hoàn tác" và lịch sử |
| 10 | Khán giả có cần thấy kết quả ngay khi ghi? | | "Ngay lập tức" nghĩa là cần máy chủ (Giai đoạn D) |
| 11 | Draft diễn ra trên một máy hay nhiều thiết bị? | | Một máy → đơn giản; nhiều thiết bị → trạng thái dùng chung |
| 12 | Sau sự kiện cần giữ lại gì? Trong bao lâu? | | Xuất CSV, trang kết quả lưu trữ |
| 13 | Thông tin nào của người chơi thật được công khai? (nhất là người dưới 18 tuổi) | | Chỉ đưa lên web thứ đã được đồng ý; dùng ID + biệt danh nếu cần |

## 2. Từ câu trả lời sang tài liệu BA (ví dụ đã điền cho 4 đội / 12 người)

### Tác nhân (actors)
- **Ban tổ chức (1 người):** nhập dữ liệu, ghi pick, hoàn tác, xuất kết quả.
- **Khán giả:** chỉ xem kết quả đã công bố.
- **Đội trưởng:** không thao tác trong ví dụ này (họ nói tên, ban tổ chức ghi).

### User stories
- Là ban tổ chức, tôi thấy **đội nào đang đến lượt** để không chọn nhầm đội.
- Là ban tổ chức, tôi chọn một cầu thủ còn lại để **ghi pick**, và hệ thống không cho chọn người đã bị chọn.
- Là ban tổ chức, tôi **hoàn tác pick cuối** nếu ghi nhầm, và lịch sử vẫn còn.
- Là ban tổ chức, tôi **nhập danh sách từ Excel** và được báo lỗi rõ ràng trước khi dữ liệu thay đổi.
- Là khán giả, tôi xem **bảng draft** và đội hình từng đội.
- Là ban tổ chức, tôi **xuất kết quả** ra CSV để lưu và công bố.

### Yêu cầu chức năng
1. Hiển thị đội đang đến lượt theo `draft_order.csv`.
2. Ghi pick cho đội đang đến lượt; không cho pick ngoài lượt.
3. Từ chối cầu thủ đã chọn hoặc không đủ điều kiện.
4. Hoàn tác pick cuối (đánh dấu `void`, không xoá).
5. Nhập CSV, kiểm tra **trước khi** áp dụng (xem mục 3).
6. Xuất `draft_results.csv` và bản sao lưu JSON.
7. Bảng draft và đội hình tự cập nhật sau mỗi thay đổi.

### Quy tắc nghiệp vụ (business rules) — của ví dụ, không phải của giải thật
- BR1: Mỗi cầu thủ chỉ được chọn **một lần** (tính trên các pick `official`).
- BR2: Mỗi `overall_pick` có **tối đa một** kết quả `official`.
- BR3: Pick được ghi **theo thứ tự**: không có pick 5 nếu chưa có pick 4.
- BR4: Chỉ cầu thủ `eligible` mới được chọn.
- BR5: Hoàn tác chỉ áp dụng cho pick **gần nhất**; sửa pick cũ hơn = hoàn tác dần về đó.
- BR6: Thứ tự draft (ví dụ snake) nằm trong `draft_order.csv`; đổi thứ tự = sửa dữ liệu, không sửa code.

### Từ điển dữ liệu
| File | Cột | Ghi chú |
|---|---|---|
| `teams.csv` | `team_id`, `team_name` | `team_id` duy nhất, không đổi |
| `players.csv` | `player_id`, `player_name`, `position`, `eligibility_status` | `eligible` / `ineligible` |
| `draft_order.csv` | `overall_pick`, `team_id` | `overall_pick` 1..N liên tục |
| `draft_results.csv` | `overall_pick`, `player_id`, `status` | `official` / `void` |

**Vì sao dùng ID, không dùng tên?** Hai người có thể trùng tên, tên có dấu/viết hoa/viết tắt khác nhau, và tên có thể đổi.
ID thì ổn định. Mọi file tham chiếu nhau bằng ID, và phần mềm báo lỗi nếu ID không tồn tại.

### Ngoại lệ và tình huống biên
- Hai file dùng cùng `player_id` → từ chối cả lô nhập.
- Cầu thủ rút lui giữa chừng → đổi `eligibility_status`; nếu đã được pick thì cần quyết định thủ công (không để phần mềm tự xoá).
- Ghi nhầm pick → hoàn tác pick cuối rồi ghi lại.
- Đóng tab giữa chừng → trạng thái vẫn còn trong trình duyệt đó, nhưng **hãy xuất CSV sau mỗi vài pick**.
- Mất mạng → bản local chạy được, vì không cần máy chủ (đó cũng là giới hạn: không chia sẻ).
- Tên có dấu phẩy hoặc dấu nháy → CSV phải đặt trong ngoặc kép; phần mềm phải đọc đúng.

### Tiêu chí chấp nhận (acceptance criteria)
- [ ] Mở trang với dữ liệu mẫu: thấy "Pick 9" của Team Rồng đang đến lượt, 4 cầu thủ còn lại.
- [ ] Chọn Bảo Long → pick 9 hiện tên, đội kế tiếp là Team Hổ, còn 3 cầu thủ.
- [ ] Bảo Long biến mất khỏi danh sách còn lại (không thể chọn lần hai; nếu cố ghi trùng bằng cách khác, hệ thống từ chối).
- [ ] Hoàn tác → quay về pick 9, Bảo Long còn lại; bản xuất CSV có dòng `9,P08,void`.
- [ ] Nhập `players_duplicate_id.csv` → hiện lỗi `E_DUP_ID`, **dữ liệu cũ không đổi**.
- [ ] Tải lại trang → trạng thái còn nguyên (cùng trình duyệt).
- [ ] Xem trên điện thoại ~390 px: không bị cắt chữ.

### Ngoài phạm vi (non-goals) — giai đoạn đầu
Đăng nhập, nhiều người ghi cùng lúc, đồng hồ đếm giờ, trao đổi pick, đồng bộ thời gian thực, thanh toán, tự gửi thông báo.

## 3. Lộ trình theo giai đoạn

| Giai đoạn | Làm được | Lưu ở đâu | Cần máy chủ? |
|---|---|---|---|
| **A. Bảng chỉ xem** | Hiển thị đội, thứ tự, cầu thủ, pick mẫu từ file CSV. Đăng lên GitHub Pages | Trong file CSV (trong repo) | Không |
| **B. Một người ghi pick** | Ghi, hoàn tác, chống trùng, xuất CSV | `localStorage` của trình duyệt đó | Không |
| **C. Công bố kết quả cho mọi người** | Ban tổ chức xuất CSV rồi **cập nhật file trong repo/Sheet và đăng lại** | File công bố | Không (cập nhật thủ công, có độ trễ) |
| **D. Draft trực tiếp nhiều người** | Nhiều thiết bị cùng thấy và/hoặc cùng ghi theo thời gian thực | Cơ sở dữ liệu dùng chung | **Có** (đăng nhập, quyền ghi, chống ghi trùng) |

**Chỉ lên D nếu thật sự cần** khán giả từ xa thấy tức thì hoặc nhiều người cùng ghi. Với giải ở một địa điểm, thường
A + B + C là đủ: một laptop ban tổ chức nối máy chiếu, và kết quả đăng lên sau mỗi vòng.

## 4. Kiểm tra trước ngày thật (diễn tập)
1. Chạy cả draft giả với đúng người, đúng thiết bị, đúng mạng của ngày thi đấu.
2. Cố tình ghi sai một pick và hoàn tác.
3. Cố tình đóng tab giữa chừng rồi mở lại.
4. Xuất CSV và mở bằng Excel để chắc rằng đọc được.
5. Chuẩn bị bản dự phòng: danh sách giấy + file CSV mới nhất.
