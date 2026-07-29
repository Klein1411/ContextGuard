# Định danh dự án

ContextGuard là package Python và dịch vụ FastAPI ưu tiên offline, dùng để kiểm tra văn bản sau nén có còn giữ các dữ kiện và logic quan trọng của văn bản gốc hay không. Thư mục gốc: `D:\fact_safeguard`.

# Phạm vi đã khóa

- Core chỉ nhận text: `original_text` và `candidate_text`.
- Ngôn ngữ: tiếng Việt và tiếng Anh, với các chế độ `vi`, `en`, `auto`.
- Profile: `general`, `academic`, `business`, `technical`.
- Policy: `lenient`, `balanced`, `strict`; `strict` là mặc định.
- Trạng thái an toàn: `PASS`, `FAIL`, `UNCERTAIN`.
- Core deterministic và offline. Compressor, semantic verifier là các adapter.
- Core không có React UI, bộ đọc tài liệu, cache service, telemetry hoặc remote call.
- Toàn repository chỉ cho phép đúng ba file Markdown; file này là context sống của dự án.

# Kiến trúc

`ContextGuard` điều phối normalization, extraction, deterministic validator, policy mapping, scoring và reporting. Các route FastAPI dùng cùng Pydantic schema với Python API. Compressor adapter có thể nhận `ProtectedSpan` và trả candidate text; core không import compressor cụ thể.

Bản đầu dùng regex nhẹ và quy tắc bằng chứng bảo thủ. Locale mơ hồ, relation chưa hỗ trợ và optional adapter không khả dụng sẽ tạo warning hoặc `UNCERTAIN`, không tự đoán.

# Hợp đồng API

Route V1: `GET /v1/health`, `GET /v1/capabilities`, `POST /v1/analyze`, `POST /v1/validate`. Enum và response field public nằm trong `src/context_guard/schemas/models.py`. Breaking change phải dùng `/v2`.

# Quyết định kỹ thuật

- Runtime mục tiêu là Python 3.11; ưu tiên Windows native.
- `uv` quản lý dependency và lockfile. Core runtime không phụ thuộc ML nặng.
- Vi phạm deterministic critical dùng fallback strict tới `USE_ORIGINAL`.
- Risk score dùng weighted maximum/accumulation có tài liệu, giới hạn trong `[0, 1]`.
- Exact matching chạy trước semantic matching. Semantic verification là optional và trì hoãn.
- Input có giới hạn và bị từ chối bằng lỗi có cấu trúc; không cắt âm thầm.

# Milestone

- M0 foundation: hoàn tất; audit repository sạch và các thay đổi đã commit.
- M1 schema/API contract: triển khai và đã chạy contract test.
- M2 ExactGuard: triển khai cho số, phần trăm, tiền, ngày/giờ, đơn vị, version, URL/email, path, flag và code literal.
- M3 LogicGuard: triển khai phủ định, so sánh, điều kiện, ngoại lệ và modality song ngữ.
- M4 relation/entity: đã thêm xử lý cấu trúc tường minh bảo thủ; semantic NER rộng vẫn giới hạn.
- M5 benchmark: đã có Tier A (300) và Tier B (2.001), runner deterministic, metric theo category, chữ ký tái lập, artifact validation và helper promotion có guard. Tier A đã audit/freeze; Tier B vẫn synthetic/unverified.
- M6 compressor adapter: rule-based protected-span compressor, controlled mutation, Tier C unverified candidate và LLMLingua-2 lazy revision-pinned adapter đã được chạy thử; LLM summarizer vẫn là boundary unavailable rõ ràng.
- M7 semantic verifier: orchestration chỉ chạy khi `UNCERTAIN`, fallback an toàn khi lỗi/không khả dụng, Transformers NLI lazy revision-pinned adapter. CPU smoke và benchmark uncertainty-path đã đạt; đánh giá chất lượng vẫn giới hạn.
- M8 packaging: package, CLI, FastAPI, Docker non-root, health check, build image local và container smoke đã hoàn tất.
- M9 final audit: deterministic gate, Tier A audit, dependency/security check, đo adapter thật, đo resource và promotion artifact Tier A audited đã hoàn tất; mở rộng chất lượng optional còn hạn chế.

# Phạm vi mở rộng đã khóa cho goal hiện tại

