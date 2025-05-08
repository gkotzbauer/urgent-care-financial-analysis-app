
import streamlit as st
import pandas as pd
from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt

st.set_page_config(page_title="Urgent Care Revenue Dashboard", layout="wide")
st.title("📊 Weekly Revenue Performance Dashboard")
st.markdown("Upload your weekly Excel data to evaluate revenue performance and see what drove changes.")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    df.columns = df.columns.str.strip()
    df['ISO Week of Visit Service Date'] = df['ISO Week of Visit Service Date'].ffill()
    df['Primary Financial Class'] = df['Primary Financial Class'].ffill()
    df['Average Payment'] = df['Average Payment'].abs()

    numeric_cols = ['Average Payment', 'Avg. Chart E/M Weight', 'Lab Count', 'Payments + Expected', 'Visit Count']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df = df[df['ISO Week of Visit Service Date'] != 'W19']
    weekly = df.groupby('ISO Week of Visit Service Date').agg({
        'Payments + Expected': 'sum',
        'Visit Count': 'sum',
        'Average Payment': 'mean',
        'Avg. Chart E/M Weight': 'mean',
        'Lab Count': 'sum'
    }).reset_index()
    weekly['Labs per Visit'] = weekly['Lab Count'] / weekly['Visit Count']
    weekly = weekly.dropna()

    X = weekly[['Visit Count', 'Average Payment', 'Avg. Chart E/M Weight', 'Labs per Visit']]
    y = weekly['Payments + Expected']
    model = LinearRegression().fit(X, y)
    weekly['Predicted Revenue'] = model.predict(X)
    weekly['Residual'] = weekly['Payments + Expected'] - weekly['Predicted Revenue']
    res_mean = weekly['Residual'].mean()
    res_std = weekly['Residual'].std()
    weekly['Z-Score Residual'] = (weekly['Residual'] - res_mean) / res_std

    means = X.mean()
    coefs = model.coef_

    cats, diags = [], []
    for _, row in weekly.iterrows():
        reasons = []
        for i, var in enumerate(X.columns):
            val, avg = row[var], means[var]
            delta = val - avg
            effect = delta * coefs[i]
            direction = "⬆ Above avg" if delta > 0 else "⬇ Below avg"
            if abs(delta) > 0.05 * avg:
                if row['Z-Score Residual'] >= 1.0 and effect > 0:
                    reasons.append(f"{var}: {direction}")
                elif row['Z-Score Residual'] <= -1.0 and effect < 0:
                    reasons.append(f"{var}: {direction}")
                elif row['Z-Score Residual'] > 0.25 and effect > 0:
                    reasons.append(f"{var}: {direction}")
                elif row['Z-Score Residual'] < -0.25 and effect < 0:
                    reasons.append(f"{var}: {direction}")

        if not reasons:
            diag = "Performance aligned with historical norms."
            cat = "Near Expected"
        else:
            diag = " | ".join(reasons[:2])
            if row['Z-Score Residual'] >= 1.0:
                cat = "Significantly Overperformed"
            elif row['Z-Score Residual'] >= 0.25:
                cat = "Overperformed"
            elif row['Z-Score Residual'] <= -1.0:
                cat = "Significantly Underperformed"
            elif row['Z-Score Residual'] <= -0.25:
                cat = "Underperformed"
            else:
                cat = "Near Expected"

        cats.append(cat)
        diags.append(diag)

    weekly['Performance Category'] = cats
    weekly['Performance Diagnostic'] = diags

    st.subheader("📅 Weekly Performance Table")
    st.dataframe(weekly[['ISO Week of Visit Service Date', 'Payments + Expected', 'Predicted Revenue',
                         'Residual', 'Z-Score Residual', 'Performance Category', 'Performance Diagnostic']])

    st.subheader("📈 Residual Trend")
    fig1, ax1 = plt.subplots()
    ax1.plot(weekly['ISO Week of Visit Service Date'], weekly['Residual'], marker='o')
    ax1.axhline(0, linestyle='--', color='gray')
    ax1.set_xticks(range(len(weekly)))
    ax1.set_xticklabels(weekly['ISO Week of Visit Service Date'], rotation=45)
    ax1.set_ylabel("Residual ($)")
    ax1.set_title("Actual - Predicted Revenue per Week")
    st.pyplot(fig1)

    st.subheader("📊 Category Distribution")
    st.bar_chart(weekly['Performance Category'].value_counts())

    st.download_button(
        label="📥 Download Results as Excel",
        data=weekly.to_excel(index=False, engine='xlsxwriter'),
        file_name="weekly_revenue_analysis.xlsx",
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
