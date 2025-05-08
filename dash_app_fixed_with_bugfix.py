import base64
import io
import os
import dash
from dash import dash_table
import pandas as pd
import numpy as np
from dash import dcc, html, Input, Output, State
import plotly.express as px
from sklearn.linear_model import LinearRegression

app = dash.Dash(__name__)
server = app.server

app.layout = html.Div([
    html.H2("Urgent Care Weekly Financial Diagnostic Dashboard"),
    dcc.Upload(
        id='upload-data',
        children=html.Button('Upload Excel File'),
        multiple=False
    ),
    html.Div(id='output-data-upload'),
    html.Hr(),
    dcc.Dropdown(id='week-filter', placeholder="Filter by Week"),
    dcc.Dropdown(id='category-filter', placeholder="Filter by Performance Category"),
    dcc.Dropdown(id='diagnostic-filter', placeholder="Filter by Performance Diagnostic"),
    html.Div(id='table-container'),
    html.Hr(),
    dcc.Graph(id='category-count-chart'),
    dcc.Graph(id='diagnostic-count-chart'),
    dcc.Graph(id='missed-revenue-chart')
])

def parse_data(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    df = pd.read_excel(io.BytesIO(decoded), engine='openpyxl')

    df = df.dropna(subset=['Week'])
    df['Payments + Expected'] = df['Payments + Expected'].replace('[\\$,]', '', regex=True).astype(float)
    df['Average Payment'] = df['Average Payment'].abs()
    df.fillna(0, inplace=True)

    weekly = df.groupby('Week').agg({
        'Payments + Expected': 'sum',
        'Visit Count': 'sum',
        'Lab Count': 'sum',
        'Average Payment': 'mean',
        'Avg. Chart E/M Weight': 'mean'
    }).reset_index()

    X = weekly[['Visit Count', 'Lab Count', 'Average Payment', 'Avg. Chart E/M Weight']]
    y = weekly['Payments + Expected']
    model = LinearRegression().fit(X, y)
    weekly['Predicted Revenue'] = model.predict(X)
    weekly['Residual'] = weekly['Payments + Expected'] - weekly['Predicted Revenue']
    weekly['Z-Score Residual'] = (weekly['Residual'] - weekly['Residual'].mean()) / weekly['Residual'].std()
    weekly['Missed Revenue'] = weekly['Predicted Revenue'] - weekly['Payments + Expected']

    def assign_category(z):
        if z <= -2: return "Significantly Underperformed"
        elif z <= -1: return "Underperformed"
        elif z >= 2: return "Significantly Overperformed"
        elif z >= 1: return "Overperformed"
        else: return "Near Expected"

    weekly['Performance Category'] = weekly['Z-Score Residual'].apply(assign_category)

    diagnostics = []
    for _, row in weekly.iterrows():
        reasons = []
        if row['Performance Category'] in ["Underperformed", "Significantly Underperformed"]:
            if row['Visit Count'] < weekly['Visit Count'].mean(): reasons.append("Visit Count is below average")
            if row['Lab Count'] < weekly['Lab Count'].mean(): reasons.append("Lab Count is below average")
            if row['Average Payment'] < weekly['Average Payment'].mean(): reasons.append("Average Payment is below average")
            if row['Avg. Chart E/M Weight'] < weekly['Avg. Chart E/M Weight'].mean(): reasons.append("E/M Weight is below average")
        elif row['Performance Category'] in ["Overperformed", "Significantly Overperformed"]:
            if row['Visit Count'] > weekly['Visit Count'].mean(): reasons.append("Visit Count is above average")
            if row['Lab Count'] > weekly['Lab Count'].mean(): reasons.append("Lab Count is above average")
            if row['Average Payment'] > weekly['Average Payment'].mean(): reasons.append("Average Payment is above average")
            if row['Avg. Chart E/M Weight'] > weekly['Avg. Chart E/M Weight'].mean(): reasons.append("E/M Weight is above average")
        if not reasons:
            reasons = ["Performance aligned with historical norms"]
        diagnostics.append("; ".join(reasons))

    weekly['Performance Diagnostic'] = diagnostics

    return weekly

@app.callback(
    Output('table-container', 'children'),
    Output('category-count-chart', 'figure'),
    Output('diagnostic-count-chart', 'figure'),
    Output('missed-revenue-chart', 'figure'),
    Input('upload-data', 'contents'),
    State('upload-data', 'filename'),
    Input('week-filter', 'value'),
    Input('category-filter', 'value'),
    Input('diagnostic-filter', 'value')
)
def update_output(contents, filename, week_val, cat_val, diag_val):
    if contents is None:
        return None, {}, {}, {}

    df = parse_data(contents, filename)

    if week_val:
        df = df[df['Week'] == week_val]
    if cat_val:
        df = df[df['Performance Category'] == cat_val]
    if diag_val:
        df = df[df['Performance Diagnostic'].str.contains(diag_val, na=False)]

    df_display = df.copy()
    df_display['Payments + Expected'] = df_display['Payments + Expected'].apply(lambda x: f"${int(x):,}")
    df_display['Predicted Revenue'] = df_display['Predicted Revenue'].apply(lambda x: f"${int(x):,}")
    df_display['Residual'] = df_display['Residual'].apply(lambda x: round(x, 2))
    df_display['Missed Revenue'] = df_display['Missed Revenue'].apply(lambda x: f"${int(x):,}")

    table = dash_table.DataTable(
        data=df_display.to_dict('records'),
        columns=[{"name": i, "id": i} for i in df_display.columns],
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left'}
    )

    cat_fig = px.histogram(df, x='Performance Category', title='Number of Weeks by Category')
    diag_fig = px.histogram(df, x='Performance Diagnostic', title='Count of Diagnostic Reasons')
    missed_rev_fig = px.bar(df, x='Week', y='Missed Revenue', title='Missed Revenue Opportunity by Week')

    return table, cat_fig, diag_fig, missed_rev_fig

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port)
