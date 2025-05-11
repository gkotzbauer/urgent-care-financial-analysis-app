import base64
import io
import pandas as pd
import numpy as np
import dash
from dash import dcc, html, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import plotly.express as px
from sklearn.linear_model import LinearRegression

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

app.layout = dbc.Container([
    html.H2("Weekly Financial Performance Dashboard"),
    dcc.Upload(
        id='upload-data',
        children=html.Div([
            'Drag and Drop or ',
            html.A('Select Excel File')
        ]),
        style={
            'width': '100%',
            'height': '80px',
            'lineHeight': '80px',
            'borderWidth': '1px',
            'borderStyle': 'dashed',
            'borderRadius': '5px',
            'textAlign': 'center',
        },
        multiple=False
    ),
    html.Br(),
    dbc.Row([
        dbc.Col(dcc.Dropdown(id='week-filter', placeholder="Filter by Week")),
        dbc.Col(dcc.Dropdown(id='segment-filter', placeholder="Filter by Segment"))
    ]),
    html.Br(),
    dcc.Graph(id='segment-count-chart'),
    dcc.Graph(id='missed-revenue-chart'),
    dcc.Graph(id='low-avg-payment-reason-chart'),
    html.Hr(),
    html.H4("Weekly Results"),
    dash_table.DataTable(
        id='results-table',
        page_size=20,
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left'}
    )
], fluid=True)


def parse_contents(contents):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    df = pd.read_excel(io.BytesIO(decoded))

    # Drop unnamed index if exists
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]

    return df


def analyze_data(df):
    # Clean numeric fields
    numeric_cols = [
        'Average Payment', 'Avg. Chart E/M Weight', 'Charge Amount', 'Collection %',
        'Total Payments', 'Visit_Count', 'Visits With Lab Count'
    ]
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
    df[numeric_cols] = df[numeric_cols].fillna(0)
    df['Collection %'] = df['Collection %'].abs()

    # Regression model
    features = [
        'Average Payment', 'Avg. Chart E/M Weight', 'Charge Amount', 'Collection %',
        'Visit_Count', 'Visits With Lab Count'
    ]
    df = df.copy()
    X = df[features]
    y = df['Total Payments']
    model = LinearRegression().fit(X, y)
    df['Predicted Revenue'] = model.predict(X)
    df['Residual'] = df['Total Payments'] - df['Predicted Revenue']
    df['Z-Score Residual'] = (df['Residual'] - df['Residual'].mean()) / df['Residual'].std()

    # Segment assignment
    def assign_segment(z):
        if z <= -1.75:
            return "Significantly Underperformed"
        elif z <= -0.75:
            return "Underperformed"
        elif z >= 1.75:
            return "Significantly Overperformed"
        elif z >= 0.75:
            return "Overperformed"
        else:
            return "Near Expected"

    df['Performance Segment'] = df['Z-Score Residual'].apply(assign_segment)

    # Diagnostics
    diagnostics = []
    reasons_cols = [
        'Low Average Payment', 'High Average Payment',
        'Low Avg. Chart E/M Weight', 'High Avg. Chart E/M Weight',
        'Low Charge Amount', 'High Charge Amount',
        'Low Collection %', 'High Collection %',
        'Low Visit_Count', 'High Visit_Count',
        'Low Visits With Lab Count', 'High Visits With Lab Count'
    ]
    for col in reasons_cols:
        df[col] = 0

    means = df[features].mean()
    for idx, row in df.iterrows():
        reasons = []
        if row['Performance Segment'] in ["Underperformed", "Significantly Underperformed"]:
            if row['Average Payment'] < means['Average Payment']:
                reasons.append("Low Average Payment")
                df.at[idx, 'Low Average Payment'] = 1
            if row['Avg. Chart E/M Weight'] < means['Avg. Chart E/M Weight']:
                reasons.append("Low Avg. Chart E/M Weight")
                df.at[idx, 'Low Avg. Chart E/M Weight'] = 1
            if row['Charge Amount'] < means['Charge Amount']:
                reasons.append("Low Charge Amount")
                df.at[idx, 'Low Charge Amount'] = 1
            if row['Collection %'] < means['Collection %']:
                reasons.append("Low Collection %")
                df.at[idx, 'Low Collection %'] = 1
            if row['Visit_Count'] < means['Visit_Count']:
                reasons.append("Low Visit Count")
                df.at[idx, 'Low Visit_Count'] = 1
            if row['Visits With Lab Count'] < means['Visits With Lab Count']:
                reasons.append("Low Visits With Lab Count")
                df.at[idx, 'Low Visits With Lab Count'] = 1
        elif row['Performance Segment'] in ["Overperformed", "Significantly Overperformed"]:
            if row['Average Payment'] > means['Average Payment']:
                reasons.append("High Average Payment")
                df.at[idx, 'High Average Payment'] = 1
            if row['Avg. Chart E/M Weight'] > means['Avg. Chart E/M Weight']:
                reasons.append("High Avg. Chart E/M Weight")
                df.at[idx, 'High Avg. Chart E/M Weight'] = 1
            if row['Charge Amount'] > means['Charge Amount']:
                reasons.append("High Charge Amount")
                df.at[idx, 'High Charge Amount'] = 1
            if row['Collection %'] > means['Collection %']:
                reasons.append("High Collection %")
                df.at[idx, 'High Collection %'] = 1
            if row['Visit_Count'] > means['Visit_Count']:
                reasons.append("High Visit Count")
                df.at[idx, 'High Visit_Count'] = 1
            if row['Visits With Lab Count'] > means['Visits With Lab Count']:
                reasons.append("High Visits With Lab Count")
                df.at[idx, 'High Visits With Lab Count'] = 1

        diagnostics.append("; ".join(reasons) if reasons else "No significant factors")

    df['Performance Diagnostics'] = diagnostics
    return df


