# Telegram Forum Klonlayıcı

[Telethon](https://docs.telethon.dev/) tabanlı bir script. Bir Telegram
forum grubundaki (Topics açık süpergrup) tüm konuları ve mesajları/medyayı
başka bir forum grubuna kopyalar.

- Kaynaktaki her konuyu okur, hedefte yoksa otomatik oluşturur.
- Metin ve medya mesajlarını (foto, video, dosya, ses vb.) sırayla gönderir.
- Kaldığı yeri `state.json` dosyasında tutar; kesinti olursa aynı mesajı
  iki kez göndermez.
- `DRY_RUN` modu ile hiçbir şey göndermeden önizleme yapabilirsin.

> ⚠️ Bu script bot API'si değil, **kullanıcı hesabı** (Telethon/MTProto) ile
> bağlanır. Yani senin kişisel Telegram hesabınmış gibi çalışır — API
> bilgilerini ve oturum dosyasını gizli tut (bkz. [Güvenlik](#güvenlik)).

---

## Gereksinimler

- Python 3.10 veya üzeri
- Bir Telegram hesabı (telefon numarası)
- Kaynak grupta üyelik, hedef grupta mesaj gönderme izni
- Hedef grup **Topics/Forum özelliği açık bir süpergrup** olmalı

> Not: Buradaki Python sürümü genel bir öneridir; bende çalıştığını
> doğruladığın farklı bir minimum sürüm varsa bu satırı ona göre değiştir.

---

## Kurulum

```bash
git clone https://github.com/proxrel/telegram-channel-clone.git
cd telegram-channel-clone
pip install -r requirements.txt
```

Hepsi bu kadar — `.env` dosyası oluşturmana gerek yok. Script ilk
çalıştığında eksik bilgileri sana soracak ve bir daha sormaması için
otomatik olarak `.env` dosyasına kaydedecek.

*(İstersen bağımlılıkları izole etmek için sanal ortam kullanabilirsin:
`python -m venv .venv` ve ardından `.venv` klasöründeki `activate`
scriptini çalıştır — ama bu tamamen opsiyonel, atlayabilirsin.)*

---

## API_ID ve API_HASH nasıl alınır

Script Telegram'a bağlanmak için kişisel bir `API_ID`/`API_HASH` çiftine
ihtiyaç duyar. Ücretsizdir ve hesabına özeldir.

1. **<https://my.telegram.org>** adresine git.
2. Telegram hesabına kayıtlı telefon numaranı (ülke koduyla) gir, "Next"e bas.
3. Telegram uygulamana gelen kodu gir.
4. Giriş yaptıktan sonra **"API development tools"**'a tıkla.
5. Formu doldur: App title ve Short name'e istediğin bir isim yaz, Platform
   olarak "Desktop" seç, diğer alanları boş bırakabilirsin.
6. **"Create application"**'a tıkla.
7. Karşına çıkan `App api_id` ve `App api_hash` değerlerini not al — script
   ilk çalıştığında bunları senden isteyecek.

🔒 Bu iki değeri kimseyle paylaşma ve GitHub'a commit etme.

---

## Kullanım

### Adım 1 — Önce kaynak ve hedef grubun ID'sini bul

Kaynak ve iletilecek grubun ID'sini bulmak için önce bu komutu çalıştır ve
çıkan grup ID'lerini not al:

```bash
python list_ids.py
```

API_ID/API_HASH'i henüz kaydetmediysen önce onları sorar, ardından telefon
numaranı ve kodunu ister, sonunda üye olduğun tüm grupları ID'leriyle
listeler. Kaynak ve hedef olacak grupların ID'lerini buradan not al —
bir sonraki adımda lazım olacak.

### Adım 2 — main.py'yi çalıştır

```bash
python main.py
```

İlk çalıştırmada sırayla şunları soracak, `.env` dosyasına kaydedecek ve
bir daha sormayacak:

- `API_ID`, `API_HASH`
- Kaynak grup ID'si (`SOURCE_CHANNEL`) — Adım 1'de not aldığın ID
- Hedef grup ID'si (`DEST_CHANNEL`) — Adım 1'de not aldığın ID

Ardından hesabına giriş için telefon numaranı ve Telegram'dan gelen kodu
(varsa 2FA şifreni) isteyecek.

Varsayılan olarak `DRY_RUN=true` ile çalışır: hiçbir şey göndermez, sadece
neler yapılacağını konsola yazar. Çıktı doğru görünüyorsa `.env` dosyasında
`DRY_RUN=false` yapıp scripti tekrar çalıştır — bu sefer gerçekten
gönderir.

Script kesilirse (flood wait, bağlantı kopması, elle durdurma), aynı
komutu tekrar çalıştırman yeterli; `state.json` sayesinde hiçbir mesaj iki
kez gönderilmez.

### Adım 3 — Hedefi test et (opsiyonel)

```bash
python check_dest.py
```

Hedef gruba gerçekten mesaj gönderebildiğini doğrulamak için kısa bir test
mesajı yollar.

---

## `.env` — ileri seviye ayarlar (opsiyonel)

Yukarıdaki 4 zorunlu değeri script senin için `.env` dosyasına zaten
yazıyor. Aşağıdakiler sadece varsayılanı değiştirmek istersen `.env`
dosyasını elle düzenleyerek ayarlayabileceğin ek seçenekler:

| Değişken             | Açıklama                                                       | Varsayılan           |
| -------------------- | --------------------------------------------------------------- | --------------------- |
| `SESSION_NAME`        | Oluşturulan `.session` dosyasının adı                            | `channel_forwarder`   |
| `DRY_RUN`             | `true` ise hiçbir şey göndermez, sadece simüle eder              | `true`                |
| `SILENT_FORWARD`      | `true` ise mesajlar bildirim göndermeden yollanır                | `false`               |
| `POST_DELAY_SECONDS`  | Mesajlar arası bekleme süresi (saniye)                           | `0.8`                 |
| `RESUME_FILE`         | İlerleme/log dosyasının adı                                      | `state.json`          |
| `TOPIC_MAP_FILE`      | Konu adı → hedef konu ID eşleşmesini tutan dosya                 | `topic_map.json`      |

Elle düzenlemek istersen `.env.example` dosyasını `.env` olarak kopyalayıp
doldurabilirsin — ama zorunlu değil.

---

## Proje yapısı

```
telegram-channel-clone/
├── main.py              # Ana transfer scripti
├── list_ids.py          # Üye olduğun grupların ID'lerini listeler
├── check_dest.py        # Hedefe erişimi test eder
├── requirements.txt      # Python bağımlılıkları
├── .env.example          # (opsiyonel) örnek ortam değişkeni şablonu
├── .gitignore
└── README.md
```

Script çalışırken oluşan ve `.gitignore`'da olduğu için asla commit
edilmeyen dosyalar: `*.session`, `*.session-journal`, `state.json`,
`topic_map.json`, `.env`.

---

## Güvenlik

- `.env` ve `.session` dosyalarını asla GitHub'a commit etme veya
  paylaşma — `.session` dosyası şifresiz oturum açmaya yeter, parolandan
  bile daha hassastır.
- `state.json` ve `topic_map.json` kopyaladığın grubun konu başlıklarını
  ve mesaj önizlemelerini içerebilir; kaynak grup özelse bu dosyaları da
  paylaşma.
- Kullanıcı hesabıyla çalıştığı için çok hızlı mesaj göndermek Telegram'ın
  flood/spam korumasını tetikleyip hesabını geçici kısıtlayabilir;
  `POST_DELAY_SECONDS`'ı aşırı düşürme.
- Yalnızca **sahibi olduğun veya izin aldığın** gruplarda kullan.

---

## Sorun giderme

**"Kaynak/Hedef grup bulunamadı" hatası.** Hesabının o gruba üye olduğundan ve ID'nin doğru olduğundan emin ol;
`python list_ids.py` ile kontrol et.

**"Topics/Forum özelliği açık olmalı" hatası.** Hedef (veya kaynak) grubun ayarlarından Topics'i aç. Bu özellik sadece
süpergruplarda var, normal kanal/gruplarda yok.

**`FloodWaitError: X saniye bekle` hatası.** Telegram hesabını geçici olarak sınırlamış. Belirtilen süre geçince
`python main.py` komutunu tekrar çalıştır; kaldığı yerden devam eder.

**Her seferinde telefon numaramı yeniden soruyor.** `.session` dosyasının silinmediğinden ve `SESSION_NAME` değerinin
değişmediğinden emin ol.

---

## Lisans

[MIT License](LICENSE)
