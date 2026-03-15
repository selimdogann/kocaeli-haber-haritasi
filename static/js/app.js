/* =============================================
   KOCAELI HABER HARİTASI - ANA JAVASCRIPT DOSYASI
   Google Maps Entegrasyonu & API İletişimi
   ============================================= */

// ==================== GLOBAL DEĞİŞKENLER ====================
let map;
let markers = [];
let infoWindow;
let haberler = [];

// ==================== HARİTA BAŞLATMA ====================
// Google Maps API yüklendiğinde callback olarak çağrılır.
// Harita Kocaeli merkez koordinatlarında (40.7654, 29.9408) başlatılır.
function initMap() {
    map = new google.maps.Map(document.getElementById('map'), {
        center: { lat: CONFIG.centerLat, lng: CONFIG.centerLng },
        zoom: 11, // Kocaeli ili genelini gösterecek yakınlaştırma seviyesi
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
            { featureType: 'poi', elementType: 'labels', stylers: [{ visibility: 'off' }] }
        ]
    });

    infoWindow = new google.maps.InfoWindow();

    haberleriGetir();
    istatistikleriGetir();
}

// ==================== SVG PIN İKON OLUŞTURUCU ====================
// Beyaz pin + renkli yuvarlak kare badge stili (referans görsele uygun)

function pinSvgOlustur(renk, ikonSvg) {
    // id collision'u önlemek için renk hash'i
    const hid = renk.replace('#','');
    return `<svg xmlns="http://www.w3.org/2000/svg" width="40" height="52" viewBox="0 0 40 52">
        <defs>
            <filter id="ds${hid}" x="-30%" y="-10%" width="160%" height="140%">
                <feDropShadow dx="0" dy="3" stdDeviation="2.5" flood-color="#000" flood-opacity="0.25"/>
            </filter>
        </defs>
        <!-- Beyaz pin gövdesi -->
        <path d="M20 50C20 50 37 30 37 17.5C37 8.4 29.4 1 20 1C10.6 1 3 8.4 3 17.5C3 30 20 50 20 50Z"
              fill="#fff" stroke="#d1d5db" stroke-width="1" filter="url(#ds${hid})"/>
        <!-- Renkli yuvarlak kare badge -->
        <rect x="8" y="6" width="24" height="24" rx="7" fill="${renk}"/>
        <!-- İkon -->
        ${ikonSvg}
    </svg>`;
}

let MARKER_ICONS = null;

