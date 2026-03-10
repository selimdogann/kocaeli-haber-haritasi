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
function initMap() {
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
            { featureType: 'poi', elementType: 'labels', stylers: [{ visibility: 'off' }] }
        ]
    });

    infoWindow = new google.maps.InfoWindow();

    haberleriGetir();
    istatistikleriGetir();
}

// ==================== SVG PIN İKON OLUŞTURUCU ====================

function pinSvgOlustur(renk, ikonSvg) {
    return `<svg xmlns="http://www.w3.org/2000/svg" width="36" height="48" viewBox="0 0 36 48">
        <defs>
            <filter id="s" x="-20%" y="-10%" width="140%" height="130%">
                <feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="#000" flood-opacity="0.3"/>
            </filter>
        </defs>
        <path d="M18 47C18 47 34 28 34 16.5C34 7.9 26.8 1 18 1C9.2 1 2 7.9 2 16.5C2 28 18 47 18 47Z"
              fill="${renk}" stroke="#fff" stroke-width="2" filter="url(#s)"/>
        <circle cx="18" cy="16" r="11" fill="rgba(255,255,255,0.25)"/>
        ${ikonSvg}
    </svg>`;
}

let MARKER_ICONS = null;

function markerIkonlariniHazirla() {
    if (MARKER_ICONS) return;

    const ikonlar = {
        trafik_kazasi: pinSvgOlustur('#E53E3E',
            `<g fill="#fff" transform="translate(18,16)">
                <path d="M-8,0.5 L-6,-4.5 L6,-4.5 L8,0.5 L8,3 L-8,3 Z"/>
                <rect x="-5.5" y="-4" width="4" height="3" rx="0.5" fill="#E53E3E" opacity="0.5"/>
                <rect x="1.5" y="-4" width="4" height="3" rx="0.5" fill="#E53E3E" opacity="0.5"/>
                <circle cx="-5" cy="4.5" r="1.8" fill="#fff"/>
                <circle cx="5" cy="4.5" r="1.8" fill="#fff"/>
            </g>`),

        yangin: pinSvgOlustur('#ED8936',
            `<path d="M18,7 C18,7 12.5,12.5 12.5,16.5 C12.5,19.5 14.9,22 18,22
                     C21.1,22 23.5,19.5 23.5,16.5 C23.5,12.5 18,7 18,7 Z" fill="#fff"/>
             <path d="M18,13 C18,13 15.8,15.2 15.8,16.8 C15.8,18 16.8,19 18,19
                     C19.2,19 20.2,18 20.2,16.8 C20.2,15.2 18,13 18,13 Z" fill="#ED8936"/>`),

        hirsizlik: pinSvgOlustur('#805AD5',
            `<g fill="#fff" transform="translate(18,16)">
                <path d="M0,-9 L8,-5 L8,1 C8,5.5 4.5,8.5 0,10 C-4.5,8.5 -8,5.5 -8,1 L-8,-5 Z"/>
                <path d="M0,-5 L4.5,-2.5 L4.5,0.8 C4.5,3.8 2.5,5.5 0,6.5 C-2.5,5.5 -4.5,3.8 -4.5,0.8 L-4.5,-2.5 Z"
                      fill="#805AD5" opacity="0.4"/>
            </g>`),

        elektrik_kesintisi: pinSvgOlustur('#D69E2E',
            `<polygon points="20,6.5 14.5,15.5 17.5,15.5 14.5,25 22,14 18.5,14 21,6.5" fill="#fff"/>`),

        kulturel_etkinlik: pinSvgOlustur('#3182CE',
            `<g fill="#fff" transform="translate(18,16)">
                <ellipse cx="-3.5" cy="5" rx="3.5" ry="2.5"/>
                <rect x="-0.3" y="-8" width="2" height="13"/>
                <path d="M1.7,-8 L8,-10 L8,-4.5 L1.7,-2.5 Z"/>
            </g>`),

        diger: pinSvgOlustur('#718096',
            `<g fill="#fff" transform="translate(18,16)">
                <rect x="-6.5" y="-8" width="13" height="16" rx="2"/>
                <line x1="-4" y1="-4.5" x2="4" y2="-4.5" stroke="#718096" stroke-width="1.3"/>
                <line x1="-4" y1="-1.5" x2="4" y2="-1.5" stroke="#718096" stroke-width="1.3"/>
                <line x1="-4" y1="1.5" x2="2" y2="1.5" stroke="#718096" stroke-width="1.3"/>
                <line x1="-4" y1="4.5" x2="3" y2="4.5" stroke="#718096" stroke-width="1.3"/>
            </g>`),
    };

    MARKER_ICONS = {};
    for (const [tur, svg] of Object.entries(ikonlar)) {
        MARKER_ICONS[tur] = {
            url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(svg),
            scaledSize: new google.maps.Size(36, 48),
            anchor: new google.maps.Point(18, 48),
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
    const icerikOzet = haber.icerik ? haber.icerik.substring(0, 150) + (haber.icerik.length > 150 ? '...' : '') : '';

    const konum = [];
    if (haber.konum_bilgisi) {
        if (haber.konum_bilgisi.ilce) konum.push(haber.konum_bilgisi.ilce);
        if (haber.konum_bilgisi.mahalle) konum.push(haber.konum_bilgisi.mahalle);
    }
    const konumMetni = konum.length > 0 ? konum.join(', ') : 'Kocaeli';

    const haberLinki = haber.haber_linki || (haber.kaynaklar && haber.kaynaklar.length > 0 ? haber.kaynaklar[0].link : '#');

    const icerik = `
        <div style="font-family:'Inter',sans-serif;max-width:320px;">
            <div style="font-size:14px;font-weight:600;color:#1e293b;margin-bottom:8px;line-height:1.4;">
                ${escapeHtml(haber.baslik)}
            </div>
            <div style="display:flex;flex-direction:column;gap:4px;margin-bottom:10px;font-size:12px;color:#475569;">
                <span style="display:inline-block;padding:3px 10px;border-radius:6px;color:#fff;font-size:11px;font-weight:600;background:${turBilgi.color};width:fit-content;">
                    ${turBilgi.icon} ${turBilgi.label}
                </span>
                <span>📅 ${tarih}</span>
                <span>📍 ${escapeHtml(konumMetni)}</span>
                ${kaynaklar ? `<span>📰 ${escapeHtml(kaynaklar)}</span>` : ''}
            </div>
            ${icerikOzet ? `<div style="font-size:12px;color:#64748b;line-height:1.5;margin-bottom:10px;">${escapeHtml(icerikOzet)}</div>` : ''}
            <a href="${escapeHtml(haberLinki)}" target="_blank" rel="noopener"
               style="display:block;text-align:center;background:#2563eb;color:#fff;padding:8px 16px;border-radius:8px;text-decoration:none;font-size:13px;font-weight:600;">
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
