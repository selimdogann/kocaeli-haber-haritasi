/* =============================================
   KOCAELI HABER HARİTASI - ANA JAVASCRIPT DOSYASI
   Google Maps Entegrasyonu & API İletişimi
   ============================================= */

// ==================== GLOBAL DEĞİŞKENLER ====================
let map;
let markers = [];
let infoWindow;
let haberler = [];
let markerClusterer = null;

// ==================== HARİTA BAŞLATMA ====================
function initMap() {
    // Google Maps nesnesini oluştur
    map = new google.maps.Map(document.getElementById('map'), {
        center: { lat: CONFIG.centerLat, lng: CONFIG.centerLng },
        zoom: 11,
        mapTypeControl: true,
        mapTypeControlOptions: {
            style: google.maps.MapTypeControlStyle.HORIZONTAL_BAR,
            position: google.maps.ControlPosition.TOP_RIGHT
        },
        streetViewControl: false,
        fullscreenControl: true,
        zoomControl: true,
        zoomControlOptions: {
            position: google.maps.ControlPosition.RIGHT_CENTER
        },
        styles: [
            {
                featureType: 'poi',
                elementType: 'labels',
                stylers: [{ visibility: 'off' }]
            }
        ]
    });

    // Tek bir InfoWindow nesnesi kullan
    infoWindow = new google.maps.InfoWindow();

    // Sayfa yüklendiğinde haberleri getir
    haberleriGetir();
    istatistikleriGetir();
}

// ==================== API İSTEKLERİ ====================

/**
 * Haberleri API'den çeker ve haritaya yerleştirir
 */
async function haberleriGetir() {
    try {
        // Aktif filtreleri topla
        const params = filtreParametreleriOlustur();
        const queryString = new URLSearchParams(params).toString();

        const response = await fetch(`/api/haberler?${queryString}`);
        const data = await response.json();

        if (data.basarili) {
            haberler = data.haberler;

            // Haritadaki markerları güncelle
            markerlariTemizle();
            haberleriHaritayaEkle(haberler);

            // Haber listesini güncelle
            haberListesiniGuncelle(haberler);

            // Üst bar haber sayısını güncelle
            document.getElementById('toplam-haber-sayisi').textContent = data.toplam;
        }
    } catch (error) {
        console.error('Haberler yüklenirken hata:', error);
        bildirimGoster('Haberler yüklenirken hata oluştu', 'hata');
    }
}

/**
 * İstatistikleri API'den çeker
 */
async function istatistikleriGetir() {
    try {
        const response = await fetch('/api/istatistikler');
        const data = await response.json();

        if (data.basarili) {
            const stats = data.istatistikler;

            // Toplam ve konumlu sayıları güncelle
            document.getElementById('stat-toplam').textContent = stats.toplam_haber || 0;
            document.getElementById('stat-konumlu').textContent = stats.konumlu_haber || 0;

            // Tür dağılımı grafiğini oluştur
            turDagilimiOlustur(stats.tur_dagilimi || {});
        }
    } catch (error) {
        console.error('İstatistikler yüklenirken hata:', error);
    }
}

/**
 * Scraping işlemini başlatır
 */
let progressInterval = null;

