# BÁO CÁO ĐÁNH GIÁ CHẤT LƯỢNG DỊCH

**Dự án:** LinguaFlow (P-217) · **Nhóm thực hiện:** 4U
**Thời điểm chạy:** 2026-09-01 16:01 UTC
**Provider dịch:** gemini · **Model:** gemini-3.5-flash
**Provider chấm điểm:** mistral · **Model chấm:** mistral-medium-latest
**Bộ dữ liệu:** `eval/golden_set.jsonl` (5 mẫu)

> Điểm số do LLM tự chấm (LLM-as-judge), không phải đánh giá của người thật. Kết quả dùng để so sánh tương đối giữa các lần chạy và giữa các provider.

## 1. Chỉ số tổng hợp

| Chỉ số | Mục tiêu | Thực tế | Trạng thái |
|---|---|---|---|
| Tỷ lệ đạt (điểm ≥ 0.7) | > 80% | 100.0% | Đạt |
| Điểm trung bình | > 0.80 | 0.870 | Đạt |
| Độ trễ trung bình | < 1000ms | 5025ms | Chưa đạt |
| Độ trễ p95 | < 2000ms | 9714ms | Chưa đạt |
| Số lần fallback | 0 | 0 | Đạt |
| chrF++ trung bình | — | 62.6 | Đạt |
| BLEU trung bình | — | 41.6 | Đạt |
| TER trung bình (thấp hơn tốt hơn) | — | 54.8 | Đạt |
| Đúng ngôn ngữ đích | 100% | 100.0% | Đạt |
| Tuân thủ glossary (0 mẫu có thuật ngữ) | 100% | — | Đạt |
| Rò ngữ cảnh vào bản dịch | ≈ 0 | 0.036 | Đạt |
| Số bản dịch là lời từ chối | 0 | 0 | Đạt |

Mẫu đo: 5/5 — 0 mẫu passthrough (nguồn trùng đích) bị loại khỏi mọi chỉ số vì không có model nào được gọi, judge vẫn chấm ~1.0 và điều đó chỉ làm đẹp số liệu.

Hai chỉ số dùng hai mẫu số khác nhau: **tỷ lệ đạt** tính trên 5 mẫu judge chấm được, còn **số lần fallback** tính trên cả 5 mẫu đã dịch — một mẫu judge từ chối chấm vẫn có thể đã fallback.

## 2. Điểm theo kiểu hội thoại và độ giàu ngữ cảnh

Hai chiều này tách riêng vì chúng đo hai năng lực khác nhau: hội thoại nhóm buộc Agent xử lý ngữ cảnh trộn nhiều ngôn ngữ, còn nhóm nghèo ngữ cảnh đo khả năng dịch khi không có gì để suy luận thêm.

**Kiểu hội thoại**

| Kiểu hội thoại | Số mẫu | Điểm trung bình | Tỷ lệ đạt |
|---|---|---|---|
| `direct` | 5 | 0.870 | 100% |

**Độ giàu ngữ cảnh**

| Độ giàu ngữ cảnh | Số mẫu | Điểm trung bình | Tỷ lệ đạt |
|---|---|---|---|
| `poor` | 1 | 0.700 | 100% |
| `rich` | 4 | 0.912 | 100% |

## 3. Điểm theo nhóm tình huống

Cột số mẫu quan trọng ở bảng này hơn các bảng khác: phần lớn nhóm chỉ có một đến hai mẫu, nên điểm trung bình của chúng không nói lên xu hướng.

| Nhóm | Số mẫu | Điểm trung bình | Tỷ lệ đạt |
|---|---|---|---|
| `context_pronoun` | 1 | 0.900 | 100% |
| `defect_report` | 1 | 0.700 | 100% |
| `requirement_clarify` | 1 | 0.900 | 100% |
| `schedule` | 1 | 0.950 | 100% |
| `scope_change` | 1 | 0.900 | 100% |

## 4. Điểm theo cặp ngôn ngữ

| Cặp | Số mẫu | Điểm trung bình | Tỷ lệ đạt |
|---|---|---|---|
| `en->vi` | 2 | 0.800 | 100% |
| `ja->en` | 1 | 0.950 | 100% |
| `vi->en` | 2 | 0.900 | 100% |