function markerIkonlariniHazirla() {
    if (MARKER_ICONS) return;

    const ikonlar = {
        // Trafik Kazası — kırmızı badge, beyaz araba
        trafik_kazasi: pinSvgOlustur('#DC2626',
            `<g fill="#fff" transform="translate(20,18)">
                <path d="M-7,0 L-5.5,-4 L5.5,-4 L7,0 Z" stroke="#fff" stroke-width="0.5"/>
                <rect x="-7" y="0" width="14" height="3.5" rx="1"/>
                <circle cx="-4.5" cy="5" r="2" fill="#fff"/>
                <circle cx="4.5" cy="5" r="2" fill="#fff"/>
                <circle cx="-4.5" cy="5" r="1" fill="#DC2626"/>
                <circle cx="4.5" cy="5" r="1" fill="#DC2626"/>
                <rect x="-4" y="-3.5" width="3.2" height="2.5" rx="0.8" fill="#DC2626" opacity="0.4"/>
                <rect x="0.8" y="-3.5" width="3.2" height="2.5" rx="0.8" fill="#DC2626" opacity="0.4"/>
            </g>`),

        // Yangın — turuncu badge, beyaz alev
        yangin: pinSvgOlustur('#EA580C',
            `<g fill="#fff" transform="translate(20,18)">
                <path d="M0,-8 C0,-8 -6,-2 -6,2.5 C-6,5.8 -3.3,8.5 0,8.5 C3.3,8.5 6,5.8 6,2.5 C6,-2 0,-8 0,-8Z"/>
                <path d="M0,-3 C0,-3 -2.8,0 -2.8,2 C-2.8,3.5 -1.5,4.8 0,4.8 C1.5,4.8 2.8,3.5 2.8,2 C2.8,0 0,-3 0,-3Z" fill="#EA580C" opacity="0.5"/>
            </g>`),

        // Afet ve Acil Durum — koyu kirmizi badge, beyaz uyari
        afet_acil_durum: pinSvgOlustur('#B91C1C',
            `<g fill="#fff" transform="translate(20,18)">
                <path d="M0,-8 L8,7 H-8 Z"/>
                <rect x="-1.2" y="-3.5" width="2.4" height="6" rx="1" fill="#B91C1C"/>
                <circle cx="0" cy="4.5" r="1.4" fill="#B91C1C"/>
            </g>`),

        // Hırsızlık — mor badge, beyaz gözlük/maske ikonu
        hirsizlik: pinSvgOlustur('#7C3AED',
            `<g fill="#fff" transform="translate(20,18)">
                <ellipse cx="-3.8" cy="-1" rx="3.2" ry="2.5" fill="none" stroke="#fff" stroke-width="2"/>
                <ellipse cx="3.8" cy="-1" rx="3.2" ry="2.5" fill="none" stroke="#fff" stroke-width="2"/>
                <path d="M-0.6,-1 L0.6,-1" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>
                <line x1="-7" y1="-1" x2="-7" y2="-3.5" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>
                <line x1="7" y1="-1" x2="7" y2="-3.5" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>
                <path d="M-5,4 C-5,4 -2.5,7 0,7 C2.5,7 5,4 5,4" fill="none" stroke="#fff" stroke-width="1.5" stroke-linecap="round"/>
            </g>`),

        // Vefat — koyu gri badge, beyaz güvercin
        vefat: pinSvgOlustur('#475569',
            `<g fill="#fff" transform="translate(20,18)">
                <path d="M-5,2 C-3,-4 1,-6 5,-4 C3,-2 2,0 3,3 C1,4 -2,5 -5,2Z"/>
                <path d="M-1,-1 L5,-6" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>
                <circle cx="4.8" cy="-6.2" r="1.2"/>
            </g>`),

        // Sağlık — yeşil badge, beyaz sağlık artısı
        saglik: pinSvgOlustur('#059669',
            `<g fill="#fff" transform="translate(20,18)">
                <rect x="-2" y="-7" width="4" height="14" rx="1"/>
                <rect x="-7" y="-2" width="14" height="4" rx="1"/>
            </g>`),

        // Eğitim — teal badge, beyaz kep
        egitim: pinSvgOlustur('#0F766E',
            `<g fill="#fff" transform="translate(20,18)">
                <polygon points="0,-7 9,-3 0,1 -9,-3"/>
                <rect x="-1.5" y="1" width="3" height="6" rx="1"/>
                <path d="M5,-1 L8,1.5 L8,6" stroke="#fff" stroke-width="1.5" fill="none" stroke-linecap="round"/>
            </g>`),

        // Spor — yeşil badge, beyaz top
        spor: pinSvgOlustur('#16A34A',
            `<g fill="none" stroke="#fff" stroke-width="1.5" transform="translate(20,18)">
                <circle cx="0" cy="0" r="7" fill="none"/>
                <polygon points="0,-3 -2,0 0,3 2,0" fill="#fff" stroke="none"/>
                <path d="M-6,-1 C-4,-2 -3,-4 -2,-6"/>
                <path d="M6,-1 C4,-2 3,-4 2,-6"/>
                <path d="M-5,4 C-3,3 -1,3 0,5"/>
                <path d="M5,4 C3,3 1,3 0,5"/>
            </g>`),

        // Yerel Yönetim — mor-mavi badge, beyaz bina
        yerel_yonetim: pinSvgOlustur('#8B5CF6',
            `<g fill="#fff" transform="translate(20,18)">
                <polygon points="0,-8 8,-4.5 -8,-4.5"/>
                <rect x="-7" y="-3.5" width="14" height="2"/>
                <rect x="-6.5" y="-1.5" width="2.2" height="8"/>
                <rect x="-1.1" y="-1.5" width="2.2" height="8"/>
                <rect x="4.3" y="-1.5" width="2.2" height="8"/>
                <rect x="-8" y="6.5" width="16" height="2"/>
            </g>`),

        // Toplumsal Gündem — amber badge, beyaz tokalasma
        toplumsal_gundem: pinSvgOlustur('#C2410C',
            `<g fill="none" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" transform="translate(20,18)">
                <path d="M-7,-1 L-3,-1 L-1,2 L2,2 L4,-1 L7,-1"/>
                <path d="M-4,-1 L-6,3 L-3,5 L-1,2"/>
                <path d="M4,-1 L6,3 L3,5 L1,2"/>
            </g>`),

        // Ekonomi — altin badge, beyaz canta
        ekonomi: pinSvgOlustur('#CA8A04',
            `<g fill="#fff" transform="translate(20,18)">
                <rect x="-7" y="-3" width="14" height="10" rx="2"/>
                <path d="M-3,-3 V-5 C-3,-6.2 -2.2,-7 -1,-7 H1 C2.2,-7 3,-6.2 3,-5 V-3" fill="none" stroke="#fff" stroke-width="1.7"/>
                <rect x="-1.6" y="0" width="3.2" height="2" rx="0.6" fill="#CA8A04"/>
            </g>`),

        // Kamu Duyurusu — gok mavi badge, beyaz megafon
        kamu_duyurusu: pinSvgOlustur('#0EA5E9',
            `<g fill="#fff" transform="translate(20,18)">
                <path d="M-6,-1 L1,-5 V5 L-6,1 Z"/>
                <rect x="1" y="-2" width="2.2" height="4" rx="1"/>
                <path d="M-5,2 L-3,7" stroke="#fff" stroke-width="1.6" stroke-linecap="round"/>
            </g>`),

        // Medya ve Magazin — pembe badge, beyaz klaket
        medya_magazin: pinSvgOlustur('#DB2777',
            `<g fill="#fff" transform="translate(20,18)">
                <rect x="-7" y="-1.5" width="14" height="8.5" rx="1.5"/>
                <path d="M-7,-5.5 H7 V-1.5 H-7 Z"/>
                <path d="M-4,-5.5 L-1,-1.5 M0,-5.5 L3,-1.5 M4,-5.5 L7,-1.5" stroke="#DB2777" stroke-width="1.5"/>
            </g>`),

        // Elektrik Kesintisi — koyu badge, sarı şimşek
        elektrik_kesintisi: pinSvgOlustur('#1e293b',
            `<polygon points="22,8 16,17.5 19,17.5 16,26 24,15.5 20.5,15.5 22.5,8" fill="#FACC15"/>`),

        // Kültürel Etkinlik — mavi badge, beyaz müzik notu
        kulturel_etkinlik: pinSvgOlustur('#2563EB',
            `<g fill="#fff" transform="translate(20,18)">
                <circle cx="-3.5" cy="5" r="3"/>
                <circle cx="4" cy="3.5" r="3"/>
                <rect x="-0.8" y="-7" width="2.2" height="12.5"/>
                <rect x="3.7" y="-7" width="2.2" height="10.5"/>
                <path d="M1.4,-7 L5.9,-7 L5.9,-4 L1.4,-4Z" rx="1"/>
            </g>`),

        // Diğer — gri badge, beyaz belge
        diger: pinSvgOlustur('#6B7280',
            `<g fill="#fff" transform="translate(20,18)">
                <rect x="-6" y="-7.5" width="12" height="15" rx="2"/>
                <line x1="-3.5" y1="-4" x2="3.5" y2="-4" stroke="#6B7280" stroke-width="1.5" stroke-linecap="round"/>
                <line x1="-3.5" y1="-0.8" x2="3.5" y2="-0.8" stroke="#6B7280" stroke-width="1.5" stroke-linecap="round"/>
                <line x1="-3.5" y1="2.4" x2="1.5" y2="2.4" stroke="#6B7280" stroke-width="1.5" stroke-linecap="round"/>
            </g>`),
    };

    MARKER_ICONS = {};
    for (const [tur, svg] of Object.entries(ikonlar)) {
        MARKER_ICONS[tur] = {
            url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg),
            scaledSize: new google.maps.Size(40, 52),
            anchor: new google.maps.Point(20, 52),
        };
    }
}

