
import streamlit as st
import pandas as pd
from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt

st.set_page_config(page_title="Urgent Care Revenue Dashboard", layout="wide")
st.title("📊 Urgent Care Weekly Revenue Diagnostic")
st.markdown("Upload weekly visit-level data to track revenue performance and contributing factors.")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    df.columns = df.columns.str.strip()
    df['ISO Week of Visit Service Date'] = df['ISO Week of Visit Service Date'].ffill()
    df['Primary Financial Class'] = df['Primary Financial Class'].ffill()

    numeric_cols = ['Average Payment', 'Avg. Chart E/M Weight', 'Lab Count',
                    'Payments + Expected', 'Visit Count']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    summary = df.groupby('ISO Week of Visit Service Date').agg({
        'Payments + Expected': 'sum',
        'Visit Count': 'sum',
        'Average Payment': 'mean',
        'Avg. Chart E/M Weight': 'mean',
        'Lab Count': 'sum'
    }).reset_index()

    summary['Avg Payment per Visit'] = summary['Payments + Expected'] / summary['Visit Count']
    summary['Labs per Visit'] = summary['Lab Count'] / summary['Visit Count']

    X = summary[['Visit Count', 'Avg Payment per Visit', 'Avg. Chart E/M Weight', 'Labs per Visit']]
    y = summary['Payments + Expected']
    model = LinearRegression().fit(X, y)
    summary['Predicted Revenue'] = model.predict(X)
    summary['Revenue Residual'] = summary['Payments + Expected'] - summary['Predicted Revenue']

    res_min = summary['Revenue Residual'].min()
    res_max = summary['Revenue Residual'].max()
    summary['Normalized Residual'] = (summary['Revenue Residual'] - res_min) / (res_max - res_min)

    def corrected_segment(row):
        if row['Payments + Expected'] == 0:
            return "No Revenue"
        elif row['Normalized Residual'] >= 0.75:
            return "Significantly Overperformed"
        elif row['Normalized Residual'] >= 0.5:
            return "Overperformed"
        elif row['Normalized Residual'] >= 0.25:
            return "Underperformed"
        else:
            return "Significantly Underperformed"

    summary['Performance Category'] = summary.apply(corrected_segment, axis=1)

    st.sidebar.header("🔍 Filter Options")
    selected_category = st.sidebar.multiselect("Performance Category", summary['Performance Category'].unique(), default=summary['Performance Category'].unique())
    selected_weeks = st.sidebar.multiselect("Week", summary['ISO Week of Visit Service Date'].unique(), default=summary['ISO Week of Visit Service Date'].unique())

    filtered_summary = summary[
        summary['Performance Category'].isin(selected_category) &
        summary['ISO Week of Visit Service Date'].isin(selected_weeks)
    ]

    st.subheader("📅 Weekly Revenue Performance")
    st.dataframe(filtered_summary.rename(columns={
        'ISO Week of Visit Service Date': 'Week',
        'Payments + Expected': 'Actual Revenue'
    })[['Week', 'Actual Revenue', 'Predicted Revenue', 'Revenue Residual', 'Normalized Residual', 'Performance Category']])

    st.subheader("📈 Residual Trend")
    fig1, ax1 = plt.subplots()
    ax1.plot(summary['ISO Week of Visit Service Date'], summary['Revenue Residual'], marker='o')
    ax1.axhline(0, color='gray', linestyle='--')
    ax1.set_title("Actual - Predicted Revenue by Week")
    ax1.set_ylabel("Residual ($)")
    ax1.set_xticks(range(len(summary)))
    ax1.set_xticklabels(summary['ISO Week of Visit Service Date'], rotation=45)
    st.pyplot(fig1)

    st.subheader("📊 Performance Category Distribution")
    fig2, ax2 = plt.subplots()
    summary['Performance Category'].value_counts().plot(kind='bar', ax=ax2, color='skyblue')
    ax2.set_ylabel("Number of Weeks")
    st.pyplot(fig2)

    st.download_button(
        label="📥 Download Filtered Results",
        data=filtered_summary.to_excel(index=False, engine='xlsxwriter'),
        file_name='filtered_weekly_performance.xlsx',
        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
