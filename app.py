import streamlit as st
import pandas as pd
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds
import json
import gspread
from google.oauth2.service_account import Credentials
from fpdf import FPDF

# --- BULUT (GOOGLE SHEETS) ULTRA-ROBUST VERİTABANI MOTORU ---
def google_sheets_baglan():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        
        sheet_id = st.secrets["spreadsheet_id"]
        return client.open_by_key(sheet_id).sheet1
    except Exception as e:
        st.error(f"⚠️ Bulut veritabanına bağlanılamadı: {e}")
        return None

def kayitlari_yukle():
    worksheet = google_sheets_baglan()
    if worksheet is None:
        return {}
    
    try:
        satirlar = worksheet.get_all_values()
        
        if not satirlar or len(satirlar) == 0:
            worksheet.append_row(["Isim", "List", "Settings", "Result"])
            return {}
            
        basliklar = [str(b).strip().lower() for b in satirlar[0]]
        
        if "isim" not in basliklar and "list" not in basliklar:
            worksheet.insert_row(["Isim", "List", "Settings", "Result"], 1)
            satirlar = worksheet.get_all_values()
            basliklar = [str(b).strip().lower() for b in satirlar[0]]
        
        idx_isim = basliklar.index("isim") if "isim" in basliklar else 0
        idx_list = basliklar.index("list") if "list" in basliklar else 1
        idx_settings = basliklar.index("settings") if "settings" in basliklar else 2
        idx_result = basliklar.index("result") if "result" in basliklar else 3
        
        kayitlar = {}
        for satir in satirlar[1:]:
            while len(satir) < 4:
                satir.append("")
                
            isim = satir[idx_isim].strip()
            if not isim:
                continue
                
            try:
                l_veri = satir[idx_list].strip()
                s_veri = satir[idx_settings].strip()
                res_veri = satir[idx_result].strip()
                
                kayitlar[isim] = {
                    "list": json.loads(l_veri) if l_veri else [],
                    "settings": json.loads(s_veri) if s_veri else {},
                    "result": json.loads(res_veri) if res_veri else None
                }
            except:
                continue
                
        return kayitlar
    except Exception as e:
        st.sidebar.error(f"🔍 Bulut Okuma Hatası: {e}")
        return {}

def kayit_ekle(isim, data):
    worksheet = google_sheets_baglan()
    if worksheet is None:
        return
    
    try:
        satirlar = worksheet.get_all_values()
        
        has_headers = False
        if satirlar and len(satirlar) > 0:
            first_row = [str(b).strip().lower() for b in satirlar[0]]
            if "isim" in first_row or "list" in first_row:
                has_headers = True
                
        if not has_headers:
            worksheet.insert_row(["Isim", "List", "Settings", "Result"], 1)
            satirlar = worksheet.get_all_values()
            
        basliklar = [str(b).strip().lower() for b in satirlar[0]]
        idx_isim = basliklar.index("isim") if "isim" in basliklar else 0
        
        for idx, satir in enumerate(satirlar[1:]):
            if len(satir) > idx_isim and satir[idx_isim].strip() == str(isim):
                worksheet.delete_rows(idx + 2)
                break
                
        worksheet.append_row([
            str(isim),
            json.dumps(data["list"], ensure_ascii=False),
            json.dumps(data["settings"], ensure_ascii=False),
            json.dumps(data["result"], ensure_ascii=False) if data["result"] else ""
        ])
    except Exception as e:
        st.error(f"💾 Buluta kaydedilirken hata oluştu: {e}")

def kayit_sil(isim):
    worksheet = google_sheets_baglan()
    if worksheet is None:
        return
    try:
        satirlar = worksheet.get_all_values()
        if not satirlar:
            return
        basliklar = [str(b).strip().lower() for b in satirlar[0]]
        idx_isim = basliklar.index("isim") if "isim" in basliklar else 0
        
        for idx, satir in enumerate(satirlar[1:]):
            if len(satir) > idx_isim and satir[idx_isim].strip() == str(isim):
                worksheet.delete_rows(idx + 2)
                break
    except Exception as e:
        st.sidebar.error(f"❌ Silme Hatası: {e}")

