# خط معالجة OCR للبحث عن الأدوية

اللغة: [English](README.md) | [العربية](README_AR.md)

## نظرة عامة

هذا المستودع يحتوي على إعداد Backend كامل للتشغيل المحلي لبحث الأدوية بالـ OCR وتتبع التذكيرات، مع ملفات تدريب اختيارية.

المسارات العملية داخل المشروع:

1. Django REST API لكتالوج الأدوية، OCR search، التذكيرات، وملف طبي.
2. نوتبوك تدريب YOLO (`mazen_first_(2)_(4).ipynb`) لاكتشاف علبة الدواء.
3. مسار CLI محلي لتجربة OCR + fuzzy search بدون تشغيل Django.

## خريطة المستندات

- دليل الفريق السريع (English): [TEAM_QUICKSTART_EN.md](TEAM_QUICKSTART_EN.md)
- دليل الفريق السريع (العربية): [TEAM_QUICKSTART_AR.md](TEAM_QUICKSTART_AR.md)
- README (English): [README.md](README.md)

## الملفات المهمة

- `manage.py`: نقطة تشغيل مشروع Django.
- `api/`: تطبيق Django للمصادقة، الأدوية، OCR search، التذكيرات، والسجل الطبي.
- `medicine_backend/`: إعدادات المشروع والروابط.
- `ai/ocr_pipeline.py`: تحسين الصورة + OCR (EasyOCR/Tesseract مع تجربة زوايا).
- `cli_ocr_search.py`: نسخة standalone للـ OCR + fuzzy search على CSV.
- `medicines.csv`: كتالوج تجريبي للاستيراد والاختبار.
- `postman/Medicine_OCR_API.postman_collection.json`: Postman collection جاهزة.
- `postman/Medicine_OCR_API.postman_environment.json`: إعدادات بيئة محلية لـ Postman.
- `mazen_first_(2)_(4).ipynb`: مسار تدريب YOLO.

## المتطلبات

- macOS أو Linux
- Python 3.11 أو 3.12 (مفضل للتوافق مع مكتبات OCR والرؤية)
- `pip`
- برنامج `tesseract` على مستوى النظام

التثبيت على macOS:

```bash
brew install tesseract
```

## تجهيز البيئة

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

اختياري للتجربة بدون Django:

```bash
pip install -r requirements-minimal.txt
```

## تشغيل Django Backend

```bash
source .venv/bin/activate
python manage.py migrate
python manage.py import_medicines --path medicines.csv
python manage.py runserver 127.0.0.1:8000
```

الرابط الأساسي:

```text
http://127.0.0.1:8000
```

## المسارات الأساسية والوثائق

- `GET /` يرجع `302` redirect إلى `/api/docs/`.
- `GET /api/docs/` واجهة Swagger.
- `GET /api/schema/` مخطط OpenAPI.
- `GET /api/redoc/` واجهة ReDoc.

## ملاحظة المصادقة

معظم الـ API endpoints محمية وتحتاج JWT Bearer token.

تدفق المصادقة المعتاد:

1. `POST /api/auth/token/` للحصول على `access` و`refresh`.
2. إرسال `Authorization: Bearer <access_token>` مع الطلبات المحمية.
3. استخدام `POST /api/auth/token/refresh/` عند انتهاء صلاحية access.

## أهم الـ API Endpoints

المصادقة:

- `POST /api/auth/register/`
- `POST /api/auth/token/`
- `POST /api/auth/token/refresh/`
- `POST /api/auth/token/verify/`
- `POST /api/auth/logout/`
- `GET/PATCH /api/auth/me/`
- `POST /api/auth/me/change-password/`
- `POST /api/auth/password-reset/`
- `POST /api/auth/password-reset/confirm/`

الأدوية:

- `GET /api/medicines/`
- `GET /api/medicines/?search=panadol`
- `GET /api/medicines/{id}/`
- `GET /api/medicines/{id}/interactions/`

OCR:

- `POST /api/uploads/ocr-search/`

التذكيرات:

- `GET/POST /api/reminders/`
- `GET/PATCH/DELETE /api/reminders/{id}/`
- `GET/POST /api/reminders/{id}/events/`

السجل الطبي:

- `GET/PATCH/PUT /api/medical-record/`
- `GET /api/medical-record/summary/`
- `GET/POST /api/medical-record/diagnoses/`
- `GET/POST /api/medical-record/allergies/`
- `GET/POST /api/medical-record/vitals/`
- `GET/POST /api/medical-record/lab-results/`
- `GET/POST /api/medical-record/visits/`

## ملاحظات سلوك OCR Search

- إذا `drug_detector.pt` غير موجود، النظام يعمل fallback تلقائي إلى full-image OCR.
- الـ OCR يطلع phrase/tokens ثم يعمل fuzzy matching على أسماء الأدوية.
- token fallback يستمر حتى لو phrase match ضعيف.
- الاستجابة تتضمن:
  - `match_confidence_tier`: `high` أو `medium` أو `low`
  - `action_hint`: `show_results` أو `retake_photo`

## مثال OCR Search (API)

```bash
curl -X POST "http://127.0.0.1:8000/api/uploads/ocr-search/" \
  -H "Authorization: Bearer <access_token>" \
  -F "image=@sample_medicine.png" \
  -F "top_k=5"
```

مثال response:

```json
{
  "ocr_raw_text": "Panadol Extra",
  "ocr_confidence": 0.82,
  "ocr_angle": 0,
  "ocr_engine": "easyocr",
  "ocr_tokens": ["Panadol Extra", "Panadol", "Extra"],
  "matches": [
    {
      "id": 2,
      "trade_name": "Panadol Extra",
      "active_ingredient": "Paracetamol + Caffeine",
      "strength": "500 mg + 65 mg",
      "dosage_form": "tablet",
      "name": "Panadol Extra",
      "score": 0.95,
      "matched_query": "Panadol Extra"
    }
  ],
  "match_confidence_tier": "high",
  "action_hint": "show_results",
  "message": ""
}
```

## تجربة CLI بدون Django

لتجربة OCR + fuzzy search مباشرة على صورة وCSV:

```bash
python cli_ocr_search.py sample_medicine.png --catalog medicines.csv --column trade_name
```

## YOLO (اختياري)

- التدريب عبر `mazen_first_(2)_(4).ipynb`.
- خزّن مفتاح Roboflow في متغير بيئة بدل hardcode:

```bash
export ROBOFLOW_API_KEY="your_key_here"
```

- ضع `drug_detector.pt` في جذر المشروع (أو عدّل `YOLO_MODEL_PATH` في settings).

## Postman

استورد:

- `postman/Medicine_OCR_API.postman_collection.json`
- `postman/Medicine_OCR_API.postman_environment.json`

## مشاكل شائعة

1. `ModuleNotFoundError: No module named 'django'`
   - فعّل البيئة: `source .venv/bin/activate`
   - ثبّت المتطلبات: `pip install -r requirements.txt`

2. Tesseract غير متوفر
   - ثبّت البرنامج على النظام (macOS: `brew install tesseract`)

3. OCR يرجع matches فارغة
   - تأكد من استيراد medicines.
   - استخدم صورة أوضح.
   - جرّب `top_k` أعلى.

4. تحذير `YOLO model not found`
   - طبيعي إذا `drug_detector.pt` غير موجود.
   - سيتم استخدام full-image OCR fallback تلقائيًا.
