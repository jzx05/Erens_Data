"""Shared metric computation for the SQLite BI dashboard task."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def compute(root: Path) -> dict:
    root = Path(root)
    connection = sqlite3.connect(root / "base" / "input" / "business_analytics.sqlite")
    try:
        total_revenue = connection.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM orders WHERE status = 'completed'"
        ).fetchone()[0]
        total_orders = connection.execute(
            "SELECT COUNT(*) FROM orders WHERE status = 'completed'"
        ).fetchone()[0]
        unique_customers = connection.execute(
            "SELECT COUNT(DISTINCT customer_id) FROM orders WHERE status = 'completed'"
        ).fetchone()[0]
        total_customers = connection.execute("SELECT COUNT(*) FROM customers").fetchone()[0]

        revenue_by_category = {
            category: round(amount, 2)
            for category, amount in connection.execute(
                "SELECT category, SUM(amount) FROM orders "
                "WHERE status = 'completed' GROUP BY category ORDER BY category"
            )
        }
        months = [
            row[0]
            for row in connection.execute(
                "SELECT DISTINCT substr(order_date, 1, 7) FROM orders ORDER BY 1"
            )
        ]
        monthly_revenue = {month: 0.0 for month in months}
        for month, amount in connection.execute(
            "SELECT substr(order_date, 1, 7), SUM(amount) FROM orders "
            "WHERE status = 'completed' GROUP BY 1"
        ):
            monthly_revenue[month] = round(amount, 2)

        orders_by_device = {
            device: count
            for device, count in connection.execute(
                "SELECT device, COUNT(*) FROM orders WHERE status = 'completed' "
                "GROUP BY device ORDER BY device"
            )
        }
        orders_by_channel = {
            channel: count
            for channel, count in connection.execute(
                "SELECT channel, COUNT(*) FROM orders WHERE status = 'completed' "
                "GROUP BY channel ORDER BY channel"
            )
        }

        event_funnel = {}
        for event in ("view", "add_to_cart", "checkout"):
            event_funnel[event] = connection.execute(
                "SELECT COUNT(DISTINCT customer_id) FROM events WHERE event_type = ?",
                (event,),
            ).fetchone()[0]
        event_funnel["purchase"] = unique_customers

        top_rows = connection.execute(
            """
            SELECT o.customer_id, c.customer_name, ROUND(SUM(o.amount), 2) AS total_spend
            FROM orders o
            JOIN customers c ON c.customer_id = o.customer_id
            WHERE o.status = 'completed'
            GROUP BY o.customer_id, c.customer_name
            ORDER BY total_spend DESC, o.customer_id ASC
            LIMIT 10
            """
        ).fetchall()

        return {
            "total_revenue": round(total_revenue, 2),
            "average_order_value": round(total_revenue / total_orders, 2) if total_orders else 0.0,
            "conversion_rate": round(unique_customers / total_customers * 100, 2) if total_customers else 0.0,
            "total_completed_orders": total_orders,
            "unique_purchasing_customers": unique_customers,
            "revenue_by_category": revenue_by_category,
            "monthly_revenue": monthly_revenue,
            "orders_by_device": orders_by_device,
            "orders_by_channel": orders_by_channel,
            "event_funnel": event_funnel,
            "top_10_customers": [
                {
                    "customer_id": row[0],
                    "customer_name": row[1],
                    "total_spend": round(row[2], 2),
                }
                for row in top_rows
            ],
        }
    finally:
        connection.close()