async function scrapingBaslat() {
    const btn = document.getElementById('btn-scrape');
    btn.disabled = true;
    btn.innerHTML = '⏳ Başlatılıyor...';

    loadingGoster(true);
    bildirimGoster('Haber çekme işlemi başlatıldı, lütfen bekleyiniz...', 'uyari');

    // İlerleme takibini başlat
    progressInterval = setInterval(async () => {
        try {
            const res = await fetch('/api/scrape/progress');
            const p = await res.json();
            if (p.aktif) {
                let text = `⏳ %${p.yuzde}`;
                if (p.asama === 'Haberler çekiliyor') {
                    text += ` · ${p.kaynak} (${p.kaynak_no}/${p.toplam_kaynak})`;
                } else if (p.asama === 'Haberler işleniyor') {
                    text += ` · İşleniyor ${p.islenen_haber}/${p.toplam_haber}`;
                } else {
                    text += ` · ${p.asama}`;
                }
                btn.innerHTML = text;
            }
        } catch (e) { /* ignore */ }
    }, 800);

    try {
        const response = await fetch('/api/scrape', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();

        if (data.basarili) {
            const rapor = data.rapor;
            bildirimGoster(
                `✅ Tamamlandı! ${rapor.toplam_kaydedilen} yeni haber eklendi (${rapor.toplam_cekilen} tarandı, ${rapor.sure_saniye.toFixed(0)}s)`,
                'basarili'
            );
            // Haberleri ve istatistikleri yenile
            await haberleriGetir();
            await istatistikleriGetir();
        } else {
            bildirimGoster('Haber çekme sırasında hata: ' + (data.mesaj || 'Bilinmeyen hata'), 'hata');
        }
    } catch (error) {
        console.error('Scraping hatası:', error);
        bildirimGoster('Sunucuyla bağlantı kurulamadı', 'hata');
    } finally {
        clearInterval(progressInterval);
        progressInterval = null;
        btn.disabled = false;
        btn.innerHTML = '🔄 Haberleri Güncelle';
        loadingGoster(false);
    }
}

// ==================== HARİTA İŞLEMLERİ ====================

/**
 * Haberleri harita üzerinde marker olarak gösterir
 */
function haberleriHaritayaEkle(haberListesi) {
    haberListesi.forEach(haber => {
        if (haber.koordinatlar && haber.koordinatlar.lat && haber.koordinatlar.lng) {
            markerOlustur(haber);
        }
    });
}

/**
 * Pin şeklinde SVG marker ikonu oluşturur.
 * Her haber türü için renkli pin + beyaz simge.
 */
function pinIkonuOlustur(renk, ikonSvg) {
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="44" viewBox="0 0 32 44">
        <defs>
            <filter id="ds" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="1" stdDeviation="1.5" flood-color="#000" flood-opacity="0.35"/>
            </filter>
        </defs>
        <path d="M16 43C16 43 31 26 31 15.5C31 7.2 24.3 0.5 16 0.5C7.7 0.5 1 7.2 1 15.5C1 26 16 43 16 43Z"
              fill="${renk}" stroke="#fff" stroke-width="1.5" filter="url(#ds)"/>
        <circle cx="16" cy="15" r="10" fill="rgba(255,255,255,0.2)"/>
        ${ikonSvg}
    </svg>`;
    return {
        url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg),
        scaledSize: new google.maps.Size(34, 46),
        anchor: new google.maps.Point(17, 46),
    };
}

/**
 * Haber türüne göre pin ikonları — renkli pin + beyaz simge
 * Referans: araba, alev, şimşek, kilit, nota, gazete
 */
let MARKER_ICONS = null;

function markerIkonlariniHazirla() {
    if (MARKER_ICONS) return;
    MARKER_ICONS = {
        // Trafik Kazası → Araba simgesi
        trafik_kazasi: pinIkonuOlustur('#E53E3E',
            `<g fill="#fff" transform="translate(16,15)">
                <path d="M-7.5,0.5 L-5.5,-4 L5.5,-4 L7.5,0.5 L7.5,3 L-7.5,3 Z"/>
                <rect x="-5" y="-3.5" width="3.5" height="2.5" rx="0.5" fill="#E53E3E" opacity="0.6"/>
                <rect x="1.5" y="-3.5" width="3.5" height="2.5" rx="0.5" fill="#E53E3E" opacity="0.6"/>
                <circle cx="-4.5" cy="4.2" r="1.6"/>
                <circle cx="4.5" cy="4.2" r="1.6"/>
            </g>`),

        // Yangın → Alev simgesi
        yangin: pinIkonuOlustur('#ED8936',
            `<path d="M16,6.5 C16,6.5 11,11 11,15.5 C11,18.3 13.2,20.5 16,20.5
                     C18.8,20.5 21,18.3 21,15.5 C21,11 16,6.5 16,6.5 Z" fill="#fff"/>
             <path d="M16,12 C16,12 14,14 14,15.8 C14,16.9 14.9,17.8 16,17.8
                     C17.1,17.8 18,16.9 18,15.8 C18,14 16,12 16,12 Z" fill="#ED8936"/>`),

        // Hırsızlık → Kalkan simgesi
        hirsizlik: pinIkonuOlustur('#805AD5',
            `<g fill="#fff" transform="translate(16,15)">
                <path d="M0,-8 L7,-4.5 L7,1 C7,5 4,7.5 0,9 C-4,7.5 -7,5 -7,1 L-7,-4.5 Z"/>
                <path d="M0,-4.5 L4,-2.5 L4,0.8 C4,3.5 2,5 0,6 C-2,5 -4,3.5 -4,0.8 L-4,-2.5 Z" fill="#805AD5" opacity="0.45"/>
            </g>`),

        // Elektrik Kesintisi → Şimşek simgesi
        elektrik_kesintisi: pinIkonuOlustur('#D69E2E',
            `<polygon points="18,6 13,14.5 15.5,14.5 13,23 20,13.5 17,13.5 19,6" fill="#fff"/>`),

        // Kültürel Etkinlik → Nota simgesi
        kulturel_etkinlik: pinIkonuOlustur('#3182CE',
            `<g fill="#fff" transform="translate(16,15)">
                <ellipse cx="-3" cy="4.5" rx="3" ry="2.3"/>
                <rect x="-0.3" y="-7" width="1.8" height="11.5"/>
                <path d="M1.5,-7 L7,-9 L7,-4 L1.5,-2 Z"/>
            </g>`),

        // Diğer → Gazete/belge simgesi
        diger: pinIkonuOlustur('#718096',
            `<g fill="#fff" transform="translate(16,15)">
                <rect x="-6" y="-7" width="12" height="14" rx="1.5"/>
                <line x1="-3.5" y1="-4" x2="3.5" y2="-4" stroke="#718096" stroke-width="1.2"/>
                <line x1="-3.5" y1="-1" x2="3.5" y2="-1" stroke="#718096" stroke-width="1.2"/>
                <line x1="-3.5" y1="2" x2="1.5" y2="2" stroke="#718096" stroke-width="1.2"/>
            </g>`),
    };
}

