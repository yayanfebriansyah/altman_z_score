import streamlit as st
import yfinance as yf
import pandas as pd

# Fungsi untuk menghitung Altman Z-Score
@st.cache_data(ttl=3600) # Cache data selama 1 jam agar tidak kena rate limit
def calculate_altman_z_score(ticker_symbol):
    try:
        # Menghubungkan ke ticker (asumsi bursa Indonesia jika input hanya 4 huruf)
        symbol = ticker_symbol.upper()
        if not symbol.endswith('.JK'):
            symbol += '.JK'
            
        ticker = yf.Ticker(symbol)
        
        # Fetch data
        balance_sheet = ticker.balance_sheet
        income_stmt = ticker.financials
        info = ticker.info
        fast_info = ticker.fast_info

        if balance_sheet.empty or income_stmt.empty:
            return None, "Data laporan keuangan tidak tersedia."

        # Identifikasi Sektor (Altman Z-Score tidak cocok untuk Bank)
        sector = info.get('sector', '')
        if sector == 'Financial Services':
            return "FINANCIAL", "Altman Z-Score standar tidak cocok untuk sektor Perbankan/Finansial."

        # Ambil kolom terbaru
        latest_bs = balance_sheet.iloc[:, 0]
        latest_is = income_stmt.iloc[:, 0]

        # Komponen perhitungan
        total_assets = latest_bs.get('Total Assets', 0)
        total_liabilities = latest_bs.get('Total Liabilities Net Minority Interest', 
                                          latest_bs.get('Total Liabilities', 0))
        
        # X1: Working Capital / Total Assets
        current_assets = latest_bs.get('Total Current Assets', latest_bs.get('Current Assets', 0))
        current_liabilities = latest_bs.get('Total Current Liabilities', latest_bs.get('Current Liabilities', 0))
        x1 = (current_assets - current_liabilities) / total_assets

        # X2: Retained Earnings / Total Assets
        x2 = latest_bs.get('Retained Earnings', 0) / total_assets

        # X3: EBIT / Total Assets
        ebit = latest_is.get('EBIT', latest_is.get('Operating Income', 0))
        x3 = ebit / total_assets

        # X4: Market Cap / Total Liabilities
        # Menggunakan fast_info sesuai saran sebelumnya agar lebih cepat
        market_cap = fast_info.get('market_cap', info.get('marketCap', 0))
        x4 = market_cap / total_liabilities

        # X5: Sales / Total Assets
        sales = latest_is.get('Total Revenue', 0)
        x5 = sales / total_assets

        # Hitung Z-Score
        z_score = (1.2 * x1) + (1.4 * x2) + (3.3 * x3) + (0.6 * x4) + (1.0 * x5)
        
        # Metadata untuk ditampilkan
        details = {
            'Name': info.get('longName', symbol),
            'Sector': sector,
            'Z-Score': round(z_score, 2),
            'Components': {
                'X1 (Liquidity)': round(x1, 4),
                'X2 (Profitability)': round(x2, 4),
                'X3 (Operating Efficiency)': round(x3, 4),
                'X4 (Solvency)': round(x4, 4),
                'X5 (Asset Turnover)': round(x5, 4)
            }
        }
        return details, None
        
    except Exception as e:
        return None, str(e)

# --- Konfigurasi UI Streamlit ---
st.set_page_config(page_title="Altman Z-Score Checker", layout="centered")

st.title("🛡️ Stock Health Checker")
st.markdown("Hitung skor kesehatan finansial emiten menggunakan metode **Altman Z-Score**.")

# Input User
ticker_input = st.text_input("Masukkan Kode Saham (contoh: ASII, TLKM, ICBP):", "").strip()

if ticker_input:
    with st.spinner(f'Menganalisis data {ticker_input}...'):
        data, error = calculate_altman_z_score(ticker_input)
        
        if error:
            if data == "FINANCIAL":
                st.warning(f"⚠️ {error}")
                st.info("Untuk sektor finansial, disarankan menggunakan Bank Z-Score atau rasio LDR/NPL.")
            else:
                st.error(f"Terjadi kesalahan: {error}")
        else:
            # Display Hasil Utama
            st.header(f"{data['Name']}")
            st.subheader(f"Sektor: {data['Sector']}")
            
            z = data['Z-Score']
            
            # Klasifikasi Berdasarkan Skor
            if z > 2.99:
                st.success(f"**Z-Score: {z} (Safe Zone)**")
                st.write("Perusahaan berada dalam kondisi keuangan yang sangat sehat.")
            elif 1.81 <= z <= 2.99:
                st.warning(f"**Z-Score: {z} (Grey Zone)**")
                st.write("Perusahaan menunjukkan gejala kesulitan keuangan, perlu waspada.")
            else:
                st.error(f"**Z-Score: {z} (Distress Zone)**")
                st.write("Perusahaan berisiko tinggi mengalami kebangkrutan.")

            # Menampilkan Breakdown Komponen
            st.write("---")
            st.subheader("Rincian Komponen Rasio")
            df_components = pd.DataFrame.from_dict(data['Components'], orient='index', columns=['Nilai'])
            st.table(df_components)

# Footer
st.sidebar.markdown("### Tentang Altman Z-Score")
st.sidebar.info("""
Formula ini memprediksi kemungkinan kebangkrutan dalam 2 tahun.
- **Z > 2.99**: Aman
- **1.81 - 2.99**: Abu-abu
- **Z < 1.81**: Bahaya
""")