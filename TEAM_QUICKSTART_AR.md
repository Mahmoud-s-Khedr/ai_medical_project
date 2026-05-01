# OCR Medicine Backend - Team Quickstart (Arabic)

اللغة: [English](TEAM_QUICKSTART_EN.md) | [العربية](TEAM_QUICKSTART_AR.md)

الملف ده معمول عشان أي حد في الفريق يقدر يشغل المشروع من الصفر، يجرب OCR search، ويتأكد من المخرجات بسرعة.

استخدم الرابط ده للبحث عن أدوية إضافية: http://eservices.edaegypt.gov.eg/EDASearch/SearchRegDrugs.aspx

## 1) المتطلبات قبل التشغيل

- macOS أو Linux
- Python 3.11 أو 3.12
- `pip`
- `tesseract` (برنامج نظام)

على macOS:

```bash
brew install tesseract
```

## 2) تجهيز البيئة لأول مرة

من داخل مجلد المشروع:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3) تجهيز قاعدة البيانات والبيانات

```bash
python3 manage.py migrate
python3 manage.py import_medicines --path medicines.csv
```

معلومة: أمر `import_medicines` بيعمل create/update تلقائي حسب `trade_name`.

## 4) تشغيل الـ Backend

```bash
python3 manage.py runserver 127.0.0.1:8000
```

الـ API base URL:

```text
http://127.0.0.1:8000/api/
```

## 5) المسارات الأساسية وواجهات التوثيق

- `GET /` يرجع `302` redirect إلى `/api/docs/`
- `GET /api/docs/` واجهة Swagger
- `GET /api/schema/` مخطط OpenAPI
- `GET /api/redoc/` واجهة ReDoc

## 6) المصادقة

معظم الـ endpoints محمية وتحتاج JWT Bearer token.

جلب token:

```bash
curl -X POST "http://127.0.0.1:8000/api/auth/token/" \
  -H "Content-Type: application/json" \
  -d '{"username":"<username>","password":"<password>"}'
```

الاستخدام في الطلبات:

```text
Authorization: Bearer <access_token>
```

## 7) أهم الـ Endpoints

- `GET /api/medicines/`
- `GET /api/medicines/?search=panadol`
- `GET /api/medicines/{id}/`
- `GET /api/medicines/{id}/interactions/`
- `POST /api/uploads/ocr-search/`
- `GET/POST /api/reminders/`
- `PATCH/DELETE /api/reminders/{id}/`
- `GET/POST /api/reminders/{id}/events/`
- `GET/PATCH/PUT /api/medical-record/`
- `GET /api/medical-record/summary/`

## 8) تجربة OCR Search من Terminal

```bash
curl -X POST "http://127.0.0.1:8000/api/uploads/ocr-search/" \
  -H "Authorization: Bearer <access_token>" \
  -F "image=@sample_medicine.png" \
  -F "top_k=5"
```

شكل response المتوقع يشمل:

- `ocr_raw_text`
- `ocr_confidence`
- `ocr_tokens`
- `matches`
- `match_confidence_tier` (`high|medium|low`)
- `action_hint` (`show_results|retake_photo`)

## 9) ملاحظات سلوك OCR

- لو `drug_detector.pt` مش موجود، النظام يستخدم full-image OCR fallback تلقائيًا.
- النظام يجرب phrase + token matching، وtoken fallback بيشتغل حتى لو phrase confidence ضعيف.

## 10) تجربة OCR بدون Django (CLI)

```bash
python3 cli_ocr_search.py sample_medicine.png --catalog medicines.csv --column trade_name
```

مفيد لاختبار OCR/fuzzy بسرعة بدون تشغيل السيرفر.

## 11) Postman للفريق

استورد الملفين:

- `postman/Medicine_OCR_API.postman_collection.json`
- `postman/Medicine_OCR_API.postman_environment.json`

## 12) YOLO (اختياري)

لو عندك موديل مدرب (`drug_detector.pt`):

- حطه في root المشروع بجانب `manage.py`، أو
- عدل `YOLO_MODEL_PATH` في `medicine_backend/settings.py`

## 13) مشاكل شائعة

1. `ModuleNotFoundError: No module named 'django'`
   - فعّل البيئة: `source .venv/bin/activate`
   - ثبّت المتطلبات: `pip install -r requirements.txt`

2. Tesseract غير موجود
   - ثبّت البرنامج على النظام (`brew install tesseract` على macOS)

3. OCR يرجع `matches` فاضي
   - تأكد إن `medicines.csv` اتعمله import.
   - استخدم صورة أوضح.
   - جرّب `top_k` أعلى (مثلاً 10).

4. `YOLO model not found`
   - رسالة طبيعية لو `drug_detector.pt` غير موجود.
   - النظام هيكمل full-image OCR fallback.

## 14) Check سريع قبل التسليم

```bash
python3 manage.py migrate
python3 manage.py import_medicines --path medicines.csv
python3 manage.py runserver 127.0.0.1:8000
```

ثم من terminal تانية:

```bash
curl -X POST "http://127.0.0.1:8000/api/uploads/ocr-search/" \
  -H "Authorization: Bearer <access_token>" \
  -F "image=@sample_medicine.png" \
  -F "top_k=5"
```
