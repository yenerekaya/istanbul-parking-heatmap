# İstanbul Otopark Isı Haritası

İstanbul'daki İSPARK otoparklarının doluluk verilerini harita üzerinde ısı haritası olarak gösteren interaktif web uygulaması. [wolfiesch/sf-parking-heatmap](https://github.com/wolfiesch/sf-parking-heatmap) projesinden uyarlanmıştır.

## Ne yapar

- **168-slotluk haftalık profil**: Haftanın her saati için otopark doluluk profili (7 gün × 24 saat)
- **Çok katmanlı görselleştirme**: Şehir ölçeğinde ısı haritası → ilçe ölçeğinde 3D sütunlar → sokak ölçeğinde noktalar
- **Zaman kontrolü**: Haftanın saatlerinde gezin veya oynatma modunda izleyin
- **Otopark detay paneli**: Otopark bazında saatlik doluluk dağılımı, kapasite bilgisi
- **Karşılaştırma modu**: Bir referans saati sabitleyin, diğer saatlerle farkı görün
- **Arama + yarıçap**: Belirli bir adres arayın ve çevresindeki otopark durumunu görün

## Veri kaynağı

| Kaynak | Endpoint | Kullanım |
|---|---|---|
| [İBB İSPARK API](https://api.ibb.gov.tr/ispark/Park) | `/ispark/Park` | Tüm otoparkların konum, kapasite ve anlık doluluk bilgisi |
| [İBB İSPARK API](https://api.ibb.gov.tr/ispark/ParkDetay) | `/ispark/ParkDetay?id=X` | Tekil otopark detayı |

API anahtarı gerektirmez, açık erişimlidir.

## Tech stack

- **Frontend**: Vite 7 + React 19 + TypeScript + Tailwind CSS v4
- **Harita**: [deck.gl](https://deck.gl) v9 + [MapLibre GL](https://maplibre.org)
- **Veri Pipeline**: Python 3 (standart kütüphane + SQLite)
- **Basemap**: [CARTO Dark Matter](https://carto.com/basemaps/)

## Kurulum

```bash
# 1. JS bağımlılıklarını yükle
pnpm install

# 2. Veri pipeline (ilk kurulum — mock veriyle hızlı başlangıç)
pnpm pipeline          # park lokasyonlarını çek + mock profil oluştur

# 3. Dev server başlat
pnpm dev
```

http://localhost:5173 adresinde açılır.

## Gerçek veri toplama

Mock veri yerine gerçek doluluk profilleri oluşturmak için scraper'ı periyodik çalıştırman gerekiyor:

```bash
# 1. Scraper'ı her saat başı çalıştır (cron ile)
# crontab -e ile ekle:
# 0 * * * * cd /path/to/istanbul-parking-heatmap && python3 scripts/scrape_ispark.py

# 2. Manuel test (tek seferlik)
pnpm scrape

# 3. En az 1 hafta veri toplandıktan sonra gerçek profilleri oluştur
pnpm pipeline-real
```

## Proje yapısı

```
istanbul-parking-heatmap/
├── public/data/              # Frontend'in kullandığı JSON dosyaları
│   ├── park_locations.json   # Otopark konumları ve metadata
│   └── parking_week.json     # 168-slotluk doluluk profilleri
├── data/                     # Scraper veritabanı (gitignored)
│   └── ispark_history.db     # SQLite — anlık doluluk geçmişi
├── scripts/                  # Python veri pipeline
│   ├── fetch_park_locations.py     # İSPARK API'den lokasyonları çek
│   ├── scrape_ispark.py            # Anlık doluluk scraper (cron ile)
│   ├── aggregate_ispark.py         # Haftalık profil oluştur (gerçek veri)
│   └── generate_mock_profiles.py   # Mock profil oluştur (demo amaçlı)
├── src/
│   ├── App.tsx
│   ├── components/     # Harita, paneller, kontroller, tooltip'ler
│   ├── hooks/          # Veri yükleme, zaman dilimi, URL state
│   ├── layers/         # deck.gl katman fabrikaları (zoom seviyesine göre)
│   ├── lib/            # İSPARK client, renk skaları, geo yardımcıları
│   └── types.ts
└── docker-compose.yml  # Opsiyonel Valhalla (isochrone için)
```

## Doluluk nasıl hesaplanıyor

### Mock mod (başlangıç)
Tek bir API snapshot'ından güncel doluluk oranı alınır ve tipik günlük/saatlik
İstanbul park talep paternleri uygulanarak 168-slotluk profil üretilir.

### Gerçek mod (scraper verisi ile)
1. `scrape_ispark.py` her saat başı `(kapasite - boş) / kapasite` oranını SQLite'a kaydeder
2. `aggregate_ispark.py` belirtilen zaman aralığındaki verileri `gün × saat` bazında gruplar
3. Her otopark için ISO haftanın 168 saatine ortalaması alınır
4. Sonuç `parking_week.json` olarak frontend'e sunulır

## Kullanılabilir scriptler

```bash
pnpm dev                  # Vite dev server
pnpm build                # Production build
pnpm lint                 # ESLint
pnpm preview              # Built bundle önizleme

# Veri pipeline
pnpm fetch-parks          # Otopark lokasyonları
pnpm scrape               # Anlık doluluk snapshot'ı (cron ile tekrarla)
pnpm aggregate            # Gerçek veriden haftalık profil oluştur
pnpm mock-data            # Demo amaçlı mock profil oluştur
pnpm pipeline             # Lokasyonlar + mock profil (hızlı başlangıç)
pnpm pipeline-real        # Lokasyonlar + gerçek profil (scraper verisi gerekir)
```

## Lisans

MIT — [LICENSE](LICENSE) dosyasına bakın.

## Teşekkürler

- [İBB Açık Veri Portalı](https://data.ibb.gov.tr) ve İSPARK API
- [wolfiesch/sf-parking-heatmap](https://github.com/wolfiesch/sf-parking-heatmap) — orijinal proje
- [deck.gl](https://deck.gl), [MapLibre](https://maplibre.org), [CARTO basemaps](https://carto.com/basemaps/)
