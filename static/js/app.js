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

        if (data.durum === 'basarili') {
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

        if (data.durum === 'basarili') {
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
async function scrapingBaslat() {
    const btn = document.getElementById('btn-scrape');
    btn.disabled = true;
    btn.innerHTML = '⏳ Çekiliyor...';

    loadingGoster(true);
    bildirimGoster('Haber çekme işlemi başlatıldı, lütfen bekleyiniz...', 'uyari');

    try {
        const response = await fetch('/api/scrape', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();

        if (data.durum === 'basarili') {
            const rapor = data.rapor;
            bildirimGoster(
                `✅ Tamamlandı! ${rapor.toplam_yeni_haber} yeni haber eklendi (${rapor.toplam_taranan} tarandı)`,
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
 * Tek bir haber için marker oluşturur
 */
function markerOlustur(haber) {
    const turBilgi = CONFIG.newsTypes[haber.haber_turu] || {
        color: '#6B7280',
        icon: '📰',
        label: 'Diğer'
    };

    // SVG tabanlı özel marker ikonu
    const markerIcon = {
        path: google.maps.SymbolPath.CIRCLE,
        fillColor: turBilgi.color,
        fillOpacity: 0.9,
        strokeColor: '#ffffff',
        strokeWeight: 2,
        scale: 10
    };

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
        params.tur = seciliTurler.join(',');
    }

    // İlçe filtresi
    const ilce = document.getElementById('ilce-filtre').value;
    if (ilce) params.ilce = ilce;

    // Tarih filtresi
    const baslangic = document.getElementById('baslangic-tarihi').value;
    const bitis = document.getElementById('bitis-tarihi').value;
    if (baslangic) params.baslangic = baslangic;
    if (bitis) params.bitis = bitis;

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
