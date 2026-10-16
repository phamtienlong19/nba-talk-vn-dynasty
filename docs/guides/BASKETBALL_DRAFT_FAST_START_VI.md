# Draft bóng rổ bằng AI — bản làm nhanh đêm nay

Dành cho người đã có ý tưởng cụ thể (ví dụ: tổ chức giải bóng rổ có draft) và muốn có **một bản thử chạy được** ngay tối nay,
không cần biết lập trình. Tài liệu này dùng **dữ liệu giả** (4 đội, 12 cầu thủ). Luật draft thật của giải bạn do ban tổ chức quyết định.

---

## Trả lời nhanh

**1. Tối nay cài/mở gì?**
- Một **chat AI miễn phí** (ChatGPT, Claude hoặc Gemini) trên trình duyệt — để lên kế hoạch.
- Trình duyệt Chrome/Edge (có công cụ developer).
- Một **thư mục dự án** trên máy. Cách nhanh nhất: tải sẵn ví dụ của hướng dẫn này (xem bước 1 bên dưới) — bạn có một bảng draft chạy được sau ~5 phút, **chưa cần AI**.
- Khi muốn sửa theo ý mình: **VS Code** (miễn phí) + **một** công cụ AI viết code (xem mục 5). Cần thêm một tài khoản **GitHub** miễn phí để dùng Copilot Free và để đưa trang lên mạng (tuỳ chọn).

**2. Nên dùng AI nào?** Bắt đầu với thứ bạn **đã có**. Không cần mua nhiều gói.
- Chưa trả tiền gì: chat AI miễn phí để lên kế hoạch + **GitHub Copilot Free trong VS Code** để viết code (có giới hạn hàng tháng).
- Đã có ChatGPT trả phí → thử **Codex**. Đã có Claude Pro/Max → **Claude Code**. Dùng cái nào cũng được; đừng đổi qua đổi lại.
- Muốn xem giao diện ngay không cần cài gì → công cụ tạo app trên web (Lovable, Bolt, Replit…), nhưng coi đó là **bản phác thảo**, vì credit miễn phí rất ít (xem mục 5).

**3. Nhờ AI làm gì đầu tiên?** Không phải "viết code". Hãy nhờ AI **hỏi bạn** để chốt luật và dữ liệu (prompt 1), rồi mới nhờ dựng một **bảng draft chỉ-xem** (prompt 2).

**4. Chuẩn bị thông tin gì?** Danh sách đội, danh sách cầu thủ (có vị trí), thứ tự draft, và **13 câu hỏi luật** ở mục 2. Chưa biết câu nào thì ghi "chưa quyết".

**5. Dữ liệu vào website thế nào?** Qua **4 file CSV** (xuất từ Excel/Google Sheets): `teams`, `players`, `draft_order`, `draft_results`. Trang đọc file, **kiểm tra** (trùng ID, thiếu cột, sai tham chiếu…) rồi mới dùng. Chi tiết ở mục 3.

**6. Xong buổi đầu bạn có gì?** Một trang chạy trên máy bạn: bảng draft, đội đang đến lượt, danh sách cầu thủ còn lại, ghi pick, hoàn tác, xuất kết quả CSV, và báo lỗi khi file nhập sai. Nếu muốn, đưa lên GitHub Pages thành một đường link xem được.

**7. Chưa có gì (và đừng hứa với ai là có)? — bản thử ≠ dùng thật cho giải**
- **Không chia sẻ trực tiếp** giữa nhiều thiết bị: pick được lưu **trong trình duyệt của một máy**.
- **Không có đăng nhập / phân quyền thật.** Nút ẩn đi không phải là bảo mật.
- Không có đồng hồ đếm giờ, trao đổi pick, hay cập nhật theo thời gian thực.
- **Bản này là bản thử, chưa phải công cụ đủ tin cậy cho giải thật.** Muốn dùng thật phải qua danh sách ở mục 7: diễn tập đầy đủ, xuất CSV thường xuyên, bản dự phòng, chạy trên laptop của ban tổ chức, và quyết định rõ ai là người ghi pick chính thức.

