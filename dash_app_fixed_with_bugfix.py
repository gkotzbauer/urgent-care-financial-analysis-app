import base64
import io
import os
import dash
from dash import dcc, html, dash_table, Input, Output, State
import pandas as pd
import numpy as np
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

    html.Div([
        html.Label("Week Filter"),
        dcc.Dropdown(id='week-filter', placeholder="Select Week")
    ]),
    html.Div([
        html.Label("Performance Category Filter"),
        dcc.Dropdown(id='category-filter', placeholder="Select Performance Category")
    ]),
    html.Div([
        html.Label("Diagnostic Reason Filter"),
        dcc.Dropdown(id='diagnostic-filter', placeholder="Select Diagnostic Reason")
    ]),

    html.Hr(),
    html.H3("Actual vs Predicted Revenue Table"),
    html.Div(id='revenue-table'),

    html.Hr(),
    html.H3("Weekly Diagnostic Table"),
    html.Div(id='table-container'),

    html.Hr(),
    dcc.Graph(id='revenue-chart'),
    dcc.Graph(id='category-count-chart'),
    dcc.Graph(id='diagnostic-count-chart'),
    dcc.Graph(id='missed-revenue-chart')
])

def parse_data(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    df = pd.read_excel(io.BytesIO(decoded), engine='openpyxl')

    df = df.dropna(subset=['Week'])
    df['Payments + Expected'] = df['Payments + Expected'].replace('[\$,]', '', regex=True).astype(float)
    df['Average Payment'] = df['Average Payment'].abs()
    df.fillna(0, inplace=True)

    weekly = df.groupby('Week').agg({
        'Payments + Expected': 'sum',
        'Visit Count': 'sum',
        'Lab Count': 'sum',
        'Average Payment': 'mean',
        'Avg. Chart E/M Weight': 'mean'
    }).reset_index()

    # Regression model
    X = weekly[['Visit Count', 'Lab Count', 'Average Payment', 'Avg. Chart E/M Weight']]
    y = weekly['Payments + Expected']
    model = LinearRegression().fit(X, y)
    weekly['Predicted Revenue'] = model.predict(X)
    weekly['Residual'] = weekly['Payments + Expected'] - weekly['Predicted Revenue']
    weekly['Z-Score Residual'] = (weekly['Residual'] - weekly['Residual'].mean()) / weekly['Residual'].std()
    weekly['Missed Revenue'] = weekly['Predicted Revenue'] - weekly['Payments + Expected']

    def assign_category(z):
        if z <= -2:
            return "Significantly Underperformed"
        elif z <= -1:
            return "Underperformed"
        elif z >= 2:
            return "Significantly Overperformed"
        elif z >= 1:
            return "Overperformed"
        else:
            return "Near Expected"

    weekly['Performance Category'] = weekly['Z-Score Residual'].apply(assign_category)

    diagnostics = []
    total_diag = []

    for _, row in weekly.iterrows():
        reasons = []
        if row['Performance Category'] in ["Underperformed", "Significantly Underperformed"]:
            if row['Visit Count'] < weekly['Visit Count'].mean():
                reasons.append("Visit Count is below average")
            if row['Lab Count'] < weekly['Lab Count'].mean():
                reasons.append("Lab Count is below average")
            if row['Average Payment'] < weekly['Average Payment'].mean():
                reasons.append("Average Payment is below average")
            if row['Avg. Chart E/M Weight'] < weekly['Avg. Chart E/M Weight'].mean():
                reasons.append("E/M Weight is below average")
        elif row['Performance Category'] in ["Overperformed", "Significantly Overperformed"]:
            if row['Visit Count'] > weekly['Visit Count'].mean():
                reasons.append("Visit Count is above average")
            if row['Lab Count'] > weekly['Lab Count'].mean():
                reasons.append("Lab Count is above average")
            if row['Average Payment'] > weekly['Average Payment'].mean():
                reasons.append("Average Payment is above average")
            if row['Avg. Chart E/M Weight'] > weekly['Avg. Chart E/M Weight'].mean():
                reasons.append("E/M Weight is above average")
        if not reasons:
            reasons = ["Performance aligned with historical norms"]
        diagnostics.append("; ".join(reasons))
        total_diag.append(len(reasons))

    weekly['Performance Diagnostic'] = diagnostics
    weekly['# of Diagnostics'] = total_diag

    return weekly

@app.callback(
    Output('table-container', 'children'),
    Output('category-count-chart', 'figure'),
    Output('diagnostic-count-chart', 'figure'),
    Output('missed-revenue-chart', 'figure'),
    Output('revenue-chart', 'figure'),
    Output('revenue-table', 'children'),
    Output('week-filter', 'options'),
    Output('category-filter', 'options'),
    Output('diagnostic-filter', 'options'),
    Input('upload-data', 'contents'),
    State('upload-data', 'filename'),
    Input('week-filter', 'value'),
    Input('category-filter', 'value'),
    Input('diagnostic-filter', 'value')
)
def update_output(contents, filename, week_val, cat_val, diag_val):
    if contents is None:
        return None, {}, {}, {}, {}, None, [], [], []

    df = parse_data(contents, filename)

    week_options = [{'label': w, 'value': w} for w in sorted(df['Week'].unique())]
    category_options = [{'label': c, 'value': c} for c in df['Performance Category'].unique()]
    diagnostic_options = [{'label': d, 'value': d} for d in pd.Series(
        sum(df['Performance Diagnostic'].str.split('; '), [])).dropna().unique()]

    filtered = df.copy()
    if week_val:
        filtered = filtered[filtered['Week'] == week_val]
    if cat_val:
        filtered = filtered[filtered['Performance Category'] == cat_val]
    if diag_val:
        filtered = filtered[filtered['Performance Diagnostic'].str.contains(diag_val, na=False)]

    # Table for display
    df_display = filtered.copy()
    for col in ['Payments + Expected', 'Predicted Revenue', 'Missed Revenue']:
        df_display[col] = df_display[col].apply(lambda x: f"${int(x):,}")
    df_display['Residual'] = df_display['Residual'].round(2)

    data_table = dash_table.DataTable(
        data=df_display.to_dict('records'),
        columns=[{"name": i, "id": i} for i in df_display.columns],
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left'}
    )

    # Charts
    cat_fig = px.histogram(df, x='Performance Category', title='Number of Weeks by Category')
    diag_fig = px.histogram(df.explode('Performance Diagnostic'), x='Performance Diagnostic', title='Count of Diagnostic Reasons')
    missed_rev_fig = px.bar(df, x='Week', y='Missed Revenue', title='Missed Revenue by Week')
    revenue_fig = px.line(df, x='Week', y=['Payments + Expected', 'Predicted Revenue'], title='Actual vs Predicted Revenue by Week')

    revenue_table = dash_table.DataTable(
        data=df[['Week', 'Payments + Expected', 'Predicted Revenue']].round(2).to_dict('records'),
        columns=[{"name": i, "id": i} for i in ['Week', 'Payments + Expected', 'Predicted Revenue']],
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left'}
    )

    return (
        data_table,
        cat_fig,
        diag_fig,
        missed_rev_fig,
        revenue_fig,
        revenue_table,
        week_options,
        category_options,
        diagnostic_options
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(host="0.0.0.0", port=port)
