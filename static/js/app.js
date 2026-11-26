/* =============================================
   KOCAELI HABER HARİTASI — ANA JAVASCRIPT
   Google Maps entegrasyonu, filtreler, sanal liste, API iletişimi
   ============================================= */

// ==================== GLOBAL DURUM ====================
let map = null;
let infoWindow = null;
let markers = [];
let haberler = [];          // API'den gelen (filtrelenmiş) haberler
let gorunenHaberler = [];   // + başlık araması uygulanmış hali
let aktifHaberAnahtari = null;
const CAKISAN_MARKER_OFFSET = 0.00018;

// ==================== İKONLAR (Lucide, MIT) ====================
// Emoji yerine SVG: her platformda aynı görünür, renk/kalınlık kontrol edilebilir.
const TUR_IKONLARI = {
    trafik_kazasi: '<path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><path d="M9 17h6"/><circle cx="17" cy="17" r="2"/>',
    yangin: '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.07-2.14-.22-4.05 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.15.43-2.29 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>',
    elektrik_kesintisi: '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>',
    asayis: '<path d="M7 18v-6a5 5 0 1 1 10 0v6"/><path d="M5 21a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-1a2 2 0 0 0-2-2H7a2 2 0 0 0-2 2z"/><path d="M21 12h1M18.5 4.5 18 5M2 12h1M12 2v1M4.93 4.93l.7.7M12 12v6"/>',
    hirsizlik: '<rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/>',
    kulturel_etkinlik: '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
};
const VARSAYILAN_IKON = '<circle cx="12" cy="12" r="4"/>';

const UI_IKON = {
    takvim: '<path d="M8 2v4M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/>',
    konum: '<path d="M20 10c0 5-5.5 10.2-7.4 11.8a1 1 0 0 1-1.2 0C9.5 20.2 4 15 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/>',
    gazete: '<path d="M15 18h-5M18 14h-8"/><path d="M4 22h16a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2H8a2 2 0 0 0-2 2v16a2 2 0 0 1-4 0v-9a2 2 0 0 1 2-2h2"/><rect width="8" height="4" x="10" y="6" rx="1"/>',
    dis: '<path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    yayin: '<path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5"/><circle cx="12" cy="12" r="2"/><path d="M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5M19.1 4.9C23 8.8 23 15.1 19.1 19"/>',
};

function svg(icerik, ekSinif = '') {
    return `<svg class="${ekSinif}" viewBox="0 0 24 24" aria-hidden="true">${icerik}</svg>`;
}

function turBilgisi(turId) {
    return CONFIG.newsTypes[turId] || { color: '#9aa4b5', label: 'Diğer' };
}

// Chip ikonlarını doldur (Jinja sadece yer tutucu basar)
document.querySelectorAll('[data-tur-ikon]').forEach(el => {
    el.innerHTML = svg(TUR_IKONLARI[el.dataset.turIkon] || VARSAYILAN_IKON);
});

// ==================== BAŞLANGIÇ ====================
// Veri, haritadan bağımsız yüklenir: Maps anahtarı yoksa bile liste ve sayılar çalışır.
document.addEventListener('DOMContentLoaded', () => {
    haberleriGetir();
    istatistikleriGetir();
    if (!CONFIG.mapsKeyVar) haritaHatasiGoster();
});

// Google Maps anahtar hatası (geçersiz key, faturalandırma kapalı vb.)
window.gm_authFailure = function () {
    haritaHatasiGoster('Google Maps anahtarı reddedildi. Anahtarın geçerli olduğunu ve Maps JavaScript API\'nin açık olduğunu kontrol et.');
};

function haritaHatasiGoster(metin) {
    const kutu = document.getElementById('map-empty');
    if (metin) document.getElementById('map-empty-metin').textContent = metin;
    kutu.hidden = false;
    document.getElementById('map').style.visibility = 'hidden';
}

