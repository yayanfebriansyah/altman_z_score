import streamlit as st
import yfinance as yf
import pandas as pd

# --- KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="Corporate Financial Health Dashboard",
    page_icon="stock_logo.png",
    layout="wide"
)

# --- FUNGSI CACHING ---
@st.cache_resource
def get_ticker_object(symbol):
    """Menggunakan cache_resource karena objek Ticker tidak bisa di-pickle"""
    if not symbol.endswith('.JK'):
        symbol += '.JK'
    ticker = yf.Ticker(symbol)
    return ticker

@st.cache_data(ttl=3600)
def get_company_info(symbol):
    """Mengambil info statis perusahaan"""
    ticker = get_ticker_object(symbol)
    return ticker.info

# --- ENGINE PERHITUNGAN ---

def calculate_altman(ticker):
    try:
        bs = ticker.balance_sheet
        is_stmt = ticker.financials
        if bs.empty or is_stmt.empty:
            return None, "Laporan keuangan tidak ditemukan."
        
        # Data terbaru (T0)
        l_bs = bs.iloc[:, 0]
        l_is = is_stmt.iloc[:, 0]
        
        total_assets = l_bs.get('Total Assets', 1)
        total_liab = l_bs.get('Total Liabilities Net Minority Interest', l_bs.get('Total Liabilities', 1))
        
        # Komponen X1 - X5
        x1 = (l_bs.get('Total Current Assets', 0) - l_bs.get('Total Current Liabilities', 0)) / total_assets
        x2 = l_bs.get('Retained Earnings', 0) / total_assets
        x3 = l_is.get('EBIT', l_is.get('Operating Income', 0)) / total_assets
        x4 = ticker.fast_info.get('market_cap', 0) / total_liab
        x5 = l_is.get('Total Revenue', 0) / total_assets
        
        z_score = (1.2 * x1) + (1.4 * x2) + (3.3 * x3) + (0.6 * x4) + (1.0 * x5)
        
        components = {
            'X1 (Liquidity)': round(x1, 4),
            'X2 (Profitability)': round(x2, 4),
            'X3 (Op. Efficiency)': round(x3, 4),
            'X4 (Solvency)': round(x4, 4),
            'X5 (Asset Turnover)': round(x5, 4)
        }
        return {'score': round(z_score, 2), 'components': components}, None
    except Exception as e:
        return None, str(e)

def calculate_piotroski(ticker, info):
    try:
        bs = ticker.balance_sheet
        is_stmt = ticker.financials
        cf = ticker.cashflow
        if bs.shape[1] < 2:
            return None, "Butuh minimal 2 tahun laporan keuangan."
        
        c_bs, p_bs = bs.iloc[:, 0], bs.iloc[:, 1]
        c_is, p_is = is_stmt.iloc[:, 0], is_stmt.iloc[:, 1]
        c_cf, p_cf = cf.iloc[:, 0], cf.iloc[:, 1]
        
        fmt_tr = lambda x: f"Rp {x / 1e12:.3f} T"
        rows = []
        
        # 1-4 Profitability
        roa_c = c_is.get('Net Income', 0) / c_bs.get('Total Assets', 1)
        roa_p = p_is.get('Net Income', 0) / p_bs.get('Total Assets', 1)
        cfo_c = c_cf.get('Operating Cash Flow', 0)
        
        rows.append(['Profitability', 'Net Income > 0', fmt_tr(c_is.get('Net Income', 0)), '-', 1 if roa_c > 0 else 0])
        rows.append(['Profitability', 'CFO > 0', fmt_tr(cfo_c), '-', 1 if cfo_c > 0 else 0])
        rows.append(['Profitability', 'Kenaikan ROA', f"{roa_c:.2%}", f"{roa_p:.2%}", 1 if roa_c > roa_p else 0])
        rows.append(['Profitability', 'Accruals (CFO > NI)', f"{cfo_c/c_bs.get('Total Assets', 1):.2%}", f"{roa_c:.2%}", 1 if (cfo_c/c_bs.get('Total Assets', 1)) > roa_c else 0])
        
        # 5-7 Leverage/Liquidity
        lev_c = c_bs.get('Long Term Debt', 0) / c_bs.get('Total Assets', 1)
        lev_p = p_bs.get('Long Term Debt', 0) / p_bs.get('Total Assets', 1)
        rows.append(['Leverage', 'Penurunan Debt', f"{lev_c:.2%}", f"{lev_p:.2%}", 1 if lev_c < lev_p else 0])
        
        cr_c = c_bs.get('Total Current Assets', 1) / c_bs.get('Total Current Liabilities', 1)
        cr_p = p_bs.get('Total Current Assets', 1) / p_bs.get('Total Current Liabilities', 1)
        rows.append(['Liquidity', 'Kenaikan Current Ratio', f"{cr_c:.2f}x", f"{cr_p:.2f}x", 1 if cr_c > cr_p else 0])
        rows.append(['Equity', 'Tidak Ada Dilusi Saham', f"{info.get('sharesOutstanding', 0)/1e9:.2f}B", '-', 1])
        
        # 8-9 Efficiency
        gm_c = c_is.get('Gross Profit', 0) / c_is.get('Total Revenue', 1)
        gm_p = p_is.get('Gross Profit', 0) / p_is.get('Total Revenue', 1)
        rows.append(['Efficiency', 'Kenaikan Gross Margin', f"{gm_c:.2%}", f"{gm_p:.2%}", 1 if gm_c > gm_p else 0])
        
        at_c = c_is.get('Total Revenue', 0) / c_bs.get('Total Assets', 1)
        at_p = p_is.get('Total Revenue', 0) / p_bs.get('Total Assets', 1)
        rows.append(['Efficiency', 'Kenaikan Asset Turnover', f"{at_c:.2f}x", f"{at_p:.2f}x", 1 if at_c > at_p else 0])
        
        df_logic = pd.DataFrame(rows, columns=['Kategori', 'Kriteria', 'Tahun Ini', 'Tahun Lalu', 'Skor'])
        return {'score': df_logic['Skor'].sum(), 'table': df_logic}, None
    except Exception as e:
        return None, str(e)

