"""Bot ayarları. Rakamları buradan değiştirerek stratejiyi ayarla."""

# Takip edilecek BIST hisseleri (Yahoo Finance formatı: KOD.IS)
WATCHLIST = [
    "THYAO.IS", "GARAN.IS", "AKBNK.IS", "ASELS.IS", "KCHOL.IS",
    "SISE.IS", "EREGL.IS", "BIMAS.IS", "TUPRS.IS", "SAHOL.IS",
    "YKBNK.IS", "ISCTR.IS", "PGSUS.IS", "FROTO.IS", "TCELL.IS",
    "ARCLK.IS", "TOASO.IS", "ULKER.IS", "PETKM.IS", "HALKB.IS",
    "VAKBN.IS", "ENJSA.IS", "MGROS.IS", "SASA.IS", "TAVHL.IS",
    "KRDMD.IS", "BAGFS.IS", "GUBRF.IS", "TTKOM.IS", "AEFES.IS",
    "DOAS.IS", "CCOLA.IS", "AKSA.IS", "OTKAR.IS", "ALARK.IS",
]

# Takip edilecek ABD hisseleri (Yahoo Finance formatı, .IS son eki yok).
# Fiyatları dolar cinsindendir; portföy TL bazlı olduğu için güncel USDTRY
# kuruyla TL karşılığına çevrilip aynı sanal portföyden alınıp satılırlar.
US_WATCHLIST = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "NFLX", "TSLA",
]

# --- Geniş keşif evreni (discovery) ---
# 15 dakikalık gün içi döngü sadece yukarıdaki "çekirdek" listeye (43 hisse)
# bakar — bu hızlı ve sürdürülebilir kalması için şart. Ama kullanıcı "tüm
# piyasaya baksın" istediği için, GÜNDE BİR KEZ (Görev Zamanlayıcı ile ayrı
# bir görev, discovery.py) çok daha geniş bir evren taranır; öne çıkan
# adaylar ACTIVE_WATCHLIST_FILE'a yazılır ve çekirdek listeye eklenerek gün
# içi döngüye dahil olur. Bu iki katmanlı yaklaşım (yavaş+geniş keşif,
# hızlı+dar yürütme) API hız sınırlarını aşmadan "her şeye bakma" isteğini
# karşılar. Not: bu tam bir "BIST100/S&P500" resmi endeks listesi değil —
# web'den güvenilir şekilde çekilemediği için elle derlenmiş geniş bir
# tanınmış şirket listesidir; geçersiz semboller çalışma zamanında otomatik
# atlanır.
DISCOVERY_BIST_UNIVERSE = [
    "TSKB.IS", "SKBNK.IS", "AGHOL.IS", "ENKAI.IS", "TKFEN.IS", "ZOREN.IS",
    "AKSEN.IS", "ODAS.IS", "CIMSA.IS", "OYAKC.IS", "AKCNS.IS", "BUCIM.IS",
    "KORDS.IS", "KARSN.IS", "VESTL.IS", "BRSAN.IS", "ISDMR.IS", "CEMTS.IS",
    "AYGAZ.IS", "ALKIM.IS", "HEKTS.IS", "SOKM.IS", "CRFSA.IS", "KENT.IS",
    "TATGD.IS", "BANVT.IS", "PNSUT.IS", "CLEBI.IS", "RYSAS.IS", "LOGO.IS",
    "NETAS.IS", "EGEEN.IS", "DOHOL.IS", "ISGYO.IS", "EKGYO.IS", "TRGYO.IS",
    "ISMEN.IS", "AYDEM.IS", "ASTOR.IS", "KONTR.IS", "MPARK.IS", "LKMNH.IS",
    "DEVA.IS", "SELEC.IS", "ECILC.IS", "KAREL.IS", "INDES.IS", "ARENA.IS",
    "MAVI.IS", "YATAS.IS",
]

DISCOVERY_US_UNIVERSE = [
    "ORCL", "CRM", "ADBE", "INTC", "CSCO", "IBM", "AVGO", "QCOM", "TXN",
    "AMD", "NOW", "INTU", "PANW", "MU", "JPM", "BAC", "WFC", "GS", "MS",
    "V", "MA", "AXP", "BRK-B", "JNJ", "UNH", "PFE", "ABBV", "LLY", "MRK",
    "TMO", "ABT", "KO", "PEP", "WMT", "PG", "HD", "NKE", "MCD", "SBUX",
    "COST", "DIS", "BA", "CAT", "GE", "HON", "UPS", "LMT", "XOM", "CVX",
    "CMCSA", "T", "VZ",
]

