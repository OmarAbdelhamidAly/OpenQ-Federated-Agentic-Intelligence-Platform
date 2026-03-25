"""Export utilities — PDF (WeasyPrint), PNG (Kaleido), CSV (Pandas)."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.io as pio
import structlog

from app.infrastructure.adapters.storage import get_exports_dir

logger = structlog.get_logger(__name__)

class ExportService:
    """Premium Export Service for generating high-quality analysis reports."""

    async def generate_pdf(self, job: Any, result: Any) -> str:
        """Render a professional PDF report with modern aesthetics."""
        exports_dir = get_exports_dir(str(job.tenant_id))
        file_path = str(exports_dir / f"report_{job.id}.pdf")

        # Prepare Recommendations HTML
        recs_html = ""
        recs = result.recommendations_json or []
        for i, rec in enumerate(recs, 1):
            recs_html += f"""
            <div class="card recommendation">
                <div class="card-header">
                    <span class="badge">Recommendation {i}</span>
                    <h3>{rec.get('action', 'Strategic Adjustment')}</h3>
                </div>
                <div class="card-body">
                    <p><strong>Rationale:</strong> {rec.get('expected_impact', 'N/A')}</p>
                    <div class="metrics-grid">
                        <div class="metric-item">
                            <span class="label">Confidence</span>
                            <span class="value">{rec.get('confidence_score', '0')}%</span>
                        </div>
                        <div class="metric-item">
                            <span class="label">Priority</span>
                            <span class="value">{rec.get('priority', 'Medium')}</span>
                        </div>
                    </div>
                </div>
            </div>
            """

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
                
                :root {{
                    --primary: #2563eb;
                    --primary-light: #eff6ff;
                    --text-main: #1e293b;
                    --text-muted: #64748b;
                    --border: #e2e8f0;
                    --bg-card: #ffffff;
                }}

                body {{ 
                    font-family: 'Inter', -apple-system, sans-serif; 
                    margin: 0; 
                    padding: 40px; 
                    color: var(--text-main);
                    line-height: 1.6;
                    background: #f8fafc;
                }}

                header {{
                    margin-bottom: 40px;
                    border-bottom: 2px solid var(--primary);
                    padding-bottom: 20px;
                }}

                h1 {{ margin: 0; font-size: 28px; color: var(--primary); letter-spacing: -0.025em; }}
                .metadata {{ font-size: 14px; color: var(--text-muted); margin-top: 8px; }}

                .question-box {{
                    background: var(--primary-light);
                    padding: 20px;
                    border-radius: 12px;
                    margin-bottom: 30px;
                    border-left: 4px solid var(--primary);
                }}

                .question-label {{ font-size: 12px; font-weight: 700; text-transform: uppercase; color: var(--primary); margin-bottom: 4px; display: block; }}
                .question-text {{ font-size: 18px; font-weight: 600; }}

                section {{ margin-bottom: 40px; }}
                h2 {{ font-size: 20px; border-bottom: 1px solid var(--border); padding-bottom: 8px; margin-bottom: 20px; }}

                .card {{
                    background: var(--bg-card);
                    border: 1px solid var(--border);
                    border-radius: 12px;
                    padding: 24px;
                    margin-bottom: 20px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                }}

                .recommendation {{ border-left: 4px solid #10b981; }}
                .card-header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; border-bottom: 1px solid #f1f5f9; padding-bottom: 12px; }}
                .card-header h3 {{ margin: 0; font-size: 16px; }}
                .badge {{ font-size: 10px; background: #ecfdf5; color: #059669; padding: 2px 8px; border-radius: 999px; font-weight: 700; }}

                .metrics-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 16px; }}
                .metric-item {{ background: #f8fafc; padding: 12px; border-radius: 8px; }}
                .metric-item .label {{ font-size: 11px; color: var(--text-muted); display: block; }}
                .metric-item .value {{ font-size: 16px; font-weight: 700; color: var(--primary); }}

                .footer {{ 
                    margin-top: 60px; 
                    padding-top: 20px; 
                    border-top: 1px solid var(--border);
                    font-size: 12px; 
                    color: var(--text-muted);
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <header>
                <h1>Strategic Data Analysis</h1>
                <div class="metadata">Job ID: {job.id} • Generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
            </header>

            <div class="question-box">
                <span class="question-label">Research Query</span>
                <div class="question-text">{job.question}</div>
            </div>

            <section>
                <h2>Executive Summary</h2>
                <div class="card" style="background: linear-gradient(135deg, #ffffff 0%, #f0f7ff 100%);">
                    {result.exec_summary or "Summary not available."}
                </div>
            </section>

            <section>
                <h2>Analytical Insights</h2>
                <div style="white-space: pre-wrap;">{result.insight_report or "Details not available."}</div>
            </section>

            <section>
                <h2>Strategic Recommendations</h2>
                {recs_html if recs_html else "<p>Prioritized recommendations will appear here upon completion.</p>"}
            </section>

            <div class="footer">
                Confidential Analysis • Powered by Autonomous Intelligence Engine
            </div>
        </body>
        </html>
        """

        try:
            from weasyprint import HTML
            # Ensure the directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            HTML(string=html_content).write_pdf(file_path)
            return file_path
        except Exception as e:
            # Fallback to HTML if PDF fails
            html_path = file_path.replace(".pdf", ".html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            return html_path

    async def generate_png(self, job: Any, result: Any) -> str:
        """Render chart data as a high-density PNG."""
        exports_dir = get_exports_dir(str(job.tenant_id))
        file_path = str(exports_dir / f"chart_{job.id}.png")

        chart_json = result.chart_json
        if not chart_json:
            return ""

        fig = pio.from_json(json.dumps(chart_json))
        # Premium styling for the chart image
        fig.update_layout(
            template="plotly_white",
            font_family="Inter",
            margin=dict(l=40, r=40, t=60, b=40)
        )
        
        fig.write_image(file_path, format="png", width=1200, height=800, scale=2)
        return file_path

    async def generate_csv(self, job: Any, result: Any) -> str:
        """Convert result data to a clean CSV structure."""
        exports_dir = get_exports_dir(str(job.tenant_id))
        file_path = str(exports_dir / f"data_{job.id}.csv")

        chart_json = result.chart_json
        if chart_json and "data" in chart_json:
            data_list = []
            for trace in chart_json["data"]:
                trace_name = trace.get("name", "Value")
                if "x" in trace and "y" in trace:
                    for x, y in zip(trace["x"], trace["y"]):
                        data_list.append({"Dimension": x, trace_name: y})
            
            if data_list:
                df = pd.DataFrame(data_list)
                # If multiple traces, pivoted format might be better, but simple list works
                df.to_csv(file_path, index=False)
                return file_path

        # Placeholder if no data
        pd.DataFrame([{"Message": "No tabular data available for this analysis"}]).to_csv(file_path, index=False)
        return file_path
