# LinguaChat — Ngôn ngữ thiết kế

Tài liệu này định nghĩa **ngôn ngữ thị giác** của sản phẩm và phương pháp để nó
không hội tụ về mẫu giao diện mà mọi công cụ sinh code đều cho ra.

Phạm vi: toàn bộ `frontend/`. Màn hình đầu tiên áp dụng: `/login`, `/register`.

## Quan hệ với `DESIGN.md`

[`../DESIGN.md`](../DESIGN.md) đặc tả **hành vi** màn hình chat: bố cục, gộp nhóm
tin, bốn chế độ dịch, bốn trạng thái dịch, gửi lạc quan, trạng thái rỗng, a11y.
Toàn bộ phần đó vẫn còn giá trị.

Tài liệu này thay thế phần **thẩm mỹ** của nó:

| `DESIGN.md` nói | Tài liệu này |
|---|---|
| §2.1 sửa `--text-muted` thành `#7d8ba1` | Bỏ — bảng màu slate bị loại hoàn toàn (§2) |
| §2.2 cặp token light/dark | Giữ **cấu trúc**, thay **giá trị** (§4) |
| §2.3 giữ nguyên `--space-*`, `--radius-*`, `--font-size-*` | Bỏ — thang đo 8px và bo góc 8–20px là dấu hiệu (§5) |
| §2 `--bubble-me-bg: var(--gradient-primary)` | Bỏ — không gradient nào trong sản phẩm (§3) |
| §7 chuyển động, §8 a11y, §9 typography đa ngữ | Giữ, có bổ sung (§6, §9) |

---

## 1. Vấn đề: vì sao giao diện sinh tự động hội tụ

Mô hình sinh code tối ưu cho *xác suất*, không cho *sự khác biệt*. Khi được yêu
cầu "làm trang đăng nhập đẹp, hiện đại", nó trả về trung vị của tập huấn luyện —
và tập đó bị chi phối bởi landing page SaaS 2020–2024. Kết quả là một tổ hợp lặp
lại đủ nhiều để mắt người nhận ra ngay, kể cả người không làm thiết kế.

Không phải từng yếu tố là xấu. Vấn đề là **cả cụm luôn xuất hiện cùng nhau**.

### 1.1 Sổ kê dấu hiệu — audit trên chính repo này

Trang đăng nhập hiện tại trúng 17/17. Đây không phải chỉ trích code; đây là
danh sách kiểm được, và mỗi dòng là một thứ phải biến mất.