Mục tiêu: có kết quả đầu tiên trong khoảng 30–90 phút. Thời gian thật phụ thuộc cài đặt và đăng nhập tài khoản.

---

## 1. Tối nay làm gì, theo thứ tự

### Bước 1 — Xem một bảng draft chạy thật (5–10 phút, chưa cần AI)
1. Tải gói ví dụ [`downloads/draft-board-example.zip`](downloads/draft-board-example.zip) (trên GitHub: mở file rồi bấm biểu tượng tải xuống hoặc *View raw*) và giải nén. Gói chỉ có ví dụ bảng draft + dữ liệu giả + hướng dẫn, không có gì khác của dự án.
2. Mở thư mục đã giải nén, **bấm đúp `index.html`** (Chrome hoặc Edge). Có file `BAT_DAU_VI.md` trong đó nếu cần xem lại các bước.
3. Trang sẽ yêu cầu **chọn file CSV**: vào thư mục `data/`, chọn cả 4 file cùng lúc.
4. Bạn sẽ thấy: Team Rồng đang đến lượt **pick 9**, 4 cầu thủ còn lại. Thử chọn một người → bảng cập nhật → bấm **Hoàn tác pick cuối**.

> Vì sao phải chọn file bằng tay? Mở file bằng cách bấm đúp (địa chỉ bắt đầu bằng `file://`), trình duyệt **không cho** trang tự đọc các file khác vì lý do bảo mật.
> Cách tốt hơn: chạy một máy chủ local. Trong thư mục đó, mở terminal và gõ `python3 -m http.server 8000` (Mac; máy có thể hỏi cài công cụ phát triển lần đầu) hoặc `py -m http.server 8000` (Windows, cần cài Python từ python.org), rồi mở `http://localhost:8000`. Lúc đó trang tự đọc `data/`. Nếu ngại terminal, cứ dùng nút chọn file — kết quả như nhau.

### Cài tối thiểu khi bạn muốn sửa theo ý mình (tuỳ chọn, ~30–60 phút lần đầu)
1. Tạo tài khoản **GitHub** (github.com, miễn phí) — cần để đăng trang lên mạng và để dùng Copilot Free.
2. Cài **VS Code** (code.visualstudio.com) và mở thư mục dự án bằng *File → Open Folder…*.
3. Đăng nhập **GitHub Copilot** trong VS Code (gói Free có giới hạn hàng tháng), hoặc dùng công cụ bạn đã trả tiền (Codex, Claude Code).
4. Mở khung Chat, chọn chế độ **Agent** (chế độ sửa được file, không phải chỉ hỏi đáp).
5. Cài **GitHub Desktop** nếu muốn lưu phiên bản (commit) và đăng lên mạng mà không dùng terminal.

Từng bước nhấp chuột chi tiết (bằng tiếng Anh) ở [START_HERE.md](START_HERE.md), Bước 3, 4, 8, 9. Tên nút trong VS Code thay đổi thường xuyên; hãy tìm "Chat" và "Agent".

### Bước 2 — Lên kế hoạch với chat AI (15–20 phút)
Dán **Prompt 1** (bên dưới) vào chat AI. Trả lời các câu nó hỏi. Kết quả: một bản yêu cầu một trang. Lưu thành `BRIEF.md`.

### Bước 3 — Chuẩn bị dữ liệu của bạn (10–20 phút)
Tạo 4 sheet / 4 file CSV đúng tên cột (mục 3). Dùng **ID** (T1, P01…) cho đội và cầu thủ, đừng chỉ dùng tên.

### Bước 4 — Nhờ AI dựng bản của bạn (15–30 phút)
Mở thư mục dự án trong VS Code, dùng chế độ **Agent** của công cụ AI, dán **Prompt 2**.

### Bước 5 — Kiểm tra bằng mắt và bằng dữ liệu cố tình sai (10 phút)
Làm đúng như danh sách ở mục 6. Đừng chỉ tin câu "đã xong".

### Bước 6 — (Tuỳ chọn) Đưa lên mạng
Làm theo [START_HERE.md](START_HERE.md) bước 9–10 (GitHub Pages). **Lưu ý:** trang trên GitHub Pages miễn phí là **công khai**, ai có link cũng xem được.
Chỉ đưa lên dữ liệu giả hoặc dữ liệu người chơi đã đồng ý công khai (đặc biệt khi có người dưới 18 tuổi).

