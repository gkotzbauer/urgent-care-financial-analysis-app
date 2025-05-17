
import base64
import io
import pandas as pd
import dash
from dash import dcc, html, dash_table, Input, Output, State
import plotly.express as px
import numpy as np
from sklearn.linear_model import LinearRegression
import dash_bootstrap_components as dbc

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server  # For Render deployment

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
    dcc.Graph(id='diagnostic-factor-chart'),
    dcc.Graph(id='stacked-bar-chart'),
    html.Hr(),
    html.H4("Performance Table"),
    dash_table.DataTable(
        id='performance-table',
        page_size=20,
        style_table={'overflowX': 'auto'},
        style_cell={'textAlign': 'left', 'padding': '5px'},
        style_header={'fontWeight': 'bold'},
        export_format='xlsx'
    )
])

def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    df = pd.read_excel(io.BytesIO(decoded), engine='openpyxl')
    df.columns = df.columns.str.strip()
    df = df.dropna(subset=['Week'])
    return df

@app.callback(
    Output('performance-table', 'data'),
    Output('performance-table', 'columns'),
    Output('segment-count-chart', 'figure'),
    Output('missed-revenue-chart', 'figure'),
    Output('diagnostic-factor-chart', 'figure'),
    Output('stacked-bar-chart', 'figure'),
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
        return [], [], {}, {}, {}, {}, [], [], ""

    df = parse_contents(contents, filename)

    # Filter data
    filtered = df.copy()
    if selected_week:
        filtered = filtered[filtered["Week"] == selected_week]
    if selected_segment:
        filtered = filtered[filtered["Performance Segment"] == selected_segment]

    data = filtered.to_dict("records")
    columns = [{"name": i, "id": i} for i in filtered.columns]

    fig1 = px.histogram(df, x="Performance Segment", title="Number of Weeks by Performance Segment", text_auto=True)
    df["Missed Revenue"] = df["Predicted Revenue"] - df["Total Payments"]
    fig2 = px.bar(df, x="Week", y="Missed Revenue", title="Missed Revenue Opportunity by Week", text_auto=True)
    fig3 = px.bar(
        df.groupby("Week")["Low Average Payment"].sum().reset_index(),
        x="Week", y="Low Average Payment", title="Low Average Payment Count by Week", text_auto=True
    )

    stacked_data = df[["Week"] + [col for col in df.columns if col.endswith("% of Total Payments")]]
    stacked_melted = stacked_data.melt(id_vars="Week", var_name="Financial Class", value_name="Percentage")
    fig4 = px.bar(stacked_melted, x="Week", y="Percentage", color="Financial Class", title="Financial Class % by Week", text_auto=True)

    week_options = [{"label": w, "value": w} for w in sorted(df["Week"].unique())]
    segment_options = [{"label": s, "value": s} for s in sorted(df["Performance Segment"].unique())]

    return data, columns, fig1, fig2, fig3, fig4, week_options, segment_options, f"File loaded: {filename}"

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
