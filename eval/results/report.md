# BÁO CÁO ĐÁNH GIÁ CHẤT LƯỢNG DỊCH

**Dự án:** LinguaFlow (P-217) · **Nhóm thực hiện:** 4U
**Thời điểm chạy:** 2026-08-16 16:09 UTC
**Provider dịch:** groq · **Model:** mặc định của provider
**Provider chấm điểm:** groq
**Bộ dữ liệu:** `eval/golden_set.jsonl` (25 mẫu)

> Điểm số do LLM tự chấm (LLM-as-judge), không phải đánh giá của người thật. Kết quả dùng để so sánh tương đối giữa các lần chạy và giữa các provider.

> **CẢNH BÁO:** provider chấm điểm trùng provider dịch — model đang tự chấm chính nó nên điểm số bị thiên vị. Dùng `--judge-provider` để chỉ định một model trung lập.

## 1. Chỉ số tổng hợp

| Chỉ số | Mục tiêu | Thực tế | Trạng thái |
|---|---|---|---|
| Tỷ lệ đạt (điểm ≥ 0.7) | > 80% | 100.0% | Đạt |
| Điểm trung bình | > 0.80 | 0.904 | Đạt |
| Độ trễ trung bình | < 1000ms | 1773ms | Chưa đạt |
| Độ trễ p95 | < 2000ms | 2609ms | Chưa đạt |
| Số lần fallback | 0 | 0 | Đạt |

Mẫu đo: 24/25 — 1 mẫu passthrough (nguồn trùng đích) bị loại khỏi mọi chỉ số vì không có model nào được gọi, judge vẫn chấm ~1.0 và điều đó chỉ làm đẹp số liệu.

Hai chỉ số dùng hai mẫu số khác nhau: **tỷ lệ đạt** tính trên 24 mẫu judge chấm được, còn **số lần fallback** tính trên cả 24 mẫu đã dịch — một mẫu judge từ chối chấm vẫn có thể đã fallback.

## 2. Điểm theo kiểu hội thoại và độ giàu ngữ cảnh

Hai chiều này tách riêng vì chúng đo hai năng lực khác nhau: hội thoại nhóm buộc Agent xử lý ngữ cảnh trộn nhiều ngôn ngữ, còn nhóm nghèo ngữ cảnh đo khả năng dịch khi không có gì để suy luận thêm.

**Kiểu hội thoại**

| Kiểu hội thoại | Số mẫu | Điểm trung bình | Tỷ lệ đạt |
|---|---|---|---|
| `direct` | 19 | 0.900 | 100% |
| `group` | 5 | 0.920 | 100% |

**Độ giàu ngữ cảnh**

| Độ giàu ngữ cảnh | Số mẫu | Điểm trung bình | Tỷ lệ đạt |
|---|---|---|---|
| `poor` | 6 | 0.900 | 100% |
| `rich` | 18 | 0.906 | 100% |

## 3. Điểm theo nhóm tình huống

Cột số mẫu quan trọng ở bảng này hơn các bảng khác: phần lớn nhóm chỉ có một đến hai mẫu, nên điểm trung bình của chúng không nói lên xu hướng.

| Nhóm | Số mẫu | Điểm trung bình | Tỷ lệ đạt |
|---|---|---|---|
| `acceptance` | 2 | 0.900 | 100% |
| `compliance` | 2 | 0.950 | 100% |
| `context_pronoun` | 1 | 0.900 | 100% |
| `context_reference` | 1 | 0.900 | 100% |
| `defect_report` | 1 | 0.900 | 100% |
| `elided_subject` | 1 | 0.900 | 100% |
| `escalation` | 1 | 0.900 | 100% |
| `handover` | 1 | 0.900 | 100% |
| `honorific` | 2 | 0.900 | 100% |
| `incident` | 2 | 0.900 | 100% |
| `multilingual_context` | 4 | 0.925 | 100% |
| `payment_milestone` | 2 | 0.900 | 100% |
| `requirement_clarify` | 1 | 0.800 | 100% |
| `schedule` | 1 | 0.900 | 100% |
| `scope_change` | 1 | 0.900 | 100% |
| `tech_abbrev` | 1 | 0.900 | 100% |

## 4. Điểm theo cặp ngôn ngữ

| Cặp | Số mẫu | Điểm trung bình | Tỷ lệ đạt |
|---|---|---|---|
| `de->en` | 1 | 1.000 | 100% |
| `en->de` | 1 | 0.900 | 100% |
| `en->fr` | 1 | 0.900 | 100% |
| `en->ja` | 1 | 0.900 | 100% |
| `en->th` | 1 | 0.900 | 100% |
| `en->vi` | 3 | 0.900 | 100% |
| `en->zh` | 2 | 0.900 | 100% |
| `es->en` | 1 | 1.000 | 100% |
| `es->vi` | 1 | 0.900 | 100% |
| `fr->en` | 2 | 0.900 | 100% |
| `ja->en` | 1 | 0.900 | 100% |
| `ja->vi` | 2 | 0.900 | 100% |
| `th->en` | 1 | 0.900 | 100% |
| `vi->en` | 4 | 0.875 | 100% |
| `vi->ja` | 1 | 0.900 | 100% |
| `zh->en` | 1 | 0.900 | 100% |

## 5. Chi tiết từng mẫu