@app.callback(
    Output('results-table', 'data'),
    Output('results-table', 'columns'),
    Output('week-filter', 'options'),
    Output('segment-filter', 'options'),
    Output('segment-count-chart', 'figure'),
    Output('missed-revenue-chart', 'figure'),
    Output('low-avg-payment-reason-chart', 'figure'),
    Input('upload-data', 'contents'),
    State('upload-data', 'filename'),
    Input('week-filter', 'value'),
    Input('segment-filter', 'value')
)
def update_dashboard(contents, filename, selected_week, selected_segment):
    if not contents:
        return [], [], [], [], {}, {}, {}

    df = parse_contents(contents)
    df = analyze_data(df)

    df['Missed Revenue'] = df['Predicted Revenue'] - df['Total Payments']

    # Apply filters
    filtered_df = df.copy()
    if selected_week:
        filtered_df = filtered_df[filtered_df['Week'] == selected_week]
    if selected_segment:
        filtered_df = filtered_df[filtered_df['Performance Segment'] == selected_segment]

    # Table setup
    columns = [{"name": i, "id": i} for i in filtered_df.columns]
    data = filtered_df.to_dict('records')

    # Dropdown options
    week_options = [{'label': wk, 'value': wk} for wk in sorted(df['Week'].unique())]
    segment_options = [{'label': seg, 'value': seg} for seg in df['Performance Segment'].unique()]

    # Charts
    segment_fig = px.histogram(df, x='Performance Segment', title='Number of Weeks by Segment')
    missed_rev_fig = px.bar(df, x='Week', y='Missed Revenue', title='Missed Revenue Opportunity by Week')
    low_avg_pay_fig = px.bar(df, x='Week', y='Low Average Payment', title='Weeks Flagged for Low Average Payment')

    return data, columns, week_options, segment_options, segment_fig, missed_rev_fig, low_avg_pay_fig


if __name__ == "__main__":
    app.run_server(debug=True, host='0.0.0.0', port=8050)
