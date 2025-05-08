
import dash
from dash import dcc, html, dash_table, Input, Output, State
import pandas as pd
from sklearn.linear_model import LinearRegression
import plotly.express as px
import io
import base64

app = dash.Dash(__name__)
server = app.server

app.layout = html.Div([
    html.H1("📊 Urgent Care Revenue Dashboard"),
    dcc.Upload(
        id='upload-data',
        children=html.Div(['📁 Drag and Drop or ', html.A('Select Excel File')]),
        style={'width': '100%', 'height': '60px', 'lineHeight': '60px',
               'borderWidth': '1px', 'borderStyle': 'dashed',
               'borderRadius': '5px', 'textAlign': 'center'},
        multiple=False
    ),
    html.Div(id='filters-div'),
    html.Br(),
    dash_table.DataTable(id='data-table', style_table={'overflowX': 'auto'}),
    html.Br(),
    dcc.Graph(id='category-chart'),
    html.Br(),
    dcc.Graph(id='diagnostic-chart'),
    html.Br(),
    dcc.Graph(id='missed-revenue-chart'),
    html.H3(id='missed-revenue-total')
])

def parse_data(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    df = pd.read_excel(io.BytesIO(decoded))
    df.columns = df.columns.str.strip()
    df['ISO Week of Visit Service Date'] = df['ISO Week of Visit Service Date'].ffill()
    df['Primary Financial Class'] = df['Primary Financial Class'].ffill()
    df['Average Payment'] = df['Average Payment'].abs()

    numeric_cols = ['Average Payment', 'Avg. Chart E/M Weight', 'Lab Count', 'Payments + Expected', 'Visit Count']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df = df[df['ISO Week of Visit Service Date'] != 'W19']
    weekly = df.groupby('ISO Week of Visit Service Date').agg({
        'Payments + Expected': 'sum',
        'Visit Count': 'sum',
        'Average Payment': 'mean',
        'Avg. Chart E/M Weight': 'mean',
        'Lab Count': 'sum'
    }).reset_index()
    weekly['Labs per Visit'] = weekly['Lab Count'] / weekly['Visit Count']
    weekly = weekly.dropna()

    X = weekly[['Visit Count', 'Average Payment', 'Avg. Chart E/M Weight', 'Labs per Visit']]
    y = weekly['Payments + Expected']
    model = LinearRegression().fit(X, y)
    weekly['Predicted Revenue'] = model.predict(X)
    weekly['Residual'] = weekly['Payments + Expected'] - weekly['Predicted Revenue']
    res_mean = weekly['Residual'].mean()
    res_std = weekly['Residual'].std()
    weekly['Z-Score Residual'] = ((weekly['Residual'] - res_mean) / res_std).round(2)

    means = X.mean()
    coefs = model.coef_

    cats, diags = [], []
    for _, row in weekly.iterrows():
        reasons = []
        for i, var in enumerate(X.columns):
            val, avg = row[var]
            delta = val - avg
            effect = delta * coefs[i]
            direction = "⬆ Above avg" if delta > 0 else "⬇ Below avg"
            if abs(delta) > 0.05 * avg:
                if row['Z-Score Residual'] >= 1.0 and effect > 0:
                    reasons.append(f"{var}: {direction}")
                elif row['Z-Score Residual'] <= -1.0 and effect < 0:
                    reasons.append(f"{var}: {direction}")
                elif row['Z-Score Residual'] > 0.25 and effect > 0:
                    reasons.append(f"{var}: {direction}")
                elif row['Z-Score Residual'] < -0.25 and effect < 0:
                    reasons.append(f"{var}: {direction}")

        if not reasons:
            diag = "Performance aligned with historical norms."
            cat = "Near Expected"
        else:
            diag = " | ".join(reasons[:2])
            if row['Z-Score Residual'] >= 1.0:
                cat = "Significantly Overperformed"
            elif row['Z-Score Residual'] >= 0.25:
                cat = "Overperformed"
            elif row['Z-Score Residual'] <= -1.0:
                cat = "Significantly Underperformed"
            elif row['Z-Score Residual'] <= -0.25:
                cat = "Underperformed"
            else:
                cat = "Near Expected"

        cats.append(cat)
        diags.append(diag)

    weekly['Performance Category'] = cats
    weekly['Performance Diagnostic'] = diags
    weekly['Missed Opportunity'] = weekly['Predicted Revenue'] - weekly['Payments + Expected']

    weekly['Payments + Expected'] = weekly['Payments + Expected'].apply(lambda x: f"${int(x):,}")
    weekly['Predicted Revenue'] = weekly['Predicted Revenue'].apply(lambda x: f"${int(x):,}")
    weekly['Residual'] = weekly['Residual'].apply(lambda x: f"${x:,.2f}")

    return weekly

@app.callback(
    [Output('data-table', 'data'),
     Output('data-table', 'columns'),
     Output('category-chart', 'figure'),
     Output('diagnostic-chart', 'figure'),
     Output('missed-revenue-chart', 'figure'),
     Output('missed-revenue-total', 'children')],
    [Input('upload-data', 'contents')],
    [State('upload-data', 'filename')]
)
def update_output(contents, filename):
    if contents is None:
        return [], [], {}, {}, {}, ""
    df = parse_data(contents, filename)
    fig1 = px.bar(df, x='ISO Week of Visit Service Date', color='Performance Category', title="Performance by Week")
    diag_counts = df['Performance Diagnostic'].value_counts().reset_index()
    diag_counts.columns = ['Reason', 'Count']
    fig2 = px.bar(diag_counts, x='Reason', y='Count', title="Diagnostic Reason Frequency")
    df['Missed Numeric'] = df['Missed Opportunity'].apply(lambda x: float(str(x).replace('$','').replace(',','')))
    fig3 = px.bar(df, x='ISO Week of Visit Service Date', y='Missed Numeric', title="Missed Revenue Opportunity")

    total_missed = df['Missed Numeric'].sum()
    total_text = f"💸 Total Missed Revenue Opportunity: ${int(total_missed):,}"

    return df.to_dict('records'), [{"name": i, "id": i} for i in df.columns], fig1, fig2, fig3, total_text

if __name__ == '__main__':
    app.run_server(debug=True)