---

## 2. Bạn cần chuẩn bị gì (kỹ năng BA áp dụng thẳng)

Bạn đã quen: tác nhân, user story, quy tắc nghiệp vụ, từ điển dữ liệu, ngoại lệ, tiêu chí chấp nhận, non-goals.
Với AI, **chất lượng bản yêu cầu quyết định hầu hết kết quả**. Điền 13 câu hỏi trong
[`examples/draft-board/REQUIREMENTS_EXAMPLE_VI.md`](examples/draft-board/REQUIREMENTS_EXAMPLE_VI.md):

> ai tham gia · số đội · số cầu thủ mỗi đội · thứ tự (cố định / snake / ngẫu nhiên) · có trao đổi pick không ·
> chia nhóm cầu thủ · đồng hồ · ai được ghi pick · có sửa/huỷ pick không · khán giả có cần xem ngay không ·
> một máy hay nhiều thiết bị · lưu gì sau sự kiện · thông tin người chơi nào được công khai.

Chưa trả lời được câu nào thì ghi **"chưa quyết"**. Đừng để AI tự chọn luật cho bạn — đó là việc của ban tổ chức.
File ví dụ cũng có sẵn user story, quy tắc nghiệp vụ, ngoại lệ và tiêu chí chấp nhận đã điền cho bộ dữ liệu giả.

---

## 3. Nhập dữ liệu bằng tay hay import từ Excel/Google Sheets?

Cả hai đều dùng được. Chọn theo việc **dữ liệu có hay đổi** và **ai là người bảo trì**.

| Cách | Hợp khi | Điểm yếu |
|---|---|---|
| **Gõ tay vào file nguồn** (CSV/JS) | Bản thử nhỏ, dữ liệu cố định | Mệt khi dữ liệu đổi liên tục; dễ gõ sai không ai biết |
| **Import CSV/Excel** | Ban tổ chức vốn đã có bảng tính | Cần quy ước cột cố định; phải kiểm tra dòng lỗi/trùng trước khi áp dụng |
| **Google Sheets làm nguồn** | Nhiều người không rành kỹ thuật cùng sửa bảng | Phải chủ động *xuất/đăng* (File → Chia sẻ → Phát hành lên web) và chấp nhận **độ trễ** vài phút. Một Sheet được liên kết **không** tự là một hệ thống draft trực tiếp có phân quyền |
| **Cơ sở dữ liệu / API** | Nhiều người được phép ghi cùng lúc, cần phân quyền hoặc đồng bộ tự động | Phức tạp hơn, phải bảo trì, có thể tốn tiền |

**Khuyến nghị cho lần đầu:** Excel/Google Sheets → xuất **CSV** → trang của bạn nhập và kiểm tra. Đây cũng là cách dự án NBA Talk xử lý
việc ghi 48 pick trong một ngày: một script nhập, đối chiếu tên với ID, và từ chối pick trùng hoặc sai thứ tự — thay vì nhờ AI gõ tay 48 lần.

### Cấu trúc 4 file (xem file thật trong `examples/draft-board/data/`)

```csv
teams.csv
team_id,team_name
T1,Team Rồng

players.csv
player_id,player_name,position,eligibility_status
P01,Minh Khoa,G,eligible

draft_order.csv
overall_pick,team_id
1,T1

draft_results.csv
overall_pick,player_id,status
1,P03,official
```

(Mỗi khối trên là một file riêng; dòng đầu của từng khối là tên file, không nằm trong file.)

**Chúng liên kết với nhau thế nào:** `draft_order.team_id` → `teams.team_id`; `draft_results.player_id` → `players.player_id`;
`draft_results.overall_pick` → `draft_order.overall_pick`. `status` là `official` hoặc `void` (đã hoàn tác, vẫn giữ lịch sử).

**Vì sao dùng ID thay vì tên?** Tên có thể trùng, viết khác dấu/viết tắt, hoặc đổi. ID thì cố định, và nhờ vậy trang phát hiện được "cầu thủ này đã bị chọn rồi".