/**
 * Tek bir haber için marker oluşturur
 */
function markerOlustur(haber) {
    markerIkonlariniHazirla();

    const turBilgi = CONFIG.newsTypes[haber.haber_turu] || {
        color: '#6B7280',
        icon: '📰',
        label: 'Diğer'
    };

    // Haber türüne göre pin ikonu seç
    const markerIcon = MARKER_ICONS[haber.haber_turu] || MARKER_ICONS['diger'];

    const marker = new google.maps.Marker({
        position: {
            lat: haber.koordinatlar.lat,
            lng: haber.koordinatlar.lng
        },
        map: map,
        icon: markerIcon,
        title: haber.baslik,
        animation: google.maps.Animation.DROP
    });

    // Marker'a haber verisini ekle
    marker.haberData = haber;

    // Tıklama olayı - InfoWindow aç
    marker.addListener('click', () => {
        infoWindowAc(marker, haber);
    });

    markers.push(marker);
}

/**
 * InfoWindow içeriğini oluşturur ve açar
 */
function infoWindowAc(marker, haber) {
    const turBilgi = CONFIG.newsTypes[haber.haber_turu] || {
        color: '#6B7280',
        icon: '📰',
        label: 'Diğer'
    };

    // Tarihi formatla
    const tarih = haber.tarih ? tarihFormatla(haber.tarih) : 'Tarih bilinmiyor';

    // Kaynak metni
    const kaynaklar = haber.kaynaklar ?
        haber.kaynaklar.map(k => k.kaynak_adi).join(', ') :
        (haber.kaynak_adi || '');

    // İçerik özeti (ilk 150 karakter)
    const icerikOzet = haber.icerik ?
        haber.icerik.substring(0, 150) + (haber.icerik.length > 150 ? '...' : '') :
        '';

    // Konum bilgisi
    const konum = [];
    if (haber.konum_bilgisi) {
        if (haber.konum_bilgisi.ilce) konum.push(haber.konum_bilgisi.ilce);
        if (haber.konum_bilgisi.mahalle) konum.push(haber.konum_bilgisi.mahalle);
    }
    const konumMetni = konum.length > 0 ? konum.join(', ') : 'Kocaeli';

    // Haber linki
    const haberLinki = haber.haber_linki ||
        (haber.kaynaklar && haber.kaynaklar.length > 0 ? haber.kaynaklar[0].link : '#');

    const icerik = `
        <div class="info-window">
            <div class="info-window-title">${escapeHtml(haber.baslik)}</div>
            <div class="info-window-meta">
                <span>
                    <span class="info-window-tag" style="background-color: ${turBilgi.color}">
                        ${turBilgi.icon} ${turBilgi.label}
                    </span>
                </span>
                <span>📅 ${tarih}</span>
                <span>📍 ${escapeHtml(konumMetni)}</span>
                ${kaynaklar ? `<span>📰 ${escapeHtml(kaynaklar)}</span>` : ''}
            </div>
            ${icerikOzet ? `<div class="info-window-content">${escapeHtml(icerikOzet)}</div>` : ''}
            <a href="${escapeHtml(haberLinki)}" target="_blank" rel="noopener" class="info-window-link">
                🔗 Habere Git
            </a>
        </div>
    `;

    infoWindow.setContent(icerik);
    infoWindow.open(map, marker);
}

