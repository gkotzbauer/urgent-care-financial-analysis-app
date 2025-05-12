# Performance Dashboard for Weekly Clinic Data

This Dash app allows executives to upload and interact with weekly performance data from their clinic and evaluate segments using regression diagnostics.

## 🔧 Features

- Upload Excel data (no hardcoded filenames)
- Filter by Week and Performance Segment
- View dashboards for:
  - Segment distribution
  - Missed revenue
  - Low average payment alerts
- Download results from tables

## 🚀 Deploy to Render

1. Push this repository to GitHub.
2. Create a new Web Service on [Render](https://render.com).
3. Use the following settings:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn dash_app_fixed_with_bugfix:app`
   - **Python Version**: 3.11+

## 🧪 Run Locally

```bash
pip install -r requirements.txt
python dash_app_fixed_with_bugfix.py
