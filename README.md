# Telegram Channel/Group Cloner

Bir kaynak Telegram grubundaki (forum/topic özellikli süpergrup) tüm **konu
başlıklarını (topics)** ve içindeki **mesaj/medyaları**, hedef bir forum
grubuna otomatik olarak kopyalayan bir [Telethon](https://docs.telethon.dev/)
scripti.

- Kaynaktaki her konu başlığını okur, hedefte aynı isimde yoksa otomatik oluşturur.
- Metin mesajlarını ve dosya/medya içeren mesajları (resim, video, belge, ses vb.) sırasıyla gönderir.
- Kesintiye uğrarsa nereden devam edeceğini `state.json` dosyasından hatırlar (aynı mesaj iki kez gönderilmez).
- `DRY_RUN` modu ile önce hiçbir şey göndermeden "ne yapılacağını" test edebilirsiniz.

> ⚠️ Bu araç, Telegram'ın **Bot API'si yerine kullanıcı hesabı** (MTProto/Telethon)
> üzerinden çalışır. Yani script, sizin kişisel Telegram hesabınız gibi davranır.
> Bu yüzden API kimlik bilgilerinizi ve oturum dosyanızı gizli tutmanız kritik önem taşır
> (bkz. [Güvenlik Uyarıları](#-güvenlik-uyarıları)).

---

## 📋 Gereksinimler

- Python 3.9 veya üzeri
- Bir Telegram hesabı (telefon numarası ile)
- Kaynak gruba üye olmanız ve hedef grupta mesaj gönderme yetkiniz olması
- Hedef grubun **Topics/Forum** özelliği açık bir süpergrup olması gerekir

---

## 🔑 Telegram API ID ve API Hash Nasıl Alınır?

Bu script, Telegram'a bağlanmak için kişisel bir `API_ID` ve `API_HASH`
çiftine ihtiyaç duyar. Bunlar ücretsizdir ve her Telegram hesabı için ayrı ayrı
alınır.

1. Tarayıcınızdan **https://my.telegram.org** adresine gidin.
2. Telegram hesabınızla ilişkili **telefon numaranızı** (+90 ile birlikte)
   girip "Next" / "İleri"ye tıklayın.
3. Telegram uygulamanıza gelen **giriş kodunu** girin.
4. Giriş yaptıktan sonra **"API development tools"** bağlantısına tıklayın.
5. Açılan formda:
   - **App title**: İstediğiniz bir isim (örn. `MyCloner`)
   - **Short name**: Kısa bir isim (örn. `mycloner`)
   - **Platform**: `Desktop` seçebilirsiniz
   - Diğer alanları boş bırakabilirsiniz
6. **"Create application"** butonuna basın.
7. Karşınıza çıkan sayfada:
   - **`App api_id`** → bu, `.env` dosyanızdaki `API_ID` değeridir.
   - **`App api_hash`** → bu, `.env` dosyanızdaki `API_HASH` değeridir.

🔒 **Bu iki değeri kimseyle paylaşmayın, GitHub'a asla commit etmeyin.**
Bu bilgiler sızarsa, başka biri sizin hesabınız adına Telegram API'sine istek
atabilir hâle gelir (bkz. [Güvenlik Uyarıları](#-güvenlik-uyarıları)).

---

## ⚙️ Kurulum

### 1. Depoyu klonlayın

```bash
git clone https://github.com/KULLANICI_ADINIZ/telegram-channel-clone.git
cd telegram-channel-clone
```

### 2. Sanal ortam oluşturun (önerilir)

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Bağımlılıkları yükleyin

```bash
pip install -r requirements.txt
```

### 4. `.env` dosyanızı oluşturun

`.env.example` dosyasını kopyalayıp `.env` olarak yeniden adlandırın:

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Sonra `.env` dosyasını açıp kendi bilgilerinizle doldurun:

```ini
API_ID=123456                      # my.telegram.org'dan aldığınız API ID
API_HASH=xxxxxxxxxxxxxxxxxxxxxxxxxxxx  # my.telegram.org'dan aldığınız API Hash
SESSION_NAME=channel_forwarder

SOURCE_CHANNEL=@kaynak_kanal_veya_id
DEST_CHANNEL=@hedef_kanal_veya_id

DRY_RUN=true
SILENT_FORWARD=false
POST_DELAY_SECONDS=0.8
RESUME_FILE=state.json
TOPIC_MAP_FILE=topic_map.json
```

> `.env` dosyası `.gitignore` içinde olduğu için GitHub'a otomatik olarak
> gitmeyecektir. Yine de commit atmadan önce `git status` ile kontrol etmeniz
> önerilir.

---

## 🆔 Grup ID'lerini Bulma

`SOURCE_CHANNEL` ve `DEST_CHANNEL` alanlarına `@kullaniciadi` yazabilir ya da
sayısal ID (`-100...` ile başlayan) kullanabilirsiniz. Sayısal ID'yi bulmak
için hazır bir yardımcı script var:

```bash
python list_ids.py
```

İlk çalıştırmada telefon numaranızı ve size gelen kodu girmeniz istenecek
(2FA açıksa parolanızı da). Script, üyesi olduğunuz tüm **grup**ları ID'leri
ile birlikte listeler. Buradan kaynak ve hedef grubun ID'sini `.env` dosyanıza
yazabilirsiniz.

---

## ▶️ Kullanım

### 1. Önce mutlaka DRY_RUN modu ile test edin

`.env` dosyasında `DRY_RUN=true` iken çalıştırın:

```bash
python main.py
```

Script hiçbir şey göndermeden, hangi konuların/mesajların gönderileceğini
konsola yazdırır. Beklediğiniz sonucu görene kadar bu modda test edin.

### 2. Gerçek aktarımı başlatın

`.env` dosyasında `DRY_RUN=false` yapıp tekrar çalıştırın:

```bash
python main.py
```

İlk çalıştırmada Telegram hesabınıza giriş yapmanız istenecektir
(telefon numarası → SMS/uygulama kodu → varsa 2FA parolası). Giriş
başarılı olduğunda, `SESSION_NAME` ile belirttiğiniz isimde bir
`.session` dosyası oluşur ve sonraki çalıştırmalarda tekrar giriş
istenmez.

Script şunları yapar:
- Kaynaktaki tüm konu başlıklarını (topics) sırayla gezer.
- Her konu için hedefte aynı isimde bir konu yoksa oluşturur.
- Konudaki tüm mesajları (metin + medya) eskiden yeniye doğru hedefe gönderir.
- İlerlemesini `state.json` dosyasına kaydeder.

### 3. Kesinti sonrası devam etme

Script herhangi bir sebeple durursa (flood wait, bağlantı kopması, elle
durdurma vb.), tekrar `python main.py` çalıştırmanız yeterlidir. Daha önce
gönderilmiş mesajlar ve tamamlanmış konular `state.json` sayesinde tekrar
gönderilmez.

### 4. Hedef grubu test etmek isterseniz

Hedef gruba gerçekten mesaj gönderip gönderemediğinizi hızlıca kontrol etmek
için:

```bash
python check_dest.py
```

Bu script hedef grup hakkında bilgi verir ve deneme amaçlı bir test mesajı
gönderir.

---

## 🧾 Ortam Değişkenleri (`.env`) Referansı

| Değişken             | Açıklama                                                                 | Varsayılan            |
|----------------------|---------------------------------------------------------------------------|------------------------|
| `API_ID`             | my.telegram.org'dan alınan API ID                                        | *(zorunlu)*            |
| `API_HASH`           | my.telegram.org'dan alınan API Hash                                      | *(zorunlu)*            |
| `SESSION_NAME`       | Oluşturulacak `.session` dosyasının adı                                  | `channel_forwarder`    |
| `SOURCE_CHANNEL`     | Kaynak grup (`@kullaniciadi` veya `-100...` ID)                          | *(zorunlu)*            |
| `DEST_CHANNEL`       | Hedef grup (`@kullaniciadi` veya `-100...` ID)                           | *(zorunlu)*            |
| `DRY_RUN`            | `true` ise hiçbir şey göndermez, sadece simüle eder                      | `true`                 |
| `SILENT_FORWARD`     | `true` ise gönderilen mesajlar bildirimsiz (sessiz) gider                | `false`                |
| `POST_DELAY_SECONDS` | Mesajlar arası bekleme süresi (saniye)                                   | `0.8`                  |
| `RESUME_FILE`        | İlerleme/log dosyasının adı                                              | `state.json`           |
| `TOPIC_MAP_FILE`     | Konu adı → hedef topic ID eşleşmesinin tutulduğu dosya                   | `topic_map.json`       |

---

## 📁 Proje Yapısı

```
telegram-channel-clone/
├── main.py              # Ana aktarım scripti
├── list_ids.py           # Üye olunan grupların ID'lerini listeler
├── check_dest.py          # Hedef grubu doğrulamak için test scripti
├── requirements.txt       # Python bağımlılıkları
├── .env.example            # Örnek ortam değişkenleri şablonu
├── .gitignore
└── README.md
```

Script çalıştıkça oluşan/güncellenen dosyalar (bunlar `.gitignore` içinde,
GitHub'a gitmez):

- `*.session`, `*.session-journal` — Telegram oturum bilgisi
- `state.json` — Hangi mesajların gönderildiğinin kaydı
- `topic_map.json` — Konu adı → hedef topic ID eşleşmesi
- `.env` — Kişisel API bilgileriniz

---

## 🔒 Güvenlik Uyarıları

- **`.env` dosyanızı asla GitHub'a yüklemeyin.** İçinde `API_ID`/`API_HASH`
  bulunur; bunlar hesabınız adına Telegram API'sine erişim sağlar.
- **`.session` dosyanızı asla paylaşmayın.** Bu dosya, telefon/kod/2FA
  girmeden doğrudan hesabınıza giriş yapılmasını sağlayan bir oturum
  anahtarıdır — bir şifreden bile daha hassastır. Ele geçirilirse hesabınıza
  tam erişim demektir.
- `state.json` ve `topic_map.json` dosyaları, kopyaladığınız grubun içerik
  başlıklarını ve mesaj önizlemelerini içerebilir. Bu grup özel/gizli
  içerikse, bu dosyaları da genel bir GitHub deposuna eklemeyin.
- Bu script bir **kullanıcı hesabı** ile çalıştığı için, çok hızlı ve çok
  sayıda mesaj göndermek Telegram'ın flood/spam korumasını tetikleyip
  hesabınızın geçici olarak kısıtlanmasına yol açabilir. `POST_DELAY_SECONDS`
  değerini çok düşürmeyin.
- Yalnızca **kendinize ait olan veya kopyalama izniniz olan** gruplarda
  kullanın. Başkasına ait içeriği izinsiz kopyalamak, Telegram kullanım
  şartlarını ve telif haklarını ihlal edebilir.

---

## ❓ Sık Karşılaşılan Sorunlar

**"Kaynak grup bulunamadı" / "Hedef grup bulunamadı" hatası alıyorum.**
Kullandığınız Telegram hesabının o gruba üye olduğundan ve ID'nin doğru
olduğundan emin olun. `python list_ids.py` ile ID'yi tekrar kontrol edin.

**"Hedef grup Topics/Forum özelliği açık bir süpergrup olmalı" hatası.**
Hedef grubun ayarlarından **Topics (Konular)** özelliğinin açık olduğundan
emin olun. Bu özellik yalnızca süpergruplarda bulunur, normal kanallarda
veya küçük gruplarda yoktur.

**`FloodWaitError: X saniye beklemen gerekiyor` hatası.**
Telegram, çok hızlı istek attığınızı düşünüp geçici olarak sizi
kısıtlamıştır. Belirtilen süre kadar bekleyip `python main.py` komutunu
tekrar çalıştırın; script kaldığı yerden devam edecektir.

**Script her seferinde telefon numarası soruyor.**
`.session` dosyasının silinmiş/taşınmamış olduğundan ve `SESSION_NAME`
değerinin her çalıştırmada aynı olduğundan emin olun.

---

## 📄 Lisans

Bu proje [MIT Lisansı](LICENSE) ile lisanslanmıştır.