/**
 * Tüm markerları haritadan kaldırır
 */
function markerlariTemizle() {
    markers.forEach(marker => marker.setMap(null));
    markers = [];
}

// ==================== FİLTRE İŞLEMLERİ ====================

/**
 * Aktif filtreleri bir parametre nesnesi olarak döndürür
 */
function filtreParametreleriOlustur() {
    const params = {};

    // Haber türü filtresi
    const seciliTurler = [];
    document.querySelectorAll('#haber-turu-filtre input[type="checkbox"]:checked').forEach(cb => {
        seciliTurler.push(cb.value);
    });

    // Eğer tüm türler seçili değilse, sadece seçili olanları gönder
    const tumCheckboxlar = document.querySelectorAll('#haber-turu-filtre input[type="checkbox"]');
    if (seciliTurler.length < tumCheckboxlar.length && seciliTurler.length > 0) {
        params.haber_turu = seciliTurler.join(',');
    }

    // İlçe filtresi
    const ilce = document.getElementById('ilce-filtre').value;
    if (ilce) params.ilce = ilce;

    // Tarih filtresi
    const baslangic = document.getElementById('baslangic-tarihi').value;
    const bitis = document.getElementById('bitis-tarihi').value;
    if (baslangic) params.baslangic_tarihi = baslangic;
    if (bitis) params.bitis_tarihi = bitis;

    return params;
}

/**
 * Filtreleri uygular ve haberleri yeniden yükler
 */
function filtreUygula() {
    haberleriGetir();
}

/**
 * Tüm filtreleri sıfırlar
 */
function filtreleriTemizle() {
    // Tüm checkboxları seç
    document.querySelectorAll('#haber-turu-filtre input[type="checkbox"]').forEach(cb => {
        cb.checked = true;
    });

    // İlçe filtresini sıfırla
    document.getElementById('ilce-filtre').value = '';

    // Tarih filtrelerini sıfırla
    document.getElementById('baslangic-tarihi').value = '';
    document.getElementById('bitis-tarihi').value = '';

    // Haberleri yenile
    filtreUygula();
}

// ==================== UI GÜNCELLEME ====================

/**
 * Sol paneldeki haber listesini günceller
 */