# --- ANTARMUKA UTAMA (UI) ---
col1, col2 = st.columns([1, 3])

with col1:
    st.image("logo-bursa-efek-indonesia-final.webp", width=100)

with col2:
    st.title("Financial Health & Fundamental Dashboard")

# st.title("🛡️ Financial Health & Fundamental Dashboard")
st.write("Alat analisis komprehensif untuk emiten Bursa Efek Indonesia (IDX).")

ticker_input = st.text_input("Ketik Kode Saham (contoh: ASII, ICBP, KLBF):", placeholder="Misal: UNVR").upper()

if ticker_input:
    with st.spinner(f"Menganalisis {ticker_input}..."):
        try:
            ticker = get_ticker_object(ticker_input)
            info = get_company_info(ticker_input)
            
            if not info.get('longName'):
                st.error("Ticker tidak ditemukan atau data Yahoo Finance sedang bermasalah.")
            else:
                # --- SECTION 1: PROFIL PERUSAHAAN ---
                # -----------------------
                col_head1, col_head2, col_head3, col_head4, col_head5, col_head6 = st.columns([3, 1, 1, 1, 1, 1])
                with col_head1:
                    st.header(info.get('longName'))
                    st.caption(f"**Sektor:** {info.get('sector')} | **Industri:** {info.get('industry')}")
                    if info.get('website'):
                        st.link_button("🌐 Kunjungi Situs Resmi", info.get('website'))
                
                with col_head2:
                    # m_cap = ticker.fast_info.get('market_cap', 0)
                    m_cap = ticker.info.get('marketCap', 0)
                    st.metric("Market Cap", f"Rp {m_cap/1e12:.2f} T")
                
                # ------------------------
                with col_head3:
                    per = ticker.info.get('trailingPE', 'N/A')
                    st.metric("Price to Earning Ratio", f"{per:.2f}")

                with col_head4:
                    pbv = ticker.info.get('priceToBook', 'N/A')
                    st.metric("Price to Book Ratio", f"{pbv:.2f}")
                
                with col_head5:
                    crprice = ticker.info.get('currentPrice', 'N/A')
                    st.metric("Current Price", f"Rp{crprice:,.0f}")
                
                with col_head6:
                    netmargin = ticker.info.get('profitMargins', 'N/A')
                    st.metric("Net Profit Margin", f"{netmargin*100:.2f}%")
                
                
                with st.expander("📖 Deskripsi Bisnis"):
                    st.write(info.get('longBusinessSummary'))
                
                st.divider()
                
                # --- SECTION 2: TABS SKOR ---
                tab_z, tab_f = st.tabs(["🛡️ Altman Z-Score (Risiko Bangkrut)", "📈 Piotroski F-Score (Kekuatan Fundamental)"])
                
                with tab_z:
                    if info.get('sector') == 'Financial Services':
                        st.warning("⚠️ **Catatan Sektor:** Altman Z-Score standar tidak dirancang untuk sektor Perbankan/Finansial.")
                    else:
                        z_data, z_err = calculate_altman(ticker)
                        if z_err: st.error(f"Gagal menghitung Z-Score: {z_err}")
                        else:
                            z_val = z_data['score']
                            if z_val > 2.99: st.success(f"### Z-Score: {z_val} (Safe Zone)")
                            elif 1.81 <= z_val <= 2.99: st.warning(f"### Z-Score: {z_val} (Grey Zone)")
                            else: st.error(f"### Z-Score: {z_val} (Distress Zone)")
                            
                            st.write("**Breakdown Rasio:**")
                            st.table(pd.DataFrame.from_dict(z_data['components'], orient='index', columns=['Nilai']))
                
                with tab_f:
                    f_data, f_err = calculate_piotroski(ticker, info)
                    if f_err: st.error(f_err)
                    else:
                        f_val = f_data['score']
                        if f_val >= 7: st.success(f"### F-Score: {f_val} / 9 (Strong Fundamental)")
                        elif 4 <= f_val <= 6: st.warning(f"### F-Score: {f_val} / 9 (Average)")
                        else: st.error(f"### F-Score: {f_val} / 9 (Weak Fundamental)")
                        
                        st.write("**Tabel Validasi Logika:**")
                        def style_score(v):
                            return 'background-color: #90ee90' if v == 1 else 'background-color: #ffcccb'
                        
                        styled_df = f_data['table'].style.applymap(style_score, subset=['Skor'])
                        st.table(styled_df)
                        st.caption("Hijau = Memenuhi Kriteria | Merah = Tidak Memenuhi Kriteria")

        except Exception as general_err:
            st.error(f"Terjadi kesalahan teknis: {general_err}")

# --- SIDEBAR INFO ---
st.sidebar.title("Panduan Analisis")
st.sidebar.info("""
**Altman Z-Score**
Memprediksi solvabilitas perusahaan.
- **> 2.99**: Sehat.
- **1.81 - 2.99**: Waspada.
- **< 1.81**: Risiko bangkrut tinggi.

**Piotroski F-Score**
Melihat tren kesehatan akuntansi.
- **8-9**: Excellent.
- **4-7**: Standar.
- **0-3**: Fundamental memburuk.
""")