// ==================== API İSTEKLERİ ====================

async function haberleriGetir() {
    try {
        const params = filtreParametreleriOlustur();
        const queryString = new URLSearchParams(params).toString();
        const response = await fetch(`/api/haberler?${queryString}`);
        const data = await response.json();

        if (data.basarili) {
            haberler = data.haberler;
            markerlariTemizle();
            haberleriHaritayaEkle(haberler);
            haberListesiniGuncelle(haberler);
            document.getElementById('toplam-haber-sayisi').textContent = data.toplam;
        }
    } catch (error) {
        console.error('Haberler yüklenirken hata:', error);
        bildirimGoster('Haberler yüklenirken hata oluştu', 'hata');
    }
}

async function istatistikleriGetir() {
    try {
        const response = await fetch('/api/istatistikler');
        const data = await response.json();
        if (data.basarili) {
            const stats = data.istatistikler;
            document.getElementById('stat-toplam').textContent = stats.toplam_haber || 0;
            document.getElementById('stat-konumlu').textContent = stats.konumlu_haber || 0;
            turDagilimiOlustur(stats.tur_dagilimi || {});
        }
    } catch (error) {
        console.error('İstatistikler yüklenirken hata:', error);
    }
}

let progressInterval = null;

async function scrapingBaslat() {
    const btn = document.getElementById('btn-scrape');
    btn.disabled = true;
    btn.innerHTML = '⏳ Başlatılıyor...';
    loadingGoster(true);
    bildirimGoster('Haber çekme işlemi başlatıldı, lütfen bekleyiniz...', 'uyari');

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
        } catch (e) {}
    }, 800);

    try {
        const response = await fetch('/api/scrape', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
        const data = await response.json();
        if (data.basarili) {
            const rapor = data.rapor;
            bildirimGoster(`✅ Tamamlandı! ${rapor.toplam_kaydedilen} yeni haber eklendi (${rapor.toplam_cekilen} tarandı, ${rapor.sure_saniye.toFixed(0)}s)`, 'basarili');
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

function haberleriHaritayaEkle(haberListesi) {
    haberListesi.forEach(haber => {
        if (haber.koordinatlar && haber.koordinatlar.lat && haber.koordinatlar.lng) {
            markerOlustur(haber);
        }
    });
}

function markerOlustur(haber) {
    markerIkonlariniHazirla();

    const turBilgi = CONFIG.newsTypes[haber.haber_turu] || { color: '#6B7280', icon: '📰', label: 'Diğer' };
    const ikon = MARKER_ICONS[haber.haber_turu] || MARKER_ICONS['diger'];

    const marker = new google.maps.Marker({
        position: { lat: haber.koordinatlar.lat, lng: haber.koordinatlar.lng },
        map: map,
        icon: ikon,
        title: haber.baslik,
        animation: google.maps.Animation.DROP
    });

    marker.haberData = haber;

    marker.addListener('click', () => {
        infoWindowAc(marker, haber);
    });

    markers.push(marker);
}

function infoWindowAc(marker, haber) {
    const turBilgi = CONFIG.newsTypes[haber.haber_turu] || { color: '#6B7280', icon: '📰', label: 'Diğer' };
    const tarih = haber.tarih ? tarihFormatla(haber.tarih) : 'Tarih bilinmiyor';
    const kaynaklar = haber.kaynaklar ? haber.kaynaklar.map(k => k.kaynak_adi).join(', ') : (haber.kaynak_adi || '');
    const kaynakSayisi = haber.kaynaklar ? haber.kaynaklar.length : 1;
    const icerikOzet = haber.icerik ? haber.icerik.substring(0, 150) + (haber.icerik.length > 150 ? '...' : '') : '';

    const konum = [];
    if (haber.konum_bilgisi) {
        if (haber.konum_bilgisi.ilce) konum.push(haber.konum_bilgisi.ilce);
        if (haber.konum_bilgisi.mahalle) konum.push(haber.konum_bilgisi.mahalle);
    }
    const konumMetni = konum.length > 0 ? konum.join(', ') : 'Kocaeli';

    const haberLinki = haber.haber_linki || (haber.kaynaklar && haber.kaynaklar.length > 0 ? haber.kaynaklar[0].link : '#');

    const icerik = `
        <div style="font-family:'Inter',sans-serif;max-width:330px;padding:4px;">
            <div style="font-size:15px;font-weight:700;color:#0f172a;margin-bottom:10px;line-height:1.45;letter-spacing:-0.2px;">
                ${escapeHtml(haber.baslik)}
            </div>
            <div style="display:flex;flex-direction:column;gap:6px;margin-bottom:12px;font-size:12.5px;color:#475569;">
                <span style="display:inline-block;padding:4px 12px;border-radius:8px;color:#fff;font-size:11.5px;font-weight:700;background:linear-gradient(135deg,${turBilgi.color},${turBilgi.color}dd);width:fit-content;letter-spacing:0.3px;box-shadow:0 2px 6px ${turBilgi.color}44;">
                    ${turBilgi.icon} ${turBilgi.label}
                </span>
                <span>📅 ${tarih}</span>
                <span>📍 ${escapeHtml(konumMetni)}</span>
                ${kaynaklar ? `<span>📰 ${escapeHtml(kaynaklar)}</span>` : ''}
                ${kaynakSayisi > 1 ? `<span style="display:inline-block;padding:2px 8px;border-radius:6px;font-size:10px;font-weight:700;background:linear-gradient(135deg,#6366f1,#a855f7);color:#fff;">📡 ${kaynakSayisi} kaynakta</span>` : ''}
            </div>
            ${icerikOzet ? `<div style="font-size:12.5px;color:#64748b;line-height:1.55;margin-bottom:12px;padding:8px 10px;background:#f8fafc;border-radius:8px;border-left:3px solid ${turBilgi.color};">${escapeHtml(icerikOzet)}</div>` : ''}
            <a href="${escapeHtml(haberLinki)}" target="_blank" rel="noopener"
               style="display:block;text-align:center;background:linear-gradient(135deg,#6366f1,#a855f7);color:#fff;padding:10px 18px;border-radius:10px;text-decoration:none;font-size:13.5px;font-weight:700;letter-spacing:0.3px;box-shadow:0 4px 12px rgba(99,102,241,0.3);transition:all 0.2s;">
                Habere Git &rarr;
            </a>
        </div>
    `;

    infoWindow.setContent(icerik);
    infoWindow.open(map, marker);
}

function markerlariTemizle() {
    markers.forEach(marker => marker.setMap(null));
    markers = [];
}

// ==================== FİLTRE İŞLEMLERİ ====================
// Tüm filtrelemeler AJAX ile sayfa yenilenmeden (no-reload) yapılır.
// Filtre değiştiğinde → filtreUygula() → haberleriGetir() → API çağrısı
// → marker'lar ve haber listesi dinamik güncellenir

function filtreParametreleriOlustur() {
    const params = {};
    const seciliTurler = [];
    document.querySelectorAll('#haber-turu-filtre input[type="checkbox"]:checked').forEach(cb => {
        seciliTurler.push(cb.value);
    });
    const tumCheckboxlar = document.querySelectorAll('#haber-turu-filtre input[type="checkbox"]');
    if (seciliTurler.length < tumCheckboxlar.length && seciliTurler.length > 0) {
        params.haber_turu = seciliTurler.join(',');
    }
    const ilce = document.getElementById('ilce-filtre').value;
    if (ilce) params.ilce = ilce;
    const baslangic = document.getElementById('baslangic-tarihi').value;
    const bitis = document.getElementById('bitis-tarihi').value;
    if (baslangic) params.baslangic_tarihi = baslangic;
    if (bitis) params.bitis_tarihi = bitis;
    return params;
}

function filtreUygula() { haberleriGetir(); }

function filtreleriTemizle() {
    document.querySelectorAll('#haber-turu-filtre input[type="checkbox"]').forEach(cb => { cb.checked = true; });
    document.getElementById('ilce-filtre').value = '';
    document.getElementById('baslangic-tarihi').value = '';
    document.getElementById('bitis-tarihi').value = '';
    filtreUygula();
}

// ==================== UI GÜNCELLEME ====================

function haberListesiniGuncelle(haberListesi) {
    const container = document.getElementById('haber-listesi');
    if (haberListesi.length === 0) {
        container.innerHTML = '<p class="loading-text">Gösterilecek haber bulunamadı.</p>';
        return;
    }
    let html = '';
    haberListesi.forEach((haber, index) => {
        const turBilgi = CONFIG.newsTypes[haber.haber_turu] || { color: '#6B7280', icon: '📰', label: 'Diğer' };
        const tarih = haber.tarih ? tarihFormatla(haber.tarih) : '';
        const kaynak = haber.kaynak_adi || (haber.kaynaklar && haber.kaynaklar.length > 0 ? haber.kaynaklar[0].kaynak_adi : '');
        const kaynakSayisi = haber.kaynaklar ? haber.kaynaklar.length : 1;
        const multiSourceBadge = kaynakSayisi > 1
            ? `<span class="multi-source-badge">📡 ${kaynakSayisi} kaynak</span>`
            : '';
        html += `
            <div class="haber-card" style="border-left-color: ${turBilgi.color}"
                 onclick="habereTikla(${index})" title="${escapeHtml(haber.baslik)}">
                <div class="haber-card-title">${escapeHtml(haber.baslik)}</div>
                <div class="haber-card-meta">
                    <span class="haber-card-tag" style="background-color: ${turBilgi.color}">
                        ${turBilgi.icon} ${turBilgi.label}
                    </span>
                    ${multiSourceBadge}
                    ${tarih ? `<span>📅 ${tarih}</span>` : ''}
                    ${kaynak ? `<span>📰 ${escapeHtml(kaynak)}</span>` : ''}
                </div>
            </div>
        `;
    });
    container.innerHTML = html;
}

function habereTikla(index) {
    const haber = haberler[index];
    if (!haber) return;
    if (haber.koordinatlar && haber.koordinatlar.lat && haber.koordinatlar.lng) {
        map.panTo({ lat: haber.koordinatlar.lat, lng: haber.koordinatlar.lng });
        map.setZoom(14);
        const marker = markers.find(m => m.haberData && m.haberData._id === haber._id);
        if (marker) {
            infoWindowAc(marker, haber);
            marker.setAnimation(google.maps.Animation.BOUNCE);
            setTimeout(() => marker.setAnimation(null), 1500);
        }
    } else {
        bildirimGoster('Bu haberin konum bilgisi bulunamadı', 'uyari');
    }
}

function turDagilimiOlustur(dagilim) {
    const container = document.getElementById('tur-dagilimi');
    if (!dagilim || Object.keys(dagilim).length === 0) { container.innerHTML = ''; return; }
    const maxDeger = Math.max(...Object.values(dagilim), 1);
    let html = '';
    for (const [turId, sayi] of Object.entries(dagilim)) {
        const turBilgi = CONFIG.newsTypes[turId] || { color: '#6B7280', icon: '📰', label: turId };
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

function loadingGoster(goster) {
    document.getElementById('loading-overlay').style.display = goster ? 'flex' : 'none';
}

function bildirimGoster(mesaj, tip = 'basarili') {
    const bildirim = document.getElementById('bildirim');
    bildirim.textContent = mesaj;
    bildirim.className = `bildirim ${tip}`;
    bildirim.style.display = 'block';
    setTimeout(() => { bildirim.style.display = 'none'; }, 5000);
}

function tarihFormatla(tarihStr) {
    try {
        const tarih = new Date(tarihStr);
        if (isNaN(tarih.getTime())) return tarihStr;
        return tarih.toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' });
    } catch { return tarihStr; }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