// ==================== HARİTA ====================
// Google Maps API yüklendiğinde callback olarak çağrılır.
// Harita Kocaeli merkez koordinatlarında (40.7654, 29.9408) başlatılır.
function initMap() {
    map = new google.maps.Map(document.getElementById('map'), {
        center: { lat: CONFIG.centerLat, lng: CONFIG.centerLng },
        zoom: 11,
        backgroundColor: '#0c1220',
        disableDefaultUI: true,
        zoomControl: true,
        zoomControlOptions: { position: google.maps.ControlPosition.RIGHT_BOTTOM },
        fullscreenControl: false,
        clickableIcons: false,
        styles: HARITA_STILI,
    });

    infoWindow = new google.maps.InfoWindow({ maxWidth: 340 });
    infoWindow.addListener('closeclick', () => aktifKartiIsaretle(null));

    // Veri haritadan önce geldiyse marker'ları şimdi çiz
    if (haberler.length) haritayiGuncelle();
}

// Sakin, düşük kontrastlı gece haritası: pinler tek doygun renk olsun diye.
const HARITA_STILI = [
    { elementType: 'geometry', stylers: [{ color: '#10151f' }] },
    { elementType: 'labels.text.fill', stylers: [{ color: '#7d889b' }] },
    { elementType: 'labels.text.stroke', stylers: [{ color: '#0a0d14' }] },
    { elementType: 'labels.icon', stylers: [{ visibility: 'off' }] },
    { featureType: 'administrative', elementType: 'geometry.stroke', stylers: [{ color: '#2a3346' }] },
    { featureType: 'administrative.locality', elementType: 'labels.text.fill', stylers: [{ color: '#b4bdcc' }] },
    { featureType: 'administrative.neighborhood', stylers: [{ visibility: 'off' }] },
    { featureType: 'administrative.land_parcel', stylers: [{ visibility: 'off' }] },
    { featureType: 'poi', stylers: [{ visibility: 'off' }] },
    { featureType: 'poi.park', elementType: 'geometry', stylers: [{ visibility: 'on' }, { color: '#121c1c' }] },
    { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#1a2131' }] },
    { featureType: 'road', elementType: 'labels', stylers: [{ visibility: 'simplified' }] },
    { featureType: 'road.highway', elementType: 'geometry', stylers: [{ color: '#25304a' }] },
    { featureType: 'road.highway', elementType: 'labels.text.fill', stylers: [{ color: '#8592a8' }] },
    { featureType: 'road.local', elementType: 'labels', stylers: [{ visibility: 'off' }] },
    { featureType: 'transit', stylers: [{ visibility: 'off' }] },
    { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#0b1a2c' }] },
    { featureType: 'water', elementType: 'labels.text.fill', stylers: [{ color: '#3b5a7d' }] },
];

// ==================== MARKER İKONLARI ====================
// Kategori renginde damla pin + koyu ikon. Renk tek başına anlam taşımasın diye
// her türün kendi ikonu var (erişilebilirlik: "color only" kuralı).
const MARKER_CACHE = {};

function markerIkonu(turId, aktif = false) {
    const anahtar = `${turId}|${aktif}`;
    if (MARKER_CACHE[anahtar]) return MARKER_CACHE[anahtar];

    const renk = turBilgisi(turId).color;
    const ikon = TUR_IKONLARI[turId] || VARSAYILAN_IKON;
    const olcek = aktif ? 1.25 : 1;
    const w = Math.round(34 * olcek), h = Math.round(44 * olcek);

    const kod = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 34 44">
        <path d="M17 42.5S31.5 27.6 31.5 16.6A14.5 14.5 0 0 0 2.5 16.6C2.5 27.6 17 42.5 17 42.5Z"
              fill="${renk}" stroke="#0a0d14" stroke-width="2"/>
        ${aktif ? `<path d="M17 42.5S31.5 27.6 31.5 16.6A14.5 14.5 0 0 0 2.5 16.6C2.5 27.6 17 42.5 17 42.5Z" fill="none" stroke="#e9edf3" stroke-width="1.2" transform="translate(17 22) scale(1.06) translate(-17 -22)"/>` : ''}
        <g transform="translate(8 7.6) scale(.75)" fill="none" stroke="#0a0d14" stroke-width="2.4"
           stroke-linecap="round" stroke-linejoin="round">${ikon}</g>
    </svg>`;

    MARKER_CACHE[anahtar] = {
        url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(kod),
        scaledSize: new google.maps.Size(w, h),
        anchor: new google.maps.Point(w / 2, h - 1),
    };
    return MARKER_CACHE[anahtar];
}

// ==================== API İSTEKLERİ ====================

async function haberleriGetir() {
    try {
        const params = filtreParametreleriOlustur();
        params._ts = Date.now();
        const response = await fetch(`/api/haberler?${new URLSearchParams(params)}`, { cache: 'no-store' });
        const data = await response.json();

        if (!data.basarili) throw new Error(data.hata || 'Bilinmeyen hata');
        haberler = data.haberler;
        aramaYap();
    } catch (error) {
        console.error('Haberler yüklenirken hata:', error);
        listeDurumu('hata');
        bildirimGoster('Haberler alınamadı. Sunucu ve MongoDB çalışıyor mu?', 'hata');
    }
}

async function istatistikleriGetir() {
    try {
        const params = filtreParametreleriOlustur();
        // Chip sayıları tüm türleri göstermeli; tür filtresini istatistikten çıkar
        delete params.haber_turu;
        params._ts = Date.now();
        const response = await fetch(`/api/istatistikler?${new URLSearchParams(params)}`, { cache: 'no-store' });
        const data = await response.json();
        if (data.basarili) turDagilimiOlustur(data.istatistikler.tur_dagilimi || {});
    } catch (error) {
        console.error('İstatistikler yüklenirken hata:', error);
    }
}

let progressInterval = null;

async function scrapingBaslat() {
    const btn = document.getElementById('btn-scrape');
    const btnText = btn.querySelector('.btn-text');
    const progress = document.getElementById('progress');
    btn.disabled = true;
    btnText.textContent = 'Güncelleniyor';
    progress.hidden = false;
    progressYaz('Başlatılıyor', 0);

    progressInterval = setInterval(async () => {
        try {
            const p = await (await fetch('/api/scrape/progress')).json();
            if (!p.aktif) return;
            let asama = p.asama;
            if (p.asama === 'Haberler çekiliyor') asama = `${p.kaynak} taranıyor (${p.kaynak_no}/${p.toplam_kaynak})`;
            else if (p.asama === 'Haberler işleniyor') asama = `İşleniyor: ${p.islenen_haber}/${p.toplam_haber}`;
            progressYaz(asama, p.yuzde);
        } catch (e) { /* ilerleme sorgusu kaçabilir, sorun değil */ }
    }, 800);

    try {
        const data = await (await fetch('/api/scrape', { method: 'POST', headers: { 'Content-Type': 'application/json' } })).json();
        if (data.basarili) {
            const r = data.rapor;
            bildirimGoster(`Güncellendi: ${r.toplam_kaydedilen} yeni haber eklendi, ${r.toplam_cekilen} haber tarandı (${r.sure_saniye.toFixed(0)} sn).`, 'basarili');
            await Promise.all([haberleriGetir(), istatistikleriGetir()]);
        } else {
            bildirimGoster('Güncelleme yarıda kaldı: ' + (data.hata || data.mesaj || 'bilinmeyen hata'), 'hata');
        }
    } catch (error) {
        console.error('Scraping hatası:', error);
        bildirimGoster('Sunucuya ulaşılamadı. Flask çalışıyor mu?', 'hata');
    } finally {
        clearInterval(progressInterval);
        progressInterval = null;
        btn.disabled = false;
        btnText.textContent = 'Haberleri güncelle';
        progress.hidden = true;
    }
}

function progressYaz(asama, yuzde) {
    document.getElementById('progress-asama').textContent = asama;
    document.getElementById('progress-yuzde').textContent = `%${Math.round(yuzde || 0)}`;
    document.getElementById('progress-bar').style.width = `${yuzde || 0}%`;
}

// ==================== HARİTA İŞLEMLERİ ====================

function haritayiGuncelle() {
    if (!map) return;
    markerlariTemizle();
    const konumlar = cakisanMarkerKonumlariniHesapla(gorunenHaberler);

    gorunenHaberler.forEach((haber, index) => {
        if (!konumluMu(haber)) return;
        const anahtar = haberKonumAnahtari(haber, index);
        markerOlustur(haber, konumlar.get(anahtar), anahtar);
    });
}

function markerOlustur(haber, gosterimKonumu, haberAnahtari) {
    const marker = new google.maps.Marker({
        position: gosterimKonumu || { lat: haber.koordinatlar.lat, lng: haber.koordinatlar.lng },
        map,
        icon: markerIkonu(haber.haber_turu),
        title: haber.baslik,
        optimized: true,
    });
    marker.haberData = haber;
    marker.haberKey = haberAnahtari;
    marker.addListener('click', () => {
        infoWindowAc(marker, haber);
        aktifKartiIsaretle(haberAnahtari, true);
    });
    markers.push(marker);
}

function konumluMu(haber) {
    return !!(haber.koordinatlar && haber.koordinatlar.lat && haber.koordinatlar.lng);
}

function haberKonumAnahtari(haber, index) {
    return haber._id || haber.id || `${haber.baslik || 'haber'}-${index}`;
}

function koordinatGrupAnahtari(haber) {
    return `${Number(haber.koordinatlar.lat).toFixed(6)}|${Number(haber.koordinatlar.lng).toFixed(6)}`;
}

// Aynı koordinattaki haberleri küçük bir çember üzerine dağıt (üst üste binmesin)
function cakisanMarkerKonumlariniHesapla(haberListesi) {
    const gruplar = new Map();
    const dagitim = new Map();

    haberListesi.forEach((haber, index) => {
        if (!konumluMu(haber)) return;
        const g = koordinatGrupAnahtari(haber);
        if (!gruplar.has(g)) gruplar.set(g, []);
        gruplar.get(g).push({ haber, anahtar: haberKonumAnahtari(haber, index) });
    });

    gruplar.forEach((grup) => {
        if (grup.length === 1) {
            const t = grup[0];
            dagitim.set(t.anahtar, { lat: t.haber.koordinatlar.lat, lng: t.haber.koordinatlar.lng });
            return;
        }
        grup.sort((a, b) =>
            `${a.haber.tarih || ''}|${a.haber.baslik || ''}|${a.anahtar}`
                .localeCompare(`${b.haber.tarih || ''}|${b.haber.baslik || ''}|${b.anahtar}`, 'tr'));

        const merkezLat = grup[0].haber.koordinatlar.lat;
        const merkezLng = grup[0].haber.koordinatlar.lng;
        const yaricap = CAKISAN_MARKER_OFFSET + (Math.min(grup.length, 8) - 2) * 0.00002;

        grup.forEach((kayit, sira) => {
            const aci = (2 * Math.PI * sira) / grup.length;
            dagitim.set(kayit.anahtar, {
                lat: merkezLat + Math.sin(aci) * yaricap,
                lng: merkezLng + Math.cos(aci) * yaricap,
            });
        });
    });
    return dagitim;
}

function konumMetni(haber) {
    const k = [];
    if (haber.konum_bilgisi) {
        if (haber.konum_bilgisi.ilce) k.push(haber.konum_bilgisi.ilce);
        if (haber.konum_bilgisi.mahalle) k.push(haber.konum_bilgisi.mahalle);
    }
    return k.length ? k.join(', ') : 'Kocaeli';
}

function infoWindowAc(marker, haber) {
    const tur = turBilgisi(haber.haber_turu);
    const tarih = haber.tarih ? tarihFormatla(haber.tarih) : 'Tarih yok';
    const ozet = haber.icerik ? haber.icerik.substring(0, 160) + (haber.icerik.length > 160 ? '…' : '') : '';

    // Tüm kaynaklar listelenir (aynı haber birden çok sitede çıktıysa)
    const kaynaklar = (haber.kaynaklar && haber.kaynaklar.length)
        ? haber.kaynaklar
        : [{ kaynak_adi: haber.kaynak_adi || 'Kaynak', link: haber.haber_linki }];
    const linkler = kaynaklar.map(k => `
        <a class="iw-link" href="${escapeHtml(k.link || '#')}" target="_blank" rel="noopener">
            <span>${escapeHtml(k.kaynak_adi || 'Kaynak')} sitesinde oku</span>${svg(UI_IKON.dis)}
        </a>`).join('');

    infoWindow.setContent(`
        <article class="iw" style="--c:${tur.color}">
            <div class="iw-tur"><i></i>${escapeHtml(tur.label)}</div>
            <h3>${escapeHtml(haber.baslik)}</h3>
            <div class="iw-meta">
                <span>${svg(UI_IKON.takvim)}${tarih}</span>
                <span>${svg(UI_IKON.konum)}${escapeHtml(konumMetni(haber))}</span>
            </div>
            ${ozet ? `<p class="iw-ozet">${escapeHtml(ozet)}</p>` : ''}
            <div class="iw-kaynaklar">
                ${kaynaklar.length > 1 ? `<p>${kaynaklar.length} gazetede çıktı</p>` : ''}
                ${linkler}
            </div>
        </article>`);
    infoWindow.open({ map, anchor: marker, shouldFocus: false });
}

function markerlariTemizle() {
    markers.forEach(m => m.setMap(null));
    markers = [];
}

function markeriVurgula(anahtar) {
    markers.forEach(m => {
        const aktif = m.haberKey === anahtar;
        m.setIcon(markerIkonu(m.haberData.haber_turu, aktif));
        m.setZIndex(aktif ? 1000 : null);
    });
}

// ==================== FİLTRELER ====================
// Tüm filtrelemeler AJAX ile sayfa yenilenmeden yapılır:
// filtre değişir → filtreUygula() → API → marker'lar + liste + sayılar güncellenir.

function filtreParametreleriOlustur() {
    const params = {};
    const tum = document.querySelectorAll('#haber-turu-filtre input[type="checkbox"]');
    const secili = [...tum].filter(cb => cb.checked).map(cb => cb.value);
    // Hiçbiri seçili değilse API'ye var olmayan bir tür gönder → boş sonuç
    if (secili.length === 0) params.haber_turu = '_yok_';
    else if (secili.length < tum.length) params.haber_turu = secili.join(',');

    const ilce = document.getElementById('ilce-filtre').value;
    if (ilce) params.ilce = ilce;
    const bas = document.getElementById('baslangic-tarihi').value;
    const bit = document.getElementById('bitis-tarihi').value;
    if (bas) params.baslangic_tarihi = bas;
    if (bit) params.bitis_tarihi = bit;
    return params;
}

function filtreUygula() {
    if (infoWindow) infoWindow.close();
    aktifHaberAnahtari = null;
    haberleriGetir();
    istatistikleriGetir();
}

function filtreleriTemizle() {
    document.querySelectorAll('#haber-turu-filtre input[type="checkbox"]').forEach(cb => { cb.checked = true; });
    document.getElementById('ilce-filtre').value = '';
    document.getElementById('arama').value = '';
    tarihKisayolu(0, false);
    filtreUygula();
}

function yerelTarih(d) {
    const p = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

// Hızlı tarih: 1 = bugün, 3/7 = son n gün, 0 = tümü
function tarihKisayolu(gun, uygula = true) {
    const bas = document.getElementById('baslangic-tarihi');
    const bit = document.getElementById('bitis-tarihi');
    if (gun === 0) {
        bas.value = ''; bit.value = '';
    } else {
        const d = new Date();
        d.setDate(d.getDate() - (gun - 1));
        bas.value = yerelTarih(d);
        bit.value = '';
    }
    segmentiIsaretle(gun);
    if (uygula) filtreUygula();
}

function tarihElleDegisti() {
    segmentiIsaretle(null);
    filtreUygula();
}

function segmentiIsaretle(gun) {
    document.querySelectorAll('.segmented button').forEach(b => {
        b.setAttribute('aria-pressed', String(Number(b.dataset.gun) === gun));
    });
}

// Başlık araması istemci tarafında: ağ isteği yok, anında sonuç
function aramaYap() {
    const q = document.getElementById('arama').value.trim().toLocaleLowerCase('tr');
    gorunenHaberler = q
        ? haberler.filter(h => (h.baslik || '').toLocaleLowerCase('tr').includes(q))
        : haberler;

    const konumlu = gorunenHaberler.filter(konumluMu).length;
    document.getElementById('stat-toplam').textContent = gorunenHaberler.length;
    document.getElementById('stat-konumlu').textContent = konumlu;

    haberListesiniGuncelle(gorunenHaberler);
    haritayiGuncelle();
}

// ==================== TÜR DAĞILIMI (chip sayıları + barlar) ====================

function turDagilimiOlustur(dagilim) {
    const max = Math.max(...Object.values(dagilim), 1);
    document.querySelectorAll('[data-tur-sayi]').forEach(el => {
        const sayi = dagilim[el.dataset.turSayi] || 0;
        el.textContent = sayi;
        el.closest('.chip').setAttribute('title', `${sayi} haber`);
    });
    document.querySelectorAll('[data-tur-bar]').forEach(el => {
        el.style.width = `${((dagilim[el.dataset.turBar] || 0) / max) * 100}%`;
    });
}

// ==================== SANAL LİSTE (VIRTUAL SCROLL) ====================
// Binlerce haberi DOM'a basmak yerine sadece görünür kartlar çizilir.

const KART_YUKSEKLIGI = 88; // px — .haber-card yüksekliği (84) + 4 boşluk
let _scrollHandler = null;

function haberKartiHtml(haber, index) {
    const tur = turBilgisi(haber.haber_turu);
    const tarih = haber.tarih ? tarihFormatla(haber.tarih, true) : '';
    const kaynak = haber.kaynak_adi || (haber.kaynaklar && haber.kaynaklar[0] ? haber.kaynaklar[0].kaynak_adi : '');
    const kaynakSayisi = haber.kaynaklar ? haber.kaynaklar.length : 1;
    const anahtar = haberKonumAnahtari(haber, index);
    const ilce = haber.konum_bilgisi && haber.konum_bilgisi.ilce;

    return `<button type="button" role="listitem" class="haber-card" style="--c:${tur.color};top:${index * KART_YUKSEKLIGI}px"
                ${konumluMu(haber) ? '' : 'data-konumsuz'}
                aria-current="${anahtar === aktifHaberAnahtari}"
                onclick="habereTikla(${index})">
        <span class="haber-card-title">${escapeHtml(haber.baslik)}</span>
        <span class="haber-card-meta">
            <span class="tur">${escapeHtml(tur.label)}</span>
            ${ilce ? `<span>${escapeHtml(ilce)}</span>` : ''}
            ${tarih ? `<span>${tarih}</span>` : ''}
            ${kaynakSayisi > 1
                ? `<span class="multi">${svg(UI_IKON.yayin)}${kaynakSayisi} gazete</span>`
                : (kaynak ? `<span>${escapeHtml(kaynak)}</span>` : '')}
        </span>
    </button>`;
}

function listeDurumu(durum) {
    const c = document.getElementById('haber-listesi');
    c.style.height = '';
    if (durum === 'hata') {
        c.innerHTML = `<div class="list-state"><strong>Haberler alınamadı</strong>Sunucu ya da MongoDB yanıt vermiyor. İkisinin de çalıştığını kontrol edip tekrar dene.
            <button type="button" class="btn btn-ghost" onclick="filtreUygula()">Tekrar dene</button></div>`;
        return;
    }
    const arama = document.getElementById('arama').value.trim();
    const filtreli = Object.keys(filtreParametreleriOlustur()).length > 0;
    c.innerHTML = arama
        ? `<div class="list-state"><strong>Başlığında "${escapeHtml(arama)}" geçen haber yok</strong>Başka bir kelime dene ya da aramayı temizle.
            <button type="button" class="btn btn-ghost" onclick="document.getElementById('arama').value='';aramaYap()">Aramayı temizle</button></div>`
        : filtreli
        ? `<div class="list-state"><strong>Bu filtrelerle haber yok</strong>Tarih aralığını genişlet ya da başka türleri de seç.
            <button type="button" class="btn btn-ghost" onclick="filtreleriTemizle()">Filtreleri sıfırla</button></div>`
        : `<div class="list-state"><strong>Henüz haber yok</strong>Yerel gazetelerden son 3 günün haberlerini çekmek için güncelle.
            <button type="button" class="btn btn-primary" onclick="scrapingBaslat()">Haberleri güncelle</button></div>`;
}

function haberListesiniGuncelle(liste) {
    const container = document.getElementById('haber-listesi');
    const scrollParent = document.getElementById('list-scroll');

    if (_scrollHandler) {
        scrollParent.removeEventListener('scroll', _scrollHandler);
        _scrollHandler = null;
    }
    if (liste.length === 0) { listeDurumu('bos'); return; }

    container.style.height = (liste.length * KART_YUKSEKLIGI) + 'px';
    scrollParent.scrollTop = 0;

    function render() {
        const top = scrollParent.scrollTop;
        const yuk = scrollParent.clientHeight || 600;
        const bas = Math.max(0, Math.floor((top - yuk) / KART_YUKSEKLIGI));
        const bit = Math.min(liste.length - 1, Math.ceil((top + yuk * 2) / KART_YUKSEKLIGI));
        let html = '';
        for (let i = bas; i <= bit; i++) html += haberKartiHtml(liste[i], i);
        container.innerHTML = html;
    }
    render();
    _scrollHandler = render;
    scrollParent.addEventListener('scroll', _scrollHandler, { passive: true });
}

function aktifKartiIsaretle(anahtar, kaydir = false) {
    aktifHaberAnahtari = anahtar;
    if (map) markeriVurgula(anahtar);
    const idx = gorunenHaberler.findIndex((h, i) => haberKonumAnahtari(h, i) === anahtar);
    if (kaydir && idx >= 0) {
        const sp = document.getElementById('list-scroll');
        const y = idx * KART_YUKSEKLIGI;
        if (y < sp.scrollTop || y > sp.scrollTop + sp.clientHeight - KART_YUKSEKLIGI) {
            sp.scrollTo({ top: Math.max(0, y - KART_YUKSEKLIGI), behavior: 'smooth' });
        }
    }
    if (_scrollHandler) _scrollHandler();
}

function habereTikla(index) {
    const haber = gorunenHaberler[index];
    if (!haber) return;
    if (!konumluMu(haber)) { bildirimGoster('Bu haberde konum bulunamadı, haritada gösterilemiyor.', 'uyari'); return; }
    if (!map) { bildirimGoster('Harita yüklenmediği için konum gösterilemiyor.', 'uyari'); return; }

    const anahtar = haberKonumAnahtari(haber, index);
    const marker = markers.find(m => m.haberKey === anahtar);
    map.panTo(marker ? marker.getPosition() : haber.koordinatlar);
    if (map.getZoom() < 14) map.setZoom(14);
    if (marker) infoWindowAc(marker, haber);
    aktifKartiIsaretle(anahtar);

    // Telefonda paneli kapat ki harita görünsün
    if (window.matchMedia('(max-width: 820px)').matches) paneliAcKapa(false);
}

// ==================== MOBİL PANEL ====================

function paneliAcKapa(zorla) {
    const panel = document.getElementById('panel');
    const acik = typeof zorla === 'boolean' ? zorla : panel.dataset.open !== 'true';
    panel.dataset.open = String(acik);
    document.getElementById('panel-handle').setAttribute('aria-expanded', String(acik));
}
document.querySelector('.brand').addEventListener('click', () => {
    if (window.matchMedia('(max-width: 820px)').matches) paneliAcKapa();
});

// ==================== YARDIMCILAR ====================

function bildirimGoster(mesaj, tip = 'basarili') {
    const kutu = document.getElementById('toasts');
    const t = document.createElement('div');
    t.className = `toast ${tip}`;
    t.textContent = mesaj;
    kutu.appendChild(t);
    while (kutu.children.length > 3) kutu.firstElementChild.remove();
    setTimeout(() => {
        t.classList.add('cikis');
        t.addEventListener('animationend', () => t.remove(), { once: true });
    }, 5000);
}

function tarihFormatla(tarihStr, kisa = false) {
    const tarih = new Date(tarihStr);
    if (isNaN(tarih.getTime())) return tarihStr;
    return tarih.toLocaleDateString('tr-TR', kisa
        ? { day: 'numeric', month: 'short' }
        : { day: 'numeric', month: 'long', year: 'numeric' });
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ==================== HABER TABLOSU (dialog) ====================

async function haberDetayPaneliAc() {
    const modal = document.getElementById('haber-detay-modal');
    const tbody = document.getElementById('haber-tablo-body');
    tbody.innerHTML = '<tr><td colspan="6" class="tablo-durum">Yükleniyor…</td></tr>';
    modal.showModal();

    try {
        const params = filtreParametreleriOlustur();
        params.sadece_konumlu = 'false';
        params.limit = 500;
        params._ts = Date.now();
        const data = await (await fetch(`/api/haberler?${new URLSearchParams(params)}`, { cache: 'no-store' })).json();

        const liste = data.basarili ? data.haberler : [];
        document.getElementById('modal-haber-sayisi').textContent =
            `${liste.length} haber, konumu bulunamayanlar dahil`;
        tbody.innerHTML = liste.length
            ? liste.map(haberTabloSatiri).join('')
            : '<tr><td colspan="6" class="tablo-durum">Bu filtrelerle haber yok.</td></tr>';
    } catch (error) {
        console.error('Haber tablosu hatası:', error);
        tbody.innerHTML = '<tr><td colspan="6" class="tablo-durum">Haberler alınamadı. Sunucunun çalıştığını kontrol et.</td></tr>';
    }
}

function haberTabloSatiri(haber) {
    const tur = turBilgisi(haber.haber_turu);
    const tarih = haber.tarih ? tarihFormatla(haber.tarih) : '–';
    const ilce = haber.konum_bilgisi && haber.konum_bilgisi.ilce ? haber.konum_bilgisi.ilce : '–';

    let cokluKaynak = '';
    if (haber.kaynaklar && haber.kaynaklar.length > 1) {
        cokluKaynak = `<div class="tablo-coklu-kaynak">ayrıca ${haber.kaynaklar.slice(1).map(k =>
            `<a href="${escapeHtml(k.link || '#')}" target="_blank" rel="noopener">${escapeHtml(k.kaynak_adi)}</a>`).join(', ')}</div>`;
    }

    return `<tr style="--c:${tur.color}">
        <td><span class="tablo-tur"><i></i>${escapeHtml(tur.label)}</span></td>
        <td class="tablo-baslik">${escapeHtml(haber.baslik)}</td>
        <td class="tablo-kaynak">${escapeHtml(haber.kaynak_adi || '–')}${cokluKaynak}</td>
        <td class="tablo-ilce">${escapeHtml(ilce)}</td>
        <td class="tablo-tarih">${tarih}</td>
        <td><a href="${escapeHtml(haber.haber_linki || '#')}" target="_blank" rel="noopener" class="tablo-link">Haberi aç${svg(UI_IKON.dis)}</a></td>
    </tr>`;
}

function haberDetayPaneliKapat() {
    document.getElementById('haber-detay-modal').close();
}

// Dialog dışına (backdrop'a) tıklayınca kapat. Esc'yi <dialog> zaten yönetir.
function modalDisindaTikla(event) {
    if (event.target === event.currentTarget) haberDetayPaneliKapat();
}
