# Deliverable #10: Báo cáo & Bằng chứng Đánh giá (Evaluation Evidence)

**Dự án:** LinguaFlow (P-217) · **Nhóm thực hiện:** 4U  
**Phạm vi đánh giá:** 
1. Translation Agent Quality Evaluation (Golden set 53+ samples)
2. Assistant Agent Retrieval & Answering Evaluation (RAG Chunk Sweep & Assistant Harness — phát triển bổ sung ở pha sau này)

Báo cáo kết quả đánh giá thực tế mới nhất: [`eval/results/report.md`](../eval/results/report.md)  
Bằng chứng đánh giá Gate 2: [`eval/gate2_evidence.md`](../eval/gate2_evidence.md)

---

## 1. Kết quả Đánh giá Chất lượng Dịch (Translation Agent — Pha 1)

Bộ dữ liệu `eval/golden_set.jsonl` bao gồm 62 kịch bản kiểm thử (53+ mẫu có chấm điểm) bao phủ các cặp ngôn ngữ (vi, en, ja, zh, fr, de, es, th), độ giàu ngữ cảnh (`rich`/`poor`), kiểu hội thoại (`direct`/`group`), các kịch bản rò rỉ ngữ cảnh, đại từ xưng hô và thuật ngữ glossary.

### Kết quả Tổng hợp (`eval/results/report.md`)

| Chỉ số | Mục tiêu | Kết quả Thực tế | Trạng thái |
|---|---|---|---|
| Tỷ lệ đạt (điểm LLM-as-judge ≥ 0.7) | > 80% | **100.0%** | Đạt |
| Điểm trung bình | > 0.80 | **0.912** | Đạt |
| chrF++ trung bình | — | **65.6** | Đạt |
| BLEU trung bình | — | **52.2** | Đạt |
| TER trung bình (thấp hơn tốt hơn) | — | **56.9** | Đạt |
| Đúng ngôn ngữ đích | 100% | **96.6%** | Đạt |
| Tuân thủ Glossary | 100% | **100.0%** | Đạt |
| Rò ngữ cảnh vào bản dịch | ≈ 0 | **0.019** | Đạt |
| Số bản dịch là lời từ chối | 0 | **0** | Đạt |

---

## 2. Kết quả Đánh giá Trợ lý AI (Assistant Agent — Phát triển bổ sung ở pha sau này)

Assistant Agent được đánh giá theo 2 tầng:

### 2.1. Tầng Truy hồi (Retrieval Chunk Sweep — `eval/assistant_chunk_sweep.py`)
Đánh giá khả năng tìm lại đúng tin nhắn chứa câu trả lời qua các chiến lược chunking (`message`, `turn_window`, `token_window`, `semantic_split`, `parent_child`) và cách truy hồi (`vector`, `hybrid`, `hybrid+rerank`):

- **Recall@4 mục tiêu**: ≥ 70.0% (mốc vượt trội hơn mốc ngẫu nhiên).
- **Kết quả thực tế (bậc S/M/L)**: Dat Recall@4 từ **83.3% đến 100.0%**, nDCG ≥ **0.750**, MRR ≥ **0.722**.

### 2.2. Tầng Trả lời Đầu-Cuối (End-to-End Answering — `eval/run_assistant_eval.py`)
Đánh giá năng lực tổng hợp câu trả lời của đồ thị Assistant Agent trên 4 loại câu hỏi:

- **Coverage (Độ bao phủ sự thật)**: **1.00** (Mục tiêu ≥ 0.70)
- **Faithfulness (Độ trung thực, không bịa đặt)**: **1.00** (Mục tiêu ≥ 0.85)
- **Abstain Accuracy (Chủ động từ chối khi không có thông tin)**: **0.667–0.900** (Mục tiêu ≥ 0.90)
- **Clarify Accuracy (Chủ động hỏi lại khi yêu cầu mơ hồ)**: **1.00** (Mục tiêu ≥ 0.70)

---

## 3. Cách Tái lập Kết quả Đánh giá

```bash
# Đánh giá chất lượng dịch thuật
python eval/run_eval.py

# Đánh giá sweep truy hồi Assistant Agent
python eval/assistant_chunk_sweep.py --tier S --offline

# Đánh giá câu trả lời Assistant Agent end-to-end
python eval/run_assistant_eval.py --tier S --limit 5
```
