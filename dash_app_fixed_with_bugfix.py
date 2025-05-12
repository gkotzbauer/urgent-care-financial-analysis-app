import base64
import io
import pandas as pd
import dash
from dash import dcc, html, Input, Output, State, dash_table
import plotly.express as px
import dash_bootstrap_components as dbc

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

app.layout = dbc.Container([
    html.H2("Weekly Performance Diagnostics Dashboard"),
    
    dcc.Upload(
        id='upload-data',
        children=html.Div([
            'Drag and Drop or ',
            html.A('Select Excel File')
        ]),
        style={
            'width': '100%', 'height': '60px', 'lineHeight': '60px',
            'borderWidth': '1px', 'borderStyle': 'dashed',
            'borderRadius': '5px', 'textAlign': 'center',
        },
        multiple=False
    ),
    html.Br(),

    dbc.Row([
        dbc.Col(dcc.Dropdown(id='week-filter', placeholder='Select Week'), md=6),
        dbc.Col(dcc.Dropdown(id='segment-filter', placeholder='Select Performance Segment'), md=6),
    ]),
    html.Br(),

    dbc.Row([
        dbc.Col(dcc.Graph(id='segment-chart'), md=6),
        dbc.Col(dcc.Graph(id='missed-revenue-chart'), md=6),
    ]),
    html.Br(),

    dbc.Row([
        dbc.Col(dcc.Graph(id='low-average-payment-chart'), md=12)
    ]),
    html.Hr(),

    html.H4("Detailed Weekly Data"),
    dash_table.DataTable(
        id='weekly-table',
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left', 'whiteSpace': 'normal'},
        page_size=15
    )
], fluid=True)

def parse_contents(contents):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    df = pd.read_excel(io.BytesIO(decoded), engine='openpyxl')
    return df

@app.callback(
    Output('weekly-table', 'data'),
    Output('weekly-table', 'columns'),
    Output('week-filter', 'options'),
    Output('segment-filter', 'options'),
    Output('segment-chart', 'figure'),
    Output('missed-revenue-chart', 'figure'),
    Output('low-average-payment-chart', 'figure'),
    Input('upload-data', 'contents'),
    State('upload-data', 'filename'),
    Input('week-filter', 'value'),
    Input('segment-filter', 'value')
)
def update_output(contents, filename, week, segment):
    if contents is None:
        return [], [], [], [], {}, {}, {}

    df = parse_contents(contents)

    # Filters
    if week:
        df = df[df['Week'] == week]
    if segment:
        df = df[df['Performance Segment'] == segment]

    # Table
    columns = [{"name": i, "id": i} for i in df.columns]
    data = df.to_dict('records')

    # Dropdown options
    week_options = [{'label': w, 'value': w} for w in sorted(df['Week'].unique())]
    segment_options = [{'label': s, 'value': s} for s in sorted(df['Performance Segment'].unique())]

    # Charts
    segment_fig = px.histogram(df, x='Performance Segment', title='Weeks by Performance Segment')

    df['Missed Revenue'] = df['Predicted Revenue'] - df['Total Payments']
    missed_rev_fig = px.bar(df, x='Week', y='Missed Revenue', title='Missed Revenue by Week')

    low_avg_pay_fig = px.histogram(
        df[df['Low Average Payment'] == 1],
        x='Week',
        title='Weeks Flagged: Low Average Payment'
    )

    return data, columns, week_options, segment_options, segment_fig, missed_rev_fig, low_avg_pay_fig

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)