| ID | Kiểu | Ngữ cảnh | Cặp | Nhóm | Điểm | Độ trễ | Câu gốc | Bản dịch hệ thống |
|---|---|---|---|---|---|---|---|---|
| gs-001 | direct | rich | vi->en | context_pronoun | 0.90 | 505ms | Anh xem qua rồi cho em xin ý kiến trước thứ S | Please review it and give me your feedback be |
| gs-002 | direct | rich | en->vi | scope_change | 0.90 | 262ms | We would also like to add two factor authenti | Chúng tôi cũng muốn thêm xác thực hai yếu tố  |
| gs-003 | direct | rich | vi->en | requirement_clarify | 0.80 | 255ms | Anh cho em hỏi báo cáo này xuất ra Excel hay  | Does this report export to Excel or PDF? |
| gs-004 | direct | poor | en->vi | defect_report | 0.90 | 290ms | The export button does nothing when I click i | Nút xuất không thực hiện hành động nào khi tô |
| gs-005 | direct | rich | ja->en | schedule | 0.90 | 362ms | こちらのテスト担当者は3名で、期間は2週間を希望します | There will be 3 people in charge of testing h |
| gs-006 | direct | rich | en->ja | honorific | 0.90 | 2484ms | We will send the test accounts by tomorrow no | 明日の午後までにテストアカウントを送ります |
| gs-007 | direct | rich | zh->en | payment_milestone | 0.90 | 2704ms | 第一期的付款我们会在下周三之前完成 | We will complete the payment for phase one by |
| gs-008 | direct | poor | en->zh | payment_milestone | 0.90 | 1670ms | The invoice has been sent to your finance dep | 这张发票已经在今天早上发给了你们的财务部 |
| gs-009 | direct | rich | fr->en | incident | 0.90 | 1419ms | Les utilisateurs sont déconnectés toutes les  | Users are being disconnected every five minut |
| gs-010 | direct | poor | en->fr | incident | 0.90 | 2553ms | We have escalated it to the on call engineer, | Nous avons escaladé cela vers l'ingénieur de  |
| gs-011 | direct | rich | de->en | compliance | 1.00 | 1512ms | Wie lange werden diese Protokolle gespeichert | How long are these logs stored and who has ac |
| gs-012 | direct | rich | en->de | compliance | 0.90 | 2430ms | Logs are kept for ninety days and only admini | Die Logs werden neunzig Tage lang gespeichert |
| gs-013 | direct | poor | es->vi | escalation | 0.90 | 1553ms | Necesitamos una respuesta hoy mismo, el clien | Chúng tôi cần một câu trả lời ngay hôm nay, k |
| gs-014 | direct | rich | th->en | acceptance | 0.90 | 1540ms | ผลการทดสอบผ่านทั้งหมด เรายินดีเซ็นรับมอบงานคร | The test results are all passed, we are pleas |
| gs-015 | direct | poor | en->th | acceptance | 0.90 | 2615ms | Please confirm the sign off before Friday so  | กรุณายืนยันการอนุมัติให้เสร็จสิ้นก่อนวันศุกร์ |
| gs-016 | direct | rich | vi->en | elided_subject | 0.90 | 1474ms | Sửa xong rồi nhé, em test lại giúp anh | I've fixed it, can you test it again for me? |
| gs-017 | direct | poor | en->vi | tech_abbrev | 0.90 | 2452ms | Please do not merge it until the QA sign off | Làm ơn đừng merge nó cho đến khi QA đồng ý |
| gs-018 | direct | poor | en->en | short_ambiguous | 0.90 | 212ms | Ok em | Ok em |
| gs-019 | direct | rich | ja->vi | handover | 0.90 | 1549ms | 引き継ぎ資料は金曜日までに共有します | Tài liệu bàn giao sẽ được chia sẻ vào thứ Sáu |
| gs-020 | direct | rich | vi->ja | honorific | 0.90 | 2575ms | Anh cho em hỏi phần hoàn tiền đã làm xong chư | 兄さん、返金の部分はもう完了しましたか？ |
| gs-021 | group | rich | vi->en | multilingual_context | 0.90 | 2479ms | Phần biểu đồ doanh thu em làm xong rồi, còn b | I've finished the revenue chart, and I'm stil |
| gs-022 | group | rich | en->zh | context_reference | 0.90 | 2552ms | The second one can be solved by caching, the  | 第二个风险可以通过缓存来解决，第一个风险需要您做出决定 |
| gs-023 | group | rich | fr->en | multilingual_context | 0.90 | 2421ms | Dans ce cas, nous pouvons ajouter les deux ra | In this case, we can add the two reports requ |
| gs-024 | group | rich | es->en | multilingual_context | 1.00 | 2403ms | Por favor envíen el cronograma detallado ante | Please send the detailed schedule before Frid |
| gs-025 | group | rich | ja->vi | multilingual_context | 0.90 | 2483ms | 原因はインデックスの設定ミスでした、明日リリースできます | Nguyên nhân là do thiết lập chỉ mục không chí |

## 6. Mẫu chưa đạt

Không có mẫu nào dưới ngưỡng.
## 7. Cách tái lập

```bash
python eval/run_eval.py
```

Đổi provider bằng biến `LLM_PROVIDER` trong `.env` rồi chạy lại để so sánh.