> **Bảng dưới là ảnh chụp trạng thái *trước* khi làm lại.** Nó được giữ nguyên
> làm căn cứ đối chiếu. Cả 17 dấu hiệu nay đã hết; `AuthHero.tsx` và
> `AuthHero.module.css` đã bị xoá nên các liên kết trỏ tới hai file đó không còn
> mở được. Trạng thái hiện tại kiểm bằng ba lệnh grep ở [§PP1](#pp1--sổ-kê-dấu-hiệu-kiểm-bằng-grep).

| # | Dấu hiệu | Vị trí hiện tại |
|---|---|---|
| 1 | Gradient tím→xanh 135° | `--gradient-primary: linear-gradient(135deg, #7c3aed, #3b82f6)` — [globals.css:44](../src/app/globals.css#L44) |
| 2 | Glassmorphism: nền trắng 4% + `backdrop-filter: blur(20px)` | [globals.css:64-66](../src/app/globals.css#L64-L66), [AuthHero.module.css:85](../src/components/auth/AuthHero.module.css#L85) |
| 3 | Orb mờ trôi nổi ở nền | `filter: blur(80px)` + `floatSlow` — [AuthHero.module.css:14-39](../src/components/auth/AuthHero.module.css#L14-L39) |
| 4 | Chữ bị cắt bằng gradient | `-webkit-text-fill-color: transparent` — [AuthHero.module.css:51-54](../src/components/auth/AuthHero.module.css#L51-L54), [auth.module.css:31-34](../src/app/(auth)/auth.module.css#L31-L34) |
| 5 | Bóng phát sáng | `--shadow-glow-purple: 0 0 20px rgba(124,58,237,.3)` — [globals.css:59](../src/app/globals.css#L59) |
| 6 | Nền xanh-tím tối gần đen | `--bg-primary: #0a0a14` — [globals.css:20](../src/app/globals.css#L20) |
| 7 | Chỉ có dark theme | Không có `prefers-color-scheme` ở đâu |
| 8 | Hex mặc định của Tailwind | `#94a3b8`, `#64748b`, `#f1f5f9` = slate-400/500/100 — [globals.css:36-38](../src/app/globals.css#L36-L38) |
| 9 | Chia đôi màn hình: hero trái / form phải | `grid-template-columns: 1fr 1fr` — [auth.module.css:3](../src/app/(auth)/auth.module.css#L3) |
| 10 | Icon lucide 18px nhét trong ô input | [LoginForm.tsx:72](../src/components/auth/LoginForm.tsx#L72), [Input.module.css:19-27](../src/components/ui/Input.module.css#L19-L27) |
| 11 | Copy khuôn mẫu tiếng Anh | "Welcome back" / "Sign in to continue your conversations" — [LoginForm.tsx:55-56](../src/components/auth/LoginForm.tsx#L55-L56) |
| 12 | Mọi thứ trên lưới 8px | `--space-*: 4 8 16 24 32 48 64` — [globals.css:69-75](../src/app/globals.css#L69-L75) |
| 13 | Bo góc 8–20px đồng loạt | `--radius-*: 6 8 12 16 20` — [globals.css:78-82](../src/app/globals.css#L78-L82) |
| 14 | Nút CTA gradient full-width + hover nhấc lên | `transform: translateY(-1px)` — [Button.module.css:36](../src/components/ui/Button.module.css#L36) |
| 15 | Vào trang là `fadeInUp` so le | delay 0.2/0.4/0.6/0.8/1.0s — [AuthHero.module.css:89-93](../src/components/auth/AuthHero.module.css#L89-L93) |
| 16 | Inter làm font duy nhất, nạp qua `@import` Google | [globals.css:6](../src/app/globals.css#L6), [globals.css:86](../src/app/globals.css#L86) |
| 17 | Emoji cờ làm nội dung | [constants.ts:10-19](../src/lib/constants.ts#L10-L19) |

Dấu hiệu 17 còn là **lỗi thật**, không chỉ là vấn đề thẩm mỹ: Windows không có
glyph cờ quốc gia, nên `🇻🇳` hiển thị thành hai chữ `VN` trong mọi trình duyệt
trên Windows. Bảng chọn ngôn ngữ hiện tại bị vỡ trên nền tảng chiếm phần lớn
người dùng desktop Việt Nam.

---

## 2. Sáu phương pháp

Bốn nguyên tắc của `DESIGN.md` §1 vẫn giữ. Phần dưới là **cách làm**, không phải
tuyên ngôn — mỗi phương pháp phải kiểm được bởi người khác.

### PP1 — Sổ kê dấu hiệu, kiểm bằng grep

§1.1 là danh sách cấm. Nó biến "trông giống AI" từ cảm giác thành điều kiểm được.
Trước mỗi PR, chạy:

```bash
# Không được có kết quả nào trong src/
grep -rnE "backdrop-filter|blur\(|0 0 [0-9]+px|text-fill-color|linear-gradient" frontend/src
grep -rniE "#7c3aed|#3b82f6|#94a3b8|#64748b|#f1f5f9|#0f172a|#1e293b" frontend/src
grep -rn "translateY(-" frontend/src        # hover nhấc lên
```

Ngoại lệ duy nhất được phép: `blur()` trong bộ lọc nhiễu giấy ở §3.2, vì nó tạo
vật liệu chứ không tạo hiệu ứng phát sáng.

### PP2 — Neo vào vật liệu thật, không neo vào "app hiện đại"

Đây là phương pháp gốc; năm phương pháp còn lại đều phái sinh từ nó.

Mọi quyết định thị giác phải trả lời được: **vật thật có làm thế không?**

Vật neo của LinguaChat là **nhãn sản phẩm in trên giấy không tẩy trắng** — họ
hàng gần của bao bì đồ dùng Nhật và của giấy tờ in ở Việt Nam. Hai truyền thống
này chia nhau một tập đặc điểm: giấy ngà ấm, mực đen ấm, kẻ hairline, chữ nhỏ mà
dày thông tin, nhãn song ngữ, và một mã biểu ở góc.

Từ đó suy ra, không cần tranh luận thêm:

| Vật thật | Hệ quả |
|---|---|
| Giấy không tự phát sáng | Không `box-shadow` phát sáng, không `filter: blur` trang trí |
| Mực in không chuyển hai màu trong một nét | Không gradient. Ở đâu cũng vậy |
| Giấy có thớ | Có nhiễu hạt rất nhẹ (§3.2) — thứ mà giao diện phẳng sinh tự động không bao giờ có |
| Nhãn bị cắt bằng dao, không dập khuôn tròn | Bo góc tối đa 4px (§5.3) |
| Mực đọng ở mép nét | Đường kẻ 1px màu ấm, không phải `rgba(255,255,255,.08)` |
| Nhãn in sẵn thì không động | Không animation vô hạn (§6) |

### PP3 — Sắc tố có tên, không lấy màu từ palette framework

Bảng màu lấy từ sắc tố truyền thống có tên gọi và lịch sử, mỗi màu **một vai
duy nhất**. Điều này vừa chống dấu hiệu #8, vừa buộc phải có kỷ luật: khi màu có
tên và có vai, người ta không thêm màu thứ tư cho vui.

### PP4 — Thang đo phái sinh, không phải 8px

Thang 8px là mặc định của mọi framework nên nó là chữ ký. Thang ở §5.1 dựng từ
cơ sở 5px với tỉ lệ ~1,48. Hệ quả: khoảng cách rơi vào 9/14/21/31 — vẫn có nhịp,
nhưng không phải nhịp mà mắt đã quen đo.

### PP5 — Một nước đi ký tên, bắt nguồn từ sự thật sản phẩm

Đây là phần khó thay thế nhất, và cũng là phần dễ làm sai nhất.

Nước đi ký tên **không phải trang trí**. Nó là một cơ chế chỉ tồn tại được vì
sản phẩm này làm việc này. Trang trí thì copy được trong mười phút; cơ chế thì
không, vì muốn copy phải copy cả sản phẩm.

Với LinguaChat, nước đi đó là **nhãn song ngữ sống** (§7). Không phải mượn hình
thức nhãn song ngữ của bao bì Nhật, mà dùng đúng thứ sản phẩm làm: mọi nhãn trên
form hiện đồng thời bằng tiếng Việt và bằng ngôn ngữ đang chọn, và đổi ngay khi
người dùng đổi lựa chọn. Trang đăng nhập chứng minh sản phẩm trước khi người
dùng đăng nhập.

Kiểm: nếu bỏ nước đi này đi mà trang vẫn nói đúng về sản phẩm, thì nó là trang
trí và phải thay bằng cái khác.

### PP6 — Hai bài kiểm định trước khi gọi là xong

- **Bài đổi logo.** Che tên và logo trên ảnh chụp. Nếu ảnh đó dùng được cho một
  sản phẩm khác lĩnh vực mà không ai thấy lạ → chưa xong.
- **Bài nheo mắt.** Nheo tới lúc chữ nhoè hết. Cái còn lại phải là một *cấu
  trúc* nhận ra được (khối nhãn, cột trái hẹp, dải mã). Nếu chỉ còn một hình chữ
  nhật bo góc giữa màn hình → chưa xong.

Thêm PP7 cho phần chữ: **giọng văn cụ thể**. Tiếng Việt là ngôn ngữ chính của
giao diện. Không "Welcome back", không "Chào mừng trở lại" (dịch máy của chính
nó). Câu phải nói được điều sản phẩm làm — xem §8.

---

## 3. Vật liệu

### 3.1 Ba bề mặt

Nghịch với thói quen: **nền tối hơn thẻ**. Giấy nhãn sáng hơn bìa kraft đặt dưới
nó. Điều này cho chiều sâu mà không cần bóng đổ.

```
ground   #e8e4da   bìa kraft — nền trang
label    #f5f2e9   giấy nhãn — thẻ chứa form
insert   #fdfcf9   giấy chèn — ô nhập
```

### 3.2 Thớ giấy

Nhiễu hạt đơn sắc, dán một lớp trên nền. Đây là chi tiết vật liệu rẻ nhất và
hiệu quả nhất: nó phá vỡ vẻ "phẳng tuyệt đối" của CSS mà không thêm màu, không
thêm hình, không thêm request mạng.

```css
body {
  background-color: var(--surface-ground);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='g'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.82' numOctaves='3' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='140' height='140' filter='url(%23g)' opacity='0.055'/%3E%3C/svg%3E");
}
```

Ba ràng buộc: `saturate 0` (nhiễu màu trông như lỗi nén JPEG), `opacity ≤ 0.06`
(cao hơn là bẩn chứ không phải thớ), và tile ≤ 140px (rasterise một lần rồi lặp).

Ở dark theme giảm còn `0.03` — trên nền tối, cùng một cường độ nhiễu trông đậm
hơn nhiều.

### 3.3 Đường kẻ và bóng

Chỉ có hai thứ tạo cạnh:

- **Hairline 1px** màu ấm (`--rule`). Đây là công cụ phân vùng chính. Không dùng
  bóng đổ để tách khối.
- **Một bóng duy nhất được phép:** `--shadow-seam: 0 1px 0 rgba(58,50,36,.05)` —
  mô phỏng mép giấy đè lên nhau. Bán kính mờ **0**.

Bóng có `blur > 3px` bị cấm. Bóng có màu không phải trung tính ấm bị cấm.

---

## 4. Màu

### 4.1 Sắc tố và vai

Bốn sắc tố, bốn vai không chồng nhau. Không có màu thứ năm.

| Sắc tố | Light | Dark | Vai — và **chỉ** vai này |
|---|---|---|---|
| **墨 Sumi** (mực) | `#26241f` | `#e8e3d7` | Chữ chính; nền nút hành động chính |
| **藍 Ai** (chàm) | `#2d4356` | `#8fb3c9` | Tương tác: liên kết, viền focus, mục đang chọn |
| **弁柄 Bengara** (đất son) | `#a8503c` | `#d08a72` | Lỗi và cảnh báo. **Không** dùng cho trang trí |
| **苔 Koke** (rêu) | `#4a6741` | `#93b085` | Thành công, xác nhận |

Chàm và đất son được tách vai dứt khoát để không bao giờ phải phân biệt hai màu
đỏ-nâu gần nhau: nút chính là mực đen, nên đất son được để dành trọn cho lỗi.

### 4.2 Bảng đầy đủ

Quy tắc của `DESIGN.md` §2.2 giữ nguyên và là ràng buộc cứng: **không token màu
nào được định nghĩa lần đầu trong media query.** Bảng light định nghĩa đủ ở
`:root` trần; media query chỉ ghi đè.

```css
:root {
  color-scheme: light dark;

  --surface-ground: #e8e4da;
  --surface-label:  #f5f2e9;
  --surface-insert: #fdfcf9;
  --surface-sunken: #ded9cb;   /* rãnh, thanh tiến độ */

  --ink:           #26241f;
  --ink-secondary: #57534a;
  --ink-muted:     #6e6759;
  --ink-disabled:  #a09884;
  --ink-inverse:   #f5f2e9;

  --rule:        #d9d2c2;
  --rule-strong: #bfb5a0;

  --indigo: #2d4356;
  --indigo-weak: rgba(45, 67, 86, 0.10);
  --bengara: #a8503c;
  --bengara-weak: rgba(168, 80, 60, 0.09);
  --koke: #4a6741;

  --grain-opacity: 0.055;
  --shadow-seam: 0 1px 0 rgba(58, 50, 36, 0.05);
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) { /* bảng dark */ }
}
:root[data-theme="dark"] { /* lặp lại y hệt để toggle thắng cả hai chiều */ }
```

Dark theme là **giấy dưới đèn bàn**, không phải giao diện tối chung: xám ấm
`#191714` / `#221f1a`, chữ ngà `#e8e3d7`. Không có sắc xanh-tím ở bất kỳ đâu.

### 4.3 Tương phản

| Cặp | Tỉ lệ | Ngưỡng |
|---|---|---|
| `--ink` trên `--surface-label` | ≈13,9:1 | AA ✓ AAA ✓ |
| `--ink-secondary` trên `--surface-label` | ≈6,7:1 | AA ✓ AAA ✓ |
| `--ink-muted` trên `--surface-label` | ≈5,0:1 | AA ✓ |
| `--indigo` trên `--surface-label` | ≈9,1:1 | AA ✓ AAA ✓ |
| `--bengara` trên `--surface-label` | ≈4,8:1 | AA ✓ |
| `--koke` trên `--surface-label` | ≈5,7:1 | AA ✓ |
| `--ink-inverse` trên `--ink` | ≈13,9:1 | AA ✓ AAA ✓ |
| dark: `--ink-muted` trên `--surface-label` | ≈5,4:1 | AA ✓ |

> Các số trên là **tính toán từ công thức WCAG, chưa đo bằng công cụ**. Xác nhận
> lại bằng axe hoặc Lighthouse khi implement. `--ink-disabled` (≈2,6:1) cố tình
> dưới ngưỡng và chỉ được dùng cho trạng thái vô hiệu, không bao giờ cho chữ đọc.

`--bengara` ở 4,8:1 là cặp sát ngưỡng nhất. Chữ lỗi phải giữ ≥13px và **luôn**
kèm icon + chữ, không bao giờ chỉ dựa vào màu (`DESIGN.md` §8).

---

## 5. Thang đo

### 5.1 Khoảng cách — cơ sở 5px, tỉ lệ ~1,48

```
--s-1   3px    khe trong nhãn
--s-2   5px    nhãn ↔ ô nhập
--s-3   9px    trong một khối
--s-4  14px    giữa hai trường
--s-5  21px    giữa hai nhóm
--s-6  31px    padding thẻ
--s-7  46px    lề ngoài desktop
--s-8  68px    khoảng nghỉ lớn nhất
```

### 5.2 Cỡ chữ — **trần 26px**

```
--fs-micro    0.6875rem  11px   mã biểu, nhãn phụ
--fs-label    0.75rem    12px   nhãn mono in hoa
--fs-small    0.8125rem  13px   phụ đề, lỗi
--fs-body     0.9375rem  15px   thân
--fs-lead     1.0625rem  17px   câu dẫn
--fs-title    1.3125rem  21px   tiêu đề khối
--fs-display  1.625rem   26px   cỡ lớn nhất trong sản phẩm
```

Trần 26px là ràng buộc cứng, và là đòn phản công trực tiếp vào dấu hiệu tiêu đề
hero khổng lồ. Thứ bậc đến từ **màu, trọng lượng, và mật độ** — không đến từ việc
phóng chữ to.

### 5.3 Bo góc — **trần 4px**

```
--r-1  2px   ô nhập, nút, chip
--r-2  3px   thẻ
--r-3  4px   ảnh, avatar vuông
```

Avatar tròn (`border-radius: 50%`) vẫn được phép — đó là quy ước nhận diện người,
không phải trang trí.

---

## 6. Chuyển động

Ngân sách của `DESIGN.md` §7 bị siết thêm: **trần 160ms**, và chỉ được động
`opacity`, `transform`, `border-color`, `background-color`.

| Sự kiện | Hiệu ứng | Thời lượng |
|---|---|---|
| Hover nút / chip | đổi nền | 120ms |
| Focus ô nhập | đổi màu viền | 100ms |
| Nhấn nút | `translateY(1px)` — **ấn xuống** | 80ms |
| Lỗi hiện ra | fade tại chỗ | 140ms |

Ba điều bị cấm dứt khoát:

- **`transform: translateY(-)` khi hover.** Nhãn giấy không nhấc lên khỏi bìa.
  Nút được ấn *xuống*.
- **Animation vô hạn.** `float`, `floatSlow`, `pulse`, `gradientShift` trong
  [globals.css:191-232](../src/app/globals.css#L191-L232) bị xoá.
- **Animation vào trang so le.** Nhãn in sẵn thì đã ở đó rồi.

Khối `prefers-reduced-motion` mà `DESIGN.md` §7 yêu cầu và hiện chưa có — thêm
vào `globals.css` ngay ở PR đầu tiên.

---

## 7. Nước đi ký tên: nhãn song ngữ sống

### 7.1 Cơ chế

Mỗi nhãn trên form có hai tầng:

```
MẬT KHẨU                          Password
└─ mono, in hoa, 12px,            └─ 11px, --ink-muted,
   letter-spacing .08em,             ngôn ngữ đang chọn,
   --ink-secondary                   căn phải
```

Người dùng đổi ngôn ngữ ở dải bên trái → **toàn bộ** nhãn phụ đổi ngay, không
reload. Nhãn nút cũng vậy: `ĐĂNG NHẬP · Sign in` → `ĐĂNG NHẬP · ログイン`.

### 7.2 Vì sao nó không phải trang trí

Ba lý do, theo thứ tự quan trọng:

1. **Nó chứng minh sản phẩm.** Người mới chưa có lý do tin rằng bản dịch sẽ tốt.
   Trang đăng nhập cho họ thấy trước khi họ phải tin.
2. **Nó đặt kỳ vọng đúng.** Người dùng biết ngay mình đang ở một sản phẩm
   Việt-Nam-trước, có ngôn ngữ đích, và ngôn ngữ đó thay đổi được.
3. **Nó tạo mật độ có ích.** Hướng thiết kế này cần chữ nhỏ mà dày thông tin.
   Nhãn phụ lấp mật độ đó bằng nội dung thật thay vì bằng chữ giả.

### 7.3 Ràng buộc

- Nhãn phụ **không được** cạnh tranh với nhãn chính: nhỏ hơn một bậc, màu nhạt
  hơn, không in hoa.
- Bảng chuỗi phải phủ đủ 10 ngôn ngữ ở [constants.ts](../src/lib/constants.ts).
  Thiếu một ngôn ngữ thì lùi về tiếng Anh, **không** để trống.
- Nhãn phụ mang `lang` đúng để screen reader phát âm đúng giọng, và
  `aria-hidden="true"` — nó là bản dịch của nhãn chính, đọc lại sẽ thành nhiễu.
  Ô nhập lấy tên từ nhãn chính qua `htmlFor`/`id`.
- Chuỗi CJK và Thái dùng font hệ thống (§9), nên nhãn phụ phải chịu được việc
  chiều cao dòng lệch giữa các ngôn ngữ. Dùng `min-height` cho hàng nhãn, không
  để hàng co giãn khi đổi ngôn ngữ — đổi ngôn ngữ không được làm form nhảy.

### 7.4 Mã ngôn ngữ, không phải emoji cờ

Dải chọn ngôn ngữ dùng mã hai chữ in hoa (`VI EN ZH JA KO FR DE ES TH ID`), không
dùng emoji cờ. Ba lý do:

1. **Emoji cờ không render trên Windows** — hiển thị thành hai chữ Latin.
2. **Cờ ≠ ngôn ngữ.** `🇺🇸` cho English bỏ rơi mọi người nói tiếng Anh ngoài Mỹ;
   `🇨🇳` cho 中文 bỏ rơi Đài Loan và Hồng Kông. Đây là lỗi thiết kế thật, không
   phải chuyện thẩm mỹ.
3. Mã chữ đặt trong ô vuông hairline khớp với vật neo (§2 PP2): nó trông như mã
   in trên nhãn, và render giống nhau trên mọi nền tảng.

Tên bản địa (`Tiếng Việt`, `日本語`) vẫn hiện — ở nhãn phụ khi chip được chọn, và
trong `aria-label` của mọi chip.

---

## 8. Chữ

Tiếng Việt là ngôn ngữ chính của giao diện.

| Vị trí | Cũ | Mới |
|---|---|---|
| Tiêu đề login | "Welcome back" | "Viết bằng tiếng của bạn." / "Họ đọc bằng tiếng của họ." |
| Phụ đề | "Sign in to continue your conversations" | *bỏ* — hai câu trên đã đủ |
| Nút | "Sign In" | "ĐĂNG NHẬP · Sign in" |
| Lỗi | "Invalid email format" | "Email này thiếu dấu @ hoặc phần tên miền." |
| Lỗi xác thực | "Login failed" | "Email hoặc mật khẩu không đúng." |

Ba quy tắc:

- **Nói cái sai, không nói cái luật.** "Mật khẩu phải có ít nhất 8 ký tự" là
  luật. "Còn thiếu 3 ký tự" là cái sai. Cái thứ hai giúp người dùng sửa được.
- **Không hô hào.** Không "Sẵn sàng chưa?", không "Bắt đầu hành trình". Nhãn sản
  phẩm không cổ vũ ai.
- **Không dấu chấm than.** Trừ khi đó là lời chào của người thật trong tin nhắn.

---

## 9. Font

```
Nhãn, mã, số   IBM Plex Mono     400/500   latin, latin-ext, vietnamese
Thân, tiêu đề  Be Vietnam Pro    400/500/600  latin, latin-ext, vietnamese
```

**Be Vietnam Pro** thay Inter. Ba lý do: nó được thiết kế cho tiếng Việt nên dấu
thanh không bị chồng hay lệch trên chữ hoa (`Ậ`, `Ỗ`, `Ừ`); nó hơi hẹp hơn Inter
nên chịu được mật độ mà hướng thiết kế này cần; và nó không phải chữ ký của giao
diện sinh tự động.

Nạp bằ`next/font` — bỏ `@import` Google Fonts ở
[globals.css:6](../src/app/globals.css#L6). `@import` chặn render lần vẽ đầu và
gửi request tới máy chủ bên thứ ba; `next/font` self-host và không có cả hai vấn đề.

CJK và Thái **không** nạp qua `next/font`: một subset Noto Sans JP nặng hơn toàn
bộ phần còn lại của trang. Dùng font hệ thống:

```css
--font-cjk: "Hiragino Sans", "Yu Gothic", "Meiryo", "Microsoft YaHei",
  "Malgun Gothic", "Noto Sans CJK", sans-serif;
--font-thai: "Leelawadee UI", "Noto Sans Thai", "Thonburi", sans-serif;
```

Giữ nguyên hai lưu ý của `DESIGN.md` §9: `line-height: 1.75` cho `[lang="th"]`,
`[lang="ja"]`, `[lang="zh"]`, `[lang="ko"]`; `word-break: keep-all` cho tiếng Hàn.
Viết CSS bằng thuộc tính logic (`padding-inline`, `margin-inline-start`) để không
phải viết lại khi thêm RTL.

---

## 10. Bố cục trang đăng nhập

Không chia đôi màn hình. Một **thẻ nhãn** rộng 620px, bên trong chia hai cột
không đều — đúng cấu trúc mặt sau một nhãn sản phẩm: cột thông số hẹp, cột nội
dung rộng.

```
                         ┌ mã biểu, mono 11px, --ink-muted
                         │
┌────────────────────────┴──────────────────────────────────┐
│  LinguaChat                              XÁC THỰC · 01    │
├──────────────┬────────────────────────────────────────────┤
│              │                                            │
│ NGÔN NGỮ     │   Viết bằng tiếng của bạn.                 │
│ CỦA BẠN      │   Họ đọc bằng tiếng của họ.                │
│              │                                            │
│ ┌──┐┌──┐┌──┐ │   ─────────────────────────────────────    │
│ │VI││EN││ZH│ │                                            │
│ └──┘└──┘└──┘ │   EMAIL                            Email   │
│ ┌──┐┌──┐┌──┐ │   ┌────────────────────────────────────┐   │
│ │JA││KO││FR│ │   │ ban@vidu.com                       │   │
│ └──┘└──┘└──┘ │   └────────────────────────────────────┘   │
│ ┌──┐┌──┐┌──┐ │                                            │
│ │DE││ES││TH│ │   MẬT KHẨU        Password        HIỆN     │
│ └──┘└──┘└──┘ │   ┌────────────────────────────────────┐   │
│ ┌──┐         │   │ ••••••••••                         │   │
│ │ID│         │   └────────────────────────────────────┘   │
│ └──┘         │                                            │
│              │   ☐ Ghi nhớ máy này    Quên mật khẩu?      │
│ Tiếng Việt   │                                            │
│              │   ┌────────────────────────────────────┐   │
│ ─────────    │   │   ĐĂNG NHẬP    ·    Sign in        │   │
│              │   └────────────────────────────────────┘   │
│ DỊCH TỰ ĐỘNG │                                            │
│ 10 NGÔN NGỮ  │   Chưa có tài khoản?  Tạo tài khoản        │
│              │                                            │
└──────────────┴────────────────────────────────────────────┘
   180px                        1fr
   --surface-ground             --surface-label
```

Cột trái dùng `--surface-ground` (tối hơn) để đọc như phần bìa lộ ra dưới nhãn.
Kẻ phân cột là hairline, không phải bóng.

### Điểm neo của bài nheo mắt

Nheo mắt, cấu trúc còn lại là: **một dải ô vuông nhỏ ở cột trái hẹp, cạnh một
cột trường form**. Đó là hình dạng nhận ra được, không phải "hình chữ nhật bo góc
giữa màn hình".

### Responsive

- **≥880px** — như trên, thẻ căn giữa, lề `--s-7`.
- **560–879px** — thẻ chiếm toàn bộ chiều rộng trừ lề `--s-5`. Cột trái xuống
  thành **một hàng ngang** dưới đầu thẻ: dải mã ngôn ngữ cuộn ngang, dòng thông
  số xuống chân thẻ.
- **<560px** — bỏ thẻ. Nội dung nằm trực tiếp trên `--surface-ground`, lề `--s-4`.
  Viền thẻ giữa màn hình hẹp là viền vô nghĩa. Ô chạm ≥44px (`DESIGN.md` §8).

---

## 11. Trạng thái

| Trạng thái | Hình |
|---|---|
| Ô nhập rỗng | viền `--rule`, nền `--surface-insert` |
| Hover | viền `--rule-strong` |
| Focus | viền `--indigo` + `outline: 2px solid --indigo` `outline-offset: 2px` |
| Có lỗi | viền `--bengara`, nền `--bengara-weak`, dòng lỗi kèm icon dưới ô |
| Vô hiệu | chữ `--ink-disabled`, nền `--surface-sunken`, không đổi viền |
| Nút đang tải | nhãn giữ nguyên chỗ, thêm con trỏ mono nhấp nháy `▌` ở cuối |

Hai chi tiết đáng nói:

- **Focus ring là bắt buộc ở mọi phần tử tương tác.** `Button` hiện chỉ có
  `:active` transform, chưa có focus ring — `DESIGN.md` §8 đã ghi nợ điều này.
  Dùng `:focus-visible`, không dùng `:focus`, để chuột không kéo ring theo.
- **Nút đang tải không dùng spinner tròn.** Spinner là chi tiết của giao diện
  phần mềm; con trỏ nhấp nháy là chi tiết của máy chữ, khớp vật neo. Nhãn nút
  **không được** biến mất khi tải (`Button.module.css` hiện set
  `visibility: hidden` — làm nút mất nghĩa giữa lúc chờ) và chiều rộng nút không
  được đổi.

---

## 12. Checklist triển khai

Theo thứ tự. Mỗi mục một PR.

- [x] `globals.css`: thay toàn bộ token (§4, §5), thớ giấy (§3.2), xoá animation
      vô hạn, thêm `prefers-reduced-motion`
- [x] `next/font`: Be Vietnam Pro + IBM Plex Mono, bỏ `@import` (§9)
- [x] `constants.ts`: bỏ `flag`, thêm mã hiển thị + tên bản địa (§7.4)
- [x] `lib/i18n.ts`: bảng nhãn 10 ngôn ngữ (§7.3)
- [x] `Input`: hàng nhãn hai tầng, bỏ icon trong ô, nút HIỆN/ẨN dạng chữ (§7.1, §11)
- [x] `Button`: nút mực đen, ấn xuống, focus ring, con trỏ nhấp nháy (§6, §11)
- [x] `LanguageSelector`: chip mã chữ, biến thể `rail` cho cột trái (§7.4)
- [x] Layout auth: thẻ nhãn hai cột + `LanguageContext` (§10)
- [x] `LoginForm`: nhãn song ngữ, copy tiếng Việt (§7, §8)
- [x] `RegisterForm`: theo cùng hệ; `XÁC THỰC · 02`
- [x] Xoá `AuthHero.tsx` + `AuthHero.module.css` (không còn được import)
- [x] Chạy ba lệnh grep ở §PP1 — phải sạch
- [ ] Kiểm: axe/Lighthouse, đi hết bằng bàn phím, thử ở light + dark
- [ ] Chụp ảnh và chạy hai bài kiểm ở §PP6

Hai mục cuối cần chạy trên trình duyệt thật, chưa làm được từ dòng lệnh.

### Định nghĩa "xong"

Một màn hình xong khi: ba lệnh grep ở PP1 không ra kết quả, đủ trạng thái ở §11,
đi được hết bằng bàn phím, đạt AA đo bằng công cụ, đúng ở cả light lẫn dark, và
qua được cả hai bài kiểm ở PP6.

### Việc còn nợ, cần người xác nhận

- **Tương phản ở §4.3 là số tính toán, chưa đo.** Cặp `--bengara` (4,8:1) sát
  ngưỡng nhất, kiểm trước.
- **Bảng chuỗi 10 ngôn ngữ cần người bản ngữ soát.** Chuỗi ban đầu ở
  `lib/i18n.ts` là bản dịch chưa qua kiểm tra — nhãn sai ở một sản phẩm dịch
  thuật là lỗi đắt hơn bình thường. Ưu tiên soát: ja, ko, th.
- **Thớ giấy ở §3.2 chưa đo chi phí paint.** Nếu Lighthouse báo tụt điểm trên máy
  yếu, chuyển từ `body` sang chỉ thẻ nhãn, hoặc bỏ.