ACTIVE_WATCHLIST_FILE = "active_watchlist.json"
DISCOVERY_SHORTLIST_SIZE = 40   # ucuz teknik ön-elemeden sonra tam analize alınacak aday sayısı
DISCOVERY_TOP_N = 15            # çekirdek listeye eklenecek en iyi aday sayısı
DISCOVERY_MIN_SCORE = 0.20      # bu bileşik skorun altındaki adaylar eklenmez

# --- Teknik analiz parametreleri ---
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
SMA_SHORT = 20
SMA_LONG = 50
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
VOLUME_LOOKBACK = 20        # ortalama hacim penceresi
VOLUME_SPIKE_RATIO = 1.5    # ortalamanın kaç katı hacim "sıçrama" sayılır
PRICE_HISTORY_PERIOD = "5y"  # hem teknik göstergeler hem de uzun vadeli reel getiri için

# --- Uzun vadeli reel (dolar bazlı) getiri parametreleri ---
# 10 yıllık geriye dönük analiz gösterdi ki BIST'te TL getiri kur devalüasyonuyla
# şişiyor; TL değeri yüzünden değil gerçekten değer yaratan şirketleri ayırt etmek
# için fiyatı USDTRY'ye bölüp dolar bazlı CAGR'a bakıyoruz (ör. ASELS, SASA, TUPRS
# gerçekten reel değer yaratmış; CCOLA, ARCLK, ULKER dolar bazında değer kaybetmiş).
LONG_TERM_MIN_YEARS = 2.0     # bundan az geçmişi olan hisse için bu skor nötr (0) sayılır
LONG_TERM_BEST_CAGR_PCT = 20.0   # bu ve üstü dolar CAGR -> skor +1
LONG_TERM_WORST_CAGR_PCT = -15.0  # bu ve altı dolar CAGR -> skor -1

# --- Skor ağırlıkları (toplamları 1.0 olmalı) ---
WEIGHT_TECHNICAL = 0.40
WEIGHT_FUNDAMENTAL = 0.25
WEIGHT_NEWS = 0.15
WEIGHT_LONG_TERM = 0.20

# --- Sinyal eşikleri (bileşik skor -1..+1 aralığında) ---
BUY_THRESHOLD = 0.35
SELL_THRESHOLD = -0.25

# --- Piyasa rejimi filtresi ---
# İlgili piyasanın kendi endeksi teknik olarak "ayı" bölgesindeyse, o piyasadan
# yeni pozisyon açılmaz — sadece mevcut pozisyonlardaki stop-loss/trailing-stop/
# SAT sinyalleri çalışmaya devam eder. Gerekçe: tek tek hisseye "AL" sinyaline
# güvenmek, genel piyasa düşerken risklidir. BIST ve ABD ayrı endekslerle
# (birbirinden bağımsız) değerlendirilir; biri ayıdayken diğeri normal olabilir.
BIST_REGIME_INDEX = "XU100.IS"
US_REGIME_INDEX = "^GSPC"        # S&P 500 — ABD hisseleri için genel piyasa göstergesi
MARKET_REGIME_BEARISH_THRESHOLD = -0.30

# --- Kağıt (sanal) portföy ayarları ---
INITIAL_CASH = 100_000.0     # TL
MAX_OPEN_POSITIONS = 5
MAX_POSITIONS_PER_SECTOR = 2   # aynı sektörden en fazla bu kadar pozisyon (konsantrasyon riskini sınırlar)
MAX_POSITIONS_PER_MARKET = 3   # BIST veya ABD'den en fazla bu kadar pozisyon (tek piyasaya aşırı yığılmayı engeller)

# Pozisyon büyüklüğü: sabit % yerine riske dayalı boyutlandırma (profesyonel
# yatırımcıların ortak yöntemi). Her işlemde, stop-loss'a çarpması hâlinde
# kaybedilecek tutar portföyün RISK_PER_TRADE_PCT'ini aşmayacak şekilde adet
# hesaplanır; MAX_POSITION_PCT_OF_EQUITY ise dar bir stop-loss'un aşırı büyük
# pozisyona yol açmasını engelleyen bir tavan.
# ÖNEMLİ: RISK_PER_TRADE_PCT / STOP_LOSS_PCT oranı MAX_POSITION_PCT_OF_EQUITY'den
# küçük olmalı, yoksa tavan her zaman devreye girer ve riske dayalı hesaplama
# hiç etkili olmaz (örn. 0.01/0.07 ≈ %14 < %25 tavan -> risk hesaplaması aktif).
RISK_PER_TRADE_PCT = 0.01        # işlem başına riske edilen portföy yüzdesi (klasik "%1 kuralı")
MAX_POSITION_PCT_OF_EQUITY = 0.25  # bir pozisyon portföyün bu oranını geçemez (güvenlik tavanı)
CONSECUTIVE_LOSS_COOLDOWN = 3     # bu kadar art arda kayıptan sonra risk yarıya iner
COOLDOWN_RISK_MULTIPLIER = 0.5

