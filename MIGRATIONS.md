إعداد Flask-Migrate (Alembic)

بعد إضافة `Flask-Migrate` إلى `requirements.txt`، اتبع الخطوات التالية في بيئة التطوير:

```bash
# تثبيت الحزم
python3 -m pip install -r requirements.txt

# ضبط متغير البيئة (مثال لينكس / macOS)
export FLASK_APP=app.py

# تهيئة مجلد الترحيلات (مرة واحدة)
flask db init

# إنشاء ترحيل جديد بعد أي تغيّر في النماذج
flask db migrate -m "Add your message"

# تطبيق الترحيلات
flask db upgrade
```

ملاحظات:
- تأكد من عمل نسخة احتياطية من `site.db` قبل تطبيق الترحيلات على قواعد بيانات الإنتاج.
- في بيئة الحاويات/خوادم CI قد تفضل تشغيل `flask db upgrade` كجزء من عمليات النشر.