## 5. Kết quả Sweep truy hồi (Retrieval Sweep)

> Đánh giá hiệu năng và chất lượng truy hồi ngữ cảnh của các mô hình nhúng và chiến lược truy vấn.

**Retrieval Ngữ cảnh Dịch (`eval/rag_sweep.py` — Run ID: `20260822-064517`)**

| Mô hình Embedding | Chiến lược truy vấn | Kịch bản | Hit Rate (hit@3) | MRR | Hạng TB | Độ trễ truy vấn | Hit ngẫu nhiên |
|---|---|---|---|---|---|---|---|
| `gemini:models/gemini-embedding-001` | `message` | 9 | 22.2% | 0.259 | 8.56/34 | 0.0ms | 8.8% |
| `gemini:models/gemini-embedding-001` | `message_plus_previous` | 9 | 0.0% | 0.120 | 10.44/34 | 1047.7ms | 8.8% |
| `gemini:models/gemini-embedding-001` | `message_plus_recent` | 9 | 0.0% | 0.101 | 13.22/34 | 1040.1ms | 8.8% |
| `gemini:models/gemini-embedding-001` | `recent_only` | 9 | 0.0% | 0.077 | 15.78/34 | 1050.7ms | 8.8% |

**Retrieval Assistant Agent (`eval/assistant_chunk_sweep.py` — Run ID: `20260901-155826` [offline mode])**

| Bậc | Chiến lược | Cách truy hồi | Chunks | Recall@4 | nDCG | MRR | Ngẫu nhiên |
|---|---|---|---|---|---|---|---|
| `S` | `message` | `vector` | 50 | 100.0% | 0.917 | 0.889 | 8.0% |
| `S` | `message` | `hybrid` | 50 | 100.0% | 0.855 | 0.806 | 8.0% |
| `S` | `turn_window` | `vector` | 7 | 83.3% | 0.750 | 0.722 | 57.1% |
| `S` | `turn_window` | `hybrid` | 7 | 83.3% | 0.688 | 0.639 | 57.1% |
| `S` | `token_window` | `vector` | 3 | 100.0% | 1.000 | 1.000 | 100.0% |
| `S` | `token_window` | `hybrid` | 3 | 100.0% | 0.938 | 0.917 | 100.0% |
| `S` | `semantic_split` | `vector` | 50 | 100.0% | 0.917 | 0.889 | 8.0% |
| `S` | `semantic_split` | `hybrid` | 50 | 100.0% | 0.855 | 0.806 | 8.0% |
| `S` | `parent_child` | `vector` | 9 | 100.0% | 0.938 | 0.917 | 44.4% |
| `S` | `parent_child` | `hybrid` | 9 | 100.0% | 1.000 | 1.000 | 44.4% |

## 6. Chi tiết từng mẫu

| ID | Kiểu | Ngữ cảnh | Cặp | Nhóm | Điểm | Độ trễ | Câu gốc | Bản dịch hệ thống |
|---|---|---|---|---|---|---|---|---|
| gs-001 | direct | rich | vi->en | context_pronoun | 0.90 | 10813ms | Anh xem qua rồi cho em xin ý kiến trước thứ S | Please take a look and let me know your feedb |
| gs-002 | direct | rich | en->vi | scope_change | 0.90 | 2954ms | We would also like to add two factor authenti | Chúng tôi cũng muốn bổ sung xác thực hai yếu  |
| gs-003 | direct | rich | vi->en | requirement_clarify | 0.90 | 2699ms | Anh cho em hỏi báo cáo này xuất ra Excel hay  | May I ask if this report should be exported t |
| gs-004 | direct | poor | en->vi | defect_report | 0.70 | 5318ms | The export button does nothing when I click i | An toàn, tự nhiên, chính xác. Let's use "Nút  |
| gs-005 | direct | rich | ja->en | schedule | 0.95 | 3340ms | こちらのテスト担当者は3名で、期間は2週間を希望します | We will have 3 testers on our end, and we wou |

## 7. Mẫu chưa đạt

Không có mẫu nào dưới ngưỡng.
## 8. Cách tái lập

```bash
python eval/run_eval.py
```

Đổi provider bằng biến `LLM_PROVIDER` trong `.env` rồi chạy lại để so sánh.