**Kiểm tra gì trước khi nhập** (để dữ liệu hiện tại **không bị đổi** nếu file lỗi):
- đủ cột đúng tên · không ô trống · không trùng `player_id`/`team_id`/`overall_pick`
- mọi tham chiếu tồn tại (đội, cầu thủ, pick) · mỗi cầu thủ chỉ bị chọn một lần · pick được ghi đúng thứ tự
- đọc CSV **đúng chuẩn**: tên có dấu phẩy (`"Trần, Minh Khoa"`) hoặc dấu nháy không được làm vỡ dữ liệu. Cắt từng dòng theo dấu phẩy là **không đủ**.

Thử ngay: trong `examples/draft-board/data-invalid/` có các file cố tình sai. Nhập chúng và xem trang báo lỗi thế nào.

---

## 4. Trang tĩnh khác gì ứng dụng "trực tiếp" (live)?

- **Trang tĩnh** (HTML/CSS/JS trên GitHub Pages): hiển thị thông tin đã được đăng. Rẻ, đơn giản, rất ổn định. **Không** có nơi để nhiều người cùng ghi dữ liệu.
- **`localStorage`**: ghi nhớ pick **trong một trình duyệt trên một thiết bị**. Tải lại trang vẫn còn. Nhưng **không** chia sẻ sang điện thoại khác, trình duyệt khác, và có thể mất nếu xoá dữ liệu trình duyệt.
- **GitHub Pages** không có máy chủ ghi dữ liệu và không có đăng nhập.
- **Google Sheet / file JSON đã đăng** là bước trung gian: ban tổ chức cập nhật, người xem tải lại sau vài phút. Bạn phải biết **ai là người quyết định kết quả chính thức** và độ trễ bao lâu.
- Một draft **thật sự live** cần: một nguồn dữ liệu chung duy nhất · chỉ người được phép mới ghi (kiểm tra ở **máy chủ**, không phải ẩn nút) ·
  chống chọn trùng khi hai người bấm cùng lúc · giữ lịch sử và sửa sai · khán giả tự cập nhật · khôi phục khi mất mạng hay đóng nhầm tab.

### Lộ trình theo giai đoạn
| | Làm được | Lưu ở đâu | Cần máy chủ? |
|---|---|---|---|
| **A. Bảng chỉ xem** | Hiển thị đội, thứ tự, cầu thủ, pick mẫu → đăng link | Trong file CSV | Không |
| **B. Một người ghi pick** | Ghi, hoàn tác, chống trùng, xuất CSV | Trình duyệt của máy ban tổ chức | Không |
| **C. Công bố kết quả** | Sau mỗi vòng, xuất CSV và **cập nhật + đăng lại** trang xem | File công bố | Không (thủ công, có độ trễ) |
| **D. Nhiều người, thời gian thực** | Nhiều thiết bị cùng thấy/ghi | Cơ sở dữ liệu chung | **Có** |

**Với giải ở một địa điểm**, thường chỉ cần A + B + C: một laptop của ban tổ chức nối màn hình/máy chiếu, kết quả đăng lên sau mỗi vòng.
Chỉ làm D nếu có yêu cầu thật (ví dụ khán giả ở xa phải thấy ngay, hoặc nhiều đội trưởng tự ghi pick).
D **không phải** việc của buổi đầu tiên.

---

## 5. Chọn công cụ nào? (so sánh công bằng, không xếp hạng theo "độ thông minh")

Giá và giới hạn thay đổi liên tục. Dưới đây là những gì **xác nhận từ trang chính thức ngày 16/10/2026**; mục còn lại cần bạn tự kiểm tra.

