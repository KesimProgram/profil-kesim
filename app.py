import streamlit as st
import pandas as pd
import numpy as np
from scipy.optimize import milp, LinearConstraint, Bounds
import json
import os

# --- KAYIT SİSTEMİ ALTYAPISI ---
KAYIT_DOSYASI = "kayitlar.json"

def kayitlari_yukle():
    if os.path.exists(KAYIT_DOSYASI):
        with open(KAYIT_DOSYASI, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def kayit_ekle(isim, data):
    kayitlar = kayitlari_yukle()
    kayitlar[isim] = data
    with open(KAYIT_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(kayitlar, f, ensure_ascii=False, indent=4)

def kayit_sil(isim):
    kayitlar = kayitlari_yukle()
    if isim in kayitlar:
        del kayitlar[isim]
        with open(KAYIT_DOSYASI, "w", encoding="utf-8") as f:
            json.dump(kayitlar, f, ensure_ascii=False, indent=4)

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Profil Kesim Optimizasyonu", layout="wide")
st.title("✂️ Profil Kesim Optimizasyonu")

# Tablonun SADECE ilk açılışta veya Yükle denildiğinde değişmesi için ayar
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame({"Boy (cm)": [0.0], "Adet": [0]})

# --- YAN MENÜ (AYARLAR VE YÜKLEME) ---
with st.sidebar:
    st.header("⚙️ Ayarlar")
    L_input = st.number_input("Profil Uzunluğu (cm)", value=600.0, step=1.0)
    testere = st.number_input("Testere Payı (cm)", value=0.5, step=0.1)
    
    st.divider()
    st.subheader("Fire Kuralı (Opsiyonel)")
    kural_aktif = st.checkbox("5 cm - 30 cm Kuralını Uygula", value=True)
    if kural_aktif:
        min_fire = st.number_input("Çöp Fire Üst Sınırı (cm)", value=5.0)
        max_fire = st.number_input("Kullanılabilir Fire Alt Sınırı (cm)", value=30.0)
    else:
        min_fire, max_fire = 0.0, 0.0

    st.divider()
    
    st.header("📂 Kayıtlı İşler")
    mevcut_kayitlar = kayitlari_yukle()
    if mevcut_kayitlar:
        secilen_kayit = st.selectbox("Kayıtlı Bir Liste Seç:", ["Seçiniz..."] + list(mevcut_kayitlar.keys()))
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📂 Yükle", use_container_width=True) and secilen_kayit != "Seçiniz...":
                # Listeyi yüklediğimiz an tabloyu yeniliyoruz
                st.session_state.df = pd.DataFrame(mevcut_kayitlar[secilen_kayit])
                st.rerun()
        with col2:
            if st.button("🗑️ Sil", use_container_width=True) and secilen_kayit != "Seçiniz...":
                kayit_sil(secilen_kayit)
                st.success(f"{secilen_kayit} silindi!")
                st.rerun()
    else:
        st.info("Henüz kayıtlı listen yok.")

# --- ANA EKRAN (SİPARİŞ TABLOSU) ---
st.subheader("📋 Sipariş Listesi")
st.info("Tabloya yeni satır eklemek için en alt satıra tıklayıp ölçü girebilirsin.")

# Tablo çizimi: Artık her tuşa bastığında kendi kendini sıfırlayıp silmeyecek!
df_giris = st.data_editor(st.session_state.df, num_rows="dynamic", use_container_width=True)

# --- KAYDETME BÖLÜMÜ (Tablonun Altına Taşındı) ---
st.write("---")
col_isim, col_kaydet = st.columns([3, 1])
with col_isim:
    kayit_ismi = st.text_input("Bu listeyi kaydetmek istersen bir isim yaz (Örn: Siyah Kulplar)")
with col_kaydet:
    st.write("") # Hizalama boşluğu
    st.write("")
    if st.button("💾 Kaydet", use_container_width=True):
        if kayit_ismi:
            df_gecerli = df_giris[(df_giris["Boy (cm)"] > 0) & (df_giris["Adet"] > 0)]
            kayit_ekle(kayit_ismi, df_gecerli.to_dict('records'))
            st.success("Liste kaydedildi! Sol menüden ulaşabilirsin.")
        else:
            st.warning("Lütfen kaydetmek için bir isim yaz.")
st.write("---")

# --- HESAPLAMA MOTORU ---
if st.button("🚀 Optimizasyonu Başlat", type="primary"):
    df_temiz = df_giris[(df_giris["Boy (cm)"] > 0) & (df_giris["Adet"] > 0)].copy()
    
    if df_temiz.empty:
        st.warning("Lütfen tabloya en az bir geçerli ölçü ve adet girin.")
    else:
        with st.spinner("Motor tam güçte çalışıyor, reçete hazırlanıyor (Maks. 60 saniye)..."):
            
            uzunluklar = df_temiz["Boy (cm)"].tolist()
            gercek_uzunluklar = [boy + testere for boy in uzunluklar]
            adetler = df_temiz["Adet"].tolist()
            L = L_input
            
            Gecerli_Desenler = []
            
            def desen_uret(index, mevcut_desen, mevcut_uzunluk):
                if index == len(gercek_uzunluklar):
                    fire = L - mevcut_uzunluk
                    if fire >= 0:
                        if kural_aktif:
                            if fire <= (min_fire + 0.05) or fire >= (max_fire - 0.05):
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
                st.error("Girdiğiniz kurallara ve ölçülere uygun hiçbir kesim ihtimali bulunamadı. Fire kurallarını esnetmeyi deneyin.")
            else:
                A_eq = np.array(Gecerli_Desenler).T
                b_eq = np.array(adetler)
                c = np.ones(len(Gecerli_Desenler))
                
                constraints_tam = LinearConstraint(A_eq, b_eq, b_eq)
                integrality = np.ones_like(c)
                bounds = Bounds(0, np.inf)
                
                # TIKANMAYI ÖNLEME: 60 Saniye Süre Sınırı
                res = milp(c=c, constraints=constraints_tam, integrality=integrality, bounds=bounds, options={'time_limit': 60})
                
                cozum_gecerli = False
                
                if res.success or (hasattr(res, 'x') and res.x is not None):
                    cozum_gecerli = True
                    cozum = np.round(res.x).astype(int)
                else:
                    # B planı
                    constraints_esnek = LinearConstraint(A_eq, b_eq, np.inf)
                    res_esnek = milp(c=c, constraints=constraints_esnek, integrality=integrality, bounds=bounds)
                    if res_esnek.success:
                        cozum_gecerli = True
                        cozum = np.round(res_esnek.x).astype(int)
                
                if cozum_gecerli:
                    # ATÖLYE SİMÜLASYONU
                    kalan_ihtiyac = {uzunluklar[i]: adetler[i] for i in range(len(uzunluklar))}
                    kesim_listesi = []
                    
                    for i, miktar in enumerate(cozum):
                        if miktar > 0:
                            desen = Gecerli_Desenler[i]
                            for _ in range(miktar):
                                profil_kesim = {}
                                kullanilan_boy = 0
                                for j, parca_adeti in enumerate(desen):
                                    boy = uzunluklar[j]
                                    gercek_boy = gercek_uzunluklar[j]
                                    kesilecek = min(parca_adeti, kalan_ihtiyac[boy])
                                    if kesilecek > 0:
                                        profil_kesim[boy] = kesilecek
                                        kullanilan_boy += kesilecek * gercek_boy
                                        kalan_ihtiyac[boy] -= kesilecek
                                
                                if profil_kesim:
                                    fire = round(L - kullanilan_boy, 1)
                                    kesim_listesi.append({'kesimler': tuple(profil_kesim.items()), 'fire': fire})
                    
                    toplam_profil = len(kesim_listesi)
                    st.success(f"✅ Optimizasyon Başarılı! Toplam Kullanılacak Profil: {toplam_profil} Adet")
                    
                    st.subheader("Atölye Kesim Reçetesi")
                    
                    profil_no = 1
                    grup_dict = {}
                    for p in kesim_listesi:
                        key = (p['kesimler'], p['fire'])
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
                            durum = "⚠️ Ara Fire (Siparişi tamamlamak için mecburidir)"
                            st.warning(f"- {str_baslik}: 👉 {detay_metni} *(Kalan Fire: {fire} cm - {durum})*")
                else:
                    st.error("Matematiksel olarak tam bir çözüm bulunamadı. Lütfen fire aralığını genişletin veya sipariş adetlerini kontrol edin.")
