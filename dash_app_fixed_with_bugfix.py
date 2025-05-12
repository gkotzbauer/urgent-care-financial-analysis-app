import base64
import io
import pandas as pd
import dash
from dash import dcc, html, dash_table, Input, Output, State
import plotly.express as px
import numpy as np
import dash_bootstrap_components as dbc
from sklearn.linear_model import LinearRegression

# Initialize the app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
application = app.server  # For deployment via Gunicorn

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
    df = pd.read_excel(io.BytesIO(decoded), engine='openpyxl')
    df.columns = df.columns.str.strip()
    df = df.dropna(subset=['Week'])

    numeric_columns = [
        "Average Payment", "Avg. Chart E/M Weight", "Charge Amount", "Collection %",
        "Total Payments", "Visit_Count", "Visits With Lab Count"
    ]
    df[numeric_columns] = df[numeric_columns].apply(pd.to_numeric, errors='coerce')
    df['Collection %'] = df['Collection %'].abs()

    df_model = df.copy()
    X = df_model[[
        "Average Payment", "Avg. Chart E/M Weight", "Charge Amount", "Collection %",
        "Visit_Count", "Visits With Lab Count"
    ]]
    y = df_model["Total Payments"]

    model = LinearRegression()
    model.fit(X, y)
    df_model["Predicted Revenue"] = model.predict(X)
    df_model["Residual"] = df_model["Total Payments"] - df_model["Predicted Revenue"]
    df_model["Z-Score Residual"] = (df_model["Residual"] - df_model["Residual"].mean()) / df_model["Residual"].std()

    def assign_segment(z):
        if z <= -1.75: return "Significantly Underperformed"
        elif z <= -0.75: return "Underperformed"
        elif z >= 1.75: return "Significantly Overperformed"
        elif z >= 0.75: return "Overperformed"
        else: return "Near Expected"

    df_model["Performance Segment"] = df_model["Z-Score Residual"].apply(assign_segment)

    diagnostics = []
    for _, row in df_model.iterrows():
        reasons = []
        for var in ["Average Payment", "Avg. Chart E/M Weight", "Charge Amount", "Collection %",
                    "Visit_Count", "Visits With Lab Count"]:
            if row["Performance Segment"] in ["Underperformed", "Significantly Underperformed"]:
                if row[var] < df_model[var].mean():
                    reasons.append(f"Low {var}")
            elif row["Performance Segment"] in ["Overperformed", "Significantly Overperformed"]:
                if row[var] > df_model[var].mean():
                    reasons.append(f"High {var}")
        diagnostics.append("; ".join(reasons))
    df_model["Performance Diagnostics"] = diagnostics

    for var in ["Average Payment", "Avg. Chart E/M Weight", "Charge Amount", "Collection %",
                "Visit_Count", "Visits With Lab Count"]:
        df_model[f"Low {var}"] = (df_model["Performance Diagnostics"].str.contains(f"Low {var}")).astype(int)
        df_model[f"High {var}"] = (df_model["Performance Diagnostics"].str.contains(f"High {var}")).astype(int)

    return df_model

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
def update_dashboard(contents, filename, selected_week, selected_segment):
    if not contents:
        return [], [], {}, {}, {}, [], [], ""

    df = parse_contents(contents, filename)
    filtered = df.copy()
    if selected_week:
        filtered = filtered[filtered["Week"] == selected_week]
    if selected_segment:
        filtered = filtered[filtered["Performance Segment"] == selected_segment]

    data = filtered.to_dict("records")
    columns = [{"name": i, "id": i} for i in filtered.columns]

    fig1 = px.histogram(df, x="Performance Segment", title="Number of Weeks by Segment")

    df["Missed Revenue"] = df["Predicted Revenue"] - df["Total Payments"]
    fig2 = px.bar(df, x="Week", y="Missed Revenue", title="Missed Revenue Opportunity by Week")

    fig3 = px.bar(
        df.groupby("Week")["Low Average Payment"].sum().reset_index(),
        x="Week", y="Low Average Payment",
        title="Low Average Payment Reason Count by Week"
    )

    week_options = [{"label": w, "value": w} for w in sorted(df["Week"].unique())]
    segment_options = [{"label": s, "value": s} for s in sorted(df["Performance Segment"].unique())]

    return data, columns, fig1, fig2, fig3, week_options, segment_options, f"File loaded: {filename}"

# Start the app
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
