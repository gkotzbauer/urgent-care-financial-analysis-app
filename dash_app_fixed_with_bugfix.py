import base64
import io
import pandas as pd
import dash
from dash import dcc, html, dash_table, Input, Output, State
import plotly.express as px
import numpy as np
import dash_bootstrap_components as dbc
from sklearn.linear_model import LinearRegression

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
application = app.server

app.layout = html.Div([
    html.H2("Weekly Financial Performance Dashboard"),
    dcc.Upload(
        id='upload-data',
        children=html.Button('Upload Excel File'),
        multiple=False
    ),
    html.Br(),
    html.Div(id='file-name-display', style={'marginBottom': 20}),
    dbc.Row([
        dbc.Col(dcc.Dropdown(id='week-filter', placeholder="Filter by Week"), width=6),
        dbc.Col(dcc.Dropdown(id='segment-filter', placeholder="Filter by Performance Segment"), width=6)
    ]),
    html.Br(),
    dcc.Graph(id='segment-count-chart'),
    dcc.Graph(id='missed-revenue-chart'),
    dcc.Graph(id='low-payment-reason-chart'),
    html.Hr(),
    html.H4("Performance Table"),
    dash_table.DataTable(
        id='performance-table',
        page_size=20,
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left', 'padding': '5px'},
        style_header={'fontWeight': 'bold'}
    )
])

def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    raw_df = pd.read_excel(io.BytesIO(decoded), engine='openpyxl')
    raw_df.columns = raw_df.columns.str.strip()
    raw_df = raw_df.dropna(subset=['Week'])

    numeric_columns = [
        "Average Payment", "Avg. Chart E/M Weight", "Charge Amount", "Collection %",
        "Total Payments", "Visit Count", "Visits With Lab Count"
    ]
    raw_df[numeric_columns] = raw_df[numeric_columns].apply(pd.to_numeric, errors='coerce')
    raw_df['Collection %'] = raw_df['Collection %'].abs()

    # Pivot financial class % into columns
    payment_pct = raw_df.pivot_table(
        index="Week",
        columns="Primary Financial Class",
        values="% of Total Payments",
        aggfunc='first'
    ).fillna(0)
    payment_pct.columns = [f"{col} % of Total Payments" for col in payment_pct.columns]

    # Aggregate other metrics by week
    weekly_df = raw_df.groupby("Week").agg({
        "Average Payment": "mean",
        "Avg. Chart E/M Weight": "mean",
        "Charge Amount": "sum",
        "Collection %": "mean",
        "Total Payments": "sum",
        "Visit Count": "sum",
        "Visits With Lab Count": "sum"
    }).reset_index()

    df = pd.merge(weekly_df, payment_pct, left_on="Week", right_index=True, how="left").fillna(0)

    # Regression analysis
    features = [
        "Average Payment", "Avg. Chart E/M Weight", "Charge Amount", "Collection %",
        "Visit Count", "Visits With Lab Count"
    ]
    X = df[features]
    y = df["Total Payments"]

    model = LinearRegression()
    model.fit(X, y)
    df["Predicted Revenue"] = model.predict(X)
    df["Residual"] = df["Total Payments"] - df["Predicted Revenue"]
    df["Z-Score Residual"] = (df["Residual"] - df["Residual"].mean()) / df["Residual"].std()

    def segment(z):
        if z <= -1.75: return "Significantly Underperformed"
        elif z <= -0.75: return "Underperformed"
        elif z >= 1.75: return "Significantly Overperformed"
        elif z >= 0.75: return "Overperformed"
        else: return "Near Expected"

    df["Performance Segment"] = df["Z-Score Residual"].apply(segment)

    diagnostics = []
    for _, row in df.iterrows():
        reasons = []
        for col in features:
            if row["Performance Segment"] in ["Underperformed", "Significantly Underperformed"] and row[col] < df[col].mean():
                reasons.append(f"Low {col}")
            elif row["Performance Segment"] in ["Overperformed", "Significantly Overperformed"] and row[col] > df[col].mean():
                reasons.append(f"High {col}")
        diagnostics.append("; ".join(reasons))
    df["Performance Diagnostics"] = diagnostics

    for col in features:
        df[f"Low {col}"] = df["Performance Diagnostics"].str.contains(f"Low {col}").astype(int)
        df[f"High {col}"] = df["Performance Diagnostics"].str.contains(f"High {col}").astype(int)

    return df

@app.callback(
    Output('performance-table', 'data'),
    Output('performance-table', 'columns'),
    Output('segment-count-chart', 'figure'),
    Output('missed-revenue-chart', 'figure'),
    Output('low-payment-reason-chart', 'figure'),
    Output('week-filter', 'options'),
    Output('segment-filter', 'options'),
    Output('file-name-display', 'children'),
    Input('upload-data', 'contents'),
    State('upload-data', 'filename'),
    Input('week-filter', 'value'),
    Input('segment-filter', 'value')
)
def update_dashboard(contents, filename, week_val, segment_val):
    if not contents:
        return [], [], {}, {}, {}, [], [], ""

    df = parse_contents(contents, filename)

    filtered = df.copy()
    if week_val:
        filtered = filtered[filtered["Week"] == week_val]
    if segment_val:
        filtered = filtered[filtered["Performance Segment"] == segment_val]

    data = filtered.to_dict("records")
    columns = [{"name": col, "id": col} for col in filtered.columns]

    fig1 = px.histogram(df, x="Performance Segment", title="Number of Weeks by Segment")

    df["Missed Revenue"] = df["Predicted Revenue"] - df["Total Payments"]
    fig2 = px.bar(df, x="Week", y="Missed Revenue", title="Missed Revenue Opportunity by Week")

    fig3 = px.bar(
        df.groupby("Week")["Low Average Payment"].sum().reset_index(),
        x="Week", y="Low Average Payment",
        title="Low Average Payment Reason Count by Week"
    )

    weeks = [{"label": w, "value": w} for w in sorted(df["Week"].unique())]
    segments = [{"label": s, "value": s} for s in sorted(df["Performance Segment"].unique())]

    return data, columns, fig1, fig2, fig3, weeks, segments, f"File loaded: {filename}"

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
