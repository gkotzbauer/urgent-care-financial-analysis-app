# Weekly Financial Performance Dashboard

This Dash app helps clinic executives review financial performance by week using a predictive model. It includes diagnostics, trend analysis, and interactive filtering.

## Features
- Upload Excel performance files
- Interactive charts with labels
- Filters by week and performance segment
- Diagnostic reason charts
- Stacked bar chart of financial class mix
- CSV export of weekly diagnostic table

## Deployment (Render)
1. Add all repo files (including this README, requirements.txt, Procfile, and .py code)
2. Connect to GitHub from your Render account
3. Use a build command: `pip install -r requirements.txt`
4. Use a start command: `gunicorn dash_app_fixed_with_bugfix:application`

## Dependencies
See `requirements.txt`.
