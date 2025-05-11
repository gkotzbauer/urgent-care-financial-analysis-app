import pandas as pd
import dash
import dash_table
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output
import plotly.express as px

# Load data
df = pd.read_excel("Updated_Performance_Results_With_Slimmed_Segments May 11.xlsx")

# Create missed revenue column
df['Missed Revenue'] = df['Predicted Revenue'] - df['Total Payments']

# Launch app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

# Layout
app.layout = dbc.Container([
    html.H2("Weekly Financial Performance Dashboard"),
    html.Hr(),

    dbc.Row([
        dbc.Col([
            html.Label("Filter by Week"),
            dcc.Dropdown(
                id='week-filter',
                options=[{'label': w, 'value': w} for w in sorted(df['Week'].unique())],
                multi=True
            )
        ], width=6),

        dbc.Col([
            html.Label("Filter by Performance Segment"),
            dcc.Dropdown(
                id='segment-filter',
                options=[{'label': s, 'value': s} for s in df['Performance Segment'].unique()],
                multi=True
            )
        ], width=6),
    ]),

    html.Br(),

    dbc.Row([
        dbc.Col(dcc.Graph(id='segment-count-chart'), width=12),
    ]),
    html.Br(),

    dbc.Row([
        dbc.Col(dcc.Graph(id='missed-revenue-chart'), width=12),
    ]),
    html.Br(),

    dbc.Row([
        dbc.Col(dcc.Graph(id='low-avg-payment-chart'), width=12),
    ]),
    html.Br(),

    html.Hr(),
    html.H4("Detailed Table by Week"),
    dash_table.DataTable(
        id='results-table',
        columns=[{"name": i, "id": i} for i in df.columns],
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left'},
        page_size=20,
        filter_action="native",
        sort_action="native"
    )
], fluid=True)

# Callbacks
@app.callback(
    Output('segment-count-chart', 'figure'),
    Output('missed-revenue-chart', 'figure'),
    Output('low-avg-payment-chart', 'figure'),
    Output('results-table', 'data'),
    Input('week-filter', 'value'),
    Input('segment-filter', 'value')
)
def update_dashboard(selected_weeks, selected_segments):
    dff = df.copy()

    if selected_weeks:
        dff = dff[dff['Week'].isin(selected_weeks)]
    if selected_segments:
        dff = dff[dff['Performance Segment'].isin(selected_segments)]

    # Chart 1: Performance Segment count
    seg_chart = px.histogram(dff, x='Performance Segment', title="Number of Weeks by Performance Segment")

    # Chart 2: Missed Revenue by Week
    missed_rev_chart = px.bar(dff, x='Week', y='Missed Revenue', title="Missed Revenue Opportunity by Week")

    # Chart 3: Frequency of Low Average Payment as a reason
    low_avg_payment_chart = px.histogram(
        dff[dff["Low Average Payment"] == 1],
        x='Week',
        title="Weeks Where Low Average Payment Was a Contributing Factor"
    )

    return seg_chart, missed_rev_chart, low_avg_payment_chart, dff.to_dict('records')


if __name__ == "__main__":
    app.run_server(debug=True)
