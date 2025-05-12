import dash
from dash import dcc, html, Input, Output, State, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
import io
import base64
import plotly.express as px
from sklearn.linear_model import LinearRegression
import numpy as np

# Initialize the Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

app.layout = dbc.Container([
    html.H2("Weekly Performance Dashboard", className="mt-4"),
    dcc.Upload(
        id='upload-data',
        children=html.Div(['Drag and Drop or ', html.A('Select an Excel File (.xlsx)')]),
        style={
            'width': '100%', 'height': '60px', 'lineHeight': '60px',
            'borderWidth': '1px', 'borderStyle': 'dashed', 'borderRadius': '5px',
            'textAlign': 'center', 'margin': '10px'
        },
        multiple=False
    ),
    dbc.Row([
        dbc.Col(dcc.Dropdown(id='week-filter', placeholder="Filter by Week"), md=6),
        dbc.Col(dcc.Dropdown(id='segment-filter', placeholder="Filter by Performance Segment"), md=6),
    ]),
    html.Br(),
    dbc.Row([
        dbc.Col(dcc.Graph(id='segment-chart')),
    ]),
    dbc.Row([
        dbc.Col(dcc.Graph(id='missed-revenue-chart')),
    ]),
    dbc.Row([
        dbc.Col(dcc.Graph(id='low-avg-payment-chart')),
    ]),
    html.Br(),
    html.H4("Weekly Performance Table"),
    html.Div(id='table-container')
], fluid=True)

def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    df = pd.read_excel(io.BytesIO(decoded), engine='openpyxl')
    return df

@app.callback(
    Output('week-filter', 'options'),
    Output('segment-filter', 'options'),
    Output('week-filter', 'value'),
    Output('segment-filter', 'value'),
    Output('table-container', 'children'),
    Output('segment-chart', 'figure'),
    Output('missed-revenue-chart', 'figure'),
    Output('low-avg-payment-chart', 'figure'),
    Input('upload-data', 'contents'),
    State('upload-data', 'filename'),
    Input('week-filter', 'value'),
    Input('segment-filter', 'value')
)
def update_dashboard(contents, filename, selected_week, selected_segment):
    if contents is None:
        return [], [], None, None, html.Div(), {}, {}, {}

    df = parse_contents(contents, filename)

    df['Missed Revenue'] = df['Predicted Revenue'] - df['Total Payments']

    week_options = [{'label': w, 'value': w} for w in sorted(df['Week'].unique())]
    segment_options = [{'label': s, 'value': s} for s in sorted(df['Performance Segment'].unique())]

    if selected_week:
        df = df[df['Week'] == selected_week]
    if selected_segment:
        df = df[df['Performance Segment'] == selected_segment]

    # Table
    table = dash_table.DataTable(
        data=df.to_dict('records'),
        columns=[{"name": i, "id": i} for i in df.columns],
        page_size=20,
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left', 'fontSize': 12},
    )

    # Charts
    segment_chart = px.histogram(df, x='Performance Segment', title='Number of Weeks by Performance Segment')
    missed_revenue_chart = px.bar(df, x='Week', y='Missed Revenue', title='Missed Revenue by Week')
    
    # Count of "Low Average Payment"
    if 'Low Average Payment' in df.columns:
        low_avg_df = df.groupby('Week')['Low Average Payment'].sum().reset_index()
        low_avg_chart = px.bar(low_avg_df, x='Week', y='Low Average Payment',
                               title='Low Average Payment Flag Count by Week')
    else:
        low_avg_chart = px.bar(title='Low Average Payment Flag Count by Week (Data Missing)')

    return week_options, segment_options, None, None, table, segment_chart, missed_revenue_chart, low_avg_chart

if __name__ == "__main__":
    app.run(debug=True)

application = app.server  # For Gunicorn