# --- AKILLI PDF DOSYASI ÜRETİM MOTORU ---
def pdf_recete_olustur(toplam_profil, kesim_listesi, kategori):
    pdf = FPDF()
    pdf.add_page()
    
    def tr(text):
        rep = {"ç":"c", "ğ":"g", "ı":"i", "ö":"o", "ş":"s", "ü":"u", "Ç":"C", "Ğ":"G", "İ":"I", "Ö":"O", "Ş":"S", "Ü":"U"}
        for k, v in rep.items():
            text = text.replace(k, v)
        return text

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, txt=tr(f"ATOLYE KESIM RECETESI ({kategori.upper()} MODU)"), ln=1, align="C")
    pdf.line(10, 22, 200, 22)
    pdf.ln(5)
    
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 8, txt=tr(f"Toplam Kullanilacak Profil Adedi: {toplam_profil} Adet"), ln=1)
    
    # 📊 PDF ÖZET ALANI: Hangi ölçüden toplam kaç adet kesileceğini hesapla ve PDF'e yaz
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, txt=tr("Toplam Kesilecek Parca Ozet Listesi:"), ln=1)
    pdf.set_font("Helvetica", "", 11)
    
    toplam_parcalar = {}
    for p in kesim_listesi:
        for boy, adet in p['kesimler']:
            toplam_parcalar[boy] = toplam_parcalar.get(boy, 0) + adet
            
    ozet_satirlari = []
    for boy in sorted(toplam_parcalar.keys()):
        ozet_satirlari.append(f"{toplam_parcalar[boy]} Adet {boy} cm")
        
    pdf.cell(0, 8, txt=tr(" | ".join(ozet_satirlari)), ln=1)
    pdf.line(10, pdf.get_y() + 2, 200, pdf.get_y() + 2)
    pdf.ln(5)
    
    # Detaylar Başlığı
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 10, txt=tr("Profil Kesim Planlama Detaylari:"), ln=1)
    pdf.set_font("Helvetica", "", 11)
    
    profil_no = 1
    grup_dict = {}
    for p in kesim_listesi:
        normalized_kesimler = tuple((item[0], item[1]) for item in p['kesimler'])
        key = (normalized_kesimler, p['fire'])
        if key not in grup_dict:
            grup_dict[key] = []
        grup_dict[key].append(profil_no)
        profil_no += 1
        
    for key, nolar in grup_dict.items():
        kesimler, fire = key
        if len(nolar) == 1:
            str_baslik = f"Profil {nolar[0]} (1 Adet)"
        elif len(nolar) == 2:
            str_baslik = f"Profil {nolar[0]} ve {nolar[1]} (Toplam 2 Adet)"
        else:
            if nolar == list(range(nolar[0], nolar[-1] + 1)):
                str_baslik = f"Profil {nolar[0]} - {nolar[-1]} arasi (Toplam {len(nolar)} Adet)"
            else:
                str_nolar = [str(n) for n in nolar]
                str_baslik = f"Profil {', '.join(str_nolar[:-1])} ve {str_nolar[-1]} (Toplam {len(nolar)} Adet)"
        
        kesilecek_parcalar = []
        for boy, adet in kesimler:
            kesilecek_parcalar.append(f"{adet} adet {boy} cm")
        detay_metni = " | ".join(kesilecek_parcalar)
        
        satir = f"- {str_baslik}:  {detay_metni}  (Kalan Fire: {fire} cm)"
        pdf.cell(0, 8, txt=tr(satir), ln=1)
        
    return bytes(pdf.output())