| Nhu cầu | Tạo app trên web (Lovable / Bolt / Replit) | AI viết code trong thư mục (Copilot, Codex, Claude Code, Cursor) | Bảng tính / no-code (Google Sheets, AppSheet) | Chat AI viết HTML + hosting tĩnh |
|---|---|---|---|---|
| Thấy giao diện đầu tiên **tối nay** nhanh nhất | ✅ rất nhanh, không cài gì | ⚠️ cần cài VS Code + đăng nhập | ✅ nếu chỉ cần bảng + lọc | ✅ nhanh, sao chép vào một file |
| Chi phí thấp nhất cho bản thử | ⚠️ gói miễn phí giới hạn credit | ✅ Copilot Free; Codex có trong ChatGPT Free (giới hạn chưa công bố rõ); Claude Code **cần gói trả phí** | ✅ Sheets miễn phí | ✅ gần như 0 |
| Hợp người quen làm việc với file | ➖ | ✅ | ➖ | ⚠️ khó sửa khi lớn dần |
| Hợp ban tổ chức quản lý bằng bảng tính | ➖ | ✅ nếu nhập CSV | ✅ tốt nhất | ➖ |
| Kiểm soát dài hạn, mang code đi nơi khác | ⚠️ tuỳ gói/xuất code; kiểm tra | ✅ toàn bộ code là file của bạn | ⚠️ gắn với nền tảng | ✅ nhưng cần quản lý phiên bản |
| Cần máy chủ dùng chung? | Có thể (có sẵn backend) | Chỉ khi cần Giai đoạn D | Sheets chia sẻ được, nhưng logic draft/quyền hạn bị hạn chế | Không (và không ghi chung được) |

**Đã xác nhận (trang chính thức, 16/10/2026):** Claude Code nằm trong các gói trả phí (Pro $20/tháng, hoặc $17/tháng nếu trả theo năm), **không** có trong gói Free.
ChatGPT Free và Go có Codex nhưng trang không nêu mức giới hạn. Lovable Free: 5 credit/ngày, tối đa ~30/tháng. Bolt Free: 300K token/ngày, 1M/tháng, có logo Bolt trên trang.
Google Sheets "Phát hành lên web": thay đổi tự cập nhật sau vài phút, và ai có link đều xem được. `localStorage` gắn với từng địa chỉ trang trên từng trình duyệt.
**Chưa xác nhận / kiểm tra lại:** hạn mức Copilot Free chính xác; gói miễn phí và giá của Replit; việc Lovable/Bolt gói miễn phí có cho xuất code sang GitHub hay không; giá AppSheet.

**Khuyến nghị cho bạn (nền BA, có dự án thật, ngân sách thấp):**
**chat AI miễn phí để lên yêu cầu → thư mục dự án + một công cụ AI viết code bạn đã có → dữ liệu bằng CSV → Giai đoạn A–C.**
Lý do: bạn mạnh ở yêu cầu và dữ liệu; code nằm trong file của bạn (mang đi đâu cũng được, không phụ thuộc nền tảng); chi phí thấp; và toàn bộ kiểm tra dữ liệu nằm ở chỗ bạn nhìn thấy.
Chọn hướng khác nếu: **bạn ghét cài đặt** → dùng công cụ tạo app trên web để phác thảo, rồi cân nhắc xuất code; **ban tổ chức chỉ muốn sửa bảng tính và chỉ cần xem + lọc** → Google Sheets có thể là đủ, không cần code;
**cần nhiều người ghi pick từ xa** → cần Giai đoạn D, và nên có người có kinh nghiệm backend.

---

## 6. Kiểm tra bản thử (đừng chỉ tin "AI báo xong")

- [ ] Mở trang, thấy đúng đội đang đến lượt.
- [ ] Chọn một cầu thủ → bảng cập nhật, cầu thủ biến khỏi danh sách.
- [ ] Hoàn tác pick cuối → cầu thủ quay lại; xuất CSV có dòng `void`.
- [ ] Tải lại trang → pick vẫn còn (và bạn biết **chỉ trong trình duyệt này**).
- [ ] Nhập file sai (trùng ID, thiếu cột, cầu thủ không tồn tại) → báo lỗi và **dữ liệu cũ không đổi**.
- [ ] Tên có dấu phẩy/dấu nháy hiển thị đúng.
- [ ] Điện thoại (~390 px): không bị cắt chữ; mở F12 → Console: không có chữ đỏ.
- [ ] Mở bản xuất CSV bằng Excel đọc được.

---

## 7. Trước khi dùng cho giải thật