- M10a đo R1–R5: direct Python, ASGI in-process, localhost HTTP, Docker HTTP và direct hybrid. R6–R9 được chuyển sang M13 để không chồng với compressor/token-saving evaluation.
- M11 tách rõ `externally_sourced`, `natural`, `translated` và `adversarial`; bản dịch không được gọi là naturally Vietnamese. Dev/hidden split tối thiểu 70/30.
- M12 chỉ dùng thuật ngữ `blind multi-agent AI review`, `AI-reviewed` và `AI-adjudicated`; không giả danh human/domain-expert review. Reviewer phải không thấy label, mutation, prediction hoặc builder rationale.
- M13 dùng gross saving và safe effective saving; safe saving là metric chính. Break-even inference là mục tiêu phụ, được báo limitation nếu RTX 3050 4 GB không chạy ổn định.
- Báo cáo tiến độ Word là artifact public được commit riêng; không tạo thêm Markdown ngoài ba file được phép.
- Dữ liệu dài hạn nằm ngoài repository tại `D:\fact_safeguard_data`; cleanup không được xóa thư mục này.

# Trạng thái hiện tại

Status: `PARTIALLY_COMPLETED` (M0–M9 đã hoàn tất; goal mở rộng M10–M14 đang thực thi; Tier B, output compressor thật và hybrid semantic vẫn có giới hạn rõ ràng).

Repository trống lúc bắt đầu. Audit môi trường: Windows 11, i5-12500H, RAM 24 GB, RTX 3050 Laptop 4 GB, Python 3.11, `uv` và Git khả dụng. Không có model hoặc cache trong repository.

# Công việc đã hoàn thành

Đã triển khai repository foundation, public schema, FastAPI V1, CLI, ExactGuard, LogicGuard, EntityGuard, RelationGuard, risk/policy mapping, rule-based protected-span compressor, controlled mutation adapter, Tier C candidate generator, optional adapter boundary, semantic fallback orchestration và test suite.

# Kết quả đã xác minh

Audit baseline mới ngày 2026-07-29 với `uv run`/Python 3.11.9: 55 pytest test pass; Ruff pass; mypy pass trên 33 source file; `uv lock --check` và `uv pip check` pass. Đây là số liệu chạy thật mới nhất; các đoạn lịch sử cũ không được dùng để thay thế kết quả hiện tại. Coverage 80% line là kết quả audit trước đó và sẽ được chạy lại ở M14.

Ngày 2026-07-29 với Python 3.11.9: 55 pytest test pass; Ruff pass; mypy pass trên 33 source file; package build và clean-wheel smoke pass; coverage 80% line (không tuyên bố ngưỡng tối thiểu). Với seed `20260729`, Tier A `golden_v0_provisional` có 300 mẫu (150 SAFE, 150 UNSAFE), đúng 75 mẫu cho mỗi domain: false acceptance `0.0`, unsafe detection recall `1.0`, false rejection `0.0`, precision `1.0`, P50/P95 `0.362/0.604 ms`, peak RAM `30.414 MB`, VRAM chưa đo. Tier B `mutation_v0_provisional` có 2.001 mẫu (218 SAFE, 1.783 UNSAFE), gồm 109 safe date-format và 109 safe identity: false acceptance `0.0`, unsafe detection recall `1.0`, false rejection `0.0`, precision `1.0`, P50/P95 `1.305/2.224 ms`, peak RAM `38.375 MB`, VRAM chưa đo. Hai run đều đạt metric-only gate (recall ≥95%, FAR ≤2%, P95 ≤50 ms); promotion Tier A audited, contract gate và regression gate được kiểm tra riêng.

ExactGuard có regression cho fact bị duplicate, thêm mới và literal mới; relation có metric–dataset, config–component, method–dataset; LogicGuard từ chối condition/exception bị đổi. Tier C rule-based tạo 300 candidate UTF-8 với `label_status=unverified`, không gán quality metric. LLMLingua-2 thật trên 20 mẫu dùng `microsoft/llmlingua-2-xlm-roberta-large-meetingbank@ebaba9b`, trung bình `1,501.630 ms/mẫu`, RSS khoảng `1,984.902 MB`; mọi output vẫn `unverified` và không được promote.

Docker image `contextguard:local` build thành công; container non-root trả HTTP 200 ở `/v1/health`; `/v1/capabilities` và `/v1/validate` smoke pass. `run_hybrid_benchmark` được chạy trên 20 ca `UNCERTAIN` identity: deterministic false rejection `1.0`, hybrid false rejection `0.0`, semantic call `20/20`, P50/P95 `98.695/102.872 ms`, RSS peak `1,481.086 MB`. Bộ provisional 300/2.001 không có `UNCERTAIN` nên không gọi semantic adapter; đây là đo resource/behavior, không phải quality claim.

