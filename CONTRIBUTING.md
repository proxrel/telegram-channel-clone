# Katkıda Bulunma

Katkılarınız için teşekkürler! Küçük bir proje olduğu için süreç basit tutulmuştur.

## Hata bildirimi / öneri

[Issues](../../issues) sekmesinden yeni bir kayıt açabilirsiniz. Lütfen şunları belirtin:

- Ne yapmaya çalıştığınız
- Beklediğiniz sonuç ile gerçekleşen sonuç
- Varsa hata mesajının tamamı (API_ID, API_HASH gibi kişisel bilgileri **paylaşmayın**)
- Python sürümünüz ve işletim sisteminiz

## Kod katkısı (Pull Request)

1. Depoyu fork'layın ve yeni bir dal (branch) oluşturun:
   ```bash
   git checkout -b ozellik/kisa-aciklama
   ```
2. Değişikliklerinizi yapın. Mevcut kod stiline (Türkçe konsol mesajları,
   docstring'ler, `snake_case` isimlendirme) sadık kalmaya çalışın.
3. Değişiklik yapmadan önce dosyaların derlendiğinden emin olun:
   ```bash
   python -m py_compile main.py list_ids.py check_dest.py
   ```
4. Commit'lerinizde **asla** kendi `.env`, `.session`, `state.json` veya
   `topic_map.json` dosyalarınızı eklemeyin (bunlar zaten `.gitignore`'dadır,
   yine de `git status` ile kontrol edin).
5. Pull request açıklamasında neyi, neden değiştirdiğinizi kısaca yazın.

## Güvenlikle ilgili bir açık bulduysanız

Lütfen doğrudan bir Issue açmak yerine repo sahibiyle özel olarak iletişime
geçin.