1. **Diễn tập đầy đủ** với đúng người, thiết bị, mạng của ngày thi đấu. Cố tình ghi sai một pick, hoàn tác, đóng tab giữa chừng rồi mở lại.
2. **Xuất CSV sau mỗi vài pick** và giữ bản giấy/bản dự phòng. Một máy hỏng không được làm mất kết quả.
3. Quyết định **ai là người ghi pick chính thức** và cách công bố kết quả cho mọi người.
4. **Dữ liệu người thật:** chỉ đăng thứ đã được đồng ý; với người dưới 18 tuổi, cần sự đồng ý phù hợp — dùng ID/biệt danh nếu chưa chắc. Trang GitHub Pages miễn phí là công khai.
5. Đừng hứa "đồng bộ trực tiếp" nếu bạn đang ở Giai đoạn B hoặc C.
6. **Dùng cùng một cách mở trang suốt sự kiện.** Pick lưu theo *địa chỉ*: `file://…`, `http://localhost:8000` và link GitHub Pages là ba "nơi lưu" khác nhau trong trình duyệt. Pick ghi ở chỗ này sẽ không hiện ở chỗ kia (và cũng không hiện ở trình duyệt khác).
7. **Chạy bản trên laptop của ban tổ chức** (bấm đúp hoặc localhost) — không cần internet, nên mất Wi-Fi vẫn chạy. Đừng phụ thuộc vào một đường link công khai trong lúc đang draft; đăng kết quả lên mạng riêng sau mỗi vòng.
8. Nếu trang báo đỏ **"KHÔNG LƯU ĐƯỢC"** (chế độ riêng tư/ẩn danh có thể chặn lưu), hãy tải CSV sau mỗi vài pick.

---

## 8. Tiết kiệm token, tiền và thời gian

- **Một bản yêu cầu rõ ràng** tiết kiệm nhiều nhất: ít phải làm lại hơn. Lên kế hoạch ở **chat AI**; để công cụ viết code chỉ lo thao tác trên file.
- **Đừng dán lại cả dự án vào chat.** Lưu yêu cầu vào file (`BRIEF.md`), và bảo AI *tìm đúng chỗ cần đọc* trước khi mở file lớn.
- **Chia nhỏ:** mỗi lần một thay đổi có thể kiểm tra được (bảng chỉ xem → ghi pick → nhập CSV…).
- **Việc lặp đi lặp lại** (nhập 48 pick, đổi tên cột) → nhờ AI viết **script/chức năng nhập một lần**, rồi chạy. Đừng nhờ AI gõ lại từng dòng.
- Bắt đầu **phiên mới** khi đổi sang việc khác, hoặc khi AI lặp lại lỗi bạn đã sửa; giữ trạng thái trong `STATE.md`.
- Dùng mô hình mạnh hơn cho phần **logic dễ sai** (luật, trùng pick, nhập dữ liệu); sửa chữ, đổi màu thì không cần.
- Dấu hiệu AI đang đốt token vô ích: sửa đi sửa lại cùng một lỗi, "sửa" cả những file bạn không nhờ, hoặc báo xong mà không đưa bằng chứng. Dừng, mô tả lại bằng ví dụ cụ thể, hoặc mở phiên mới.
- Phân biệt: tiền thuê bao · credit/token · **thời gian của bạn** · chi phí bảo trì sau này. Thường thời gian là thứ đắt nhất.

---

## Prompt 1 — Lên bản yêu cầu (dán vào chat AI)

Thay phần trong `<…>`.