GPU follow-up dùng CUDA venv bên ngoài với `torch 2.8.0+cu126`, nhận RTX 3050 và chạy 20 ca uncertainty-path: semantic call `20/20`, `PASS 20/20`, P50/P95 `17.087/117.275 ms`, RSS peak `2,625.801 MB`, peak allocated/reserved VRAM `1,120.0 MB` trên tổng `4,095.5 MB`. Đây là metric-only synthetic/unverified smoke; venv mặc định của repository vẫn CPU-only.

Mixed semantic smoke gồm 20 ca uncertain (16 unsafe paraphrase có kiểm soát, 4 safe identity) trên CUDA: hybrid false acceptance `0.0`, unsafe recall `1.0`, false rejection `0.0`, precision `1.0`, fallback `0.2`, P50/P95 `21.862/310.104 ms`, RSS peak `2,619.078 MB`, VRAM peak `1,120.0 MB`. Nhãn vẫn `synthetic_unverified`, không phải golden-set hoặc production claim.

Hybrid `hybrid_v0_audited` gồm 100 ca (50 SAFE entailment, 50 UNSAFE contradiction), tất cả deterministic `UNCERTAIN`. CUDA NLI gọi semantic verifier `100/100` lần và đạt false acceptance `0.0`, unsafe recall `1.0`, false rejection `0.0`, precision `1.0`, fallback `0.0`, P50/P95 `18.161/26.746 ms`, RSS peak `2,618.461 MB`, VRAM peak `1,122.0 MB`. Manifest và predictions được giữ trong `artifacts/final/`; đây là benchmark audited có kiểm soát, chưa đại diện cho natural-language coverage rộng.

Tier A audit tái sinh khớp chính xác `300/300`, xem xét toàn bộ record theo semantics của template song ngữ, có 300 ID và cặp text unique, cân bằng `75` cho mỗi language/label cell và đúng mutation count. Bản audited là `benchmarks/datasets/golden_v0_audited.jsonl` với `label_status=audited`; reviewer là Codex, không phải domain expert bên ngoài. Run audited đã validate và promote đúng whitelist sáu file trong `artifacts/final/`.

`pip-audit --local` không phát hiện known vulnerability; secret scan, large-file scan, forbidden-path scan và model-weight scan đều sạch.

# Giới hạn đã biết

- Deterministic V1 chưa chứng minh được unrestricted natural-language equivalence.
- Entity và relation xử lý bảo thủ, có thể trả `UNCERTAIN`.
- Tier A được audit theo controlled template nhưng chưa được domain expert độc lập review. Tier B vẫn là controlled synthetic record; claim ngoài audited deterministic set vẫn provisional.
- Chưa đo được token savings end-to-end. LLMLingua-2 có chi phí CPU/RAM cao; smoke 20 mẫu chưa phải quality gate.
- Hybrid semantic đã có audited benchmark 100 ca và đạt gate trên tập có kiểm soát; vẫn cần tập tự nhiên rộng hơn để khẳng định khả năng tổng quát. Full provisional set không có `UNCERTAIN`; CUDA đo trong môi trường ngoài, không phải guarantee production.
- FastAPI integration test còn upstream Starlette/httpx deprecation warning; test vẫn pass.
- Docker build và non-root smoke đã xác minh local; chưa publish registry hoặc deploy production.

# Cải tiến để sau

- FastAPI + React UI sau khi API V1, benchmark mở rộng, core quality gate và semantic evaluation riêng ổn định.
- Cache thành project riêng.
- SmartContext Gateway về sau.
- CC-DFlash integration về sau.
- Semantic verifier không được thay thế deterministic core.
- PDF/DOCX adapter thuộc repository bên ngoài.
- Distributed deployment về sau.

# Hygiene repository

File tạm phải nằm trong `.runtime/`. Dữ liệu dài hạn và checkpoint nằm trong `D:\fact_safeguard_data` với các thư mục `raw`, `extracted`, `normalized`, `model_cache`, `reviewer_runs`, `benchmark_cache` và `manifests`; cleanup phải giữ nguyên toàn bộ data home này. Final benchmark artifact chỉ nằm trong `artifacts/final/` và đúng whitelist của spec; `hybrid_manifest.json` và `hybrid_predictions.jsonl` là hai artifact bổ sung cần thiết cho benchmark semantic audited và được ghi rõ ở trên. Model dùng external cache, không copy vào Git. Source và test không chứa generated file ngoài các dataset/artifact đã được chỉ định.

# Việc tiếp theo

Hoàn tất M10a runtime matrix, sau đó mở rộng dataset có phân tầng natural/translated/adversarial, chạy blind multi-agent AI review, đo token savings end-to-end và tạo báo cáo Word public trước khi đưa ra claim production hoặc paper-grade. Không promote synthetic/unverified run; `promote_run` chỉ nhận `label_status` `verified` hoặc `audited` và artifact set đã validate.