function haberListesiniGuncelle(haberListesi) {
    const container = document.getElementById('haber-listesi');

    if (haberListesi.length === 0) {
        container.innerHTML = '<p class="loading-text">Gösterilecek haber bulunamadı.</p>';
        return;
    }

    let html = '';
    haberListesi.forEach((haber, index) => {
        const turBilgi = CONFIG.newsTypes[haber.haber_turu] || {
            color: '#6B7280',
            icon: '📰',
            label: 'Diğer'
        };
        const tarih = haber.tarih ? tarihFormatla(haber.tarih) : '';
        const kaynak = haber.kaynak_adi || (haber.kaynaklar && haber.kaynaklar.length > 0 ? haber.kaynaklar[0].kaynak_adi : '');

        html += `
            <div class="haber-card" style="border-left-color: ${turBilgi.color}"
                 onclick="habereTikla(${index})" title="${escapeHtml(haber.baslik)}">
                <div class="haber-card-title">${escapeHtml(haber.baslik)}</div>
                <div class="haber-card-meta">
                    <span class="haber-card-tag" style="background-color: ${turBilgi.color}">
                        ${turBilgi.icon} ${turBilgi.label}
                    </span>
                    ${tarih ? `<span>📅 ${tarih}</span>` : ''}
                    ${kaynak ? `<span>📰 ${escapeHtml(kaynak)}</span>` : ''}
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

/**
 * Haber kartına tıklandığında haritayı o habere odaklar
 */
function habereTikla(index) {
    const haber = haberler[index];
    if (!haber) return;

    // Koordinatı olan markerı bul
    if (haber.koordinatlar && haber.koordinatlar.lat && haber.koordinatlar.lng) {
        // Haritayı haberin konumuna taşı
        map.panTo({
            lat: haber.koordinatlar.lat,
            lng: haber.koordinatlar.lng
        });
        map.setZoom(14);

        // İlgili markerı bul ve InfoWindow aç
        const marker = markers.find(m =>
            m.haberData && m.haberData._id === haber._id
        );
        if (marker) {
            infoWindowAc(marker, haber);
            // Marker animasyonu
            marker.setAnimation(google.maps.Animation.BOUNCE);
            setTimeout(() => marker.setAnimation(null), 1500);
        }
    } else {
        bildirimGoster('Bu haberin konum bilgisi bulunamadı', 'uyari');
    }
}

/**
 * Tür dağılımı grafiğini oluşturur
 */
function turDagilimiOlustur(dagilim) {
    const container = document.getElementById('tur-dagilimi');
    if (!dagilim || Object.keys(dagilim).length === 0) {
        container.innerHTML = '';
        return;
    }

    // Maksimum değeri bul (bar genişliği için)
    const maxDeger = Math.max(...Object.values(dagilim), 1);

    let html = '';
    for (const [turId, sayi] of Object.entries(dagilim)) {
        const turBilgi = CONFIG.newsTypes[turId] || {
            color: '#6B7280',
            icon: '📰',
            label: turId
        };
        const yuzde = (sayi / maxDeger) * 100;

        html += `
            <div class="tur-bar">
                <span class="tur-bar-label">${turBilgi.icon} ${turBilgi.label}</span>
                <div class="tur-bar-track">
                    <div class="tur-bar-fill" style="width: ${yuzde}%; background-color: ${turBilgi.color}"></div>
                </div>
                <span class="tur-bar-count">${sayi}</span>
            </div>
        `;
    }

    container.innerHTML = html;
}

// ==================== YARDIMCI FONKSİYONLAR ====================

/**
 * Loading overlay'i göster/gizle
 */
function loadingGoster(goster) {
    document.getElementById('loading-overlay').style.display = goster ? 'flex' : 'none';
}

/**
 * Bildirim göster
 */
function bildirimGoster(mesaj, tip = 'basarili') {
    const bildirim = document.getElementById('bildirim');
    bildirim.textContent = mesaj;
    bildirim.className = `bildirim ${tip}`;
    bildirim.style.display = 'block';

    // 5 saniye sonra gizle
    setTimeout(() => {
        bildirim.style.display = 'none';
    }, 5000);
}

/**
 * Tarih formatlama (ISO → Türkçe)
 */
function tarihFormatla(tarihStr) {
    try {
        const tarih = new Date(tarihStr);
        if (isNaN(tarih.getTime())) return tarihStr;

        return tarih.toLocaleDateString('tr-TR', {
            day: 'numeric',
            month: 'long',
            year: 'numeric'
        });
    } catch {
        return tarihStr;
    }
}

/**
 * HTML XSS koruması
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