# --- HESAPLAMA MOTORU ---
def optimizasyon_yap(df_temiz, L, testere, kural_aktif, min_fire, max_fire):
    uzunluklar = df_temiz["Boy (cm)"].tolist()
    gercek_uzunluklar = [boy + testere for boy in uzunluklar]
    indent = df_temiz["Adet"].tolist()
    
    Gecerli_Desenler = []
    
    def desen_uret(index, mevcut_desen, mevcut_uzunluk):
        if index == len(gercek_uzunluklar):
            fire = L - mevcut_uzunluk
            if fire >= -0.01:
                if kural_aktif:
                    if fire <= (min_fire + 0.45) or fire >= (max_fire - 0.45):
                        Gecerli_Desenler.append(tuple(mevcut_desen))
                else:
                    Gecerli_Desenler.append(tuple(mevcut_desen))
            return
        
        max_adet = int((L - mevcut_uzunluk) // gercek_uzunluklar[index])
        for i in range(max_adet + 1):
            mevcut_desen.append(i)
            desen_uret(index + 1, mevcut_desen, mevcut_uzunluk + i * gercek_uzunluklar[index])
            mevcut_desen.pop()

    desen_uret(0, [], 0.0)
    
    if not Gecerli_Desenler:
        return None, "Girdiğiniz kurallara uygun kesim ihtimali bulunamadı. Lütfen fire kurallarını esnetmeyi deneyin."
    
    A_eq = np.array(Gecerli_Desenler).T
    b_eq = np.array(indent)
    
    c = []
    for desen in Gecerli_Desenler:
        mevcut_uzunluk = sum(desen[k] * gercek_uzunluklar[k] for k in range(len(gercek_uzunluklar)))
        fire = L - mevcut_uzunluk
        
        if kural_aktif:
            if min_fire < fire < max_fire:
                ceza = 0.001 
            else:
                ceza = 0.0   
        else:
            if 5.0 < fire < (L / 2):
                ceza = 0.001 
            else:
                ceza = 0.0
        c.append(1.0 + ceza)
        
    c = np.array(c)
    
    constraints_tam = LinearConstraint(A_eq, b_eq, b_eq)
    res = milp(c=c, constraints=constraints_tam, integrality=np.ones_like(c), bounds=Bounds(0, np.inf), options={'time_limit': 60})
    
    cozum_gecerli = False
    if res.success or (hasattr(res, 'x') and res.x is not None):
        cozum_gecerli = True
        cozum = np.round(res.x).astype(int)
    else:
        res_esnek = milp(c=c, constraints=LinearConstraint(A_eq, b_eq, np.inf), integrality=np.ones_like(c), bounds=Bounds(0, np.inf))
        if res_esnek.success:
            cozum_gecerli = True
            cozum = np.round(res_esnek.x).astype(int)
    
    if cozum_gecerli:
        kalan_ihtiyac = {uzunluklar[i]: indent[i] for i in range(len(uzunluklar))}
        kesim_listesi = []
        
        for i, miktar in enumerate(cozum):
            if miktar > 0:
                for _ in range(miktar):
                    profil_kesim = {}
                    kullanilan_boy = 0
                    for j, parca_adeti in enumerate(Gecerli_Desenler[i]):
                        boy = uzunluklar[j]
                        kesilecek = min(parca_adeti, kalan_ihtiyac[boy])
                        if kesilecek > 0:
                            profil_kesim[boy] = kesilecek
                            kullanilan_boy += kesilecek * gercek_uzunluklar[j]
                            kalan_ihtiyac[boy] -= kesilecek
                    
                    if profil_kesim:
                        fire = round(L - kullanilan_boy, 1)
                        kesim_listesi.append({'kesimler': list(profil_kesim.items()), 'fire': fire})
        
        return {"toplam_profil": len(kesim_listesi), "kesim_listesi": kesim_listesi}, None
    else:
        return None, "Matematiksel bir çözüm bulunamadı. Lütfen sipariş adetlerini kontrol edin."

# --- ARACI VE BULUT HAFIZA YAPILANDIRMASI ---
if 'mevcut_kayitlar' not in st.session_state:
    st.session_state.mevcut_kayitlar = None
if 'bulut_yenile' not in st.session_state:
    st.session_state.bulut_yenile = True

if st.session_state.bulut_yenile or st.session_state.mevcut_kayitlar is None:
    st.session_state.mevcut_kayitlar = kayitlari_yukle()
    st.session_state.bulut_yenile = False

mevcut_kayitlar = st.session_state.mevcut_kayitlar

varsayilan_ayarlar = [
    ("set_kat", "Profil"), ("set_L", 600.0), ("set_testere", 0.5), 
    ("set_kural", True), ("set_min", 5.0), ("set_max", 30.0)
]
for key, default in varsayilan_ayarlar:
    if key not in st.session_state:
        st.session_state[key] = default

if 'df_profil' not in st.session_state: st.session_state.df_profil = pd.DataFrame({"Boy (cm)": [0.0], "Adet": [0]})
if 'aktif_hesap_sonucu' not in st.session_state: st.session_state.aktif_hesap_sonucu = None
if 'tablo_anahtari' not in st.session_state: st.session_state.tablo_anahtari = 0
if 'hesaplanan_df' not in st.session_state: st.session_state.hesaplanan_df = None
if 'hesaplanan_ayarlar' not in st.session_state: st.session_state.hesaplanan_ayarlar = None
if 'saved_name_val' not in st.session_state: st.session_state.saved_name_val = ""

def kategori_tetikleyici():
    st.session_state.set_kat = st.session_state.kategori_widget
    if st.session_state.set_kat == "Kulplar":
        st.session_state.set_L = 500.0
        st.session_state.set_min = 5.0
        st.session_state.set_max = 70.0
    else:
        st.session_state.set_L = 600.0
        st.session_state.set_min = 5.0
        st.session_state.set_max = 30.0

# --- REÇETE GÖSTERİM FONKSİYONU ---
def receteyi_ekrana_bas(toplam_profil, kesim_listesi, kural_aktif, min_fire, max_fire):
    st.success(f"✅ Hesaplama Tamam! Toplam Kullanılacak Profil: {toplam_profil} Adet")
    
    # 📊 EKRAN ÖZET ALANI: Reçetenin en tepesinde toplam parça dağılımını gösterir
    st.subheader("📊 Toplam Kesilecek Parça Özet Listesi")
    toplam_parcalar = {}
    for p in kesim_listesi:
        for boy, adet in p['kesimler']:
            toplam_parcalar[boy] = toplam_parcalar.get(boy, 0) + adet
            
    ozet_metinleri = []
    for boy in sorted(toplam_parcalar.keys()):
        ozet_metinleri.append(f"**{toplam_parcalar[boy]} Adet {boy} cm**")
    st.markdown(" | ".join(ozet_metinleri))
    st.write("---")
    
    st.subheader("Atölye Kesim Reçetesi")
    
    profil_no = 1
    grup_dict = {}
    for p in kesim_listesi:
        normalized_kesimler = tuple((item[0], item[1]) for item in p['kesimler'])
        key = (normalized_kesimler, p['fire'])
        if key not in grup_dict:
            grup_dict[key] = []
        grup_dict[key].append(profil_no)
        profil_no += 1
        
    for key, nolar in grup_dict.items():
        kesimler, fire = key
        if len(nolar) == 1:
            str_baslik = f"**Profil {nolar[0]}** (1 Adet)"
        elif len(nolar) == 2:
            str_baslik = f"**Profil {nolar[0]} ve {nolar[1]}** (Toplam 2 Adet)"
        else:
            if nolar == list(range(nolar[0], nolar[-1] + 1)):
                str_baslik = f"**Profil {nolar[0]} - {nolar[-1]} arası** (Toplam {len(nolar)} Adet)"
            else:
                str_nolar = [str(n) for n in nolar]
                str_baslik = f"**Profil {', '.join(str_nolar[:-1])} ve {str_nolar[-1]}** (Toplam {len(nolar)} Adet)"
        
        kesilecek_parcalar = []
        for boy, adet in kesimler:
            kesilecek_parcalar.append(f"{adet} adet {boy} cm")
        detay_metni = " | ".join(kesilecek_parcalar)
        
        if kural_aktif and fire >= max_fire:
            durum = "♻️ Sağlam Parça (Geri Kullanılabilir)"
            st.info(f"- {str_baslik}: 👉 {detay_metni} *(Kalan Fire: {fire} cm - {durum})*")
        elif kural_aktif and fire <= min_fire:
            durum = "🗑️ Çöp Fire"
            st.markdown(f"- {str_baslik}: 👉 {detay_metni} *(Kalan Fire: {fire} cm - {durum})*")
        else:
            durum = "⚠️ Ara Fire (Mecburi)"
            st.warning(f"- {str_baslik}: 👉 {detay_metni} *(Kalan Fire: {fire} cm - {durum})*")

# --- YAN MENÜ ---
with st.sidebar:
    st.header("⚙️ İş ve Tezgâh Ayarları")
    
    kategori_listesi = ["Profil", "Kulplar"]
    kat_idx = kategori_listesi.index(st.session_state.set_kat) if st.session_state.set_kat in kategori_listesi else 0
    st.selectbox("İş Kategorisi", kategori_listesi, index=kat_idx, key="kategori_widget", on_change=kategori_tetikleyici)
    
    L_input = st.number_input("Profil Standart Uzunluğu (cm)", value=float(st.session_state.set_L), step=1.0)
    testere = st.number_input("Testere Payı (cm)", value=float(st.session_state.set_testere), step=0.1)
    
    st.divider()
    st.subheader("Fire Kuralı Ayarları")
    kural_aktif = st.checkbox("Fire Sınır Kuralını Uygula", value=bool(st.session_state.set_kural))
    
    if kural_aktif:
        min_fire = st.number_input("Çöp Fire Üst Sınırı (cm)", value=float(st.session_state.set_min))
        max_fire = st.number_input("Kullanılabilir Fire Alt Sınırı (cm)", value=float(st.session_state.set_max))
    else:
        min_fire, max_fire = 0.0, 0.0

    st.session_state.set_L = L_input
    st.session_state.set_testere = testere
    st.session_state.set_kural = kural_aktif
    st.session_state.set_min = min_fire
    st.session_state.set_max = max_fire

    st.divider()
    st.header("☁️ Google Buluttan Yükle")
    
    if mevcut_kayitlar:
        secilen_kayit = st.selectbox("Kayıtlı Komple İş Seç:", ["Seçiniz..."] + list(mevcut_kayitlar.keys()))
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📂 Yükle", use_container_width=True) and secilen_kayit != "Seçiniz...":
                data = mevcut_kayitlar[secilen_kayit]
                st.session_state.df_profil = pd.DataFrame(data["list"])
                
                st.session_state.set_kat = data["settings"]["kategori"]
                st.session_state.set_L = float(data["settings"]["L"])
                st.session_state.set_testere = float(data["settings"]["testere"])
                st.session_state.set_kural = bool(data["settings"]["kural_aktif"])
                st.session_state.set_min = float(data["settings"]["min_fire"])
                st.session_state.set_max = float(data["settings"]["max_fire"])
                
                st.session_state.aktif_hesap_sonucu = data.get("result", None)
                st.session_state.hesaplanan_df = st.session_state.df_profil.copy()
                st.session_state.hesaplanan_ayarlar = data["settings"]
                st.session_state.saved_name_val = secilen_kayit
                
                st.session_state.tablo_anahtari += 1
                st.rerun() 
        with col2:
            if st.button("🗑️ Sil", use_container_width=True) and secilen_kayit != "Seçiniz...":
                kayit_sil(secilen_kayit)
                st.session_state.bulut_yenile = True
                st.success(f"{secilen_kayit} silindi!")
                st.rerun()
    else:
        st.info("Bulutta henüz kayıtlı iş bulunamadı.")

# --- ANA EKRAN ---
col_baslik, col_temizle = st.columns([3, 1])
with col_baslik:
    st.subheader(f"📋 Sipariş Listesi ({st.session_state.set_kat} Modu)")
    st.info("Tabloya yeni satır eklemek için en alt satıra tıklayıp ölçü girebilirsin.")
with col_temizle:
    st.write("") 
    if st.button("🔄 Yeni İşlem (Temizle)", use_container_width=True):
        st.session_state.df_profil = pd.DataFrame({"Boy (cm)": [0.0], "Adet": [0]})
        st.session_state.aktif_hesap_sonucu = None
        st.session_state.hesaplanan_df = None
        st.session_state.saved_name_val = ""
        st.session_state.tablo_anahtari += 1
        st.rerun()

df_giris = st.data_editor(st.session_state.df_profil, num_rows="dynamic", use_container_width=True, key=f"profil_tablosu_{st.session_state.tablo_anahtari}")

st.write("---")
col_hesap, col_bos = st.columns([1, 3])
with col_hesap:
    if st.button("🚀 Sadece Hesapla (Kaydetmeden)", type="primary", use_container_width=True):
        df_temiz = df_giris[(df_giris["Boy (cm)"] > 0) & (df_giris["Adet"] > 0)].copy()
        if df_temiz.empty:
            st.warning("Lütfen tabloya en az bir geçerli ölçü ve adet girin.")
        else:
            with st.spinner("Motor hesaplıyor..."):
                sonuc, hata = optimizasyon_yap(
                    df_temiz, st.session_state.set_L, st.session_state.set_testere, 
                    st.session_state.set_kural, st.session_state.set_min, st.session_state.set_max
                )
                if hata:
                    st.error(hata)
                    st.session_state.aktif_hesap_sonucu = None
                else:
                    st.session_state.aktif_hesap_sonucu = sonuc
                    st.session_state.hesaplanan_df = df_temiz.copy()
                    st.session_state.hesaplanan_ayarlar = {
                        "kategori": st.session_state.set_kat, "L": st.session_state.set_L,
                        "testere": st.session_state.set_testere, "kural_aktif": st.session_state.set_kural,
                        "min_fire": st.session_state.set_min, "max_fire": st.session_state.set_max
                    }

col_isim, col_kaydet = st.columns([3, 1])
with col_isim:
    kayit_ismi = st.text_input("Bu işi kaydetmek için isim ver (Doğrudan Google Buluta kilitler):", value=st.session_state.saved_name_val)
    st.session_state.saved_name_val = kayit_ismi
with col_kaydet:
    st.write(""); st.write("")
    if st.button("💾 Kaydet", use_container_width=True):
        if kayit_ismi:
            df_gecerli = df_giris[(df_giris["Boy (cm)"] > 0) & (df_giris["Adet"] > 0)].copy()
            if df_gecerli.empty:
                st.warning("Kaydedilecek geçerli bir ölçü tablosu yok.")
            else:
                guncel_ayarlar = {
                    "kategori": st.session_state.set_kat, "L": st.session_state.set_L,
                    "testere": st.session_state.set_testere, "kural_aktif": st.session_state.set_kural,
                    "min_fire": st.session_state.set_min, "max_fire": st.session_state.set_max
                }
                
                degisti_mi = False
                if st.session_state.hesaplanan_df is None or not df_gecerli.equals(st.session_state.hesaplanan_df):
                    degisti_mi = True
                if st.session_state.hesaplanan_ayarlar != guncel_ayarlar:
                    degisti_mi = True

                with st.spinner("Google Buluta gönderiliyor..."):
                    if degisti_mi or st.session_state.aktif_hesap_sonucu is None:
                        sonuc, hata = optimizasyon_yap(
                            df_gecerli, st.session_state.set_L, st.session_state.set_testere, 
                            st.session_state.set_kural, st.session_state.set_min, st.session_state.set_max
                        )
                        st.session_state.hesaplanan_df = df_gecerli.copy()
                        st.session_state.hesaplanan_ayarlar = guncel_ayarlar
                    else:
                        sonuc = st.session_state.aktif_hesap_sonucu
                        hata = None

                    if hata:
                        st.error(f"Hesaplama hatası nedeniyle kaydedilemedi: {hata}")
                    else:
                        st.session_state.aktif_hesap_sonucu = sonuc
                        paket_veri = {
                            "list": df_gecerli.to_dict('records'),
                            "settings": guncel_ayarlar,
                            "result": sonuc
                        }
                        kayit_ekle(kayit_ismi, paket_veri)
                        st.session_state.bulut_yenile = True
                        st.success("✅ Tebrikler! Veriler kalıcı olarak Google Drive bulutuna kilitlendi!")
                        st.rerun()
        else:
            st.warning("Lütfen kaydetmek için bir isim yaz.")
st.write("---")

if st.session_state.aktif_hesap_sonucu is not None:
    receteyi_ekrana_bas(
        st.session_state.aktif_hesap_sonucu["toplam_profil"],
        st.session_state.aktif_hesap_sonucu["kesim_listesi"],
        st.session_state.set_kural,
        st.session_state.set_min,
        st.session_state.set_max
    )
    
    st.write("")
    try:
        pdf_bytes = pdf_recete_olustur(
            st.session_state.aktif_hesap_sonucu["toplam_profil"],
            st.session_state.aktif_hesap_sonucu["kesim_listesi"],
            st.session_state.set_kat
        )
        st.download_button(
            label="🖨️ Kesim Reçetesini PDF Olarak İndir (Çıktı Al)",
            data=pdf_bytes,
            file_name=f"kesim_recetesi_{st.session_state.saved_name_val if st.session_state.saved_name_val else 'is'}.pdf",
            mime="application/pdf",
            type="secondary"
        )
    except Exception as pdf_error:
        st.error(f"PDF Hazirlanirken hata olustu: {pdf_error}")