STOP_LOSS_PCT = 0.07                 # pozisyon -%7 olursa sat (giriş anındaki sabit koruma)
TRAILING_STOP_ACTIVATION_PCT = 0.07  # pozisyon zirveden bu kadar kâra geçince iz süren stop devreye girer
TRAILING_STOP_PCT = 0.08             # zirveden bu kadar geri çekilirse sat (kazananı uzun tutmayı sağlar)

# --- İşlem maliyeti (gerçekçilik için) ---
# Türkiye'deki düşük komisyonlu aracı kurumlarda tipik oran; BSMV dahil kaba tahmin.
# Gerçek aracı kurumunun oranıyla değiştir.
COMMISSION_RATE = 0.0015   # işlem tutarının %0,15'i, hem alışta hem satışta

# --- Portföy düzeyinde zarar kesici (drawdown circuit breaker) ---
# Portföy zirve değerinden bu oranda gerilerse, zirve toparlanana kadar
# yeni pozisyon açılmaz (mevcut pozisyonlar stop/trailing kurallarıyla yönetilmeye devam eder).
MAX_PORTFOLIO_DRAWDOWN_PCT = 0.20

MAX_TRADE_LOG_ROWS = 5000

# --- Gün içi (intraday) mod ---
# Bot artık piyasalar açıkken periyodik olarak (Görev Zamanlayıcı ile 15 dakikada
# bir) çalışır. Teknik göstergeler (SMA/RSI/MACD/hacim) AYNI periyotlarla
# (yukarıdaki SMA_SHORT/SMA_LONG/RSI_PERIOD vb.) ama günlük yerine gün içi
# mumlara uygulanır — bu, gün içi işlemde yaygın kullanılan bir yaklaşımdır.
# Temel analiz, uzun vadeli (dolar bazlı) skor ve haber duyarlılığı gün içinde
# değişmediği için her taramada yeniden hesaplanmaz; günde bir kez hesaplanıp
# SLOW_SCORE_CACHE_FILE'da önbelleğe alınır (aksi halde Yahoo/Google'a 15
# dakikada bir 43 hisse için istek atıp hız sınırına takılırdık).
INTRADAY_INTERVAL = "15m"
INTRADAY_PERIOD = "5d"   # 15dk mumlarla ~130-160 bar -> SMA/RSI/MACD ısınması için yeterli
SLOW_SCORE_CACHE_FILE = "slow_scores_cache.json"

# --- Veri kalitesi kontrolü ---
# 8 Eylül 2026'da geçici bir ağ/DNS kesintisinde neredeyse tüm hisseler için
# veri alınamamıştı; bot çökmedi ama elindeki tek pozisyonu (avg_price'a geri
# düşerek) yanlışlıkla "%0 getiri" gibi gösterdi. Bunun tekrarını önlemek için,
# izleme listesinin yeterli bir kısmı için veri gelmediyse o çalıştırmada
# hiçbir alım/satım/değerleme yapılmaz — sadece uyarı verilir.
MIN_DATA_COVERAGE_PCT = 0.7

# 10 Eylül 2026'da bir ağ kesintisinde her başarısız istek ~10 saniye sürdü
# (yfinance'in kendi tekrar deneme mekanizması) ve tarama 43 hisse boyunca
# tek tek başarısız olmaya devam ederek 10+ dakika takılı kaldı. Art arda bu
# kadar hisse üst üste başarısız olursa (muhtemelen sistemik bir ağ sorunu),
# kalan taramayı hemen durdurup MIN_DATA_COVERAGE_PCT kontrolüne bırakıyoruz —
# 10+ dakika beklemek yerine ~1 dakikada pes ediyoruz.
CONSECUTIVE_FAILURE_ABORT_LIMIT = 8

# --- Dosya yolları ---
STATE_FILE = "portfolio_state.json"
TRADE_LOG_FILE = "docs/trade_log.csv"  # telefon paneli (GitHub Pages) bu klasoru yayinliyor
STATUS_FILE = "docs/status.json"  # telefon gösterge paneli (GitHub Pages) bunu okur

# --- Haber duyarlılığı ---
NEWS_LOOKBACK_COUNT = 12      # ticker başına kontrol edilecek haber başlığı sayısı
NEWS_TIMEOUT_SECONDS = 6