```
Tôi là BA, muốn dựng một website nhỏ cho giải bóng rổ có draft. Hiện tại <mô tả cách bạn đang làm: bảng tính, nhóm chat…>.
Ràng buộc: bắt đầu bằng trang HTML/CSS/JavaScript thuần, không máy chủ, không đăng nhập, dữ liệu qua file CSV, dùng dữ liệu GIẢ.
KHÔNG tự quyết định luật giải. Hãy hỏi tôi tối đa 13 câu để chốt: ai tham gia, số đội, số cầu thủ mỗi đội, thứ tự draft,
trao đổi pick, nhóm cầu thủ, đồng hồ, ai được ghi pick, sửa/huỷ pick, khán giả cần xem ngay không, một hay nhiều thiết bị,
lưu gì sau sự kiện, thông tin người chơi nào được công khai.
Sau khi tôi trả lời, viết một bản yêu cầu ngắn: tác nhân, user story, quy tắc nghiệp vụ, từ điển dữ liệu (teams, players,
draft_order, draft_results — dùng ID ổn định), ngoại lệ, tiêu chí chấp nhận, ngoài phạm vi, và danh sách câu hỏi còn mở.
Điều nào tôi chưa trả lời, ghi "chưa quyết", đừng đoán.
```
**Trả lời tốt có:** các câu hỏi cụ thể trước, rồi bản yêu cầu ≤ 1–2 trang với mục "chưa quyết"; không tự bịa luật.

## Prompt 2 — Dựng bản đầu (dán vào công cụ AI trong thư mục dự án, chế độ Agent)

```
Đọc BRIEF.md. Dựng bản đầu của bảng draft trong thư mục này bằng HTML/CSS/JavaScript thuần (index.html, style.css, app.js, draft-core.js),
không thư viện, không máy chủ, giao diện tiếng Việt, dùng được trên điện thoại (~390 px).
Dữ liệu: 4 file CSV trong data/ (teams, players, draft_order, draft_results) dùng ID ổn định, KHÔNG so khớp bằng tên.
Yêu cầu:
1) Đọc CSV bằng bộ đọc đúng chuẩn (có xử lý ngoặc kép, dấu phẩy trong tên), không cắt dòng theo dấu phẩy.
2) Khi mở bằng file:// thì fetch() bị chặn: hãy cho người dùng chọn các file CSV; khi chạy qua http thì tự đọc data/.
3) Kiểm tra TRƯỚC khi áp dụng: đủ cột, ô trống, trùng ID, tham chiếu không tồn tại, cầu thủ chọn hai lần, pick sai thứ tự. Lỗi thì báo rõ
   và KHÔNG thay đổi dữ liệu hiện có.
4) Hiện: đội đang đến lượt, bảng draft, cầu thủ còn lại (tìm theo tên + lọc vị trí), đội hình từng đội.
5) Ghi pick, từ chối cầu thủ đã chọn, hoàn tác pick cuối (đánh dấu void, giữ lịch sử), xuất draft_results.csv.
6) Lưu trạng thái bằng localStorage và ghi rõ trên trang rằng nó CHỈ nằm trong trình duyệt này.
7) Đừng gọi nút ẩn/hiện là "bảo mật". Hiển thị tên bằng textContent, không dùng innerHTML với dữ liệu nhập vào.
Cuối cùng: viết 5 dòng cách chạy và cách kiểm tra, và liệt kê thứ trang CHƯA làm được.
```
**Trả lời tốt có:** các file nằm thật trong thư mục; hướng dẫn chạy; danh sách giới hạn; không thêm thư viện hay backend bạn không yêu cầu.

**Cách khác (nhanh hơn):** mở thư mục ví dụ `examples/draft-board/` trong VS Code và nhờ AI *chỉnh* nó theo `BRIEF.md` của bạn (đổi tên cột, thêm vị trí, đổi thứ tự…) thay vì viết lại từ đầu. Khi AI sửa, luôn yêu cầu chạy lại bài kiểm tra (`node --test`) nếu máy có Node.js, hoặc thử lại các bước ở mục 6.

---

## Đọc tiếp
- [START_HERE.md](START_HERE.md) — lần đầu dùng GitHub, VS Code và đưa trang lên mạng.
- [BUILDING_WITH_AI.md](BUILDING_WITH_AI.md) — phương pháp đầy đủ, chọn công cụ, dữ liệu, từ tĩnh sang dùng chung, kiểm tra, chi phí.
- [COPY_PASTE_PROMPTS.md](COPY_PASTE_PROMPTS.md) — thêm prompt cho từng giai đoạn của dự án draft.
- [Ví dụ draft-board](examples/draft-board/README.md) — mã nguồn và dữ liệu mẫu đã được kiểm thử; gói tải về: [`downloads/draft-board-example.zip`](downloads/draft-board-example.zip).
