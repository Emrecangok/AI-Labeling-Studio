🏷️ AI Labeling Studio

AI Labeling Studio, kodlama bilgisine ihtiyaç duymadan Büyük Dil Modellerini (LLM) kullanarak metin verilerini Relevant (1) veya Irrelevant (0) şeklinde etiketlemenizi sağlayan, Streamlit tabanlı açık kaynaklı bir annotation aracıdır.

Bu araç ile binlerce satırlık veriyi dakikalar içinde analiz edebilir, sonuçları arayüz üzerinde filtreleyip düzeltebilir  ve Excel / JSON formatında dışarı aktarabilirsiniz.

🔗 Repo: https://github.com/Emrecangok/AI-Labeling-Studio

🚀 Özellikler

Çoklu Model Desteği: OpenAI (GPT-4o, GPT-3.5) ve Google Gemini (Flash, Pro)

Paralel İşleme: Concurrent Futures ile çoklu thread desteği

Detaylı Prompt Yönetimi: Role / Include / Exclude / Output ayrımı

Akıllı Arayüz: Filtreleme, arama ve manuel düzeltme

Proje Yönetimi: Prompt ayarlarını proje bazlı kaydetme

Esnek Çıktı: Excel (.xlsx) ve JSON dışa aktarma

📥 Kurulum
1. Repoyu İndirin

git clone https://github.com/Emrecangok/AI-Labeling-Studio.git

cd AI-Labeling-Studio

2. Gerekli Paketleri Kurun

pip install -r requirements.txt

3. Uygulamayı Çalıştırın

streamlit run main.py

Tarayıcı otomatik açılmazsa:

http://localhost:8501

🧠 Kullanım Kılavuzu

Uygulama arayüzü 3 ana aşamadan oluşur:

Ayarlar

Prompt Tasarımı

Sonuç Kontrolü

⚙️ Adım 1: API ve Sistem Ayarları (Sol Menü)
Ayar	Açıklama
📂 Proje Seçimi	Daha önce kaydedilmiş .json ayarlarını yükler
🤖 API Provider	OpenAI veya Google Gemini
🧠 Model	Örn: gpt-4o-mini, gemini-1.5-flash
⚡ Threads	Aynı anda işlenecek satır sayısı (Önerilen: 5–10)
📝 Adım 2: Veri Yükleme ve Prompt Tasarımı
1. Veri Setini Yükle

Desteklenen formatlar:

CSV

XLSX

JSON

JSONL

Yükleme sonrası Analysis Column (analiz edilecek metin sütunu) seçilir.

2. Prompt Alanlarını Doldur

Not: Marka Adı ve Proje Kayıt Adı sadece sizin takibiniz içindir, modele gönderilmez.

Prompt Bileşenleri

1️⃣ Role
AI’a kimliğini tanımlayın.
Örn: “Sen kıdemli bir veri analistisin.”

2️⃣ Include (Relevant – 1)
Hangi durumlarda 1 verilmeli?

3️⃣ Exclude (Irrelevant – 0)
Hangi durumlarda 0 verilmeli?

4️⃣ Output Format
Örn: “Sadece 1 veya 0 yaz.”

Tüm ayarlar tamamlandıktan sonra Test Limit belirleyip START butonuna basın.

🕵️‍♂️ Adım 3: Sonuç Kontrol Paneli (Results)

📊 Canlı İstatistikler: 1 / 0 dağılımı

🔍 Filtre & Arama: Sadece relevant sonuçları görme

📝 Veri Editörü: AI_Response alanını manuel düzeltme

💾 Save: Değişiklikleri ana veri setine kaydetme

📥 Export: Excel veya JSON indirme
